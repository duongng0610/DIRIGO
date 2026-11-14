# Bắt buộc import pipeline_paths  trước các module src.
#Khi chạy python scripts/....py thì python đặt thư mục scripts vào sys.path :D:\Code\Dirigo\dirigo_pipeline\scripts 
#Khi import src... => sẽ tìm scripts/src 
# src nằm ngang hàng với scripts nên python ko tự tìm module src 
import argparse

from pipeline_paths import PipelinePaths
from src.llm.source_profiler import (
    ProfilerConfig,
    profile_sqlite,
    save_profile,
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Profile a SQLite source database",
    )

    parser.add_argument("sqlite_file")

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    paths = PipelinePaths.from_sqlite_file(
        args.sqlite_file
    )


    config = ProfilerConfig(
        sample_rows_per_table=3,
        max_key_width=3,
        max_candidate_columns=8,
        redact_columns=frozenset({
            "NationalIDNumber",
            "LoginID",
            "EmailAddress",
            "BirthDate",
        }),
    )

    profile = profile_sqlite(
        paths.database_path,
        config=config,
    )

    save_profile(
        profile,
        paths.source_profile_path,
    )

    print("SOURCE PROFILE COMPLETED")
    print("Database:", paths.database_path)
    print("Tables:", profile["database"]["table_count"])
    print("Output:", paths)


if __name__ == "__main__":
    main()