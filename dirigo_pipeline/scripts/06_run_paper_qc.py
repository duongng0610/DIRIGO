
import argparse
from pipeline_paths import PipelinePaths, save_json

from src.qc.paper_qc.qc_validator import (
    validate_all_qc,
)
from src.qc.projection.expected_projection_builder import (
    build_expected_projection,
)
from src.qc.projection.actual_projection_builder import (
    read_actual_projection,
)
from src.readers.reader_yaml import (
    read_yaml_file,
)
from src.readers.sqlite_reader import (
    SQLiteReader,
)





def print_summary(
    report: dict,
) -> None:
    print()
    print("=" * 78)
    print("PAPER QC SUMMARY")
    print("=" * 78)

    passed = 0
    failed = 0
    not_applicable = 0

    for qc_id, result in report["results"].items():
        status = result["status"]

        if status == "PASS":
            passed += 1

        elif status == "FAIL":
            failed += 1

        elif status == "NOT_APPLICABLE":
            not_applicable += 1

        ratio = result["completeness_ratio"]

        ratio_text = (
            "N/A"
            if ratio is None
            else f"{ratio * 100:.2f}%"
        )

        print(
            f"{qc_id:<5} | "
            f"{status:<14} | "
            f"expected={result['expected_count']:<5} | "
            f"actual={result['actual_count']:<5} | "
            f"missing={result['missing_count']:<5} | "
            f"unexpected={result['unexpected_count']:<5} | "
            f"ratio={ratio_text}"
        )

        if status == "FAIL":
            if result["missing_samples"]:
                print(
                    "      Missing:",
                    result["missing_samples"],
                )

            if result["unexpected_samples"]:
                print(
                    "      Unexpected:",
                    result["unexpected_samples"],
                )

    overall_status = (
        "PASS"
        if report["all_passed"]
        else "FAIL"
    )

    print()
    print("Overall status:", overall_status)
    print("Passed:", passed)
    print("Failed:", failed)
    print("Not applicable:", not_applicable)
    print("=" * 78)


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

    reader = SQLiteReader(
        paths.database_path
    )

    expected = build_expected_projection(
        reader,
        mapping,
    )

    actual = read_actual_projection(
        paths.output_directory,
        mapping,
    )

    report = validate_all_qc(
        expected=expected,
        actual=actual,
        mapping=mapping,
    )

    save_json(
        report,
        paths.paper_qc_report_path,
    )

    print_summary(report)

    print(
        "Full report:",
        paths.paper_qc_report_path,
    )

    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()