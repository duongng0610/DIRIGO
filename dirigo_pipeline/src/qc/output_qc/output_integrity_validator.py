from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _blank_mask(series: pd.Series) -> pd.Series:
    """True nếu giá trị null hoặc chuỗi rỗng."""

    return (
        series.isna()
        | series.fillna("").astype(str).str.strip().eq("")
    )


def validate_dirigo_output(
    output_directory: str | Path,
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """
    Kiểm tra toàn vẹn CSV Dirigo sau khi writer hoàn tất.

    Không so sánh source ở đây; việc đó thuộc REC-QC.
    """

    output_directory = Path(output_directory)
    issues: list[dict[str, Any]] = []

    def add_issue(
        code: str,
        message: str,
        count: int = 0,
    ) -> None:
        issues.append(
            {
                "code": code,
                "message": message,
                "count": count,
            }
        )

    object_ids: set[str] = set()

    # Kiểm tra từng object CSV.
    for object_mapping in mapping["objects"]:
        object_type = object_mapping["type"]
        object_path = (
            output_directory / f"OCEL_{object_type}.csv"
        )

        if not object_path.exists():
            add_issue(
                "OUT-OBJECT-FILE-MISSING",
                f"Missing object file: {object_path.name}",
            )
            continue

        object_df = pd.read_csv(object_path)

        required_columns = {
            "Object_id",
            "Timestamp",
            "Ocel_changed_field",
        }

        missing_columns = required_columns - set(
            object_df.columns
        )

        if missing_columns:
            add_issue(
                "OUT-OBJECT-COLUMNS-MISSING",
                f"{object_path.name}: missing "
                f"{sorted(missing_columns)}",
            )
            continue

        missing_ids = int(
            _blank_mask(object_df["Object_id"]).sum()
        )

        if missing_ids:
            add_issue(
                "OUT-OBJECT-ID-MISSING",
                f"{object_path.name} contains empty Object_id",
                missing_ids,
            )

        change_field = (
            object_df["Ocel_changed_field"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        initial_rows = object_df[change_field.eq("")]

        duplicate_initial_ids = int(
            initial_rows["Object_id"]
            .astype(str)
            .duplicated()
            .sum()
        )

        if duplicate_initial_ids:
            add_issue(
                "OUT-DUPLICATE-INITIAL-OBJECT",
                f"{object_path.name} has duplicate initial objects",
                duplicate_initial_ids,
            )

        object_ids.update(
            object_df["Object_id"]
            .dropna()
            .astype(str)
            .tolist()
        )

    events_path = output_directory / "OCEL_Events.csv"
    e2o_path = output_directory / "OCEL_E2O.csv"
    o2o_path = output_directory / "OCEL_O2O.csv"

    if not events_path.exists():
        add_issue(
            "OUT-EVENT-FILE-MISSING",
            "OCEL_Events.csv does not exist",
        )
        event_ids: set[str] = set()

    else:
        events_df = pd.read_csv(events_path)

        expected = {"Event_id", "Timestamp", "Activity"}
        missing = expected - set(events_df.columns)

        if missing:
            add_issue(
                "OUT-EVENT-COLUMNS-MISSING",
                f"OCEL_Events.csv missing {sorted(missing)}",
            )
            event_ids = set()

        else:
            duplicate_events = int(
                events_df["Event_id"]
                .astype(str)
                .duplicated()
                .sum()
            )

            if duplicate_events:
                add_issue(
                    "OUT-DUPLICATE-EVENT-ID",
                    "OCEL_Events.csv has duplicate Event_id",
                    duplicate_events,
                )

            invalid_timestamps = int(
                pd.to_datetime(
                    events_df["Timestamp"],
                    format="mixed",
                    errors="coerce",
                )
                .isna()
                .sum()
            )

            if invalid_timestamps:
                add_issue(
                    "OUT-INVALID-EVENT-TIMESTAMP",
                    "Events contain invalid timestamps",
                    invalid_timestamps,
                )

            event_ids = set(
                events_df["Event_id"]
                .dropna()
                .astype(str)
            )

    if not e2o_path.exists():
        add_issue(
            "OUT-E2O-FILE-MISSING",
            "OCEL_E2O.csv does not exist",
        )

    else:
        e2o_df = pd.read_csv(e2o_path)

        required = {
            "Event_id",
            "Object_id",
            "E2O_qualifier",
        }

        missing = required - set(e2o_df.columns)

        if missing:
            add_issue(
                "OUT-E2O-COLUMNS-MISSING",
                f"OCEL_E2O.csv missing {sorted(missing)}",
            )

        else:
            missing_events = int(
                (
                    ~e2o_df["Event_id"]
                    .astype(str)
                    .isin(event_ids)
                ).sum()
            )

            missing_objects = int((
                ~e2o_df["Object_id"]
                .astype(str)
                .isin(object_ids)
            ).sum())

            blank_qualifiers = int(
                _blank_mask(e2o_df["E2O_qualifier"]).sum()
            )

            if missing_events:
                add_issue(
                    "OUT-E2O-UNKNOWN-EVENT",
                    "E2O references unknown events",
                    missing_events,
                )

            if missing_objects:
                add_issue(
                    "OUT-E2O-UNKNOWN-OBJECT",
                    "E2O references unknown objects",
                    missing_objects,
                )

            if blank_qualifiers:
                add_issue(
                    "OUT-E2O-EMPTY-QUALIFIER",
                    "E2O contains empty qualifiers",
                    blank_qualifiers,
                )

    if not o2o_path.exists():
        add_issue(
            "OUT-O2O-FILE-MISSING",
            "OCEL_O2O.csv does not exist",
        )

    else:
        o2o_df = pd.read_csv(o2o_path)

        required = {
            "Source_object_id",
            "Target_object_id",
            "O2O_qualifier",
            "Timestamp",
        }

        missing = required - set(o2o_df.columns)

        if missing:
            add_issue(
                "OUT-O2O-COLUMNS-MISSING",
                f"OCEL_O2O.csv missing {sorted(missing)}",
            )

        else:
            unknown_sources = int((
                ~o2o_df["Source_object_id"]
                .astype(str)
                .isin(object_ids)
            ).sum())

            unknown_targets = int((
                ~o2o_df["Target_object_id"]
                .astype(str)
                .isin(object_ids)
            ).sum())

            blank_qualifiers = int(
                _blank_mask(o2o_df["O2O_qualifier"]).sum()
            )

            if unknown_sources:
                add_issue(
                    "OUT-O2O-UNKNOWN-SOURCE",
                    "O2O contains unknown source objects",
                    unknown_sources,
                )

            if unknown_targets:
                add_issue(
                    "OUT-O2O-UNKNOWN-TARGET",
                    "O2O contains unknown target objects",
                    unknown_targets,
                )

            if blank_qualifiers:
                add_issue(
                    "OUT-O2O-EMPTY-QUALIFIER",
                    "O2O contains empty qualifiers",
                    blank_qualifiers,
                )

            dynamic_qualifiers = {
                qualifier["qualifier"]
                for relationship in (
                    mapping
                    .get("relationships", {})
                    .get("o2o", [])
                )
                if relationship.get("mode") == "dynamic"
                for qualifier in relationship.get(
                    "qualifiers",
                    [],
                )
            }

            dynamic_rows = o2o_df[
                o2o_df["O2O_qualifier"].isin(
                    dynamic_qualifiers
                )
            ]

            invalid_dynamic_timestamps = int(
                pd.to_datetime(
                    dynamic_rows["Timestamp"],
                    errors="coerce",
                )
                .isna()
                .sum()
            )

            if invalid_dynamic_timestamps:
                add_issue(
                    "OUT-O2O-DYNAMIC-TIMESTAMP-INVALID",
                    "Dynamic O2O contains invalid timestamp",
                    invalid_dynamic_timestamps,
                )

    return {
        "status": "PASS" if not issues else "FAIL",
        "issue_count": len(issues),
        "issues": issues,
    }