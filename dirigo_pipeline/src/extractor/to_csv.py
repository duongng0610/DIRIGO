import csv
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.ir import EventRecord, ObjectRecord, RelationshipRecord


BASE_COLUMNS = ["Object_id", "Timestamp", "Ocel_changed_field"]
EVENT_COLUMNS = ["Event_id", "Timestamp", "Activity"]
E2O_COLUMNS = ["Event_id", "Object_id", "E2O_qualifier"]
O2O_COLUMNS = ["Source_object_id",
               "Target_object_id", "O2O_qualifier", "Timestamp"]


def _format_value(value: Any) -> Any:
    """Return a value in the text form expected by the Dirigo CSV files."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def _get_attribute_columns(objects: List[ObjectRecord]) -> List[str]:
    columns: List[str] = []
    for obj in objects:
        for name in obj.attributes:
            if name not in columns:
                columns.append(name)
        for change in obj.changes:
            if change.ocel_change_field not in columns:
                columns.append(change.ocel_change_field)
    return columns


def _initial_row(obj: ObjectRecord, fieldnames: List[str]) -> Dict[str, Any]:
    row = {field: "" for field in fieldnames}
    row["Object_id"] = obj.object_id
    row["Timestamp"] = _format_value(obj.time_stamp)
    for name, value in obj.attributes.items():
        row[name] = _format_value(value)
    return row


def _change_rows(obj: ObjectRecord, fieldnames: List[str]) -> Iterable[Dict[str, Any]]:
    for change in obj.changes:
        row = {field: "" for field in fieldnames}
        row["Object_id"] = obj.object_id
        row["Timestamp"] = _format_value(change.time_stamp)
        row["Ocel_changed_field"] = change.ocel_change_field
        row[change.ocel_change_field] = _format_value(change.new_value)
        yield row


def convert_objects(objects: List[ObjectRecord], output_dir: Path) -> List[Path]:
    """Convert IR ObjectRecords to Dirigo object CSV files.

    One file is written per object type, for example ``OCEL_Employee.csv``.
    Each object contributes one initial row containing static attributes, and
    each ObjectChangeRecord contributes one history row with only the changed
    attribute populated.
    """
    objects_by_type: Dict[str, List[ObjectRecord]] = {}
    for obj in objects:
        objects_by_type.setdefault(obj.object_type, []).append(obj)

    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []

    for object_type, typed_objects in objects_by_type.items():
        fieldnames = BASE_COLUMNS + _get_attribute_columns(typed_objects)
        output_path = output_dir / f"OCEL_{object_type}.csv"

        with output_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for obj in typed_objects:
                writer.writerow(_initial_row(obj, fieldnames))
                writer.writerows(_change_rows(obj, fieldnames))

        written_files.append(output_path)

    return written_files


def convert_events(events: Iterable[EventRecord], output_dir: Path) -> List[Path]:
    """Convert event IR records to the two Dirigo event CSV files.

    The Dirigo format stores event attributes and event-to-object relations in
    separate files:

    * ``OCEL_Events.csv`` with ``Event_id,Timestamp,Activity``;
    * ``OCEL_E2O.csv`` with ``Event_id,Object_id,E2O_qualifier``.

    Each relation is written once, in the same order as its parent event's
    ``objects`` collection. Events without related objects are still retained
    in ``OCEL_Events.csv``.
    """
    event_records = list(events)
    output_dir.mkdir(parents=True, exist_ok=True)

    events_path = output_dir / "OCEL_Events.csv"
    e2o_path = output_dir / "OCEL_E2O.csv"

    with events_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        for event in event_records:
            writer.writerow({
                "Event_id": event.event_id,
                "Timestamp": _format_value(event.time_stamp),
                "Activity": event.activity,
            })

    with e2o_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=E2O_COLUMNS)
        writer.writeheader()
        for event in event_records:
            for relation in event.objects or []:
                writer.writerow({
                    "Event_id": event.event_id,
                    "Object_id": relation.object_id,
                    "E2O_qualifier": relation.qualifier,
                })

    return [events_path, e2o_path]


def convert_relationships(relationships: Iterable[RelationshipRecord], output_dir: Path) -> Path:
    relationship_records = list(relationships)
    output_dir.mkdir(parents=True, exist_ok=True)

    relationship_path = output_dir / "OCEL_O2O.csv"

    with relationship_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=O2O_COLUMNS)
        writer.writeheader()
        for relationship in relationship_records:
            writer.writerow({
                "Source_object_id": relationship.source_object_id,
                "Target_object_id": relationship.target_object_id,
                "O2O_qualifier": relationship.qualifier,
                "Timestamp": _format_value(relationship.time_stamp),
            })

    return relationship_path
