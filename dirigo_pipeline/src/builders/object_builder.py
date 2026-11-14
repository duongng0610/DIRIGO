from typing import Any, Dict, List

from src.ir import ObjectChangeRecord, ObjectRecord
from src.readers.sqlite_reader import SQLiteReader
from src.builders.helper import build_id_from_row, build_data_frame_by_table_name, build_resolver_index, build_object_reference_id


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


def build_objects(sqlite_reader: SQLiteReader, mapping: dict) -> List[ObjectRecord]:
    objects: List[ObjectRecord] = []

    for object_mapping in mapping["objects"]:

        source_df = build_data_frame_by_table_name(sqlite_reader,object_mapping["source_table"], mapping["tables"])

        objects_by_id: dict[str, ObjectRecord] = {}

        attributes_mapping = object_mapping["attributes"]
        
        static_attribute_mappings = attributes_mapping.get("static",[])
        
        dynamic_attribute_mappings = attributes_mapping.get("dynamic",[])

        for _, row in source_df.iterrows():

            object_id = build_id_from_row(row=row, id_mapping=object_mapping["id"])
            # create static attributes
           

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

            #lưu object theo id
            objects_by_id[object_id] = object_record

        #Duyệt dynamic_attribute bên ngoài row , 
        # object sẽ được lấy qua objects_by_id bới key = Khóa ngoại tại bảng chứa thuộc tính động
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

            # resolver_index đều = None do có thể lấy trực tiếp ở bảng
            resolver_index = build_resolver_index(
                sqlite_reader,
                object_reference,
                mapping,
            )

            #duyệt từng row ở bảng history 
            for _, history_row in history_df.iterrows():
                #lấy object_id là khóa ngoại tham chiếu đến bảng object
                object_id = build_object_reference_id(
                    row=history_row,
                    object_config=object_mapping,#chuyền vào object_mapping 
                    object_mapping=object_reference,
                    lookup_index=resolver_index,
                )

                #lấy object_record đã được nạp trước đó
                object_record = objects_by_id.get(object_id)

                if object_record is None:
                    raise ValueError(
                        f"Dynamic attribute '{attribute_mapping['name']}' "
                        f"references unknown object '{object_id}'"
                    )

                #thêm vào changes cho object_record
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