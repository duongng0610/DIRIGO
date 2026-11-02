import src.readers.sqlite_reader as sqlite_reader
import src.readers.reader_yaml as yaml_reader
import src.builders.object_builder as object_builder
from src.extractor.to_csv import convert_objects

from pathlib import Path


def main():
    # Define the path to the SQLite database and the mapping YAML file
    data_path = Path(
        r"E:\UET\SPECIALIZATION\Infomation System\BTL_CuoiKi\code\dirigo\dirigo_pipeline\data\raw"
    )

    mapping_path = Path(
        r"E:\UET\SPECIALIZATION\Infomation System\BTL_CuoiKi\code\dirigo\dirigo_pipeline\configs\mappings"
    )
    # Create an instance of SQLiteReader
    reader = sqlite_reader.SQLiteReader(data_path / "adventureworks_hr.sqlite")

    # Read the mapping from the YAML file
    mapping = yaml_reader.read_yaml_file(
        mapping_path / "adventureworks_hr_mapping.yaml")

    # Build objects based on the mapping
    objects = object_builder.build_objects(reader, mapping)

    # Convert the IR ObjectRecords to Dirigo-compatible object CSV files
    output_dir = Path(
        r"E:\UET\SPECIALIZATION\Infomation System\BTL_CuoiKi\code\dirigo\dirigo_pipeline\outputs"
    )
    output_files = convert_objects(objects, output_dir)
    for output_file in output_files:
        print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
