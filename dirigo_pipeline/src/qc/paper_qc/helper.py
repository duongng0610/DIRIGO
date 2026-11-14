from collections import Counter
from typing import Any


def compare_records(
    qc_id: str,
    expected_records: list[tuple],
    actual_records: list[tuple],
) -> dict[str, Any]:
    """
    So sánh expected và actual.

    Dùng Counter thay vì set để phát hiện cả trường hợp
    một record bị sinh thừa nhiều lần.
    """

    expected_counter = Counter(expected_records)
    actual_counter = Counter(actual_records)

    missing_counter = (
        expected_counter - actual_counter
    )

    unexpected_counter = (
        actual_counter - expected_counter
    )

    matched_counter = (
        expected_counter & actual_counter
    )

    expected_count = sum(
        expected_counter.values()
    )
    actual_count = sum(
        actual_counter.values()
    )
    matched_count = sum(
        matched_counter.values()
    )

    missing_count = sum(
        missing_counter.values()
    )
    unexpected_count = sum(
        unexpected_counter.values()
    )

    if expected_count == 0 and actual_count == 0:
        status = "NOT_APPLICABLE"
        completeness_ratio = None

    else:
        status = (
            "PASS"
            if missing_count == 0
            and unexpected_count == 0
            else "FAIL"
        )

        completeness_ratio = (
            matched_count / expected_count
            if expected_count > 0
            else 0.0
        )

    return {
        "qc_id": qc_id,
        "status": status,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "matched_count": matched_count,
        "missing_count": missing_count,
        "unexpected_count": unexpected_count,
        "completeness_ratio": completeness_ratio,
        "missing_samples": list(
            missing_counter.elements()
        )[:10],
        "unexpected_samples": list(
            unexpected_counter.elements()
        )[:10],
    }
def build_o2o_mode_index(
    mapping: dict[str, Any],
) -> dict[tuple, str]:
    """
    Ví dụ key:
        employee, department, assignment_started

    Value:
        dynamic
    """

    result = {}

    relationships = (
        mapping
        .get("relationships", {})
        .get("o2o", [])
    )

    for relationship in relationships:
        source_type = (
            relationship["source"]["object_type"]
        )

        target_type = (
            relationship["target"]["object_type"]
        )

        mode = relationship["mode"]

        for qualifier_mapping in relationship.get(
            "qualifiers",
            [],
        ):
            qualifier = qualifier_mapping["qualifier"]

            result[(
                source_type,
                target_type,
                qualifier,
            )] = mode

    return result


def get_o2o_mode(
    relation: dict[str, Any],
    mode_index: dict[tuple, str],
) -> str | None:
    key = (
        relation.get("source_object_type"),
        relation.get("target_object_type"),
        relation.get("qualifier"),
    )

    return mode_index.get(key)