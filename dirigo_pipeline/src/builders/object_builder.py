from typing import Any, Dict, List, Optional

from src.ir import ObjectChangeRecord, ObjectRecord
from src.readers.sqlite_reader import SQLiteReader


def create_option_id(prefix: str, columns: List[str], separator="-") -> str:
    if not prefix or not columns or not separator:
        raise ValueError(
            "Prefix, columns, and separator must be provided to create an option ID."
        )

    return f"{prefix}{separator}{separator.join(columns)}"


def create_static_attributes(
    row, static_attribute_mappings: List[dict]
) -> Dict[str, Any]:
    attributes: Dict[str, Any] = {}
    for mapping in static_attribute_mappings:
        timestamp_mapping = mapping.get("timestamp")
        if timestamp_mapping:
            attributes[timestamp_mapping["name"]] = row.get(
                timestamp_mapping["source_column"]
            )
        else:
            attributes[mapping["name"]] = row.get(mapping["source_column"])
    return attributes


def create_dynamic_attributes(
    sqlite_reader: SQLiteReader,
    source_table: str,
    object_row,
    dynamic_attribute_mappings: List[dict],
) -> List[ObjectChangeRecord]:
    changes: List[ObjectChangeRecord] = []
    for mapping in dynamic_attribute_mappings:
        join_columns = [(mapping["join_column"]["source"],
                         mapping["join_column"]["target"])]
        source_id_column = mapping["join_column"]["source"]
        dynamic_attributes_rows = sqlite_reader.get_joined_data(
            source_table,
            mapping["target_table"],
            join_columns,
            filter_column=source_id_column,
            filter_value=object_row[source_id_column],
        )

        for _, row in dynamic_attributes_rows.iterrows():
            change = ObjectChangeRecord(
                time_stamp=row[mapping["timestamp_column"]],
                ocel_change_field=mapping["name"],
                new_value=row[mapping["target_column"]],
            )
            changes.append(change)

    return changes


def _source_table_name(source_table: str, table_mapping: Dict[str, dict]) -> str:
    return table_mapping.get(source_table, {}).get("table", source_table)


def build_objects(sqlite_reader: SQLiteReader, mapping: dict) -> List[ObjectRecord]:
    objects: List[ObjectRecord] = []
    for object_mapping in mapping["objects"]:
        source_table = _source_table_name(
            object_mapping["source_table"], mapping["tables"]
        )
        source_df = sqlite_reader.read_table(source_table)
        if source_df is None:
            continue

        for _, row in source_df.iterrows():
            # create object_id
            id_mapping = object_mapping["id"]
            if id_mapping["mode"] == "option":
                object_id = create_option_id(
                    id_mapping["prefix"],
                    [str(row[column]) for column in id_mapping["columns"]],
                    id_mapping.get("separator", "-"),
                )
            else:
                object_id = str(row[id_mapping["columns"][0]])

            # create static and dynamic attributes
            attributes_mapping = object_mapping["attributes"]
            attributes = create_static_attributes(
                row, attributes_mapping.get("static", [])
            )
            timestamp = attributes.pop("timestamp", None)

            changes = create_dynamic_attributes(
                sqlite_reader,
                source_table,
                row,
                attributes_mapping.get("dynamic", []),
            )
            objects.append(
                ObjectRecord(
                    object_id=object_id,
                    object_type=object_mapping["type"],
                    attributes=attributes,
                    time_stamp=timestamp,
                    changes=changes,
                )
            )
    return objects
