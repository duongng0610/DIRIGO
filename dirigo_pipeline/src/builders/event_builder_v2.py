
from typing import Any
from pathlib import Path
from src.ir.models import EventRecord
from src.ir.models import EventToObjectRecord
from src.builders.helper import build_object_reference_id, build_id_from_row, _source_table_name, build_resolver_index,build_data_frame_by_table_name
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader

def build_events(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[EventRecord]:
    event_records = []

    object_configs = {
        obj["type"]: obj
        for obj in mapping["objects"]
    }

    for event_mapping in mapping["events"]:
        
        source_df = build_data_frame_by_table_name(
            sqlite_reader,
            event_mapping["source_table"],
            mapping["tables"] )

        #Giữ những row là event trong bảng 
        source_df = sqlite_reader.apply_where(
            source_df,
            event_mapping.get("where", []),
        )

        object_mappings = event_mapping.get("objects",[])

        # Vì object liên quan đến event có thể nằm ở bảng khác bảng event hiện tại  
        # build lookup_index (key(giá trị khóa ngoại liên kết giữa bảng event - object),
        # val-row trong bảng lookup) trước khi duyệt từng row trong event ,  
        lookup_indexes = {}

        #Bọc [] trong enumerate để duyệt lấy được (index, value)
        for position, object_mapping in enumerate(object_mappings):
            lookup_indexes[position] = build_resolver_index(sqlite_reader, object_mapping, mapping)
        
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
                    row=row,
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



