
"""Triển khai QC2a-QC4b bằng phép so sánh multiset expected/actual.

Mỗi QC chủ động chọn các trường tạo identity của record. Ví dụ QC3 chỉ kiểm
tra khả năng biểu diễn quan hệ, còn QC4 thêm qualifier. Tách hai nhóm này giúp
báo cáo đúng tiêu chí bị mất thay vì gộp mọi sai khác thành một lỗi chung.
"""

from typing import Any


from src.qc.projection.normalization import (
    normalize_id,
    normalize_timestamp,
    normalize_value,
)


from src.qc.paper_qc.context import PaperQCContext
from src.qc.paper_qc.helper import compare_records, get_o2o_mode, build_o2o_mode_index

#QC2a — Static object attributes
def check_qc2a(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC2a: bảo toàn thuộc tính tĩnh theo object ID và attribute name.

    Record key gồm ``object_type, object_id, attribute_name, value``.
    """
    expected_records = []
    actual_records = []

    for attribute in context.expected.object_attributes:
        if attribute.kind != "static":
            continue

        expected_records.append((
            attribute.object_type,
            normalize_id(attribute.object_id),
            attribute.attribute_name,
            normalize_value(
                attribute.value,
                attribute.value_type,
            ),
        ))

    for attribute in context.actual.object_attributes:
        if attribute.kind != "static":
            continue

        actual_records.append((
            attribute.object_type,
            normalize_id(attribute.object_id),
            attribute.attribute_name,
            normalize_value(
                attribute.value,
                attribute.value_type,
            ),
        ))

    return compare_records(
        "QC2a",
        expected_records,
        actual_records,
    )

#QC2b — Dynamic object attributes
def check_qc2b(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC2b: bảo toàn lịch sử thuộc tính động.

    Timestamp thuộc identity vì hai lần đổi cùng giá trị tại hai thời điểm là
    hai change records khác nhau.
    """
    expected_records = []
    actual_records = []

    for attribute in context.expected.object_attributes:
        if attribute.kind != "dynamic":
            continue

        expected_records.append((
            attribute.object_type,
            normalize_id(attribute.object_id),
            attribute.attribute_name,
            normalize_timestamp(attribute.timestamp),
            normalize_value(
                attribute.value,
                attribute.value_type,
            ),
        ))

    for attribute in context.actual.object_attributes:
        if attribute.kind != "dynamic":
            continue

        actual_records.append((
            attribute.object_type,
            normalize_id(attribute.object_id),
            attribute.attribute_name,
            normalize_timestamp(attribute.timestamp),
            normalize_value(
                attribute.value,
                attribute.value_type,
            ),
        ))

    return compare_records(
        "QC2b",
        expected_records,
        actual_records,
    )

#QC2c — Event attributes
def check_qc2c(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC2c: bảo toàn event core fields hiện được runtime hỗ trợ.

    Record key hiện gồm ``event_id, activity, timestamp``. Custom event
    attributes chưa được exporter lưu và MAP-QC đang từ chối mapping có loại
    thuộc tính đó.
    """
    expected_records = []
    actual_records = []

    for event in context.expected.events:
        expected_records.append((
            normalize_id(event["event_id"]),
            str(event["activity"]).strip(),
            normalize_timestamp(event["timestamp"]),
        ))

    for event in context.actual.events:
        actual_records.append((
            normalize_id(event["event_id"]),
            str(event["activity"]).strip(),
            normalize_timestamp(event["timestamp"]),
        ))

    return compare_records(
        "QC2c",
        expected_records,
        actual_records,
    )

def check_qc3a(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC3a: bảo toàn các cặp O2O tĩnh, chưa xét qualifier.

    Qualifier được kiểm tra riêng ở QC4a; timestamp không thuộc quan hệ tĩnh.
    """
    mode_index = build_o2o_mode_index(
        context.mapping
    )

    expected_records = []
    actual_records = []

    for relation in context.expected.o2o:
        if get_o2o_mode(
            relation,
            mode_index,
        ) != "static":
            continue

        expected_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
        ))

    for relation in context.actual.o2o:
        if get_o2o_mode(
            relation,
            mode_index,
        ) != "static":
            continue

        actual_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
        ))

    return compare_records(
        "QC3a",
        expected_records,
        actual_records,
    )

def check_qc3b(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC3b: bảo toàn lịch sử các cặp O2O động, chưa xét qualifier.

    Record key gồm source/target type, source/target ID và timestamp. Nhờ có
    timestamp, nhiều trạng thái của cùng một cặp object không bị gộp lại.
    """
    mode_index = build_o2o_mode_index(
        context.mapping
    )

    expected_records = []
    actual_records = []

    for relation in context.expected.o2o:
        if get_o2o_mode(
            relation,
            mode_index,
        ) != "dynamic":
            continue

        expected_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
            normalize_timestamp(
                relation["timestamp"]
            ),
        ))

    for relation in context.actual.o2o:
        if get_o2o_mode(
            relation,
            mode_index,
        ) != "dynamic":
            continue

        actual_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
            normalize_timestamp(
                relation["timestamp"]
            ),
        ))

    return compare_records(
        "QC3b",
        expected_records,
        actual_records,
    )

def check_qc3c(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC3c: bảo toàn liên kết event-object, chưa xét E2O qualifier."""
    expected_records = []
    actual_records = []

    for relation in context.expected.e2o:
        expected_records.append((
            str(relation["activity"]).strip(),
            normalize_id(relation["event_id"]),
            relation["object_type"],
            normalize_id(relation["object_id"]),
        ))

    for relation in context.actual.e2o:
        actual_records.append((
            str(relation["activity"]).strip(),
            normalize_id(relation["event_id"]),
            relation["object_type"],
            normalize_id(relation["object_id"]),
        ))

    return compare_records(
        "QC3c",
        expected_records,
        actual_records,
    )

def check_qc4a(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC4a: bảo toàn O2O qualifier cùng cặp object và timestamp."""
    expected_records = []
    actual_records = []

    for relation in context.expected.o2o:
        expected_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
            str(
                relation.get("qualifier") or ""
            ).strip(),
            normalize_timestamp(
                relation.get("timestamp")
            ),
        ))

    for relation in context.actual.o2o:
        actual_records.append((
            relation["source_object_type"],
            normalize_id(
                relation["source_object_id"]
            ),
            relation["target_object_type"],
            normalize_id(
                relation["target_object_id"]
            ),
            str(
                relation.get("qualifier") or ""
            ).strip(),
            normalize_timestamp(
                relation.get("timestamp")
            ),
        ))

    return compare_records(
        "QC4a",
        expected_records,
        actual_records,
    )

def check_qc4b(
    context: PaperQCContext,
) -> dict[str, Any]:
    """QC4b: bảo toàn E2O qualifier cho từng event-object relation."""
    expected_records = []
    actual_records = []

    for relation in context.expected.e2o:
        expected_records.append((
            str(relation["activity"]).strip(),
            normalize_id(relation["event_id"]),
            relation["object_type"],
            normalize_id(relation["object_id"]),
            str(
                relation.get("qualifier") or ""
            ).strip(),
        ))

    for relation in context.actual.e2o:
        actual_records.append((
            str(relation["activity"]).strip(),
            normalize_id(relation["event_id"]),
            relation["object_type"],
            normalize_id(relation["object_id"]),
            str(
                relation.get("qualifier") or ""
            ).strip(),
        ))

    return compare_records(
        "QC4b",
        expected_records,
        actual_records,
    )

def run_all_paper_qc(
    context: PaperQCContext,
) -> dict[str, Any]:
    """Chạy tám QC và tổng hợp trạng thái chung.

    ``NOT_APPLICABLE`` không làm toàn bộ pipeline fail vì nó có nghĩa dataset
    hoặc mapping không chứa loại cấu trúc mà tiêu chí đó đánh giá.
    """
    results = {
        "QC2a": check_qc2a(context),
        "QC2b": check_qc2b(context),
        "QC2c": check_qc2c(context),
        "QC3a": check_qc3a(context),
        "QC3b": check_qc3b(context),
        "QC3c": check_qc3c(context),
        "QC4a": check_qc4a(context),
        "QC4b": check_qc4b(context),
    }

    all_passed = all(
        result["status"] in {
            "PASS",
            "NOT_APPLICABLE",
        }
        for result in results.values()
    )

    return {
        "all_passed": all_passed,
        "results": results,
    }
