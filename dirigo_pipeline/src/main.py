import src.readers.sqlite_reader as sqlite_reader
import src.readers.reader_yaml as yaml_reader
from src.builders import object_builder_v2, event_builder_v2, o2o_builder

from src.extractor.to_csv import convert_objects, convert_events, convert_relationships
from src.validation.qc_validator import validate_all_qc

from pathlib import Path


def main():
    # Define the path to the SQLite database and the mapping YAML file
    # Comparatively path
    data_path = Path(
        r".\data\raw"
    )

    mapping_path = Path(
        r".\configs\mappings"
    )
    # Create an instance of SQLiteReader
    reader = sqlite_reader.SQLiteReader(data_path / "adventureworks_hr.sqlite")

    # Read the mapping from the YAML file
    mapping = yaml_reader.read_yaml_file(
        mapping_path / "adventureworks_hr_mapping.yaml")

    # Build objects based on the mapping
    objects = object_builder_v2.build_objects(reader, mapping)

    # Convert the IR ObjectRecords to Dirigo-compatible object CSV files
    output_dir = Path(
        r".\outputs"
    )

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

    # print(validate_all_qc(objects=objects, events=events, relationships=o2o,
    #                       validate_mapping=mapping, reader=reader))


if __name__ == "__main__":
    main()
