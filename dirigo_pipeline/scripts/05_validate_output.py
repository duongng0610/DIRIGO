
import argparse


from pipeline_paths import PipelinePaths, save_json

from src.qc.output_qc.output_integrity_validator import (
    validate_dirigo_output,
)
from src.readers.reader_yaml import (
    read_yaml_file,
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

    mapping = read_yaml_file(
        paths.published_mapping_path
    )

    report = validate_dirigo_output(
        paths.output_directory,
        mapping,
    )

    save_json(
        report,
        paths.output_qc_report_path,
    )

    print("OUTPUT QC RESULT")
    print("Status:", report["status"])
    print("Issues:", len(report["issues"]))

    for issue in report["issues"]:
        print(
            f"[{issue['code']}] "
            f"{issue['message']} "
            f"(count={issue['count']})"
        )

    print("Report:", paths.output_qc_report_path)

    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()