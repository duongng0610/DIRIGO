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


def create_objects_out_table(
        sqlite_reader: SQLiteReader,
        source_table: str,
        target_table: str,
        where_mapping: dict[str, Any],
        out_mapping: dict[str, Any],
        objects_id_config: dict[str, Any],
        event_row,
) -> list[EventToObjectRecord]:

    objects = []

    join_columns = [(out_mapping["join_column"]["source"],
                     out_mapping["join_column"]["target"])]

    source_id_column = out_mapping["join_column"]["source"]

    e2o_rows = sqlite_reader.get_joined_data(
        source_table,
        target_table,
        join_columns=join_columns,
        filter_column=source_id_column,
        filter_value=event_row[source_id_column],
    )

    if where_mapping is not None:
        e2o_rows = sqlite_reader.apply_where(
            e2o_rows, where_mapping)

    if e2o_rows is None or e2o_rows.empty:
        return

    for _, row in e2o_rows.iterrows():
        id_mapping = objects_id_config[out_mapping["object_type"]]

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
            object_id = row[source_id_column]

        objects.append(
            EventToObjectRecord(
                object_id=object_id,
                qualifier=out_mapping["qualifier"]
            )
        )

    return objects


def create_objects_in_table(
    objects_id_config: dict[str, Any],
    in_mapping: dict[str, Any],
    event_row,

) -> EventToObjectRecord:
    id_mapping = objects_id_config[in_mapping["object_type"]]
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

    return EventToObjectRecord(
        object_id=object_id,
        qualifier=in_mapping["qualifier"]
    )


def create_objects(
        sqlite_reader: SQLiteReader,
        source_table: str,
        objects_id_config: dict[str, Any],
        table_mapping: dict[str, Any],
        event_mapping: dict[str, Any],
        event_row,
) -> list[EventToObjectRecord]:

    objects = []

    if event_mapping.get("objects") is None:
        return objects

    for mapping in event_mapping["objects"]:
        if (mapping["mode"] == "out_table"):
            # get name table in original sqlite
            target_table = _source_table_name(
                mapping["target_table"], table_mapping)

            where_mapping = event_mapping.get("where")

            out_objects = create_objects_out_table(
                sqlite_reader=sqlite_reader,
                source_table=source_table,
                target_table=target_table,
                where_mapping=where_mapping,
                out_mapping=mapping,
                objects_id_config=objects_id_config,
                event_row=event_row
            )

            objects.extend(out_objects)

        else:
            in_object = create_objects_in_table(
                objects_id_config=objects_id_config,
                in_mapping=mapping,
                event_row=event_row
            )

            objects.append(in_object)

    return objects


def build_events(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[EventRecord]:
    events: list[EventRecord] = []
    objects_id_config = get_objects_id_config(mapping["objects"])

    for event_mapping in mapping["events"]:
        source_table = _source_table_name(
            event_mapping["source_table"], mapping["tables"])

        source_df = sqlite_reader.read_table(source_table)

        if source_df is None:
            continue

        # where condition to fill fit row data
        source_df = sqlite_reader.apply_where(
            source_df, event_mapping.get("where"))

        for _, row in source_df.iterrows():

            # create event_id
            if (event_mapping["id"]["mode"] == "option"):
                id_mapping = event_mapping["id"]

                event_id = create_option_id(
                    id_mapping["prefix"],
                    [str(row[column]) for column in id_mapping["columns"]],
                    id_mapping.get("separator", "-"),
                )

            else:
                event_id = str(id_mapping["columns"][0])

            # create timestamp
            timestamp = create_timestamp(event_mapping, row)

            # create objects
            objects = create_objects(
                sqlite_reader, source_table, objects_id_config, mapping["tables"], event_mapping, row
            )

            events.append(
                EventRecord(
                    event_id=event_id,
                    activity=event_mapping["type"],
                    time_stamp=timestamp,
                    objects=objects
                )
            )

    return events
