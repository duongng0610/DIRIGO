from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm_client import (
    LLMGenerationResult,
    MappingLLMClient,
)
from .mapping_models import MappingProposal
from .mapping_prompt import (
    SYSTEM_PROMPT,
    build_mapping_user_prompt,
)


@dataclass(frozen=True)
class MappingProposalRun:
    """
    Kết quả của một lần chạy Mapping Proposer.

    prompt_hash và source_profile_hash giúp tái lập/audit:
    biết chính xác proposal được tạo từ profile và prompt nào.
    """

    proposal: MappingProposal

    provider: str
    model: str
    response_id: str | None

    source_profile_hash: str
    prompt_hash: str

    usage: dict[str, Any]


def stable_json_hash(value: Any) -> str:
    """
    Tính SHA-256 ổn định cho dictionary/list.

    sort_keys=True đảm bảo hai dictionary có cùng nội dung
    nhưng thứ tự key khác nhau vẫn sinh cùng hash.
    """

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def text_hash(value: str) -> str:
    """Tính SHA-256 của prompt."""

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def validate_source_profile_shape(
    source_profile: dict[str, Any],
) -> None:
    """
    Kiểm tra tối thiểu source profile trước khi gửi LLM.

    Đây chưa phải MAP-QC. Hàm chỉ ngăn gửi profile rỗng
    hoặc sai format cơ bản.
    """

    tables = source_profile.get("tables")

    if not isinstance(tables, list):
        raise ValueError(
            "source_profile.tables must be a list"
        )

    if not tables:
        raise ValueError(
            "source_profile contains no tables"
        )

    for table_index, table in enumerate(tables):
        if not isinstance(table, dict):
            raise ValueError(
                f"tables[{table_index}] must be an object"
            )

        if not table.get("name"):
            raise ValueError(
                f"tables[{table_index}] has no name"
            )

        if not isinstance(table.get("columns"), list):
            raise ValueError(
                f"Table '{table['name']}' has invalid columns"
            )


def propose_mapping(
    source_profile: dict[str, Any],
    dataset_name: str,
    llm_client: MappingLLMClient,
    domain_hint: str | None = None,
) -> MappingProposalRun:
    """
    Sinh MappingProposal từ source profile.

    Hàm này không:
    - Ghi YAML production.
    - Chạy builder.
    - Tự sửa proposal.
    - Tin rằng proposal đã đúng nghiệp vụ.

    Những việc đó thuộc tầng MAP-QC và approval.
    """

    validate_source_profile_shape(source_profile)

    user_prompt = build_mapping_user_prompt(
        source_profile=source_profile,
        dataset_name=dataset_name,
        domain_hint=domain_hint,
    )

    generation_result: LLMGenerationResult = (
        llm_client.generate_mapping(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    )

    combined_prompt = (
        SYSTEM_PROMPT
        + "\n\n"
        + user_prompt
    )

    return MappingProposalRun(
        proposal=generation_result.proposal,
        provider=generation_result.provider,
        model=generation_result.model,
        response_id=generation_result.response_id,
        source_profile_hash=stable_json_hash(
            source_profile
        ),
        prompt_hash=text_hash(combined_prompt),
        usage=generation_result.usage,
    )


def save_mapping_proposal_run(
    run: MappingProposalRun,
    output_directory: str | Path,
) -> None:
    """
    Ghi proposal và metadata ra hai file riêng.

    mapping_proposal.json:
        Nội dung do LLM đề xuất.

    mapping_run.json:
        Model, hash, usage và thông tin audit.

    Không ghi trực tiếp thành YAML vì proposal chưa qua MAP-QC.
    """

    output_directory = Path(output_directory)

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    proposal_path = (
        output_directory / "mapping_proposal.json"
    )

    metadata_path = (
        output_directory / "mapping_run.json"
    )

    proposal_path.write_text(
        run.proposal.model_dump_json(indent=2),
        encoding="utf-8",
    )

    metadata = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "provider": run.provider,
        "model": run.model,
        "response_id": run.response_id,
        "source_profile_hash": (
            run.source_profile_hash
        ),
        "prompt_hash": run.prompt_hash,
        "usage": run.usage,
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )