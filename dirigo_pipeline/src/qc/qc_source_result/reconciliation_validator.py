
from collections import Counter
from collections.abc import Callable
from typing import Any

from src.qc.models import (
    ActualProjection,
    ExpectedProjection,
    ObjectAttributeProjection,
    ReconciliationResult,
)
from src.qc.normalization import (
    normalize_id,
    normalize_timestamp,
    normalize_value,
)


def reconcile_objects(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    results = []

    object_types = (
        set(expected.objects)
        | set(actual.objects)
    )

    for object_type in sorted(object_types):
        expected_ids = expected.objects.get(
            object_type,
            [],
        )
        actual_ids = actual.objects.get(
            object_type,
            [],
        )

        expected_counter = Counter(expected_ids)
        actual_counter = Counter(actual_ids)

        missing_counter = (
            expected_counter - actual_counter
        )
        unexpected_counter = (
            actual_counter - expected_counter
        )

        missing_ids = list(
            missing_counter.elements()
        )
        unexpected_ids = list(
            unexpected_counter.elements()
        )

        duplicate_initial_ids = [
            object_id
            for object_id, count
            in actual_counter.items()
            if count > 1
        ]

        passed = (
            not missing_ids
            and not unexpected_ids
            and not duplicate_initial_ids
        )

        results.append(
            ReconciliationResult(
                check_id="REC-01",
                scope=object_type,
                status="PASS" if passed else "FAIL",
                severity="error",
                expected_count=len(expected_ids),
                actual_count=len(actual_ids),
                missing_count=len(missing_ids),
                unexpected_count=len(unexpected_ids),
                mismatch_count=len(
                    duplicate_initial_ids
                ),
                samples=[
                    {
                        "missing_ids": missing_ids[:10],
                        "unexpected_ids": unexpected_ids[:10],
                        "duplicate_initial_ids":
                            duplicate_initial_ids[:10],
                    }
                ],
                message=(
                    "Object IDs match"
                    if passed
                    else "Object completeness or ID reconciliation failed"
                ),
            )
        )

    return results



def _reconcile_counter(
    check_id: str,
    scope: str,
    expected_records: list[Any],
    actual_records: list[Any],
    key_function: Callable[[Any], tuple],
) -> ReconciliationResult:
    expected_counter = Counter(
        key_function(record)
        for record in expected_records
    )

    actual_counter = Counter(
        key_function(record)
        for record in actual_records
    )

    missing = list(
        (
            expected_counter - actual_counter
        ).elements()
    )

    unexpected = list(
        (
            actual_counter - expected_counter
        ).elements()
    )

    passed = not missing and not unexpected

    return ReconciliationResult(
        check_id=check_id,
        scope=scope,
        status="PASS" if passed else "FAIL",
        severity="error",
        expected_count=len(expected_records),
        actual_count=len(actual_records),
        missing_count=len(missing),
        unexpected_count=len(unexpected),
        samples=[{
            "missing": missing[:10],
            "unexpected": unexpected[:10],
        }],
        message=(
            "Expected and actual records match"
            if passed
            else "Missing or unexpected records found"
        ),
    )


def _event_key(event: dict) -> tuple:
    return (
        normalize_id(event["event_id"]),
        str(event["activity"]).strip(),
        normalize_timestamp(event["timestamp"]),
    )


def reconcile_events(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    activities = {
        event["activity"]
        for event in expected.events
    } | {
        event["activity"]
        for event in actual.events
    }

    results = []

    for activity in sorted(
        activities,
        key=lambda value: str(value),
    ):
        expected_records = [
            event
            for event in expected.events
            if event["activity"] == activity
        ]

        actual_records = [
            event
            for event in actual.events
            if event["activity"] == activity
        ]

        results.append(
            _reconcile_counter(
                check_id="REC-05",
                scope=str(activity),
                expected_records=expected_records,
                actual_records=actual_records,
                key_function=_event_key,
            )
        )

    return results


def _e2o_key(relation: dict) -> tuple:
    return (
        normalize_id(relation["event_id"]),
        normalize_id(relation["object_id"]),
        str(relation["qualifier"]).strip(),
    )


def reconcile_e2o(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    def scope_key(relation: dict) -> tuple:
        return (
            relation.get("activity"),
            relation.get("object_type"),
            relation.get("qualifier"),
        )

    scopes = {
        scope_key(relation)
        for relation in expected.e2o
    } | {
        scope_key(relation)
        for relation in actual.e2o
    }

    results = []

    for scope in sorted(
        scopes,
        key=lambda value: str(value),
    ):
        expected_records = [
            relation
            for relation in expected.e2o
            if scope_key(relation) == scope
        ]

        actual_records = [
            relation
            for relation in actual.e2o
            if scope_key(relation) == scope
        ]

        results.append(
            _reconcile_counter(
                check_id="REC-06",
                scope=(
                    f"activity={scope[0]}, "
                    f"object_type={scope[1]}, "
                    f"qualifier={scope[2]}"
                ),
                expected_records=expected_records,
                actual_records=actual_records,
                key_function=_e2o_key,
            )
        )

    return results


def _o2o_key(relation: dict) -> tuple:
    return (
        normalize_id(
            relation["source_object_id"]
        ),
        normalize_id(
            relation["target_object_id"]
        ),
        str(relation["qualifier"]).strip(),
        normalize_timestamp(
            relation.get("timestamp")
        ),
    )


def reconcile_o2o(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    def scope_key(relation: dict) -> tuple:
        return (
            relation.get("source_object_type"),
            relation.get("target_object_type"),
            relation.get("qualifier"),
        )

    scopes = {
        scope_key(relation)
        for relation in expected.o2o
    } | {
        scope_key(relation)
        for relation in actual.o2o
    }

    results = []

    for scope in sorted(
        scopes,
        key=lambda value: str(value),
    ):
        expected_records = [
            relation
            for relation in expected.o2o
            if scope_key(relation) == scope
        ]

        actual_records = [
            relation
            for relation in actual.o2o
            if scope_key(relation) == scope
        ]

        results.append(
            _reconcile_counter(
                check_id="REC-07",
                scope=(
                    f"source={scope[0]}, "
                    f"target={scope[1]}, "
                    f"qualifier={scope[2]}"
                ),
                expected_records=expected_records,
                actual_records=actual_records,
                key_function=_o2o_key,
            )
        )

    return results


def _attribute_key(
    attribute: ObjectAttributeProjection,
) -> tuple:
    return (
        attribute.object_type,
        normalize_id(attribute.object_id),
        attribute.kind,
        attribute.attribute_name,
        (
            normalize_timestamp(attribute.timestamp)
            if attribute.kind == "dynamic"
            else None
        ),
        normalize_value(
            attribute.value,
            attribute.value_type,
        ),
    )


def reconcile_object_attributes(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    def scope_key(
        attribute: ObjectAttributeProjection,
    ) -> tuple:
        return (
            attribute.object_type,
            attribute.kind,
            attribute.attribute_name,
        )

    scopes = {
        scope_key(attribute)
        for attribute in expected.object_attributes
    } | {
        scope_key(attribute)
        for attribute in actual.object_attributes
    }

    results = []

    for scope in sorted(
        scopes,
        key=lambda value: str(value),
    ):
        expected_records = [
            attribute
            for attribute
            in expected.object_attributes
            if scope_key(attribute) == scope
        ]

        actual_records = [
            attribute
            for attribute
            in actual.object_attributes
            if scope_key(attribute) == scope
        ]

        check_id = (
            "REC-03"
            if scope[1] == "static"
            else "REC-04"
        )

        results.append(
            _reconcile_counter(
                check_id=check_id,
                scope=(
                    f"object_type={scope[0]}, "
                    f"kind={scope[1]}, "
                    f"attribute={scope[2]}"
                ),
                expected_records=expected_records,
                actual_records=actual_records,
                key_function=_attribute_key,
            )
        )

    return results


def reconcile_all(
    expected: ExpectedProjection,
    actual: ActualProjection,
) -> list[ReconciliationResult]:
    results = []

    results.extend(
        reconcile_objects(expected, actual)
    )

    results.extend(
        reconcile_object_attributes(
            expected,
            actual,
        )
    )

    results.extend(
        reconcile_events(expected, actual)
    )

    results.extend(
        reconcile_e2o(expected, actual)
    )

    results.extend(
        reconcile_o2o(expected, actual)
    )

    return results