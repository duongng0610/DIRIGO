from src.qc.projection.models import (
    ActualProjection,
    ExpectedProjection,
)
from dataclasses import dataclass
from typing import Any

@dataclass
class PaperQCContext:
    mapping: dict[str, Any]
    expected: ExpectedProjection
    actual: ActualProjection