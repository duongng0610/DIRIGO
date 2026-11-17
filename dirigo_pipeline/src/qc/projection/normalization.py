"""Chuẩn hóa ID, timestamp và value trước khi so sánh QC.

CSV và SQLite có thể biểu diễn cùng giá trị theo kiểu khác nhau, ví dụ ``1``
và ``1.0`` hoặc date-only và ISO datetime. Normalization loại khác biệt biểu
diễn nhưng vẫn giữ khác biệt nghiệp vụ thực sự.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


def is_null(value: Any) -> bool:
    """Nhận diện None, pandas NA/NaN và chuỗi rỗng như giá trị null."""
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip() == ""

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_id(value: Any) -> str:
    """Đưa ID về chuỗi ổn định; ID null trở thành chuỗi rỗng để QC fail."""
    if is_null(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return str(value).strip()


def normalize_timestamp(value: Any) -> str | None:
    """Đưa timestamp parse được về ISO-8601, timezone về UTC.

    Giá trị không parse được được giữ dưới dạng chuỗi thay vì đổi thành None,
    nhờ vậy hai timestamp lỗi khác nhau không bị xem là cùng một giá trị.
    """
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
    """Chuẩn hóa value theo logical type đã khai báo trong mapping."""
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
    """So sánh hai value đã chuẩn hóa, hỗ trợ tolerance cho số thực."""
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
