from __future__ import annotations

import json

from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

from .mapping_models import (
    FilterCondition,
    IdMapping,
    MappingProposal,
    ObjectReference,
    RelationshipMapping,
    ResolverMapping,
    ValueMapping,
)


class MappingCompilationError(ValueError):
    """Proposal hợp lệ về schema nhưng chưa compile được cho builder."""


def _compile_filter(rule: FilterCondition) -> dict[str, Any]:
    """Đổi FilterCondition của LLM sang format SQLiteReader.apply_where."""

    result: dict[str, Any] = {
        "column": rule.column,
        "condition": rule.operator,
    }

    if rule.operator in {"in", "not_in"}:
        result["value"] = rule.values
    elif rule.operator not in {"is_null", "is_not_null"}:
        result["value"] = rule.value

    return result


def _compile_filters(
    rules: list[FilterCondition],
) -> list[dict[str, Any]]:
    return [_compile_filter(rule) for rule in rules]


def _compile_id(id_mapping: IdMapping) -> dict[str, Any]:
    """Loại các field null và giữ đúng contract build_id_from_row."""

    result: dict[str, Any] = {
        "mode": id_mapping.mode,
        "columns": list(id_mapping.columns),
    }

    if id_mapping.prefix is not None:
        result["prefix"] = id_mapping.prefix

    # Builder đã mặc định separator là "-". Chỉ ghi khi LLM chọn
    # một separator khác để YAML ngắn và dễ review hơn.
    if id_mapping.separator and id_mapping.separator != "-":
        result["separator"] = id_mapping.separator

    return result


def _compile_value(value: ValueMapping) -> dict[str, Any]:
    """Đổi value_type của proposal thành field type của YAML runtime."""

    return {
        "column": value.column,
        "type": value.value_type,
    }


def _compile_key_mapping(
    reference: ObjectReference,
) -> dict[str, str]:
    """
    Đổi key_mapping dạng list sang dictionary builder đang sử dụng.

    Proposal dùng list để tương thích Structured Output. Runtime YAML
    dùng mapping canonical object column -> current/lookup row column.
    """

    result: dict[str, str] = {}

    for item in reference.key_mapping:
        if item.object_id_column in result:
            raise MappingCompilationError(
                "Duplicate object ID column in key_mapping: "
                f"{item.object_id_column}"
            )

        result[item.object_id_column] = item.row_column

    return result


def _compile_resolver(
    resolver: ResolverMapping,
) -> dict[str, Any]:
    """Đổi resolver proposal sang contract build_resolver_index."""

    # build_resolver_index hiện chưa áp dụng where cho lookup table.
    # Không được âm thầm bỏ điều kiện vì có thể resolve sai object.
    if resolver.where:
        raise MappingCompilationError(
            "Resolver.where is not supported by the current builder"
        )

    return {
        "mode": "lookup",
        "table": resolver.lookup_table,
        "on": [
            {
                "source_column": join.source_column,
                "lookup_column": join.lookup_column,
            }
            for join in resolver.joins
        ],
    }


def _compile_reference(
    reference: ObjectReference,
) -> dict[str, Any]:
    """Làm phẳng ObjectReference để event/O2O builder đọc được."""

    result: dict[str, Any] = {
        "object_type": reference.object_type,
        "key_mapping": _compile_key_mapping(reference),
    }

    if reference.mode == "lookup":
        if reference.resolver is None:
            raise MappingCompilationError(
                "Lookup reference has no resolver"
            )

        result["resolver"] = _compile_resolver(
            reference.resolver
        )

    return result


def _compile_objects(proposal: MappingProposal) -> list[dict[str, Any]]:
    """Compile objects, static attributes và dynamic attributes."""

    compiled_objects: list[dict[str, Any]] = []

    for object_mapping in proposal.mapping.objects:
        static_attributes = [
            {
                "name": attribute.name,
                "source_column": attribute.value.column,
                "type": attribute.value.value_type,
            }
            for attribute in object_mapping.attributes.static
        ]

        dynamic_attributes: list[dict[str, Any]] = []

        for attribute in object_mapping.attributes.dynamic:
            compiled_attribute: dict[str, Any] = {
                "name": attribute.name,
                "source_table": attribute.source_table,
                "value": _compile_value(attribute.value),
                "timestamp": {
                    "column": attribute.timestamp.column,
                },
                "object_reference": _compile_reference(
                    attribute.object_reference
                ),
            }

            if attribute.where:
                compiled_attribute["where"] = _compile_filters(
                    attribute.where
                )

            dynamic_attributes.append(compiled_attribute)

        compiled_objects.append(
            {
                "type": object_mapping.type,
                "source_table": object_mapping.source_table,
                "id": _compile_id(object_mapping.id),
                "attributes": {
                    "static": static_attributes,
                    "dynamic": dynamic_attributes,
                },
            }
        )

    return compiled_objects


def _compile_events(proposal: MappingProposal) -> list[dict[str, Any]]:
    """Compile events và E2O object references."""

    compiled_events: list[dict[str, Any]] = []

    for event in proposal.mapping.events:
        compiled_event: dict[str, Any] = {
            "type": event.type,
            "source_table": event.source_table,
            "id": _compile_id(event.id),
            # Event builder dùng source_column, khác TimestampMapping
            # của dynamic attribute và O2O đang dùng column.
            "timestamp": {
                "source_column": event.timestamp.column,
            },
            # Giữ event attributes trong candidate YAML để compiler
            # không làm mất thông tin. MAP-QC phải cảnh báo rằng
            # event_builder_v2 hiện chưa xuất các field này ra CSV.
            "attributes": [
                {
                    "name": attribute.name,
                    "source_column": attribute.value.column,
                    "type": attribute.value.value_type,
                }
                for attribute in event.attributes
            ],
            "objects": [],
        }

        if event.where:
            compiled_event["where"] = _compile_filters(
                event.where
            )

        for event_object in event.objects:
            compiled_reference = _compile_reference(
                event_object.reference
            )
            compiled_reference["qualifier"] = event_object.qualifier
            compiled_event["objects"].append(compiled_reference)

        compiled_events.append(compiled_event)

    return compiled_events


def _relationship_group_key(
    relationship: RelationshipMapping,
) -> str:
    """Tạo key ổn định để gom nhiều qualifier vào cùng một O2O."""

    identity = {
        "name": relationship.name,
        "mode": relationship.relation_mode,
        "source": relationship.source.model_dump(mode="json"),
        "target": relationship.target.model_dump(mode="json"),
    }

    return json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compile_relationships(
    proposal: MappingProposal,
) -> dict[str, list[dict[str, Any]]]:
    """
    Compile và gom O2O theo name/source/target/mode.

    Proposal biểu diễn mỗi qualifier thành một relationship record.
    Builder hiện tại lại đọc một O2O có danh sách qualifiers, nên cần
    group ở bước compiler.
    """

    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for relationship in proposal.mapping.relationships:
        group_key = _relationship_group_key(relationship)

        if group_key not in grouped:
            grouped[group_key] = {
                "name": relationship.name,
                "mode": relationship.relation_mode,
                "source": _compile_reference(
                    relationship.source
                ),
                "target": _compile_reference(
                    relationship.target
                ),
                "qualifiers": [],
            }

        qualifier: dict[str, Any] = {
            "qualifier": relationship.qualifier,
            "source_table": relationship.source_table,
        }

        if relationship.timestamp is not None:
            qualifier["timestamp"] = {
                "column": relationship.timestamp.column,
            }

        if relationship.where:
            qualifier["where"] = _compile_filters(
                relationship.where
            )

        grouped[group_key]["qualifiers"].append(qualifier)

    return {
        "o2o": list(grouped.values()),
    }


def _collect_source_tables(
    proposal: MappingProposal,
) -> list[str]:
    """Thu thập tên bảng để sinh identity table mapping."""

    tables: set[str] = set()

    def add_reference(reference: ObjectReference) -> None:
        if reference.resolver is not None:
            tables.add(reference.resolver.lookup_table)

    for object_mapping in proposal.mapping.objects:
        tables.add(object_mapping.source_table)
        for attribute in object_mapping.attributes.dynamic:
            tables.add(attribute.source_table)
            add_reference(attribute.object_reference)

    for event in proposal.mapping.events:
        tables.add(event.source_table)
        for event_object in event.objects:
            add_reference(event_object.reference)

    for relationship in proposal.mapping.relationships:
        tables.add(relationship.source_table)
        add_reference(relationship.source)
        add_reference(relationship.target)

    return sorted(tables)


def compile_mapping_proposal(
    proposal: MappingProposal,
    source_database_path: str,
) -> dict[str, Any]:
    """
    Chuyển MappingProposal sang dictionary đúng runtime YAML contract.

    Hàm từ chối proposal có unresolved question blocking. Việc MAP-QC
    pass vẫn phải được kiểm tra bên ngoài trước khi đưa YAML vào configs.
    """

    blocking_questions = [
        question
        for question in proposal.unresolved_questions
        if question.blocking
    ]

    if blocking_questions:
        codes = ", ".join(
            question.code for question in blocking_questions
        )
        raise MappingCompilationError(
            f"Proposal has blocking unresolved questions: {codes}"
        )

    table_names = _collect_source_tables(proposal)

    return {
        "contract_version": 2,
        "name": proposal.mapping.dataset_name,
        "sources": {
            "type": "sqlite",
            "path": source_database_path,
            "read_only": True,
        },
        # LLM dùng tên bảng thật từ source profile. Identity mapping
        # giúp builders vẫn dùng chung cơ chế alias hiện tại.
        "tables": {
            table_name: {"table": table_name}
            for table_name in table_names
        },
        "objects": _compile_objects(proposal),
        "events": _compile_events(proposal),
        "relationships": _compile_relationships(proposal),
    }


def compile_proposal_file(
    proposal_path: str | Path,
    output_path: str | Path,
    source_database_path: str,
) -> Path:
    """Đọc proposal JSON, validate Pydantic rồi ghi YAML candidate."""

    proposal_path = Path(proposal_path)
    output_path = Path(output_path)

    proposal = MappingProposal.model_validate_json(
        proposal_path.read_text(encoding="utf-8")
    )

    compiled_mapping = compile_mapping_proposal(
        proposal=proposal,
        source_database_path=source_database_path,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(
            compiled_mapping,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    # Đọc lại để phát hiện ngay YAML bị ghi hỏng.
    loaded_mapping = yaml.safe_load(
        output_path.read_text(encoding="utf-8")
    )
    if loaded_mapping != compiled_mapping:
        raise MappingCompilationError(
            "YAML round-trip changed the compiled mapping"
        )

    return output_path
