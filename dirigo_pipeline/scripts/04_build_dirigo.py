"""Build Dirigo IR từ mapping đã publish và xuất các CSV runtime."""

import argparse


from pipeline_paths import PipelinePaths

from src.builders import event_builder, object_builder
from src.builders import (
    o2o_builder,
)
from src.extractor.to_csv import (
    convert_events,
    convert_objects,
    convert_relationships,
)
from src.readers.reader_yaml import (
    read_yaml_file,
)
from src.readers.sqlite_reader import (
    SQLiteReader,
)


def parse_arguments():
    """Đọc tên SQLite trong data/raw cho dataset cần build."""
    parser = argparse.ArgumentParser()

    parser.add_argument("sqlite_file")

    parser.add_argument(
        "--domain-hint",
        default=None,
        help="Optional business-domain description",
    )

    return parser.parse_args()

def main() -> None:
    """Chạy ba builders rồi chuyển IR thành object/event/E2O/O2O CSV.

    Script chỉ đọc ``published_mapping_path`` — tức mapping đã vượt MAP-QC.
    Object, event và relationship được build độc lập nhưng phải dùng chung
    canonical ID helpers để E2O/O2O tham chiếu đúng object CSV.
    """
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

    print("Building objects...")
    objects = object_builder.build_objects(
        reader,
        mapping,
    )

    print("Building events and E2O...")
    events = event_builder.build_events(
        reader,
        mapping,
    )

    print("Building O2O...")
    relationships = o2o_builder.build_o2o(
        reader,
        mapping,
    )

    object_files = convert_objects(
        objects,
        paths.output_directory,
    )

    event_files = convert_events(
        events,
        paths.output_directory,
    )

    relationship_file = convert_relationships(
        relationships,
        paths.output_directory,
    )

    print()
    print("DIRIGO BUILD COMPLETED")
    print("Object records:", len(objects))
    print("Event records:", len(events))
    print(
        "O2O relationship records:",
        len(relationships),
    )
    print("Output directory:", paths.output_directory)

    print()
    print("Written files:")

    for path in object_files:
        print("-", path)

    for path in event_files:
        print("-", path)

    print("-", relationship_file)


if __name__ == "__main__":
    main()
