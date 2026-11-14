from typing import Any

from src.builders.helper import (
    build_data_frame_by_table_name,
    build_id_from_row,
    build_object_reference_id,
    build_resolver_index,
    resolve_lookup_row,
)
from src.qc.projection.models import (
    ExpectedProjection,
    ObjectAttributeProjection,
)


def build_expected_projection(
    sqlite_reader,
    mapping: dict[str, Any],
) -> ExpectedProjection:
    projection = ExpectedProjection()

    project_expected_objects_and_attributes(
        sqlite_reader,
        mapping,
        projection,
    )

    project_expected_events_and_e2o(
        sqlite_reader,
        mapping,
        projection,
    )

    project_expected_o2o(
        sqlite_reader,
        mapping,
        projection,
    )

    return projection


def project_expected_objects_and_attributes(
    sqlite_reader,
    mapping: dict[str, Any],
    projection: ExpectedProjection,
) -> None:
    for object_mapping in mapping.get("objects", []):
        object_type = object_mapping["type"]

        source_df = build_data_frame_by_table_name(
            sqlite_reader,
            object_mapping["source_table"],
            mapping["tables"],
        )

        source_df = sqlite_reader.apply_where(
            source_df,
            object_mapping.get("where", []),
        )

        expected_ids: set[str] = set()

        static_mappings = (
            object_mapping
            .get("attributes", {})
            .get("static", [])
        )

        for _, row in source_df.iterrows():
            object_id = build_id_from_row(
                row=row,
                id_mapping=object_mapping["id"],
            )

            expected_ids.add(object_id)

            for attribute_mapping in static_mappings:
                # Timestamp của initial row không phải
                # một object attribute.
                if "timestamp" in attribute_mapping:
                    continue

                projection.object_attributes.append(
                    ObjectAttributeProjection(
                        object_type=object_type,
                        object_id=object_id,
                        attribute_name=attribute_mapping[
                            "name"
                        ],
                        value=row[
                            attribute_mapping[
                                "source_column"
                            ]
                        ],
                        value_type=attribute_mapping.get(
                            "type",
                            "string",
                        ),
                        kind="static",
                    )
                )

        projection.objects[object_type] = sorted(
            expected_ids
        )

        project_expected_dynamic_attributes(
            sqlite_reader,
            mapping,
            object_mapping,
            projection,
        )


def project_expected_dynamic_attributes(
    sqlite_reader,
    mapping: dict[str, Any],
    object_mapping: dict[str, Any],
    projection: ExpectedProjection,
) -> None:
    object_type = object_mapping["type"]

    expected_object_ids = set(
        projection.objects.get(object_type, [])
    )

    dynamic_mappings = (
        object_mapping
        .get("attributes", {})
        .get("dynamic", [])
    )

    for attribute_mapping in dynamic_mappings:
        change_policy = attribute_mapping.get(
            "change_policy",
            "every_source_row",
        )

        if change_policy != "every_source_row":
            raise ValueError(
                "Current builder only supports "
                f"change_policy=every_source_row, got "
                f"'{change_policy}' for "
                f"'{attribute_mapping['name']}'"
            )

        history_df = build_data_frame_by_table_name(
            sqlite_reader,
            attribute_mapping["source_table"],
            mapping["tables"],
        )

        history_df = sqlite_reader.apply_where(
            history_df,
            attribute_mapping.get("where", []),
        )

        object_reference = attribute_mapping.get(
            "object_reference",
            {},
        )

        resolver_index = build_resolver_index(
            sqlite_reader,
            object_reference,
            mapping,
        )

        timestamp_column = (
            attribute_mapping["timestamp"]["column"]
        )
        value_column = (
            attribute_mapping["value"]["column"]
        )

        for _, row in history_df.iterrows():
            object_id = build_object_reference_id(
                row=row,
                object_config=object_mapping,
                object_mapping=object_reference,
                lookup_index=resolver_index,
            )

            if object_id not in expected_object_ids:
                projection.filter_audits.append({
                    "check_id": "REC-04",
                    "object_type": object_type,
                    "object_id": object_id,
                    "reason": (
                        "Dynamic attribute references "
                        "unknown object"
                    ),
                })
                continue

            projection.object_attributes.append(
                ObjectAttributeProjection(
                    object_type=object_type,
                    object_id=object_id,
                    attribute_name=attribute_mapping[
                        "name"
                    ],
                    value=row[value_column],
                    value_type=attribute_mapping[
                        "value"
                    ].get("type", "string"),
                    kind="dynamic",
                    timestamp=row[timestamp_column],
                )
            )


def project_expected_events_and_e2o(
    sqlite_reader,
    mapping: dict[str, Any],
    projection: ExpectedProjection,
) -> None:
    object_configs = {
        config["type"]: config
        for config in mapping.get("objects", [])
    }

    for event_mapping in mapping.get("events", []):
        source_df = build_data_frame_by_table_name(
            sqlite_reader,
            event_mapping["source_table"],
            mapping["tables"],
        )

        unfiltered_count = len(source_df)

        source_df = sqlite_reader.apply_where(
            source_df,
            event_mapping.get("where", []),
        )

        projection.filter_audits.append({
            "mapping": event_mapping["type"],
            "source_rows": unfiltered_count,
            "accepted_rows": len(source_df),
            "filtered_rows": (
                unfiltered_count - len(source_df)
            ),
        })

        object_mappings = event_mapping.get(
            "objects",
            [],
        )

        lookup_indexes = {
            position: build_resolver_index(
                sqlite_reader,
                object_reference,
                mapping,
            )
            for position, object_reference
            in enumerate(object_mappings)
        }

        timestamp_column = event_mapping[
            "timestamp"
        ]["source_column"]

        for _, row in source_df.iterrows():
            event_id = build_id_from_row(
                row=row,
                id_mapping=event_mapping["id"],
            )

            activity = event_mapping["type"]

            projection.events.append({
                "event_id": event_id,
                "activity": activity,
                "timestamp": row[timestamp_column],
            })

            for position, object_reference in enumerate(
                object_mappings
            ):
                object_type = object_reference[
                    "object_type"
                ]

                object_id = build_object_reference_id(
                    row=row,
                    object_config=object_configs[
                        object_type
                    ],
                    object_mapping=object_reference,
                    lookup_index=lookup_indexes[
                        position
                    ],
                )

                projection.e2o.append({
                    "event_id": event_id,
                    "activity": activity,
                    "object_id": object_id,
                    "object_type": object_type,
                    "qualifier": object_reference[
                        "qualifier"
                    ],
                })


def project_expected_o2o(
    sqlite_reader,
    mapping: dict[str, Any],
    projection: ExpectedProjection,
) -> None:
    object_configs = {
        config["type"]: config
        for config in mapping.get("objects", [])
    }

    relationship_mappings = (
        mapping
        .get("relationships", {})
        .get("o2o", [])
    )

    for relationship_mapping in relationship_mappings:
            source_object_mapping = relationship_mapping["source"]
            source_object_type = source_object_mapping["object_type"]
    
            target_object_mapping = relationship_mapping["target"]
            target_object_type = target_object_mapping["object_type"]
    
            for qualifier_mapping in relationship_mapping["qualifiers"]:
                o2o_source_df = build_data_frame_by_table_name(
                    sqlite_reader,
                    qualifier_mapping["source_table"],
                    mapping["tables"])
    
                # Giữ những row là event trong bảng
                o2o_source_df = sqlite_reader.apply_where(
                    o2o_source_df,
                    qualifier_mapping.get("where", []),
                )
    
                source_lookup_index = build_resolver_index(
                    sqlite_reader, source_object_mapping, mapping)
    
                target_lookup_index = build_resolver_index(
                    sqlite_reader, target_object_mapping, mapping)
    
                qualifier = qualifier_mapping["qualifier"]
                time_stamp_column = qualifier_mapping["timestamp"]["column"]
    
                for _, row in o2o_source_df.iterrows():
    
                    source_object_id = build_object_reference_id(
                        row=row,
                        object_config=object_configs[source_object_type],
                        object_mapping=source_object_mapping,
                        lookup_index=source_lookup_index,
                    )
    
                    target_object_id = build_object_reference_id(
                        row=row,
                        object_config=object_configs[target_object_type],
                        object_mapping=target_object_mapping,
                        lookup_index=target_lookup_index
                    )
    
                    time_stamp = row[time_stamp_column]
    

                    projection.o2o.append({
                        "relationship_name":
                            relationship_mapping.get("name"),
                        "source_object_id": source_object_id,
                        "source_object_type": source_object_type,
                        "target_object_id": target_object_id,
                        "target_object_type": target_object_type,
                        "qualifier": qualifier,
                        "timestamp": time_stamp,
                    })