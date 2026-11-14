
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