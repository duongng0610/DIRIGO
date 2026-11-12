
from typing import Any
from pathlib import Path
from src.ir.models import RelationshipRecord
<<<<<<< Updated upstream
from src.builders.helper import build_object_reference_id, build_resolver_index, build_data_frame_by_table_name
=======
from src.builders.helper import build_object_reference_id, build_resolver_index, build_data_frame_by_table_name, resolve_lookup_row
>>>>>>> Stashed changes
import pandas as pd
from src.readers.sqlite_reader import SQLiteReader


def build_o2o(sqlite_reader: SQLiteReader, mapping: dict[str, Any]) -> list[RelationshipRecord]:
    o2o_records = []

    object_configs = {
        obj["type"]: obj
        for obj in mapping["objects"]
    }
    relationships = (
        mapping
        .get("relationships", {})
        .get("o2o", [])
    )

    for relationship_mapping in relationships:
        source_object_mapping = relationship_mapping["source"]
        source_object_type = source_object_mapping["object_type"]

        target_object_mapping = relationship_mapping["target"]
        target_object_type = target_object_mapping["object_type"]

        for qualifier_mapping in relationship_mapping["qualifiers"]:
            o2o_source_df = build_data_frame_by_table_name(
                sqlite_reader,
                qualifier_mapping["source_table"],
                mapping["tables"])

<<<<<<< Updated upstream
            # Giữ những row là event trong bảng
            o2o_source_df = sqlite_reader.apply_where(
                o2o_source_df,
                qualifier_mapping.get("where", []),
=======
        qualifier = relationship_mapping["qualifier"]
        relationship_mode = relationship_mapping.get("mode", "dynamic")
        timestamp_mapping = relationship_mapping.get("timestamp")

        if relationship_mode == "dynamic":
            if not timestamp_mapping or "column" not in timestamp_mapping:
                raise ValueError(
                    f"Dynamic relationship '{relationship_mapping.get('name')}' "
                    "requires timestamp.column"
                )
        elif relationship_mode == "static":
            pass
        else:
            raise ValueError(
                f"Unsupported relationship mode: {relationship_mode}"
            )

        timestamp_lookup_index = (
            build_resolver_index(sqlite_reader, timestamp_mapping, mapping)
            if timestamp_mapping
            else None
        )

        for _,row in o2o_source_df.iterrows():

            source_object_id = build_object_reference_id(
                row=row,
                object_config= object_configs[source_object_type],
                object_mapping= source_object_mapping, 
                lookup_index=source_lookup_index,
>>>>>>> Stashed changes
            )

            source_lookup_index = build_resolver_index(
                sqlite_reader, source_object_mapping, mapping)

<<<<<<< Updated upstream
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

                o2o_records.append(RelationshipRecord(
                    qualifier=qualifier,
                    source_object_id=source_object_id,
                    source_object_type=source_object_type,
                    target_object_id=target_object_id,
                    target_object_type=target_object_type,
                    time_stamp=time_stamp
                ))
=======
            if timestamp_mapping is None:
                time_stamp = None
            else:
                timestamp_row = row
                timestamp_resolver = timestamp_mapping.get("resolver")

                if timestamp_resolver is not None:
                    timestamp_row = resolve_lookup_row(
                        row=row,
                        resolver_mapping=timestamp_resolver,
                        lookup_index=timestamp_lookup_index,
                    )

                time_stamp = timestamp_row[timestamp_mapping["column"]]
>>>>>>> Stashed changes

    return o2o_records
