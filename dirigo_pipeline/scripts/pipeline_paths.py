import json
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Xử lý lỗi import src... khi run  python scripts/....py
#Khi chạy python scripts/....py thì python đặt thư mục scripts vào sys.path :D:\Code\Dirigo\dirigo_pipeline\scripts 
#Khi import src... => sẽ tìm scripts/src 
# src nằm ngang hàng với scripts nên python ko tự tìm module src
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


RAW_DATA_DIRECTORY = (
    PROJECT_ROOT / "data" / "raw"
)

#Dựa tên file sqlite trong data/raw => mỗi output sẽ ghép với mục tên tương ứng với tên sqlite 
@dataclass(frozen=True)
class PipelinePaths:
    sqlite_file_name: str
    dataset_name: str

    database_path: Path
    runtime_database_path: str

    work_directory: Path
    source_profile_path: Path
    mapping_proposal_path: Path
    mapping_run_path: Path
    map_qc_report_path: Path
    output_qc_report_path: Path
    paper_qc_report_path: Path

    published_mapping_path: Path
    output_directory: Path

    @classmethod
    def from_sqlite_file(
        cls,
        sqlite_file: str,
    ) -> "PipelinePaths":
        """
        Nhận tên file nằm trực tiếp trong data/raw.

        Ví dụ:
            adventureworks_hr.sqlite
            inventory_management.db
        """

        input_path = Path(sqlite_file)

        # Không cho truyền path ra ngoài data/raw.
        if (
            input_path.is_absolute()
            or input_path.name != sqlite_file
        ):
            raise ValueError(
                "Only provide a SQLite file name located "
                "directly inside data/raw, for example "
                "'adventureworks_hr.sqlite'"
            )

        allowed_suffixes = {
            ".sqlite",
            ".sqlite3",
            ".db",
        }

        if input_path.suffix.lower() not in allowed_suffixes:
            raise ValueError(
                "Unsupported database extension. "
                f"Expected one of {sorted(allowed_suffixes)}"
            )

        dataset_name = input_path.stem

        database_path = (
            RAW_DATA_DIRECTORY / input_path.name
        )

        if not database_path.exists():
            raise FileNotFoundError(
                f"SQLite database does not exist: "
                f"{database_path}"
            )

        work_directory = (
            PROJECT_ROOT
            / "reports"
            / "steps"
            / dataset_name
        )

        mapping_directory = (
            PROJECT_ROOT
            / "configs"
            / "mappings"
            / dataset_name
        )

        output_directory = (
            PROJECT_ROOT
            / "outputs"
            / dataset_name
        )

        return cls(
            sqlite_file_name=input_path.name,
            dataset_name=dataset_name,
            database_path=database_path,
            runtime_database_path=(
                Path("data")
                .joinpath("raw", input_path.name)
                .as_posix()
            ),
            work_directory=work_directory,
            source_profile_path=(
                work_directory / "source_profile.json"
            ),
            mapping_proposal_path=(
                work_directory / "mapping_proposal.json"
            ),
            mapping_run_path=(
                work_directory / "mapping_run.json"
            ),
            map_qc_report_path=(
                work_directory / "map_qc_report.json"
            ),
            output_qc_report_path=(
                work_directory / "output_qc_report.json"
            ),
            paper_qc_report_path=(
                work_directory / "paper_qc_report.json"
            ),
            published_mapping_path=(
                mapping_directory / "mapping.yaml"
            ),
            output_directory=output_directory,
        )


def save_json(
    value: Any,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )