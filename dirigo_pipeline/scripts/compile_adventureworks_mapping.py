import sys

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.llm.mapping_compiler import compile_proposal_file


def main() -> None:
    """
    Compile proposal JSON thành YAML candidate để review/MAP-QC.

    File được ghi vào reports, không ghi thẳng vào configs/mappings
    vì đây chưa phải mapping đã được phê duyệt.
    """

    output_path = compile_proposal_file(
        proposal_path=(
            PROJECT_ROOT
            / "reports/llm/adventureworks/mapping_proposal.json"
        ),
        output_path=(
            PROJECT_ROOT
            / "reports/llm/adventureworks/mapping_candidate.yaml"
        ),
        source_database_path=(
            "data/raw/adventureworks_hr.sqlite"
        ),
    )

    print("Candidate YAML created:", output_path)


if __name__ == "__main__":
    main()
