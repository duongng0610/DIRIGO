from __future__ import annotations

from collections import Counter
from typing import Any, Optional


from src.ir.models import ObjectChangeRecord, ObjectRecord, EventRecord, RelationshipRecord
from src.readers.sqlite_reader import SQLiteReader
from src.builders.helper import build_data_frame_by_table_name
from src.validation.helper import is_valid_value, get_relationship_type_change_positions


# QC2a: Static Attributes Completeness Ratio

def validate_no_missing_static_object_attributes(
    objects: list[ObjectChangeRecord] | list[ObjectRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    for obj_cfg in validate_mapping.get("objects", []):
        obj_type = obj_cfg.get("type", "")

        # 1. Danh sách các thuộc tính static từ mapping
        static_attrs: list[str] = [
            item["name"] if isinstance(item, dict) and "name" in item else (
                item["timestamp"].get("name", "timestamp") if isinstance(
                    item, dict) and "timestamp" in item else item
            )
            for item in obj_cfg.get("attributes", {}).get("static", [])
        ]

        # 2. Số mong đợi: Đọc trực tiếp số row của source_table trong SQLite
        source_df = build_data_frame_by_table_name(
            reader, obj_cfg["source_table"], tables_cfg)
        expected_rows = len(source_df)

        type_objs = [
            obj for obj in objects
            if getattr(obj, "object_type", None) == obj_type or (isinstance(obj, dict) and obj.get("object_type") == obj_type)
        ]

        if len(type_objs) != expected_rows:
            failures.append(
                f"Object type '{obj_type}': Số đối tượng tạo ra ({len(type_objs)}) khác số row trong bảng nguồn ({expected_rows})."
            )

        # 3. Kiểm tra các attribute static trong list có bị null không
        for attr in static_attrs:
            filled_count = 0
            for obj in type_objs:
                if isinstance(obj, ObjectRecord):
                    val = obj.time_stamp if attr.lower() == "timestamp" else obj.attributes.get(attr)
                elif isinstance(obj, dict):
                    val = obj.get(attr)
                else:
                    val = getattr(obj, attr, None)

                if is_valid_value(val):
                    filled_count += 1

            if filled_count < expected_rows:
                missing = expected_rows - filled_count
                failures.append(
                    f"Object type '{obj_type}', thuộc tính tĩnh '{attr}': Chỉ có {filled_count}/{expected_rows} bản ghi có giá trị (thiếu/null {missing} bản ghi)."
                )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC2b: Dynamic Attributes Completeness Ratio

def validate_no_missing_dynamic_object_attributes(
    objects: list[ObjectRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    for obj_cfg in validate_mapping.get("objects", []):

        # 1. Danh sách các thuộc tính động từ mapping
        obj_type = obj_cfg.get("type", "")
        dynamic_attrs = obj_cfg.get("attributes", {}).get("dynamic", [])

        type_objs = [
            obj for obj in objects
            if getattr(obj, "object_type", None) == obj_type or (isinstance(obj, dict) and obj.get("object_type") == obj_type)
        ]

        for dyn in dynamic_attrs:
            attr_name = dyn.get("name")
            source_table = dyn.get("source_table")

            # 2. Số mong đợi: kiểm tra số row thỏa mãn trong sqlite
            source_df = build_data_frame_by_table_name(
                reader, source_table, tables_cfg)
            if dyn.get("where"):
                source_df = reader.apply_where(source_df, dyn["where"])
            expected_changes = len(source_df)

            # 3. Đếm số phần từ change tồn tại trong các object với từng loại thuộc tính động
            actual_changes = 0
            for obj in type_objs:
                for ch in getattr(obj, "changes", []):
                    if (getattr(ch, "ocel_change_field", None) == attr_name
                            and is_valid_value(getattr(ch, "new_value", None))):
                        actual_changes += 1

            if actual_changes < expected_changes:
                missing = expected_changes - actual_changes
                failures.append(
                    f"Object type '{obj_type}', thuộc tính động '{attr_name}': Chỉ có {actual_changes}/{expected_changes} bản ghi thay đổi (thiếu {missing} bản ghi)."
                )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC2c: Event Attributes Completeness Ratio

def validate_no_missing_event_attributes(
    events: list[EventRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    # 1. Danh sách các events
    for ev_cfg in validate_mapping.get("events", []):

        # 2. Số mọng đơi: kiểm tra số row thỏa mãn trong sqlite
        ev_type = ev_cfg.get("type", "")
        source_df = build_data_frame_by_table_name(
            reader, ev_cfg.get("source_table"), tables_cfg)
        if ev_cfg.get("where"):
            source_df = reader.apply_where(source_df, ev_cfg["where"])
        expected_events = len(source_df)

        # 3. Đếm só dòng thu được trong kết quả của mỗi loại sự kiện
        actual_events = [e for e in events if getattr(
            e, "activity", None) == ev_type]

        if len(actual_events) != expected_events:
            failures.append(
                f"Sự kiện '{ev_type}': Số sự kiện tạo ra ({len(actual_events)}) khác số dòng trong bảng nguồn ({expected_events})."
            )

        # Kiểm tra tính toàn vẹn của 3 trường bắt buộc: event_id, activity, time_stamp
        for e in actual_events:
            if not is_valid_value(getattr(e, "event_id", None)):
                failures.append(
                    f"Sự kiện '{ev_type}' bị thiếu hoặc rỗng event_id.")
                break
            if not is_valid_value(getattr(e, "activity", None)):
                failures.append(
                    f"Sự kiện '{ev_type}' bị thiếu hoặc rỗng activity.")
                break
            if getattr(e, "time_stamp", None) is None:
                failures.append(f"Sự kiện '{ev_type}' bị thiếu timestamp.")
                break

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC3a: Static O2O Relationship Completeness Ratio
def validate_no_missing_static_o2o_relationships(
    relationships: list[RelationshipRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
    change_positions: Optional[list[int]] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    if change_positions is None:
        change_positions = get_relationship_type_change_positions(
            relationships)

    # Đếm số lần xuất hiện thực tế của từng bộ (source_type, target_type)
    actual_pair_counts: dict[tuple[str, str], int] = {}
    total_rels = len(relationships)
    for idx, start in enumerate(change_positions):
        end = change_positions[idx + 1] if idx + \
            1 < len(change_positions) else total_rels
        r = relationships[start]
        pair = (getattr(r, "source_object_type", None),
                getattr(r, "target_object_type", None))
        actual_pair_counts[pair] = actual_pair_counts.get(
            pair, 0) + (end - start)

    for rel_cfg in validate_mapping.get("relationships", {}).get("o2o", []):
        source_type = rel_cfg["source"]["object_type"]
        target_type = rel_cfg["target"]["object_type"]
        pair = (source_type, target_type)

        # 1. Số mong đợi: Đếm tổng số dòng trong source_table của các qualifier cho cặp này
        expected_rows = 0
        for q_cfg in rel_cfg.get("qualifiers", []):
            df = build_data_frame_by_table_name(
                reader, q_cfg["source_table"], tables_cfg)
            if q_cfg.get("where"):
                df = reader.apply_where(df, q_cfg["where"])
            expected_rows += len(df)

        # 2. Số thực tế: Số lần xuất hiện của bộ (source_type, target_type) trong relationship records
        actual_rows = actual_pair_counts.get(pair, 0)

        if actual_rows != expected_rows:
            failures.append(
                f"Quan hệ O2O ({source_type} -> {target_type}): Số thực tế ({actual_rows}) khác số mong đợi trong source table ({expected_rows})."
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC3b: Dynamic O2O Relationship Completeness Ratio

def validate_no_missing_dynamic_o2o_relationships(
    relationships: list[RelationshipRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
    change_positions: Optional[list[int]] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    if change_positions is None:
        change_positions = get_relationship_type_change_positions(
            relationships)

    for rel_cfg in validate_mapping.get("relationships", {}).get("o2o", []):
        source_type = rel_cfg["source"]["object_type"]
        target_type = rel_cfg["target"]["object_type"]

        # 1. Số mong đợi: Đếm tần suất xuất hiện của bộ ba (source_type, target_type, timestamp) ở SQLite
        expected_triplets: Counter[tuple[str, str, str]] = Counter()
        for q_cfg in rel_cfg.get("qualifiers", []):
            df = build_data_frame_by_table_name(
                reader, q_cfg["source_table"], tables_cfg)
            if q_cfg.get("where"):
                df = reader.apply_where(df, q_cfg["where"])

            ts_col = q_cfg["timestamp"]["column"]
            for _, row in df.iterrows():
                ts_val = str(row[ts_col])
                expected_triplets[(source_type, target_type, ts_val)] += 1

        # 2. Số thực tế: Đếm tần suất xuất hiện của bộ ba (source_type, target_type, timestamp) trên relationship records
        actual_triplets: Counter[tuple[str, str, str]] = Counter(
            (r.source_object_type, r.target_object_type, str(r.time_stamp))
            for r in relationships
            if getattr(r, "source_object_type", None) == source_type and getattr(r, "target_object_type", None) == target_type
        )

        # 3. So sánh tổng số lần xuất hiện
        exp_total = sum(expected_triplets.values())
        act_total = sum(actual_triplets.values())
        if act_total != exp_total:
            failures.append(
                f"Quan hệ O2O ({source_type} -> {target_type}): Tổng số bộ ba thực tế ({act_total}) khác mong đợi ({exp_total})."
            )

        # So sánh chi tiết từng bộ ba
        for triplet, exp_count in expected_triplets.items():
            act_count = actual_triplets.get(triplet, 0)
            if act_count != exp_count:
                failures.append(
                    f"Bộ ba ({triplet[0]}, {triplet[1]}, timestamp='{triplet[2]}'): Thực tế có {act_count} lần, mong đợi {exp_count} lần."
                )

        # Kiểm tra nếu có bộ ba thừa xuất hiện trong thực tế
        for triplet, act_count in actual_triplets.items():
            if triplet not in expected_triplets:
                failures.append(
                    f"Bộ ba ({triplet[0]}, {triplet[1]}, timestamp='{triplet[2]}') xuất hiện {act_count} lần trong kết quả nhưng không có trong database nguồn."
                )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }

# QC3c: E2O Relationship Completeness Ratio

def validate_no_missing_e2o_relationships(
    events: list[EventRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
) -> dict[str, Any]:

    failures: list[str] = []
    tables_cfg = validate_mapping.get("tables", {})

    # 1. Danh sách các loại sự kiện
    for ev_cfg in validate_mapping.get("events", []):

        #2. Số lượng mong đợi: 
        # số lượng bản ghi thỏa mãn của mỗi loại event trong sqlite * số lượng objects liên quan tới mỗi loại đó
        ev_type = ev_cfg.get("type", "")
        e2o_objs_cfg = ev_cfg.get("objects", [])

        source_df = build_data_frame_by_table_name(
            reader, ev_cfg.get("source_table"), tables_cfg)
        if ev_cfg.get("where"):
            source_df = reader.apply_where(source_df, ev_cfg["where"])

        expected_e2o_for_type = len(source_df) * len(e2o_objs_cfg)

        #3. Số thực tế: đếm số phẩn tử objects trong mỗi event của loại đó 
        # (mỗi ptu trong events bao gồm ttin của event, loại event và objects - danh sách các object liên quan)
        type_events = [e for e in events if getattr(
            e, "activity", None) == ev_type]
        actual_e2o_for_type = sum(len(getattr(e, "objects", []))
                                  for e in type_events)

        if actual_e2o_for_type < expected_e2o_for_type:
            missing = expected_e2o_for_type - actual_e2o_for_type
            failures.append(
                f"Sự kiện '{ev_type}': Chỉ có {actual_e2o_for_type}/{expected_e2o_for_type} liên kết E2O (thiếu {missing} liên kết)."
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC4a: O2O Qualifier Completeness
def validate_no_missing_o2o_qualifiers(
    relationships: list[RelationshipRecord] | Any,
) -> dict[str, Any]:
    failures: list[str] = []
    missing_count = sum(1 for r in relationships if not is_valid_value(
        getattr(r, "qualifier", None)))

    if missing_count > 0:
        failures.append(
            f"Liên kết O2O: Có {missing_count}/{len(relationships)} liên kết bị thiếu/rỗng qualifier.")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# QC4b: E2O Qualifier Completeness
def validate_no_missing_e2o_qualifiers(
    events: list[EventRecord] | Any,
) -> dict[str, Any]:

    failures: list[str] = []
    total_e2o = 0
    missing_count = 0

    for e in events:
        for rel in getattr(e, "objects", []):
            total_e2o += 1
            if not is_valid_value(getattr(rel, "qualifier", None)):
                missing_count += 1

    if missing_count > 0:
        failures.append(
            f"Liên kết E2O: Có {missing_count}/{total_e2o} liên kết bị thiếu/rỗng qualifier.")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


def validate_all_qc(
    objects: list[ObjectRecord] | Any,
    events: list[EventRecord] | Any,
    relationships: list[RelationshipRecord] | Any,
    validate_mapping: dict,
    reader: Optional[SQLiteReader] = None,
) -> dict[str, Any]:

    change_positions = get_relationship_type_change_positions(relationships)

    results = {
        "QC2a": validate_no_missing_static_object_attributes(objects, validate_mapping, reader),
        "QC2b": validate_no_missing_dynamic_object_attributes(objects, validate_mapping, reader),
        "QC2c": validate_no_missing_event_attributes(events, validate_mapping, reader),
        "QC3a": validate_no_missing_static_o2o_relationships(relationships, validate_mapping, reader=reader, change_positions=change_positions),
        "QC3b": validate_no_missing_dynamic_o2o_relationships(relationships, validate_mapping, reader=reader, change_positions=change_positions),
        "QC3c": validate_no_missing_e2o_relationships(events, validate_mapping, reader),
        "QC4a": validate_no_missing_o2o_qualifiers(relationships),
        "QC4b": validate_no_missing_e2o_qualifiers(events),
    }

    results["all_passed"] = all(
        r["passed"] for r in results.values() if isinstance(r, dict) and "passed" in r)
    return results
