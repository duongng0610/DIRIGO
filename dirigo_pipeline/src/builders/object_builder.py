from typing import Any, Dict, List

from src.ir import ObjectChangeRecord, ObjectRecord
from src.readers.sqlite_reader import SQLiteReader
from src.builders.helper import _source_table_name
from src.builders.helper import build_id_from_row


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


def create_dynamic_attribute(
    source_df,
    joined_table_by_key: dict[str, Any],
    dynamic_attribute_mapping: dict[str, Any],
    objects_by_key: dict[str, Any],
):

    for _, row in source_df.iterrows():

        join_column_source = dynamic_attribute_mapping["join_column"]["source"]
        object_key = row[join_column_source]

        # get rows from dict (joinned table group by object key)
        dynamic_rows = joined_table_by_key.get(object_key)

        changes = []
        object_record = objects_by_key.get(object_key)
        if dynamic_rows is None or object_record is None:
            continue

        for _, dynamic_row in dynamic_rows.iterrows():
            change = ObjectChangeRecord(
                time_stamp=dynamic_row[dynamic_attribute_mapping["timestamp_column"]],
                ocel_change_field=dynamic_attribute_mapping["name"],
                new_value=dynamic_row[dynamic_attribute_mapping["target_column"]],
            )
            changes.append(change)

        object_record.changes.extend(changes)


def build_objects(sqlite_reader: SQLiteReader, mapping: dict) -> List[ObjectRecord]:
    objects: List[ObjectRecord] = []

    for object_mapping in mapping["objects"]:

        source_table = _source_table_name(
            object_mapping["source_table"], mapping["tables"]
        )
        source_df = sqlite_reader.read_table(source_table)
        if source_df is None:
            continue

        current_objects: List[ObjectRecord] = []

        for _, row in source_df.iterrows():
            # create object_id
            id_mapping = object_mapping["id"]

            object_id = build_id_from_row(row=row, id_mapping=id_mapping)
            # create static attributes
            attributes_mapping = object_mapping["attributes"]
            attributes = create_static_attributes(
                row, attributes_mapping.get("static", [])
            )
            timestamp = attributes.pop("timestamp", None)

            object_record = ObjectRecord(
                object_id=object_id,
                object_type=object_mapping["type"],
                attributes=attributes,
                time_stamp=timestamp,
                changes=[]
            )

            objects.append(object_record)
            current_objects.append(object_record)

        # create dynamic attributes
        dynamic_attributes_mapping = object_mapping["attributes"].get(
            "dynamic", [])

        join_cache = {}

        for dynamic_attribute_mapping in dynamic_attributes_mapping:

            target_table = dynamic_attribute_mapping["target_table"]
            join_column_source = dynamic_attribute_mapping["join_column"]["source"]
            join_column_target = dynamic_attribute_mapping["join_column"]["target"]

            cache_key = (
                source_table,
                target_table,
                join_column_source,
                join_column_target,
            )

            if cache_key not in join_cache:
                join_columns = [(join_column_source, join_column_target)]
                joined_table = sqlite_reader.get_joined_data(
                    source_table, target_table, join_columns)

                if joined_table is None:
                    joined_table_by_key = {}
                else:
                    joined_table_by_key = {
                        key: group
                        for key, group in joined_table.groupby(join_column_source)
                    }

                join_cache[cache_key] = joined_table_by_key

            objects_by_key = dict(
                zip(source_df[join_column_source], current_objects)
            )

            create_dynamic_attribute(
                source_df,
                join_cache[cache_key],
                dynamic_attribute_mapping,
                objects_by_key,
            )

    return objects
