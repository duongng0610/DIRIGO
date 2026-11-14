import sys

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.llm.mapping_validator import validate_and_publish_mapping


def main() -> None:
    """Chạy MAP-QC và publish mapping LLM nếu report PASS."""

    report = validate_and_publish_mapping(
        proposal_path=(
            PROJECT_ROOT
            / "reports/llm/adventureworks/mapping_proposal.json"
        ),
        source_profile_path=(
            PROJECT_ROOT
            / "reports/llm/adventureworks/source_profile.json"
        ),
        database_path=(
            PROJECT_ROOT / "data/raw/adventureworks_hr.sqlite"
        ),
        report_path=(
            PROJECT_ROOT
            / "reports/llm/adventureworks/map_qc_report.json"
        ),
        published_mapping_path=(
            PROJECT_ROOT
            / "configs/mappings/adventureworks_hr_llm.yaml"
        ),
        runtime_database_path="data/raw/adventureworks_hr.sqlite",
    )

    print(
        f"MAP-QC {report.status}: "
        f"{len(report.errors)} errors, "
        f"{len(report.warnings)} warnings"
    )

    for issue in report.issues:
        print(
            f"[{issue.severity}] {issue.code} "
            f"{issue.path}: {issue.message} "
            f"(repair={issue.repair_strategy})"
        )

    if report.status == "FAIL":
        raise SystemExit(1)

    print(
        "Published mapping:",
        PROJECT_ROOT
        / "configs/mappings/adventureworks_hr_llm.yaml",
    )


if __name__ == "__main__":
    main()
