from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


def is_null(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip() == ""

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_id(value: Any) -> str:
    if is_null(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return str(value).strip()


def normalize_timestamp(value: Any) -> str | None:
    if is_null(value):
        return None

    timestamp = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(timestamp):
        # Giữ giá trị lỗi để hai timestamp lỗi khác nhau
        # không bị coi là cùng None.
        return str(value).strip()

    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC")

    return timestamp.isoformat()


def normalize_value(
    value: Any,
    value_type: str = "string",
):
    if is_null(value):
        return None

    normalized_type = value_type.lower()

    if normalized_type == "string":
        return str(value).strip()

    if normalized_type == "integer":
        return int(Decimal(str(value)))

    if normalized_type in {
        "decimal",
        "float",
        "number",
    }:
        try:
            return Decimal(str(value)).normalize()
        except InvalidOperation:
            return str(value).strip()

    if normalized_type == "boolean":
        if isinstance(value, bool):
            return value

        normalized = str(value).strip().lower()

        if normalized in {"1", "true", "yes"}:
            return True

        if normalized in {"0", "false", "no"}:
            return False

        return normalized

    if normalized_type in {
        "date",
        "datetime",
        "timestamp",
    }:
        return normalize_timestamp(value)

    return str(value).strip()


def values_equal(
    expected: Any,
    actual: Any,
    value_type: str = "string",
    tolerance: float = 1e-6,
) -> bool:
    expected_value = normalize_value(
        expected,
        value_type,
    )
    actual_value = normalize_value(
        actual,
        value_type,
    )

    if expected_value is None or actual_value is None:
        return expected_value is actual_value

    if value_type.lower() in {
        "decimal",
        "float",
        "number",
    }:
        try:
            return abs(
                float(expected_value)
                - float(actual_value)
            ) <= tolerance
        except (TypeError, ValueError):
            pass

    return expected_value == actual_value