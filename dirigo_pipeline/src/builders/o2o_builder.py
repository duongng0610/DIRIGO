
"""Build lịch sử quan hệ object-to-object thành RelationshipRecord IR."""

from typing import Any
from pathlib import Path
from src.ir.models import RelationshipRecord
from src.builders.helper import build_object_reference_id, build_resolver_index, build_data_frame_by_table_name
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader


def build_o2o(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[RelationshipRecord]:
    """Tạo O2O records từ các relationship và qualifier mappings.

    Một logical relationship có thể có nhiều qualifier, ví dụ
    ``assigned`` và ``unassigned``. Mỗi qualifier có source table, filter và
    timestamp riêng, nên builder xử lý từng qualifier như một luồng lịch sử
    độc lập nhưng dùng chung source/target object reference.
    """
    o2o_records = []

    object_configs = {
        obj["type"]: obj
        for obj in mapping["objects"]
    }
    relationships = (
        mapping
        .get("relationships", {})
        .get("o2o", [])
    )

    for relationship_mapping in relationships:
        source_object_mapping = relationship_mapping["source"]
        source_object_type = source_object_mapping["object_type"]

        target_object_mapping = relationship_mapping["target"]
        target_object_type = target_object_mapping["object_type"]

        for qualifier_mapping in relationship_mapping["qualifiers"]:
            o2o_source_df = build_data_frame_by_table_name(
                sqlite_reader,
                qualifier_mapping["source_table"],
                mapping["tables"])

            # where thường phân biệt lifecycle row hợp lệ, ví dụ chỉ sinh
            # unassigned khi EndDate không null.
            o2o_source_df = sqlite_reader.apply_where(
                o2o_source_df,
                qualifier_mapping.get("where", []),
            )

            # Cả source lẫn target đều có thể là lookup reference. Index được
            # chuẩn bị trước khi duyệt rows để giữ chi phí lookup tuyến tính.
            source_lookup_index = build_resolver_index(
                sqlite_reader, source_object_mapping, mapping)

            target_lookup_index = build_resolver_index(
                sqlite_reader, target_object_mapping, mapping)

            qualifier = qualifier_mapping["qualifier"]
            time_stamp_column = qualifier_mapping["timestamp"]["column"]

            for _, row in o2o_source_df.iterrows():

                source_object_id = build_object_reference_id(
                    row=row,
                    object_config=object_configs[source_object_type],
                    object_mapping=source_object_mapping,
                    lookup_index=source_lookup_index,
                )

                target_object_id = build_object_reference_id(
                    row=row,
                    object_config=object_configs[target_object_type],
                    object_mapping=target_object_mapping,
                    lookup_index=target_lookup_index
                )

                time_stamp = row[time_stamp_column]

                o2o_records.append(RelationshipRecord(
                    qualifier=qualifier,
                    source_object_id=source_object_id,
                    source_object_type=source_object_type,
                    target_object_id=target_object_id,
                    target_object_type=target_object_type,
                    time_stamp=time_stamp
                ))

    return o2o_records
