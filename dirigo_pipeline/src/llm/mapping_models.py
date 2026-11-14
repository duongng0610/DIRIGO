from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class StrictModel(BaseModel):
    """
    Base model chung.

    extra="forbid" ngăn LLM tự sinh thêm field không thuộc schema.
    Ví dụ LLM sinh `description`, `sql` hoặc `join_query`
    ngoài định nghĩa thì Pydantic sẽ báo lỗi.
    """

    model_config = ConfigDict(extra="forbid")


ScalarValue = str | int | float | bool


class FilterCondition(StrictModel):
    """
    Một điều kiện lọc source row.

    Ví dụ:

        EndDate IS NOT NULL

    được biểu diễn:

        {
            "column": "EndDate",
            "operator": "is_not_null",
            "value": null,
            "values": []
        }

    Với operator `in`, dùng `values` thay cho `value`.
    """

    column: str

    operator: Literal[
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "is_null",
        "is_not_null",
    ]

    value: ScalarValue | None = None
    values: list[ScalarValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operator_value(self) -> "FilterCondition":
        """Kiểm tra value phù hợp với từng operator."""

        if self.operator in {"in", "not_in"} and not self.values:
            raise ValueError(
                f"Operator '{self.operator}' requires non-empty values"
            )

        if self.operator in {"is_null", "is_not_null"}:
            if self.value is not None or self.values:
                raise ValueError(
                    f"Operator '{self.operator}' must not have value"
                )

        if self.operator not in {
            "in",
            "not_in",
            "is_null",
            "is_not_null",
        }:
            if self.value is None:
                raise ValueError(
                    f"Operator '{self.operator}' requires value"
                )

        return self


class IdMapping(StrictModel):
    """
    Cách sinh ID của object hoặc event.

    direct:
        Lấy trực tiếp một cột.
        Ví dụ BusinessEntityID.

    option:
        Ghép prefix và một hoặc nhiều cột.
        Ví dụ:
            prefix = "assignment"
            columns = ["BusinessEntityID", "StartDate"]

        Kết quả:
            assignment-1-2020-01-01
    """

    mode: Literal["direct", "option"]

    columns: list[str] = Field(min_length=1)

    prefix: str | None = None
    separator: str = "-"

    @model_validator(mode="after")
    def validate_id_mapping(self) -> "IdMapping":
        if self.mode == "direct" and len(self.columns) != 1:
            raise ValueError(
                "Direct ID mapping must contain exactly one column"
            )

        if self.mode == "option" and not self.prefix:
            raise ValueError(
                "Option ID mapping requires a non-empty prefix"
            )

        return self


class TimestampMapping(StrictModel):
    """Cột được dùng làm timestamp."""

    column: str


class ValueMapping(StrictModel):
    """Nguồn của một giá trị attribute."""

    column: str

    value_type: Literal[
        "string",
        "integer",
        "decimal",
        "boolean",
        "datetime",
    ]


class KeyColumnMapping(StrictModel):
    """
    Ánh xạ từ cột canonical trong object ID config
    sang cột của row hiện tại.

    Ví dụ object employee dùng:

        id.columns = ["BusinessEntityID"]

    Bảng history cũng có BusinessEntityID:

        object_id_column = "BusinessEntityID"
        row_column = "BusinessEntityID"

    Nếu sau lookup, `row_column` được hiểu là cột ở lookup row.
    """

    object_id_column: str
    row_column: str


class JoinColumnMapping(StrictModel):
    """
    Một cặp cột dùng để join source row với lookup table.

    source_column:
        Cột trong bảng đang duyệt.

    lookup_column:
        Cột trong resolver.lookup_table.
    """

    source_column: str
    lookup_column: str


class ResolverMapping(StrictModel):
    """
    Cấu hình lookup khi object ID không có trực tiếp trong source row.

    Ví dụ order_item cần lookup order_document để lấy customer_id.
    """

    lookup_table: str

    joins: list[JoinColumnMapping] = Field(min_length=1)

    where: list[FilterCondition] = Field(default_factory=list)

    expected_cardinality: Literal[
        "exactly_one",
        "zero_or_one",
    ] = "exactly_one"


class ObjectReference(StrictModel):
    """
    Cách một event, dynamic attribute hoặc O2O tham chiếu object.

    mode=direct:
        ID được build trực tiếp từ row hiện tại.

    mode=lookup:
        Cần lookup sang bảng khác trước khi build ID.
    """

    object_type: str

    mode: Literal["direct", "lookup"]

    key_mapping: list[KeyColumnMapping] = Field(min_length=1)

    resolver: ResolverMapping | None = None

    @model_validator(mode="after")
    def validate_reference_mode(self) -> "ObjectReference":
        if self.mode == "direct" and self.resolver is not None:
            raise ValueError(
                "Direct object reference must not contain resolver"
            )

        if self.mode == "lookup" and self.resolver is None:
            raise ValueError(
                "Lookup object reference requires resolver"
            )

        return self


class StaticAttributeMapping(StrictModel):
    """Một thuộc tính tĩnh của object."""

    name: str
    value: ValueMapping


class DynamicAttributeMapping(StrictModel):
    """
    Một thuộc tính động.

    Mỗi source row hợp lệ sẽ tạo một ObjectChangeRecord,
    trừ khi change policy sau này định nghĩa khác.
    """

    name: str

    source_table: str

    value: ValueMapping
    timestamp: TimestampMapping

    object_reference: ObjectReference

    where: list[FilterCondition] = Field(default_factory=list)


class ObjectAttributesMapping(StrictModel):
    """Nhóm thuộc tính tĩnh và động của object."""

    static: list[StaticAttributeMapping] = Field(
        default_factory=list
    )

    dynamic: list[DynamicAttributeMapping] = Field(
        default_factory=list
    )


class ObjectMapping(StrictModel):
    """Mapping hoàn chỉnh cho một object type."""

    type: str
    source_table: str

    id: IdMapping

    attributes: ObjectAttributesMapping


class EventAttributeMapping(StrictModel):
    """Thuộc tính của event nếu dataset có event attributes."""

    name: str
    value: ValueMapping


class EventObjectMapping(StrictModel):
    """
    Một object tham gia event.

    qualifier mô tả vai trò object trong event,
    không chỉ lặp lại object type.
    """

    reference: ObjectReference
    qualifier: str


class EventMapping(StrictModel):
    """Mapping cho một event type."""

    type: str
    source_table: str

    id: IdMapping
    timestamp: TimestampMapping

    where: list[FilterCondition] = Field(default_factory=list)

    attributes: list[EventAttributeMapping] = Field(
        default_factory=list
    )

    objects: list[EventObjectMapping] = Field(
        min_length=1
    )


class RelationshipMapping(StrictModel):
    """
    Mapping cho một O2O relationship.

    static:
        Quan hệ không có timestamp trong mapping.

    dynamic:
        Bắt buộc phải có timestamp nguồn.

    Không dùng timestamp giả như 1 cho static relationship.
    Nếu output format cần giá trị đại diện thì builder/extractor
    quyết định, không phải LLM.
    """

    name: str
    source_table: str

    source: ObjectReference
    target: ObjectReference

    qualifier: str

    relation_mode: Literal["static", "dynamic"]

    timestamp: TimestampMapping | None = None

    where: list[FilterCondition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relationship_timestamp(
        self,
    ) -> "RelationshipMapping":
        if self.relation_mode == "dynamic":
            if self.timestamp is None:
                raise ValueError(
                    "Dynamic relationship requires timestamp"
                )

        if self.relation_mode == "static":
            if self.timestamp is not None:
                raise ValueError(
                    "Static relationship must not contain timestamp"
                )

        return self


class DirigoMappingConfig(StrictModel):
    """
    Phần mapping có thể được compile thành YAML sau khi MAP-QC pass.
    """

    dataset_name: str

    objects: list[ObjectMapping] = Field(default_factory=list)

    events: list[EventMapping] = Field(default_factory=list)

    relationships: list[RelationshipMapping] = Field(
        default_factory=list
    )


class MappingDecision(StrictModel):
    """
    Evidence giải thích một quyết định của LLM.

    mapping_path dùng cú pháp gần giống JSON path, ví dụ:

        objects[employee].id
        events[employee_hired].timestamp
    """

    mapping_path: str

    confidence: float = Field(ge=0.0, le=1.0)

    evidence: list[str] = Field(default_factory=list)

    assumptions: list[str] = Field(default_factory=list)


class UnresolvedQuestion(StrictModel):
    """
    Điểm LLM chưa đủ evidence để quyết định.

    blocking=True nghĩa là không nên compile proposal thành
    production YAML trước khi người dùng trả lời.
    """

    code: str
    affected_path: str

    question: str
    blocking: bool


class MappingProposal(StrictModel):
    """
    Output đầy đủ của tầng Mapping Proposer.

    Chỉ trường `mapping` được compile sang YAML.
    decisions và unresolved_questions dùng cho audit/review.
    """

    mapping: DirigoMappingConfig

    decisions: list[MappingDecision] = Field(
        default_factory=list
    )

    unresolved_questions: list[UnresolvedQuestion] = Field(
        default_factory=list
    )