"""Context bất biến về mặt tham chiếu được truyền cho mọi Paper QC."""

from src.qc.projection.models import (
    ActualProjection,
    ExpectedProjection,
)
from dataclasses import dataclass
from typing import Any

@dataclass
class PaperQCContext:
    """Gom mapping, expected và actual để các QC dùng cùng một input."""

    mapping: dict[str, Any]
    expected: ExpectedProjection
    actual: ActualProjection
