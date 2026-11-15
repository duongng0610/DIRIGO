import argparse
import json
import os

from pathlib import Path

# Import trước src để bootstrap project root.
from pipeline_paths import (
    PROJECT_ROOT,
    PipelinePaths,
    save_json,
)

from dotenv import load_dotenv

from src.llm.llm_client import (
    GoogleMappingLLMClient,
)
from src.llm.mapping_compiler import (
    compile_proposal_file,
)
from src.llm.mapping_models import (
    MappingProposal,
)
from src.llm.mapping_repair import (
    MappingRepairBlockedError,
    repair_mapping_with_llm,
)
from src.llm.mapping_validator import (
    MappingValidator,
    save_validation_report,
)
def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Validate, repair and publish a mapping proposal"
        ),
    )

    parser.add_argument(
        "sqlite_file",
        help="SQLite file name inside data/raw",
    )

    parser.add_argument(
        "--max-repairs",
        type=int,
        default=2,
        help="Maximum number of LLM repair attempts",
    )

    return parser.parse_args()

def get_required_environment_variable(
    name: str,
) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Environment variable '{name}' is not set. "
            f"Check {PROJECT_ROOT / '.env'}"
        )

    return value

def save_proposal(
    proposal: MappingProposal,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        proposal.model_dump_json(indent=2),
        encoding="utf-8",
    )

def print_report(
    attempt: int,
    report,
) -> None:
    print()
    print("=" * 72)
    print(f"MAP-QC ATTEMPT {attempt}")
    print("=" * 72)

    print("Status:", report.status)
    print("Errors:", len(report.errors))
    print("Warnings:", len(report.warnings))

    for issue in report.issues:
        print(
            f"[{issue.severity}] "
            f"{issue.code} "
            f"{issue.path}: "
            f"{issue.message} "
            f"(repair={issue.repair_strategy})"
        )
def main() -> None:
    args = parse_arguments()

    if args.max_repairs < 0:
        raise ValueError(
            "--max-repairs cannot be negative"
        )

    paths = PipelinePaths.from_sqlite_file(
        args.sqlite_file
    )

    required_files = [
        paths.database_path,
        paths.source_profile_path,
        paths.mapping_proposal_path,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file does not exist: {path}"
            )

    # Load .env trước khi tạo Gemini client.
    env_path = PROJECT_ROOT / ".env"

    if not env_path.exists():
        raise FileNotFoundError(
            f".env file does not exist: {env_path}"
        )

    load_dotenv(
        dotenv_path=env_path,
        override=False,
    )

    # GoogleMappingLLMClient tự đọc GOOGLE_API_KEY.
    get_required_environment_variable(
        "GOOGLE_API_KEY"
    )

    model = get_required_environment_variable(
        "GOOGLE_LLM_MODEL"
    )

    llm_client = GoogleMappingLLMClient(
        model=model,
    )

    source_profile = json.loads(
        paths.source_profile_path.read_text(
            encoding="utf-8",
        )
    )

    proposal = MappingProposal.model_validate_json(
        paths.mapping_proposal_path.read_text(
            encoding="utf-8",
        )
    )

    approved_proposal_path = (
        paths.work_directory
        / "mapping_proposal_approved.json"
    )

    # attempt=0 là proposal ban đầu.
    # Các attempt sau là proposal đã được LLM repair.
    for attempt in range(
        args.max_repairs + 1
    ):
        attempt_proposal_path = (
            paths.work_directory
            / f"mapping_proposal_attempt_{attempt}.json"
        )

        attempt_report_path = (
            paths.work_directory
            / f"map_qc_attempt_{attempt}.json"
        )

        save_proposal(
            proposal,
            attempt_proposal_path,
        )

        validator = MappingValidator(
            proposal=proposal,
            source_profile=source_profile,
            database_path=paths.database_path,
        )

        report = validator.validate()

        save_validation_report(
            report,
            attempt_report_path,
        )

        # Ghi report mới nhất vào tên cố định.
        save_validation_report(
            report,
            paths.map_qc_report_path,
        )

        print_report(
            attempt,
            report,
        )

        if report.status == "PASS":
            save_proposal(
                proposal,
                approved_proposal_path,
            )

            compile_proposal_file(
                proposal_path=approved_proposal_path,
                output_path=(
                    paths.published_mapping_path
                ),
                source_database_path=(
                    paths.runtime_database_path
                ),
            )

            print()
            print("MAP-QC PASSED")
            print(
                "Approved proposal:",
                approved_proposal_path,
            )
            print(
                "Published mapping:",
                paths.published_mapping_path,
            )

            return

        # Không còn lượt repair.
        if attempt >= args.max_repairs:
            print()
            print(
                "MAP-QC FAILED AFTER "
                f"{args.max_repairs} REPAIR ATTEMPTS"
            )
            print(
                "Final report:",
                paths.map_qc_report_path,
            )

            raise SystemExit(1)

        print()
        print(
            f"Calling LLM repair "
            f"{attempt + 1}/{args.max_repairs}..."
        )

        try:
            proposal = repair_mapping_with_llm(
                source_profile=source_profile,
                previous_proposal=proposal,
                validation_report=report,
                llm_client=llm_client,
            )

        except MappingRepairBlockedError as error:
            print()
            print("AUTOMATIC REPAIR BLOCKED")
            print(error)

            raise SystemExit(1) from error

if __name__ == "__main__":
    main()