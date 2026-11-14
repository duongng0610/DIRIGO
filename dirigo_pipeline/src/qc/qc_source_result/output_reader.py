from pathlib import Path
from typing import Any

import pandas as pd

from src.qc.qc_source_result.models import (
    ActualProjection,
    ObjectAttributeProjection,
)


def _read_csv(
    path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=sorted(required_columns)
        )

    dataframe = pd.read_csv(
        path,
        encoding="utf-8-sig",
        keep_default_na=False,
        dtype=object,
    )

    missing_columns = (
        required_columns - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Output '{path.name}' missing columns: "
            f"{sorted(missing_columns)}"
        )

    return dataframe


def read_actual_projection(
    output_dir: Path | str,
    mapping: dict[str, Any],
) -> ActualProjection:
    output_dir = Path(output_dir)
    projection = ActualProjection()

    read_actual_objects_and_attributes(
        output_dir,
        mapping,
        projection,
    )

    read_actual_events(
        output_dir,
        projection,
    )

    read_actual_e2o(
        output_dir,
        projection,
    )

    read_actual_o2o(
        output_dir,
        projection,
    )

    return projection


def read_actual_objects_and_attributes(
    output_dir: Path,
    mapping: dict[str, Any],
    projection: ActualProjection,
) -> None:
    for object_mapping in mapping.get("objects", []):
        object_type = object_mapping["type"]

        output_df = _read_csv(
            output_dir / f"OCEL_{object_type}.csv",
            {
                "Object_id",
                "Timestamp",
                "Ocel_changed_field",
            },
        )

        changed_field = (
            output_df["Ocel_changed_field"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        initial_rows = output_df[
            changed_field.eq("")
        ]

        dynamic_rows = output_df[
            changed_field.ne("")
        ]

        projection.objects[object_type] = [
            str(value).strip()
            for value in initial_rows["Object_id"]
        ]

        static_mappings = (
            object_mapping
            .get("attributes", {})
            .get("static", [])
        )

        for attribute_mapping in static_mappings:
            if "timestamp" in attribute_mapping:
                continue

            attribute_name = attribute_mapping["name"]

            for _, row in initial_rows.iterrows():
                projection.object_attributes.append(
                    ObjectAttributeProjection(
                        object_type=object_type,
                        object_id=str(
                            row["Object_id"]
                        ).strip(),
                        attribute_name=attribute_name,
                        value=row.get(attribute_name),
                        value_type=attribute_mapping.get(
                            "type",
                            "string",
                        ),
                        kind="static",
                    )
                )

        dynamic_configs = {
            config["name"]: config
            for config in (
                object_mapping
                .get("attributes", {})
                .get("dynamic", [])
            )
        }

        for _, row in dynamic_rows.iterrows():
            attribute_name = str(
                row["Ocel_changed_field"]
            ).strip()

            config = dynamic_configs.get(
                attribute_name
            )

            projection.object_attributes.append(
                ObjectAttributeProjection(
                    object_type=object_type,
                    object_id=str(
                        row["Object_id"]
                    ).strip(),
                    attribute_name=attribute_name,
                    value=row.get(attribute_name),
                    value_type=(
                        config["value"].get(
                            "type",
                            "string",
                        )
                        if config
                        else "string"
                    ),
                    kind="dynamic",
                    timestamp=row["Timestamp"],
                )
            )


def read_actual_events(
    output_dir: Path,
    projection: ActualProjection,
) -> None:
    event_df = _read_csv(
        output_dir / "OCEL_Events.csv",
        {
            "Event_id",
            "Timestamp",
            "Activity",
        },
    )

    for _, row in event_df.iterrows():
        projection.events.append({
            "event_id": str(
                row["Event_id"]
            ).strip(),
            "activity": str(
                row["Activity"]
            ).strip(),
            "timestamp": row["Timestamp"],
        })


def read_actual_e2o(
    output_dir: Path,
    projection: ActualProjection,
) -> None:
    e2o_df = _read_csv(
        output_dir / "OCEL_E2O.csv",
        {
            "Event_id",
            "Object_id",
            "E2O_qualifier",
        },
    )

    activity_by_event = {
        event["event_id"]: event["activity"]
        for event in projection.events
    }

    object_type_by_id = {
        object_id: object_type
        for object_type, object_ids
        in projection.objects.items()
        for object_id in object_ids
    }

    for _, row in e2o_df.iterrows():
        event_id = str(row["Event_id"]).strip()
        object_id = str(row["Object_id"]).strip()

        projection.e2o.append({
            "event_id": event_id,
            "activity": activity_by_event.get(
                event_id
            ),
            "object_id": object_id,
            "object_type": object_type_by_id.get(
                object_id
            ),
            "qualifier": str(
                row["E2O_qualifier"]
            ).strip(),
        })


def read_actual_o2o(
    output_dir: Path,
    projection: ActualProjection,
) -> None:
    o2o_df = _read_csv(
        output_dir / "OCEL_O2O.csv",
        {
            "Source_object_id",
            "Target_object_id",
            "O2O_qualifier",
            "Timestamp",
        },
    )

    object_type_by_id = {
        object_id: object_type
        for object_type, object_ids
        in projection.objects.items()
        for object_id in object_ids
    }

    for _, row in o2o_df.iterrows():
        source_id = str(
            row["Source_object_id"]
        ).strip()

        target_id = str(
            row["Target_object_id"]
        ).strip()

        projection.o2o.append({
            "source_object_id": source_id,
            "source_object_type":
                object_type_by_id.get(source_id),
            "target_object_id": target_id,
            "target_object_type":
                object_type_by_id.get(target_id),
            "qualifier": str(
                row["O2O_qualifier"]
            ).strip(),
            "timestamp": row["Timestamp"],
        })