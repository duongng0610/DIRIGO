from src.ir.models import RelationshipRecord
from typing import Any
import pandas as pd


def is_valid_value(val: Any) -> bool:
    if val is None or pd.isna(val):
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return True

# Duyệt toàn bộ relationships truyền vào và tạo 1 danh sách lưu trữ các vị trí 
# có sự thay đổi của source type và target type so với các bản ghi trước đó

def get_relationship_type_change_positions(
    relationships: list[RelationshipRecord] | Any
) -> list[int]:

    if not relationships:
        return []

    change_positions: list[int] = [0]
    for i in range(1, len(relationships)):
        prev_pair = (
            getattr(relationships[i - 1], "source_object_type", None),
            getattr(relationships[i - 1], "target_object_type", None),
        )
        curr_pair = (
            getattr(relationships[i], "source_object_type", None),
            getattr(relationships[i], "target_object_type", None),
        )
        if prev_pair != curr_pair:
            change_positions.append(i)

    return change_positions
