"""Chuyển object mapping và dữ liệu SQLite thành ObjectRecord IR.

Object builder chạy theo hai pha: tạo toàn bộ object ban đầu trước, sau đó
gắn các thay đổi thuộc tính động. Thứ tự này bảo đảm một history row không
thể vô tình tạo ra object mới ngoài bảng master.
"""

from typing import Any, Dict, List

from src.ir import ObjectChangeRecord, ObjectRecord
from src.readers.sqlite_reader import SQLiteReader
from src.builders.helper import build_id_from_row, build_data_frame_by_table_name, build_resolver_index, build_object_reference_id


def create_static_attributes(
    row, static_attribute_mappings: List[dict]
) -> Dict[str, Any]:
    """Lấy các thuộc tính tĩnh được khai báo từ một source row.

    Tên thuộc tính output lấy từ ``name``; tên cột nguồn lấy từ
    ``source_column``. Nhánh timestamp được giữ để tương thích mapping cũ,
    trong đó timestamp của initial object row được khai báo chung với static
    attributes rồi tách ra trước khi tạo ObjectRecord.
    """
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


def build_objects(sqlite_reader: SQLiteReader, mapping: dict) -> List[ObjectRecord]:
    """Build initial objects và lịch sử thuộc tính động cho mọi object type.

    Mỗi object type có một ``objects_by_id`` riêng. Dynamic history row phải
    resolve về một ID đã xuất hiện trong bảng nguồn của chính object type đó;
    nếu không, pipeline dừng thay vì sinh object ngầm từ bảng history.
    """
    objects: List[ObjectRecord] = []

    for object_mapping in mapping["objects"]:

        source_df = build_data_frame_by_table_name(sqlite_reader,object_mapping["source_table"], mapping["tables"])

        objects_by_id: dict[str, ObjectRecord] = {}

        attributes_mapping = object_mapping["attributes"]
        
        static_attribute_mappings = attributes_mapping.get("static",[])
        
        dynamic_attribute_mappings = attributes_mapping.get("dynamic",[])

        # Pha 1: tạo initial ObjectRecord và index theo canonical object ID.
        for _, row in source_df.iterrows():

            object_id = build_id_from_row(row=row, id_mapping=object_mapping["id"])
            attributes = create_static_attributes(
                row, static_attribute_mappings
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

            # Index này chỉ tồn tại trong object type hiện tại.
            objects_by_id[object_id] = object_record

        # Pha 2: đọc từng bảng history và gắn change vào object đã tạo ở pha 1.
        for attribute_mapping in dynamic_attribute_mappings:
            history_df = build_data_frame_by_table_name(
                sqlite_reader,
                attribute_mapping["source_table"],
                mapping["tables"],
            )

            history_df = sqlite_reader.apply_where(
                history_df,
                attribute_mapping.get("where", []),
            )

            object_reference = attribute_mapping.get(
                "object_reference",
                {},
            )

            # Direct reference trả None; lookup reference tạo index một lần
            # trước khi duyệt history rows.
            resolver_index = build_resolver_index(
                sqlite_reader,
                object_reference,
                mapping,
            )

            for _, history_row in history_df.iterrows():
                # Reference có thể direct hoặc cần lookup sang bảng trung gian.
                object_id = build_object_reference_id(
                    row=history_row,
                    object_config=object_mapping,#chuyền vào object_mapping 
                    object_mapping=object_reference,
                    lookup_index=resolver_index,
                )

                object_record = objects_by_id.get(object_id)

                if object_record is None:
                    raise ValueError(
                        f"Dynamic attribute '{attribute_mapping['name']}' "
                        f"references unknown object '{object_id}'"
                    )

                # Mỗi source history row hiện tạo đúng một change record.
                object_record.changes.append(
                    ObjectChangeRecord(
                        time_stamp=history_row[
                        attribute_mapping["timestamp"]["column"]
                        ],
                        ocel_change_field=attribute_mapping["name"],
                        new_value=history_row[
                        attribute_mapping["value"]["column"]
                        ],
                    )
                )             
    return objects
