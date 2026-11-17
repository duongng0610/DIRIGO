"""Intermediate Representation giữa mapping/builders và CSV extractor.

IR giữ pipeline độc lập với định dạng CSV: builders chỉ tạo record có ý nghĩa
nghiệp vụ, còn extractor quyết định tên cột và cách trải record thành dòng.
"""

from dataclasses import dataclass
from typing import Any
from datetime import datetime


@dataclass
class ObjectChangeRecord:
    """Một lần thay đổi giá trị của đúng một thuộc tính object."""

    time_stamp: datetime
    ocel_change_field: str
    new_value: Any


@dataclass
class ObjectRecord:
    """Object ban đầu cùng toàn bộ lịch sử thuộc tính động của nó.

    ``attributes`` chỉ chứa trạng thái tĩnh/ban đầu. ``changes`` chứa các
    lần thay đổi và sẽ được extractor ghi thành những dòng riêng có
    ``Ocel_changed_field``.
    """

    object_id: str
    object_type: str
    attributes: dict[str, Any]
    time_stamp: datetime
    changes: list[ObjectChangeRecord]


@dataclass
class EventToObjectRecord:
    """Vai trò của một object trong một event, dùng để xuất E2O."""

    object_id: str
    qualifier: str


@dataclass
class EventRecord:
    """Một event cùng danh sách object tham gia và qualifier tương ứng."""

    event_id: str
    activity: str
    time_stamp: datetime
    objects: list[EventToObjectRecord]


@dataclass
class RelationshipRecord:
    """Một trạng thái/lần thay đổi của quan hệ O2O.

    Source/target type được giữ trong IR để QC có thể phân loại quan hệ;
    Dirigo CSV hiện chỉ xuất hai ID, qualifier và timestamp.
    """

    qualifier: str
    source_object_id: str
    source_object_type: str
    target_object_id: str
    target_object_type: str
    time_stamp: datetime
