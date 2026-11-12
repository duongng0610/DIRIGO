from dataclasses import dataclass
from typing import Any
from datetime import datetime


@dataclass
class ObjectChangeRecord:
    time_stamp: datetime
    ocel_change_field: str
    new_value: Any


@dataclass
class ObjectRecord:
    object_id: str
    object_type: str
    attributes: dict[str, Any]
    time_stamp: datetime
    changes: list[ObjectChangeRecord]


@dataclass
class EventToObjectRecord:
    object_id: str
    qualifier: str


@dataclass
class EventRecord:
    event_id: str
    activity: str
    time_stamp: datetime
    objects: list[EventToObjectRecord]


@dataclass
class RelationshipRecord:
    qualifier: str
    source_object_id: str
    source_object_type: str
    target_object_id: str
    target_object_type: str
    time_stamp: datetime
