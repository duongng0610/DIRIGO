
from typing import Any
from pathlib import Path
from src.ir.models import EventRecord
from src.ir.models import EventToObjectRecord
from src.builders.helper import build_object_reference_id, build_id_from_row, _source_table_name, build_lookup_index
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader

def build_events(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[EventRecord]:
    event_records = []

    object_configs = {
        obj["type"]: obj
        for obj in mapping["objects"]
    }

    for event_mapping in mapping["events"]:
        source_table = _source_table_name(
            event_mapping["source_table"],
            mapping["tables"],
        )
        source_df = sqlite_reader.read_table(source_table)

        if source_df is None:
            raise ValueError(f"Cannot read table: {source_table}")

        #Giữ những row là event trong bảng 
        source_df = sqlite_reader.apply_where(
            source_df,
            event_mapping.get("where", []),
        )

        object_mappings = event_mapping.get("objects",[])

        #build lookup_index trước khi duyệt từng row 
        lookup_indexes = {}

        #Bọc [] trong enumerate để duyệt lấy được (index, value)
        for position, object_mapping in enumerate(object_mappings):
            resolver_mapping = object_mapping.get("resolver")

            if resolver_mapping is None:
                continue

            lookup_table = _source_table_name(
                 resolver_mapping["table"],
                 mapping["tables"]
            )

            lookup_df = sqlite_reader.read_table(lookup_table)

            if lookup_df is None:
                raise ValueError(
                    f"Cannot read lookup table: {lookup_table}"
                )

            lookup_indexes[position] = build_lookup_index(lookup_df, resolver_mapping)
        
        for _,row in source_df.iterrows():
            event_id = build_id_from_row(
                row,
                event_mapping["id"],
            )

            timestamp_column = event_mapping["timestamp"]["source_column"]

            event_time = row[timestamp_column]

            #list[EventToObjectRecord]
            object_relations = []

            for position,object_mapping in enumerate(event_mapping.get("objects",[])):
                object_type = object_mapping["object_type"]
                #Lấy config yaml của objects có sẵn 
                object_config = object_configs[object_type]

                #/....
                object_id = build_object_reference_id(
                    event_row=row,
                    object_config=object_config,
                    object_mapping=object_mapping,
                    lookup_index= lookup_indexes.get(position)
                )

                #..../
               
                object_relations.append(
                    EventToObjectRecord(
                        object_id=object_id,
                        qualifier=object_mapping["qualifier"],
                    )
                )

            event_records.append(
                EventRecord(
                    event_id=event_id,
                    activity= event_mapping["type"],
                    time_stamp= event_time,
                    objects=object_relations
                )
            )

    return event_records



