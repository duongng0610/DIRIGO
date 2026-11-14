from __future__ import annotations

import json
import sqlite3

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .mapping_compiler import compile_proposal_file
from .mapping_models import (
    FilterCondition,
    IdMapping,
    MappingProposal,
    ObjectReference,
    ValueMapping,
)


IssueSeverity = Literal["ERROR", "WARNING"]
RepairStrategy = Literal["llm", "human", "code"]


@dataclass(frozen=True)
class MappingIssue:
    """Một lỗi/cảnh báo có cấu trúc để người hoặc LLM sửa được."""

    code: str
    severity: IssueSeverity
    path: str
    message: str
    repair_strategy: RepairStrategy
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MappingValidationReport:
    """Kết quả MAP-QC của một proposal."""

    status: Literal["PASS", "FAIL"]
    checks_run: int
    issues: list[MappingIssue]

    @property
    def errors(self) -> list[MappingIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "ERROR"
        ]

    @property
    def warnings(self) -> list[MappingIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "WARNING"
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks_run": self.checks_run,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [asdict(issue) for issue in self.issues],
        }


def _quote_identifier(identifier: str) -> str:
    """Quote tên bảng/cột an toàn khi chạy truy vấn QC."""

    return '"' + identifier.replace('"', '""') + '"'


class MappingValidator:
    """
    Validator deterministic cho Source Profile -> MappingProposal.

    Validator không đánh giá toàn bộ ý nghĩa nghiệp vụ. Nó kiểm tra
    những điều có thể chứng minh từ profile và SQLite: table/column,
    ID, reference, filters, timestamp và resolver cardinality.
    """

    def __init__(
        self,
        proposal: MappingProposal,
        source_profile: dict[str, Any],
        database_path: str | Path | None = None,
    ) -> None:
        self.proposal = proposal
        self.source_profile = source_profile
        self.database_path = (
            Path(database_path).resolve()
            if database_path is not None
            else None
        )

        self.tables: dict[str, dict[str, Any]] = {
            table["name"]: table
            for table in source_profile.get("tables", [])
            if isinstance(table, dict) and table.get("name")
        }

        self.objects = {
            object_mapping.type: object_mapping
            for object_mapping in proposal.mapping.objects
        }

        self.issues: list[MappingIssue] = []
        self.checks_run = 0

    def _add_issue(
        self,
        code: str,
        severity: IssueSeverity,
        path: str,
        message: str,
        repair_strategy: RepairStrategy,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.issues.append(
            MappingIssue(
                code=code,
                severity=severity,
                path=path,
                message=message,
                repair_strategy=repair_strategy,
                evidence=evidence or {},
            )
        )

    def _table_exists(self, table_name: str, path: str) -> bool:
        self.checks_run += 1

        if table_name not in self.tables:
            self._add_issue(
                code="MAP-TABLE-NOT-FOUND",
                severity="ERROR",
                path=path,
                message=f"Source table '{table_name}' does not exist",
                repair_strategy="llm",
                evidence={
                    "available_tables": sorted(self.tables),
                },
            )
            return False

        return True

    def _column_profile(
        self,
        table_name: str,
        column_name: str,
    ) -> dict[str, Any] | None:
        table = self.tables.get(table_name)
        if table is None:
            return None

        return next(
            (
                column
                for column in table.get("columns", [])
                if column.get("name") == column_name
            ),
            None,
        )

    def _column_exists(
        self,
        table_name: str,
        column_name: str,
        path: str,
    ) -> bool:
        self.checks_run += 1

        if self._column_profile(table_name, column_name) is None:
            table = self.tables.get(table_name, {})
            self._add_issue(
                code="MAP-COLUMN-NOT-FOUND",
                severity="ERROR",
                path=path,
                message=(
                    f"Column '{column_name}' does not exist in "
                    f"table '{table_name}'"
                ),
                repair_strategy="llm",
                evidence={
                    "available_columns": [
                        column.get("name")
                        for column in table.get("columns", [])
                    ],
                },
            )
            return False

        return True

    def _validate_unique_names(
        self,
        names: list[str],
        path: str,
        entity_name: str,
    ) -> None:
        self.checks_run += 1
        duplicates = sorted(
            {
                name
                for name in names
                if names.count(name) > 1
            }
        )

        if duplicates:
            self._add_issue(
                code="MAP-DUPLICATE-NAME",
                severity="ERROR",
                path=path,
                message=f"Duplicate {entity_name} names: {duplicates}",
                repair_strategy="llm",
            )

    def _validate_id(
        self,
        table_name: str,
        id_mapping: IdMapping,
        path: str,
    ) -> None:
        if not self._table_exists(table_name, path):
            return

        all_columns_exist = True
        for index, column_name in enumerate(id_mapping.columns):
            exists = self._column_exists(
                table_name,
                column_name,
                f"{path}.columns[{index}]",
            )
            all_columns_exist = all_columns_exist and exists

            column = self._column_profile(table_name, column_name)
            if column is not None and column.get("null_count", 0) > 0:
                self._add_issue(
                    code="MAP-ID-COLUMN-NULLABLE",
                    severity="ERROR",
                    path=f"{path}.columns[{index}]",
                    message=(
                        f"ID column '{table_name}.{column_name}' "
                        "contains null values"
                    ),
                    repair_strategy="llm",
                    evidence={
                        "null_count": column.get("null_count"),
                    },
                )

        if not all_columns_exist:
            return

        self.checks_run += 1
        table = self.tables[table_name]
        candidate_keys = [
            tuple(candidate.get("columns", []))
            for candidate in table.get(
                "primary_key_candidates",
                [],
            )
        ]

        if tuple(id_mapping.columns) not in candidate_keys:
            self._add_issue(
                code="MAP-ID-NOT-CANDIDATE-KEY",
                severity="WARNING",
                path=path,
                message=(
                    f"ID columns {id_mapping.columns} are not listed "
                    f"as a candidate key for '{table_name}'"
                ),
                repair_strategy="human",
                evidence={
                    "candidate_keys": [list(key) for key in candidate_keys],
                },
            )

    def _validate_filters(
        self,
        table_name: str,
        filters: list[FilterCondition],
        path: str,
    ) -> None:
        for index, rule in enumerate(filters):
            self._column_exists(
                table_name,
                rule.column,
                f"{path}[{index}].column",
            )

    def _has_not_null_filter(
        self,
        filters: list[FilterCondition],
        column_name: str,
    ) -> bool:
        return any(
            rule.column == column_name
            and rule.operator == "is_not_null"
            for rule in filters
        )

    def _validate_timestamp(
        self,
        table_name: str,
        column_name: str,
        filters: list[FilterCondition],
        path: str,
    ) -> None:
        if not self._column_exists(table_name, column_name, path):
            return

        self.checks_run += 1
        column = self._column_profile(table_name, column_name) or {}
        null_count = int(column.get("null_count", 0) or 0)

        if null_count > 0 and not self._has_not_null_filter(
            filters,
            column_name,
        ):
            self._add_issue(
                code="MAP-TIMESTAMP-NULL-WITHOUT-FILTER",
                severity="ERROR",
                path=path,
                message=(
                    f"Timestamp '{table_name}.{column_name}' contains "
                    "null values but mapping has no is_not_null filter"
                ),
                repair_strategy="llm",
                evidence={"null_count": null_count},
            )

    def _validate_value(
        self,
        table_name: str,
        value: ValueMapping,
        path: str,
    ) -> None:
        self._column_exists(table_name, value.column, f"{path}.column")

    def _validate_reference(
        self,
        reference: ObjectReference,
        current_table: str,
        path: str,
    ) -> None:
        self.checks_run += 1
        object_mapping = self.objects.get(reference.object_type)

        if object_mapping is None:
            self._add_issue(
                code="MAP-UNKNOWN-OBJECT-TYPE",
                severity="ERROR",
                path=f"{path}.object_type",
                message=(
                    f"Object type '{reference.object_type}' is not declared"
                ),
                repair_strategy="llm",
                evidence={
                    "available_object_types": sorted(self.objects),
                },
            )
            return

        expected_key_columns = set(object_mapping.id.columns)
        actual_key_columns = {
            item.object_id_column
            for item in reference.key_mapping
        }

        if actual_key_columns != expected_key_columns:
            self._add_issue(
                code="MAP-REFERENCE-KEY-MISMATCH",
                severity="ERROR",
                path=f"{path}.key_mapping",
                message=(
                    "Reference key_mapping does not cover the object ID "
                    f"columns for '{reference.object_type}'"
                ),
                repair_strategy="llm",
                evidence={
                    "expected": sorted(expected_key_columns),
                    "actual": sorted(actual_key_columns),
                },
            )

        if reference.mode == "direct":
            for index, key_mapping in enumerate(reference.key_mapping):
                self._column_exists(
                    current_table,
                    key_mapping.row_column,
                    f"{path}.key_mapping[{index}].row_column",
                )
            return

        resolver = reference.resolver
        if resolver is None:
            return  # Pydantic model_validator đã báo trường hợp này.

        if resolver.where:
            self._add_issue(
                code="MAP-UNSUPPORTED-RESOLVER-WHERE",
                severity="ERROR",
                path=f"{path}.resolver.where",
                message=(
                    "Current build_resolver_index does not support "
                    "resolver.where"
                ),
                repair_strategy="code",
            )

        if not self._table_exists(
            resolver.lookup_table,
            f"{path}.resolver.lookup_table",
        ):
            return

        for index, join in enumerate(resolver.joins):
            self._column_exists(
                current_table,
                join.source_column,
                f"{path}.resolver.joins[{index}].source_column",
            )
            self._column_exists(
                resolver.lookup_table,
                join.lookup_column,
                f"{path}.resolver.joins[{index}].lookup_column",
            )

        for index, key_mapping in enumerate(reference.key_mapping):
            self._column_exists(
                resolver.lookup_table,
                key_mapping.row_column,
                f"{path}.key_mapping[{index}].row_column",
            )

        self._validate_resolver_cardinality(
            reference=reference,
            source_table=current_table,
            path=f"{path}.resolver",
        )

    def _validate_resolver_cardinality(
        self,
        reference: ObjectReference,
        source_table: str,
        path: str,
    ) -> None:
        """Kiểm tra mỗi source key resolve tối đa/đúng một lookup row."""

        resolver = reference.resolver
        if resolver is None or self.database_path is None:
            return

        self.checks_run += 1

        if not self.database_path.exists():
            self._add_issue(
                code="MAP-DATABASE-NOT-FOUND",
                severity="ERROR",
                path=path,
                message=f"Database does not exist: {self.database_path}",
                repair_strategy="human",
            )
            return

        source_table_sql = _quote_identifier(source_table)
        lookup_table_sql = _quote_identifier(resolver.lookup_table)

        join_condition = " AND ".join(
            "lookup.{lookup} = source.{source}".format(
                lookup=_quote_identifier(join.lookup_column),
                source=_quote_identifier(join.source_column),
            )
            for join in resolver.joins
        )

        query = f"""
            SELECT
                SUM(CASE WHEN match_count = 0 THEN 1 ELSE 0 END)
                    AS orphan_count,
                SUM(CASE WHEN match_count > 1 THEN 1 ELSE 0 END)
                    AS ambiguous_count
            FROM (
                SELECT source.rowid, COUNT(lookup.rowid) AS match_count
                FROM {source_table_sql} AS source
                LEFT JOIN {lookup_table_sql} AS lookup
                  ON {join_condition}
                GROUP BY source.rowid
            )
        """

        database_uri = self.database_path.as_uri() + "?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            row = connection.execute(query).fetchone()

        orphan_count = int(row[0] or 0)
        ambiguous_count = int(row[1] or 0)

        if ambiguous_count > 0:
            self._add_issue(
                code="MAP-RESOLVER-AMBIGUOUS",
                severity="ERROR",
                path=path,
                message=(
                    f"Resolver returns more than one row for "
                    f"{ambiguous_count} source rows"
                ),
                repair_strategy="llm",
                evidence={"ambiguous_count": ambiguous_count},
            )

        if (
            orphan_count > 0
            and resolver.expected_cardinality == "exactly_one"
        ):
            self._add_issue(
                code="MAP-RESOLVER-ORPHAN",
                severity="ERROR",
                path=path,
                message=(
                    f"Resolver cannot find a lookup row for "
                    f"{orphan_count} source rows"
                ),
                repair_strategy="llm",
                evidence={"orphan_count": orphan_count},
            )

    def _validate_objects(self) -> None:
        objects = self.proposal.mapping.objects
        self._validate_unique_names(
            [item.type for item in objects],
            "mapping.objects",
            "object type",
        )

        for object_index, object_mapping in enumerate(objects):
            path = f"mapping.objects[{object_index}]"
            self._validate_id(
                object_mapping.source_table,
                object_mapping.id,
                f"{path}.id",
            )

            self._validate_unique_names(
                [
                    attribute.name
                    for attribute in object_mapping.attributes.static
                ]
                + [
                    attribute.name
                    for attribute in object_mapping.attributes.dynamic
                ],
                f"{path}.attributes",
                "attribute",
            )

            for attribute_index, attribute in enumerate(
                object_mapping.attributes.static
            ):
                self._validate_value(
                    object_mapping.source_table,
                    attribute.value,
                    f"{path}.attributes.static[{attribute_index}].value",
                )

            for attribute_index, attribute in enumerate(
                object_mapping.attributes.dynamic
            ):
                attribute_path = (
                    f"{path}.attributes.dynamic[{attribute_index}]"
                )
                if not self._table_exists(
                    attribute.source_table,
                    f"{attribute_path}.source_table",
                ):
                    continue

                self._validate_value(
                    attribute.source_table,
                    attribute.value,
                    f"{attribute_path}.value",
                )
                self._validate_filters(
                    attribute.source_table,
                    attribute.where,
                    f"{attribute_path}.where",
                )
                self._validate_timestamp(
                    attribute.source_table,
                    attribute.timestamp.column,
                    attribute.where,
                    f"{attribute_path}.timestamp.column",
                )
                self._validate_reference(
                    attribute.object_reference,
                    attribute.source_table,
                    f"{attribute_path}.object_reference",
                )

    def _validate_events(self) -> None:
        events = self.proposal.mapping.events
        self._validate_unique_names(
            [item.type for item in events],
            "mapping.events",
            "event type",
        )

        for event_index, event in enumerate(events):
            path = f"mapping.events[{event_index}]"
            if not self._table_exists(
                event.source_table,
                f"{path}.source_table",
            ):
                continue

            self._validate_id(
                event.source_table,
                event.id,
                f"{path}.id",
            )
            self._validate_filters(
                event.source_table,
                event.where,
                f"{path}.where",
            )
            self._validate_timestamp(
                event.source_table,
                event.timestamp.column,
                event.where,
                f"{path}.timestamp.column",
            )

            if event.attributes:
                self._add_issue(
                    code="MAP-UNSUPPORTED-EVENT-ATTRIBUTES",
                    severity="ERROR",
                    path=f"{path}.attributes",
                    message=(
                        "event_builder_v2 and OCEL_Events.csv do not "
                        "currently persist event attributes"
                    ),
                    repair_strategy="llm",
                    evidence={
                        "attribute_names": [
                            attribute.name
                            for attribute in event.attributes
                        ],
                    },
                )

            for attribute_index, attribute in enumerate(event.attributes):
                self._validate_value(
                    event.source_table,
                    attribute.value,
                    f"{path}.attributes[{attribute_index}].value",
                )

            for object_index, event_object in enumerate(event.objects):
                if not event_object.qualifier.strip():
                    self._add_issue(
                        code="MAP-EMPTY-E2O-QUALIFIER",
                        severity="ERROR",
                        path=f"{path}.objects[{object_index}].qualifier",
                        message="E2O qualifier must not be empty",
                        repair_strategy="llm",
                    )

                self._validate_reference(
                    event_object.reference,
                    event.source_table,
                    f"{path}.objects[{object_index}].reference",
                )

    def _validate_relationships(self) -> None:
        relationships = self.proposal.mapping.relationships

        relationship_keys = [
            f"{item.name}:{item.qualifier}"
            for item in relationships
        ]
        self._validate_unique_names(
            relationship_keys,
            "mapping.relationships",
            "relationship name/qualifier",
        )

        for relationship_index, relationship in enumerate(relationships):
            path = f"mapping.relationships[{relationship_index}]"
            if not self._table_exists(
                relationship.source_table,
                f"{path}.source_table",
            ):
                continue

            self._validate_filters(
                relationship.source_table,
                relationship.where,
                f"{path}.where",
            )

            if not relationship.qualifier.strip():
                self._add_issue(
                    code="MAP-EMPTY-O2O-QUALIFIER",
                    severity="ERROR",
                    path=f"{path}.qualifier",
                    message="O2O qualifier must not be empty",
                    repair_strategy="llm",
                )

            if relationship.timestamp is not None:
                self._validate_timestamp(
                    relationship.source_table,
                    relationship.timestamp.column,
                    relationship.where,
                    f"{path}.timestamp.column",
                )

            self._validate_reference(
                relationship.source,
                relationship.source_table,
                f"{path}.source",
            )
            self._validate_reference(
                relationship.target,
                relationship.source_table,
                f"{path}.target",
            )

    def _validate_unresolved_questions(self) -> None:
        for index, question in enumerate(
            self.proposal.unresolved_questions
        ):
            self.checks_run += 1
            self._add_issue(
                code=(
                    "MAP-UNRESOLVED-BLOCKING"
                    if question.blocking
                    else "MAP-UNRESOLVED-NONBLOCKING"
                ),
                severity="ERROR" if question.blocking else "WARNING",
                path=f"unresolved_questions[{index}]",
                message=f"{question.code}: {question.question}",
                repair_strategy="human",
                evidence={
                    "affected_path": question.affected_path,
                },
            )

    def validate(self) -> MappingValidationReport:
        self._validate_objects()
        self._validate_events()
        self._validate_relationships()
        self._validate_unresolved_questions()

        status: Literal["PASS", "FAIL"] = (
            "FAIL"
            if any(issue.severity == "ERROR" for issue in self.issues)
            else "PASS"
        )

        return MappingValidationReport(
            status=status,
            checks_run=self.checks_run,
            issues=self.issues,
        )


def validate_proposal_files(
    proposal_path: str | Path,
    source_profile_path: str | Path,
    database_path: str | Path | None = None,
) -> tuple[MappingProposal, MappingValidationReport]:
    """Đọc proposal/profile rồi chạy MAP-QC."""

    proposal = MappingProposal.model_validate_json(
        Path(proposal_path).read_text(encoding="utf-8")
    )
    source_profile = json.loads(
        Path(source_profile_path).read_text(encoding="utf-8")
    )

    report = MappingValidator(
        proposal=proposal,
        source_profile=source_profile,
        database_path=database_path,
    ).validate()

    return proposal, report


def save_validation_report(
    report: MappingValidationReport,
    output_path: str | Path,
) -> Path:
    """Ghi report JSON để audit và làm input cho LLM repair."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def validate_and_publish_mapping(
    proposal_path: str | Path,
    source_profile_path: str | Path,
    database_path: str | Path,
    report_path: str | Path,
    published_mapping_path: str | Path,
    runtime_database_path: str,
) -> MappingValidationReport:
    """
    Chạy MAP-QC và chỉ publish YAML nếu tất cả ERROR đã hết.

    Nếu FAIL, file config hiện có không bị ghi/xóa/ghi đè.
    """

    _, report = validate_proposal_files(
        proposal_path=proposal_path,
        source_profile_path=source_profile_path,
        database_path=database_path,
    )
    save_validation_report(report, report_path)

    if report.status == "PASS":
        compile_proposal_file(
            proposal_path=proposal_path,
            output_path=published_mapping_path,
            source_database_path=runtime_database_path,
        )

    return report
