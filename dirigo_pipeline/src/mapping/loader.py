from pathlib import Path
from typing import Any

from src.readers import read_yaml_file
from src.readers.sqlite_reader import SQLiteReader


def load_mapping(path: Path) -> dict[str, Any]:
    mapping = read_yaml_file(path)

    if "objects" not in mapping:
        raise ValueError(
            f"Mapping file {path} does not contain 'objects' key.")

    if "events" not in mapping:
        raise ValueError(f"Mapping file {path} does not contain 'events' key.")

    if "relationships" not in mapping:
        raise ValueError(
            f"Mapping file {path} does not contain 'relationships' key.")

    if "tables" not in mapping:
        raise ValueError(f"Mapping file {path} does not contain 'tables' key.")

    exist_tables = SQLiteReader(
        "dirigo_inventory_pipeline/data/dirigo_inventory.db").get_all_tables()
    for table in mapping["tables"]:
        if table not in exist_tables:
            raise ValueError(
                f"Table '{table}' specified in mapping file {path} does not exist in the database.")

    return mapping
