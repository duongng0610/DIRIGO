
"""Build EventRecord và các quan hệ E2O từ event mapping."""

from typing import Any
from pathlib import Path
from src.ir.models import EventRecord
from src.ir.models import EventToObjectRecord
from src.builders.helper import build_object_reference_id, build_id_from_row, _source_table_name, build_resolver_index,build_data_frame_by_table_name
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader

def build_events(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[EventRecord]:
    """Tạo event IR và E2O references cho mọi event type trong mapping.

    ``where`` quyết định source row nào thực sự biểu diễn event. Object ID
    luôn được tạo qua object config canonical, kể cả khi event row cần lookup
    sang bảng khác để lấy khóa object.
    """
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

        # Chỉ các row vượt qua where mới sinh EventRecord.
        source_df = sqlite_reader.apply_where(
            source_df,
            event_mapping.get("where", []),
        )

        object_mappings = event_mapping.get("objects",[])

        # Một event có thể tham chiếu object nằm ở bảng khác. Index từng
        # reference trước vòng lặp để tránh đọc/scan lại lookup table cho mỗi row.
        lookup_indexes = {}

        for position, object_mapping in enumerate(object_mappings):
            lookup_indexes[position] = build_resolver_index(sqlite_reader, object_mapping, mapping)
        
        for _,row in source_df.iterrows():
            event_id = build_id_from_row(
                row,
                event_mapping["id"],
            )

            timestamp_column = event_mapping["timestamp"]["source_column"]

            event_time = row[timestamp_column]

            # Danh sách này được extractor trải thành các dòng OCEL_E2O.csv.
            object_relations = []

            for position,object_mapping in enumerate(event_mapping.get("objects",[])):
                object_type = object_mapping["object_type"]
                # ID rule thuộc object config; event mapping chỉ mô tả cách
                # tìm các giá trị khóa cần thiết trên row hiện tại.
                object_config = object_configs[object_type]
                object_id = build_object_reference_id(
                    row=row,
                    object_config=object_config,
                    object_mapping=object_mapping,
                    lookup_index= lookup_indexes.get(position)
                )

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



