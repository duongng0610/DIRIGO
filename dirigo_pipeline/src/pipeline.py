from __future__ import annotations

import json

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.builders import (
    event_builder_v2,
    o2o_builder,
    object_builder_v2,
)
from src.extractor.to_csv import (
    convert_events,
    convert_objects,
    convert_relationships,
)
from src.llm.llm_client import GoogleMappingLLMClient
from src.llm.mapping_compiler import compile_proposal_file
from src.llm.mapping_models import MappingProposal
from src.llm.mapping_proposer import propose_mapping
from src.llm.mapping_repair import (
    MappingRepairBlockedError,
    repair_mapping_with_llm,
)
from src.llm.mapping_validator import MappingValidator
from src.llm.source_profiler import (
    ProfilerConfig,
    profile_sqlite,
    save_profile,
)
from src.qc.output_integrity_validator import (
    validate_dirigo_output,
)
from src.qc.qc_source_result.expected_projection import (
    build_expected_projection,
)
from src.qc.qc_source_result.output_reader import (
    read_actual_projection,
)
from src.qc.qc_source_result.reconciliation_validator import (
    reconcile_all,
)
from src.readers.reader_yaml import read_yaml_file
from src.readers.sqlite_reader import SQLiteReader
from src.validation.qc_validator import validate_all_qc


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path

    dataset_name: str
    database_path: Path
    runtime_database_path: str

    domain_hint: str
    model: str

    published_mapping_path: Path
    reports_root: Path
    outputs_root: Path

    max_llm_repairs: int = 2


class PipelineFailedError(RuntimeError):
    """Pipeline dừng vì một tầng QC thất bại."""


def _json_safe(value: Any) -> Any:
    """Chuyển dataclass/Path thành dạng ghi JSON được."""

    if is_dataclass(value):
        return {
            key: _json_safe(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    return value


def save_json(
    value: Any,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            _json_safe(value),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return output_path


def save_proposal(
    proposal: MappingProposal,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        proposal.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return output_path


def run_pipeline(
    config: PipelineConfig,
) -> dict[str, Any]:
    """
    Chạy toàn bộ SQLite -> LLM mapping -> Dirigo -> QC.

    Mỗi lần chạy có thư mục riêng, không xóa output lần trước.
    """

    run_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    run_directory = (
        config.reports_root
        / config.dataset_name
        / "runs"
        / run_id
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    source_profile_path = (
        run_directory / "source_profile.json"
    )

    # ---------------------------------------------------------
    # PHASE 1 — Source profiling
    # ---------------------------------------------------------

    profiler_config = ProfilerConfig(
        sample_rows_per_table=3,
        max_key_width=3,
        max_candidate_columns=8,
        redact_columns=frozenset(
            {
                "NationalIDNumber",
                "LoginID",
                "EmailAddress",
            }
        ),
    )

    source_profile = profile_sqlite(
        config.database_path,
        config=profiler_config,
    )

    save_profile(
        source_profile,
        source_profile_path,
    )

    # ---------------------------------------------------------
    # PHASE 2 — Initial mapping proposal
    # ---------------------------------------------------------

    llm_client = GoogleMappingLLMClient(
        model=config.model,
    )

    proposal_run = propose_mapping(
        source_profile=source_profile,
        dataset_name=config.dataset_name,
        domain_hint=config.domain_hint,
        llm_client=llm_client,
    )

    proposal = proposal_run.proposal

    save_json(
        {
            "provider": proposal_run.provider,
            "model": proposal_run.model,
            "response_id": proposal_run.response_id,
            "source_profile_hash": (
                proposal_run.source_profile_hash
            ),
            "prompt_hash": proposal_run.prompt_hash,
            "usage": proposal_run.usage,
        },
        run_directory / "proposal_metadata.json",
    )

    # ---------------------------------------------------------
    # PHASE 3 — MAP-QC and bounded LLM repair
    # ---------------------------------------------------------

    approved_proposal_path: Path | None = None
    final_map_report = None

    for attempt in range(
        config.max_llm_repairs + 1
    ):
        proposal_path = (
            run_directory
            / f"mapping_proposal_attempt_{attempt}.json"
        )

        save_proposal(
            proposal,
            proposal_path,
        )

        validator = MappingValidator(
            proposal=proposal,
            source_profile=source_profile,
            database_path=config.database_path,
        )

        map_report = validator.validate()

        save_json(
            map_report.to_dict(),
            run_directory
            / f"map_qc_attempt_{attempt}.json",
        )

        final_map_report = map_report

        if map_report.status == "PASS":
            approved_proposal_path = (
                run_directory
                / "mapping_proposal_approved.json"
            )

            save_proposal(
                proposal,
                approved_proposal_path,
            )

            break

        if attempt >= config.max_llm_repairs:
            raise PipelineFailedError(
                "MAP-QC failed after maximum repair attempts. "
                f"See {run_directory}"
            )

        try:
            proposal = repair_mapping_with_llm(
                source_profile=source_profile,
                previous_proposal=proposal,
                validation_report=map_report,
                llm_client=llm_client,
            )

        except MappingRepairBlockedError as error:
            raise PipelineFailedError(
                f"MAP-QC requires human/code action: {error}"
            ) from error

    if approved_proposal_path is None:
        raise PipelineFailedError(
            "No approved mapping proposal"
        )

    # ---------------------------------------------------------
    # PHASE 4 — Publish approved mapping
    # ---------------------------------------------------------

    config.published_mapping_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    compile_proposal_file(
        proposal_path=approved_proposal_path,
        output_path=config.published_mapping_path,
        source_database_path=(
            config.runtime_database_path
        ),
    )

    # ---------------------------------------------------------
    # PHASE 5 — Build Dirigo intermediate records
    # ---------------------------------------------------------

    mapping = read_yaml_file(
        config.published_mapping_path
    )

    reader = SQLiteReader(
        config.database_path
    )

    objects = object_builder_v2.build_objects(
        reader,
        mapping,
    )

    events = event_builder_v2.build_events(
        reader,
        mapping,
    )

    relationships = o2o_builder.build_o2o(
        reader,
        mapping,
    )

    # ---------------------------------------------------------
    # PHASE 6 — Representation QC before writing CSV
    # ---------------------------------------------------------

    representation_qc = validate_all_qc(
        objects=objects,
        events=events,
        relationships=relationships,
        validate_mapping=mapping,
        reader=reader,
    )

    save_json(
        representation_qc,
        run_directory / "representation_qc.json",
    )

    if not representation_qc["all_passed"]:
        raise PipelineFailedError(
            "Representation QC failed; output CSV was not "
            f"published. See {run_directory}"
        )

    # ---------------------------------------------------------
    # PHASE 7 — Write run-scoped Dirigo CSV
    # ---------------------------------------------------------

    output_directory = (
        config.outputs_root
        / config.dataset_name
        / run_id
    )

    convert_objects(
        objects,
        output_directory,
    )

    convert_events(
        events,
        output_directory,
    )

    convert_relationships(
        relationships,
        output_directory,
    )

    # ---------------------------------------------------------
    # PHASE 8 — REC-QC Source -> Output
    # ---------------------------------------------------------

    expected_projection = build_expected_projection(
        reader,
        mapping,
    )

    actual_projection = read_actual_projection(
        output_directory,
        mapping,
    )

    reconciliation_results = reconcile_all(
        expected_projection,
        actual_projection,
    )

    save_json(
        reconciliation_results,
        run_directory / "reconciliation_qc.json",
    )

    reconciliation_failures = [
        result
        for result in reconciliation_results
        if result.status == "FAIL"
    ]

    if reconciliation_failures:
        raise PipelineFailedError(
            "REC-QC failed: "
            f"{len(reconciliation_failures)} checks failed. "
            f"See {run_directory}"
        )

    # ---------------------------------------------------------
    # PHASE 9 — Output integrity QC
    # ---------------------------------------------------------

    output_qc = validate_dirigo_output(
        output_directory,
        mapping,
    )

    save_json(
        output_qc,
        run_directory / "output_qc.json",
    )

    if output_qc["status"] != "PASS":
        raise PipelineFailedError(
            "OUT-QC failed. "
            f"See {run_directory / 'output_qc.json'}"
        )

    # ---------------------------------------------------------
    # PHASE 10 — Final summary
    # ---------------------------------------------------------

    summary = {
        "status": "PASS",
        "run_id": run_id,
        "dataset": config.dataset_name,
        "database": str(config.database_path),
        "mapping": str(config.published_mapping_path),
        "output_directory": str(output_directory),
        "map_qc": final_map_report.to_dict(),
        "object_records": len(objects),
        "event_records": len(events),
        "relationship_records": len(relationships),
        "reconciliation_checks": len(
            reconciliation_results
        ),
    }

    save_json(
        summary,
        run_directory / "pipeline_summary.json",
    )

    return summary