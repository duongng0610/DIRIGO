from typing import Any
from pathlib import Path
from src.ir.models import EventRecord
from src.ir.models import EventToObjectRecord
from src.builders.helper import _source_table_name
from src.builders.helper import create_option_id
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader


def get_objects_id_config(objects_mapping: dict[str, Any]) -> dict[str, Any]:
    result = {
        obj["type"]: obj["id"] for obj in objects_mapping
    }

    return result


def create_timestamp(event_mapping: dict[str, Any], row):
    return row[event_mapping["timestamp"]["source_column"]]


def create_out_table_object(
        source_df,
        joined_table_by_key: dict[str, Any],
        events_by_row: dict[Any, EventRecord],
        out_table_mapping: dict[str, Any],
        objects_id_config: dict[str, Any],
):

    for _, source_row in source_df.iterrows():

        id_mapping = objects_id_config[out_table_mapping["object_type"]]
        event_key = source_row[out_table_mapping["join_column"]["source"]]

        e2o_rows = joined_table_by_key.get(event_key)
        event_record = events_by_row.get(source_row.name)

        objects = []
        seen_objects = set()

        if e2o_rows is None or event_record is None:
            continue

        for _, row in e2o_rows.iterrows():
            if (id_mapping["mode"] == "option"):
                option_columns = [
                    str(row[column]) for column in id_mapping["columns"]
                ]

                object_id = create_option_id(
                    id_mapping["prefix"],
                    option_columns,
                    id_mapping.get("separator"),
                )

            else:
                object_id = row[id_mapping["columns"][0]]

            object_key = (object_id, out_table_mapping["qualifier"])
            if object_key not in seen_objects:
                objects.append(EventToObjectRecord(
                    object_id=object_id,
                    qualifier=out_table_mapping["qualifier"]
                ))
                seen_objects.add(object_key)

        event_record.objects.extend(objects)


def create_in_table_objects(
        objects_id_config: dict[str, Any],
        in_table_mapping: dict[str, Any],
        event_row,
) -> list[EventToObjectRecord]:

    in_table_objects = []

    if in_table_mapping is None or in_table_mapping == []:
        return in_table_objects

    for mapping in in_table_mapping:

        id_mapping = objects_id_config[mapping["object_type"]]
        if (id_mapping["mode"] == "option"):
            option_columns = [
                str(event_row[column]) for column in id_mapping["columns"]
            ]

            object_id = create_option_id(
                id_mapping["prefix"],
                option_columns,
                id_mapping.get("separator"),
            )

        else:
            object_id = event_row[id_mapping["columns"][0]]

        in_table_object = EventToObjectRecord(
            object_id=object_id,
            qualifier=mapping["qualifier"]
        )

        in_table_objects.append(in_table_object)

    return in_table_objects


def build_events(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[EventRecord]:
    events: list[EventRecord] = []
    objects_id_config = get_objects_id_config(mapping["objects"])

    for event_mapping in mapping["events"]:
        event_objects = event_mapping.get("objects", {})
        source_table = _source_table_name(
            event_mapping["source_table"], mapping["tables"])

        source_df = sqlite_reader.read_table(source_table)

        if source_df is None:
            continue

        current_events: list[EventRecord] = []

        # where condition to fill fit row data
        source_df = sqlite_reader.apply_where(
            source_df, event_mapping.get("where"))

        for _, row in source_df.iterrows():

            # create event_id
            id_mapping = event_mapping["id"]
            if (event_mapping["id"]["mode"] == "option"):
                event_id = create_option_id(
                    id_mapping["prefix"],
                    [str(row[column]) for column in id_mapping["columns"]],
                    id_mapping.get("separator", "-"),
                )

            else:
                event_id = str(row[id_mapping["columns"][0]])

            # create timestamp
            timestamp = create_timestamp(event_mapping, row)

            # create in table objects
            objects = create_in_table_objects(
                objects_id_config=objects_id_config,
                in_table_mapping=event_objects.get("in_table"),
                event_row=row
            )

            event_record = EventRecord(
                event_id=event_id,
                activity=event_mapping["type"],
                time_stamp=timestamp,
                objects=objects
            )

            events.append(event_record)
            current_events.append(event_record)

        # create out table objects
        out_tables_mapping = event_objects.get("out_table")

        if (out_tables_mapping is None or out_tables_mapping == []):
            continue

        # cache joinned table
        join_cache = {}

        for out_mapping in out_tables_mapping:
            target_table = _source_table_name(
                out_mapping["target_table"], mapping["tables"])
            join_column_source = out_mapping["join_column"]["source"]
            join_column_target = out_mapping["join_column"]["target"]

            cache_key = (
                source_table,
                target_table,
                join_column_source,
                join_column_target
            )

            if cache_key not in join_cache:
                join_columns = [(join_column_source, join_column_target)]
                joined_table = sqlite_reader.get_joined_data(
                    source_table, target_table, join_columns)

                # where condition to fill fit row data
                joined_table = sqlite_reader.apply_where(
                    joined_table, event_mapping.get("where"))

                if joined_table is None:
                    joined_table_by_key = {}
                else:
                    joined_table_by_key = {
                        key: group
                        for key, group in joined_table.groupby(join_column_source)
                    }

                join_cache[cache_key] = joined_table_by_key

            events_by_row = dict(zip(source_df.index, current_events))

            create_out_table_object(
                source_df, joined_table_by_key, events_by_row,
                out_mapping, objects_id_config)

    return events
