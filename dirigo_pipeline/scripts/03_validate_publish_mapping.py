import argparse
from pipeline_paths import PipelinePaths
from src.llm.mapping_validator import (
    validate_and_publish_mapping,
)

def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("sqlite_file")

    parser.add_argument(
        "--domain-hint",
        default=None,
        help="Optional business-domain description",
    )

    return parser.parse_args()

def main() -> None:
    args = parse_arguments()

    paths = PipelinePaths.from_sqlite_file(
        args.sqlite_file
    )
    required_files = [
        paths.source_profile_path,
        paths.mapping_proposal_path,
        paths.database_path,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file does not exist: {path}"
            )

    report = validate_and_publish_mapping(
        proposal_path=paths.mapping_proposal_path,
        source_profile_path=paths.source_profile_path,
        database_path=paths.database_path,
        report_path=paths.map_qc_report_path,
        published_mapping_path=paths.published_mapping_path,
        runtime_database_path=paths.runtime_database_path,
    )

    print("MAP-QC RESULT")
    print("Status:", report.status)
    print("Errors:", len(report.errors))
    print("Warnings:", len(report.warnings))

    for issue in report.issues:
        print(
            f"[{issue.severity}] "
            f"{issue.code} "
            f"{issue.path}: "
            f"{issue.message}"
        )

    print("Report:", paths.map_qc_report_path)

    if report.status != "PASS":
        raise SystemExit(1)

    print(
        "Published mapping:",
        paths.published_mapping_path,
    )


if __name__ == "__main__":
    main()