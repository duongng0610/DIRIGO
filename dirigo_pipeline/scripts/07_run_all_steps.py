"""Entry point chạy tuần tự sáu bước của Dirigo extraction pipeline."""

import subprocess
import sys

from pathlib import Path

import argparse

from pipeline_paths import PipelinePaths

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent

STEPS = [
    "01_profile_source.py",
    "02_propose_mapping.py",
    "03_validate_publish_mapping.py",
    "04_build_dirigo.py",
    "05_validate_output.py",
    "06_run_paper_qc.py",
]

def run_script(
    script_name: str,
    sqlite_file: str,
    extra_arguments: list[str] | None = None,
) -> None:
    """Chạy một step bằng đúng Python interpreter của process hiện tại.

    Dùng ``sys.executable`` bảo đảm subprocess tiếp tục chạy trong cùng
    virtual environment. ``check=True`` dừng pipeline ngay khi một bước fail.
    """
    script_path = (
        SCRIPTS_DIRECTORY / script_name
    )

    command = [
        sys.executable,
        str(script_path),
        sqlite_file,  # Bắt buộc phải có
    ]

    if extra_arguments:
        command.extend(extra_arguments)

    print()
    print("Running:", " ".join(command))

    subprocess.run(
        command,
        check=True,
    )

def parse_arguments():
    """Đọc SQLite filename và domain hint tùy chọn cho mapping proposer."""
    parser = argparse.ArgumentParser()

    parser.add_argument("sqlite_file")

    parser.add_argument(
        "--domain-hint",
        default=None,
        help="Optional business-domain description",
    )

    return parser.parse_args()

def main() -> None:
    """Chạy profile -> propose -> validate/repair -> build -> OUT-QC -> QC."""
    args = parse_arguments()

    run_script(
        "01_profile_source.py",
        args.sqlite_file,
    )

    proposal_arguments = []

    if args.domain_hint:
        proposal_arguments.extend([
            "--domain-hint",
            args.domain_hint,
        ])

    run_script(
        "02_propose_mapping.py",
        args.sqlite_file,
        proposal_arguments,
    )

    for script_name in [
        "03_validate_publish_mapping.py",
        "04_build_dirigo.py",
        "05_validate_output.py",
        "06_run_paper_qc.py",
    ]:
        run_script(
            script_name,
            args.sqlite_file,
        )

    print()
    print("FULL PIPELINE COMPLETED")


if __name__ == "__main__":
    main()
