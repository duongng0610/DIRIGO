from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ReconciliationResult:
    check_id: str
    scope: str
    status: str
    severity: str

    expected_count: int | None = None
    actual_count: int | None = None

    missing_count: int = 0
    unexpected_count: int = 0
    mismatch_count: int = 0

    samples: list[dict[str, Any]] = field(
        default_factory=list
    )
    message: str = ""


@dataclass
class ObjectAttributeProjection:
    object_type: str
    object_id: str
    attribute_name: str
    value: Any
    value_type: str
    kind: Literal["static", "dynamic"]
    timestamp: Any | None = None


@dataclass
class ExpectedProjection:
    objects: dict[str, list[str]] = field(
        default_factory=dict
    )

    object_attributes: list[
        ObjectAttributeProjection
    ] = field(default_factory=list)

    events: list[dict[str, Any]] = field(
        default_factory=list
    )

    e2o: list[dict[str, Any]] = field(
        default_factory=list
    )

    o2o: list[dict[str, Any]] = field(
        default_factory=list
    )

    filter_audits: list[dict[str, Any]] = field(
        default_factory=list
    )


@dataclass
class ActualProjection:
    objects: dict[str, list[str]] = field(
        default_factory=dict
    )

    object_attributes: list[
        ObjectAttributeProjection
    ] = field(default_factory=list)

    events: list[dict[str, Any]] = field(
        default_factory=list
    )

    e2o: list[dict[str, Any]] = field(
        default_factory=list
    )

    o2o: list[dict[str, Any]] = field(
        default_factory=list
    )