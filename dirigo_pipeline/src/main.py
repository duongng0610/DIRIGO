import src.readers.sqlite_reader as sqlite_reader
import src.readers.reader_yaml as yaml_reader
from src.builders import object_builder_v2, event_builder_v2, o2o_builder

from src.readers.sqlite_reader import SQLiteReader
from typing import Any
from dataclasses import asdict
from pprint import pprint

from src.llm.source_profiler import (
    ProfilerConfig,
    profile_sqlite,
    save_profile,
)

from src.qc.qc_source_result.expected_projection import (
    build_expected_projection,
)
from src.qc.qc_source_result.output_reader import (
    read_actual_projection,
)
from src.qc.qc_source_result.reconciliation_validator import (
    reconcile_all,
)

from src.extractor.to_csv import convert_objects, convert_events,convert_relationships

from pathlib import Path



def main():
    execute("adventureworks_hr.sqlite","adventureworks_hr_mapping.yaml", "adventureworks_hr")

def qc_completeness_of_dirigo(
    reader: SQLiteReader,
    mapping: dict[str, Any],
    output_dir: Path,
):
    expected = build_expected_projection(
        reader,
        mapping,
    )

    actual = read_actual_projection(
        output_dir,
        mapping,
    )

    results = reconcile_all(
        expected,
        actual,
    )

    for result in results:
        pprint(asdict(result))

    failed_results = [
        result
        for result in results
        if result.status == "FAIL"
    ]

    if failed_results:
        raise ValueError(
            "REC-QC failed: "
            f"{len(failed_results)} checks failed"
        )

def execute(sqlite_file:str, mapping_file:str, output_folder:str):
    # Define the path to the SQLite database and the mapping YAML file
    # Comparatively path
    data_path = Path(
        r".\data\raw"
    )

    mapping_path = Path(
        r".\configs\mappings"
    )
    # Create an instance of SQLiteReader
    reader = sqlite_reader.SQLiteReader(data_path / sqlite_file)

    # Read the mapping from the YAML file
    mapping = yaml_reader.read_yaml_file(
        mapping_path / mapping_file
        )

    # Build objects based on the mapping
    objects = object_builder_v2.build_objects(reader, mapping)

    # Convert the IR ObjectRecords to Dirigo-compatible object CSV files
    output_dir = Path("outputs") / output_folder

    print(output_folder)

    output_objects_files = convert_objects(objects, output_dir)
    for output_file in output_objects_files:
        print(f"Wrote {output_file}")

    # Build events and e2o based on mapping
    events = event_builder_v2.build_events(reader, mapping)

    output_events_files = convert_events(events, output_dir)
    for output_file in output_events_files:
        print(f"Wrote {output_file}")

    # Build events and e2o based on mapping
    o2o = o2o_builder.build_o2o(reader, mapping)

    output_o2o_file = convert_relationships(o2o, output_dir)

    print(f"Wrote {output_o2o_file}") 

    print('\n')  

    


if __name__ == "__main__":
    main()
