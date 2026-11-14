from __future__ import annotations

import json
import sqlite3

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProfilerConfig:
    """
    Cấu hình giới hạn dữ liệu và chi phí chạy source profiler.

    max_key_width:
        Số cột tối đa được thử khi tìm khóa ghép.
        Không nên đặt quá lớn vì số tổ hợp tăng rất nhanh.

    max_candidate_columns:
        Chỉ các cột được đánh giá có khả năng làm khóa cao nhất
        mới được đưa vào quá trình thử khóa ghép.

    redact_columns:
        Các cột không được đưa giá trị thật vào sample_rows.
        Có thể khai báo theo tên cột hoặc "table.column".
    """

    sample_rows_per_table: int = 50
    max_sample_string_length: int = 120

    max_key_width: int = 3
    max_candidate_columns: int = 8
    max_key_candidates: int = 10

    infer_foreign_keys: bool = True

    redact_columns: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "NationalIDNumber",
                "LoginID",
                "EmailAddress",
                "PhoneNumber",
            }
        )
    )


def quote_identifier(identifier: str) -> str:
    """
    Quote tên bảng/cột an toàn cho SQLite.

    Không thể truyền tên bảng hoặc tên cột bằng SQL parameter `?`.
    Vì vậy tên identifier phải được quote và escape dấu `"`.
    """

    return '"' + identifier.replace('"', '""') + '"'


def sqlite_affinity(declared_type: str | None) -> str:
    """
    Chuyển declared type của SQLite thành SQLite type affinity.

    SQLite không quản lý kiểu chặt như PostgreSQL/MySQL.
    Ví dụ VARCHAR, NVARCHAR và TEXT đều có affinity TEXT.
    """

    type_name = (declared_type or "").upper()

    if "INT" in type_name:
        return "INTEGER"

    if any(item in type_name for item in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"

    if "BLOB" in type_name or not type_name:
        return "BLOB"

    if any(item in type_name for item in ("REAL", "FLOA", "DOUB")):
        return "REAL"

    return "NUMERIC"


def list_user_tables(connection: sqlite3.Connection) -> list[str]:
    """
    Lấy các bảng nghiệp vụ, bỏ qua bảng nội bộ sqlite_*.
    """

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return [row["name"] for row in rows]


def get_row_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    """Đếm tổng số dòng của một bảng."""

    query = f"SELECT COUNT(*) AS row_count FROM {quote_identifier(table_name)}"

    return int(connection.execute(query).fetchone()["row_count"])


def read_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Đọc schema cột bằng PRAGMA table_info.

    Trường `pk_position`:
        0  -> không thuộc primary key
        1+ -> thứ tự của cột trong primary key ghép
    """

    query = f"PRAGMA table_info({quote_identifier(table_name)})"
    rows = connection.execute(query).fetchall()

    columns: list[dict[str, Any]] = []

    for row in rows:
        pk_position = int(row["pk"])

        columns.append(
            {
                "name": row["name"],
                "type": row["type"] or "",
                "affinity": sqlite_affinity(row["type"]),
                # Primary key về mặt logic được coi là không nullable.
                "is_nullable": not (
                    bool(row["notnull"]) or pk_position > 0
                ),
                "default_value": row["dflt_value"],
                "pk_position": pk_position,
            }
        )

    return columns


def read_declared_foreign_keys(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Đọc foreign key được khai báo thật trong SQLite.

    `PRAGMA foreign_key_list` trả một row cho mỗi cột FK.
    Các row có cùng `id` thuộc cùng một foreign key ghép,
    vì vậy phải group theo `id`.
    """

    query = f"PRAGMA foreign_key_list({quote_identifier(table_name)})"
    rows = connection.execute(query).fetchall()

    grouped_foreign_keys: dict[int, dict[str, Any]] = {}

    for row in rows:
        foreign_key_id = int(row["id"])

        foreign_key = grouped_foreign_keys.setdefault(
            foreign_key_id,
            {
                "columns": [],
                "referenced_table": row["table"],
                "referenced_columns": [],
                "on_update": row["on_update"],
                "on_delete": row["on_delete"],
                "origin": "declared_foreign_key",
            },
        )

        foreign_key["columns"].append(row["from"])
        foreign_key["referenced_columns"].append(row["to"])

    return list(grouped_foreign_keys.values())


def add_column_statistics(
    connection: sqlite3.Connection,
    table_name: str,
    columns: list[dict[str, Any]],
    row_count: int,
) -> None:
    """
    Thêm null_count và distinct_count cho từng cột.

    Hàm thay đổi trực tiếp các dictionary trong `columns`.

    Những statistics này rất hữu ích cho LLM:
    - null_count = 0 giúp nhận diện cột khóa.
    - distinct_count gần row_count gợi ý identifier.
    - distinct_count nhỏ gợi ý enum/status/category.
    """

    quoted_table = quote_identifier(table_name)

    for column in columns:
        quoted_column = quote_identifier(column["name"])

        query = f"""
            SELECT
                COUNT({quoted_column}) AS non_null_count,
                COUNT(DISTINCT {quoted_column}) AS distinct_count
            FROM {quoted_table}
        """

        stats = connection.execute(query).fetchone()

        non_null_count = int(stats["non_null_count"])
        distinct_count = int(stats["distinct_count"])

        column["null_count"] = row_count - non_null_count
        column["distinct_count"] = distinct_count
        column["distinct_ratio"] = (
            distinct_count / row_count if row_count > 0 else 0.0
        )


def get_declared_primary_key(
    columns: list[dict[str, Any]],
) -> list[str]:
    """
    Lấy primary key theo đúng thứ tự khai báo.

    Với khóa ghép, pk_position lần lượt là 1, 2, 3...
    """

    primary_key_columns = [
        column
        for column in columns
        if column["pk_position"] > 0
    ]

    primary_key_columns.sort(
        key=lambda column: column["pk_position"]
    )

    return [column["name"] for column in primary_key_columns]


def get_key_statistics(
    connection: sqlite3.Connection,
    table_name: str,
    key_columns: list[str],
) -> dict[str, int]:
    """
    Kiểm tra một tập cột có phải candidate key không.

    Một candidate key hợp lệ trên snapshot hiện tại cần:

        null_row_count == 0
        distinct_key_count == row_count

    Với khóa ghép, SQLite không hỗ trợ:

        COUNT(DISTINCT col1, col2)

    nên cần dùng subquery GROUP BY.
    """

    quoted_table = quote_identifier(table_name)
    quoted_columns = [
        quote_identifier(column)
        for column in key_columns
    ]

    null_condition = " OR ".join(
        f"{column} IS NULL"
        for column in quoted_columns
    )

    not_null_condition = " AND ".join(
        f"{column} IS NOT NULL"
        for column in quoted_columns
    )

    group_by_columns = ", ".join(quoted_columns)

    null_query = f"""
        SELECT COUNT(*) AS null_row_count
        FROM {quoted_table}
        WHERE {null_condition}
    """

    distinct_query = f"""
        SELECT COUNT(*) AS distinct_key_count
        FROM (
            SELECT 1
            FROM {quoted_table}
            WHERE {not_null_condition}
            GROUP BY {group_by_columns}
        )
    """

    null_row_count = int(
        connection.execute(null_query).fetchone()["null_row_count"]
    )

    distinct_key_count = int(
        connection.execute(distinct_query).fetchone()["distinct_key_count"]
    )

    return {
        "null_row_count": null_row_count,
        "distinct_key_count": distinct_key_count,
    }


def rank_candidate_key_columns(
    columns: list[dict[str, Any]],
    config: ProfilerConfig,
) -> list[str]:
    """
    Chọn các cột có khả năng tham gia business key.

    Không thử mọi tổ hợp cột vì nếu bảng có 30 cột thì số tổ hợp
    có thể rất lớn. Thay vào đó, chấm điểm dựa trên:

    - Tên giống identifier: id, number, code, key.
    - Không có null.
    - Distinct ratio cao.
    - Kiểu INTEGER hoặc TEXT.
    """

    ranked_columns: list[tuple[float, str]] = []

    for column in columns:
        if column["null_count"] > 0:
            continue

        if column["distinct_count"] <= 1:
            continue

        if column["affinity"] == "BLOB":
            continue

        name = column["name"].lower()
        score = float(column["distinct_ratio"]) * 10

        if column["pk_position"] > 0:
            score += 100

        if name == "id" or name.endswith("_id") or name.endswith("id"):
            score += 20

        if any(token in name for token in ("number", "code", "key")):
            score += 10

        if column["affinity"] in {"INTEGER", "TEXT"}:
            score += 2

        ranked_columns.append((score, column["name"]))

    ranked_columns.sort(
        key=lambda item: (-item[0], item[1])
    )

    return [
        column_name
        for _, column_name in ranked_columns[
            : config.max_candidate_columns
        ]
    ]


def infer_primary_key_candidates(
    connection: sqlite3.Connection,
    table_name: str,
    columns: list[dict[str, Any]],
    row_count: int,
    config: ProfilerConfig,
) -> list[dict[str, Any]]:
    """
    Tìm primary/business key candidate.

    Thứ tự:
    1. Khóa chính được khai báo trong SQLite.
    2. Khóa đơn unique và không null.
    3. Khóa ghép unique và không null.

    Candidate suy luận chỉ đúng với snapshot hiện tại. Nó có thể
    tình cờ unique nhưng không phải khóa nghiệp vụ thật.
    """

    candidates: list[dict[str, Any]] = []
    known_candidate_sets: set[frozenset[str]] = set()

    declared_primary_key = get_declared_primary_key(columns)

    if declared_primary_key:
        stats = get_key_statistics(
            connection,
            table_name,
            declared_primary_key,
        )

        candidates.append(
            {
                "columns": declared_primary_key,
                "origin": "declared_primary_key",
                "confidence": 1.0,
                **stats,
            }
        )

        known_candidate_sets.add(
            frozenset(declared_primary_key)
        )

    if row_count == 0:
        return candidates

    candidate_pool = rank_candidate_key_columns(
        columns,
        config,
    )

    # Kiểm tra khóa đơn trước.
    for column_name in candidate_pool:
        column = next(
            column
            for column in columns
            if column["name"] == column_name
        )

        if (
            column["null_count"] == 0
            and column["distinct_count"] == row_count
        ):
            candidate_set = frozenset({column_name})

            if candidate_set in known_candidate_sets:
                continue

            name = column_name.lower()

            confidence = (
                0.85
                if name == "id" or name.endswith("id")
                else 0.75
            )

            candidates.append(
                {
                    "columns": [column_name],
                    "origin": "inferred_snapshot_unique",
                    "confidence": confidence,
                    "null_row_count": 0,
                    "distinct_key_count": row_count,
                }
            )

            known_candidate_sets.add(candidate_set)

    max_width = min(
        config.max_key_width,
        len(candidate_pool),
    )

    # Thử khóa ghép, bắt đầu từ 2 cột.
    for width in range(2, max_width + 1):
        for combination in combinations(candidate_pool, width):
            combination_set = frozenset(combination)

            # Nếu một tập con đã unique thì tổ hợp lớn hơn không còn
            # là minimal candidate key và không cần kiểm tra tiếp.
            if any(
                existing_set < combination_set
                for existing_set in known_candidate_sets
            ):
                continue

            stats = get_key_statistics(
                connection,
                table_name,
                list(combination),
            )

            if (
                stats["null_row_count"] == 0
                and stats["distinct_key_count"] == row_count
            ):
                candidates.append(
                    {
                        "columns": list(combination),
                        "origin": "inferred_snapshot_unique",
                        "confidence": 0.70,
                        **stats,
                    }
                )

                known_candidate_sets.add(combination_set)

            if len(candidates) >= config.max_key_candidates:
                return candidates

    return candidates


def should_redact_column(
    table_name: str,
    column_name: str,
    config: ProfilerConfig,
) -> bool:
    """Kiểm tra cột có cần ẩn khỏi sample row hay không."""

    redacted_names = {
        name.lower()
        for name in config.redact_columns
    }

    return (
        column_name.lower() in redacted_names
        or f"{table_name}.{column_name}".lower() in redacted_names
    )


def make_json_safe_value(
    value: Any,
    max_string_length: int,
) -> Any:
    """
    Chuyển giá trị SQLite thành dạng an toàn để ghi JSON.

    Không gửi nội dung BLOB. Chuỗi dài được cắt để giảm token.
    """

    if value is None:
        return None

    if isinstance(value, bytes):
        return f"<BLOB:{len(value)} bytes>"

    if isinstance(value, (int, float, bool)):
        return value

    text = str(value)

    if len(text) > max_string_length:
        return text[:max_string_length] + "...<truncated>"

    return text


def read_sample_rows(
    connection: sqlite3.Connection,
    table_name: str,
    columns: list[dict[str, Any]],
    primary_key_candidates: list[dict[str, Any]],
    config: ProfilerConfig,
) -> list[dict[str, Any]]:
    """
    Lấy một số row mẫu nhỏ để LLM hiểu ngữ nghĩa dữ liệu.

    Nếu có candidate key, ORDER BY candidate key để kết quả sample
    ổn định hơn giữa các lần chạy.
    """

    if config.sample_rows_per_table <= 0:
        return []

    quoted_table = quote_identifier(table_name)

    order_by_clause = ""

    if primary_key_candidates:
        ordering_columns = primary_key_candidates[0]["columns"]

        order_by_clause = " ORDER BY " + ", ".join(
            quote_identifier(column)
            for column in ordering_columns
        )

    query = (
        f"SELECT * FROM {quoted_table}"
        f"{order_by_clause} "
        f"LIMIT ?"
    )

    rows = connection.execute(
        query,
        (config.sample_rows_per_table,),
    ).fetchall()

    samples: list[dict[str, Any]] = []

    for row in rows:
        sample: dict[str, Any] = {}

        for column in columns:
            column_name = column["name"]

            if should_redact_column(
                table_name,
                column_name,
                config,
            ):
                sample[column_name] = "<REDACTED>"
                continue

            sample[column_name] = make_json_safe_value(
                row[column_name],
                config.max_sample_string_length,
            )

        samples.append(sample)

    return samples


def count_foreign_key_orphans(
    connection: sqlite3.Connection,
    source_table: str,
    source_column: str,
    target_table: str,
    target_column: str,
) -> int:
    """
    Đếm giá trị source không tìm thấy trong target.

    Dùng NOT EXISTS thay vì NOT IN để tránh vấn đề logic NULL.
    """

    source_table_sql = quote_identifier(source_table)
    source_column_sql = quote_identifier(source_column)

    target_table_sql = quote_identifier(target_table)
    target_column_sql = quote_identifier(target_column)

    query = f"""
        SELECT COUNT(*) AS orphan_count
        FROM {source_table_sql} AS source
        WHERE source.{source_column_sql} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM {target_table_sql} AS target
              WHERE target.{target_column_sql}
                    = source.{source_column_sql}
          )
    """

    return int(
        connection.execute(query).fetchone()["orphan_count"]
    )


def infer_foreign_key_candidates(
    connection: sqlite3.Connection,
    table_profiles: list[dict[str, Any]],
) -> None:
    """
    Suy luận FK candidate đơn giản từ các cột trùng tên.

    Ví dụ:
        PurchaseOrderItems.material_number
        Materials.material_number

    Chỉ suy luận khi:
    - Cột target là candidate key đơn.
    - Tên cột source và target giống nhau.
    - Không có orphan.

    Kết quả nằm trong `foreign_key_candidates`, không trộn với
    `foreign_keys`, vì đây không phải constraint thật của SQLite.
    """

    target_keys: list[tuple[str, str]] = []

    for target_table in table_profiles:
        for candidate in target_table["primary_key_candidates"]:
            if len(candidate["columns"]) == 1:
                target_keys.append(
                    (
                        target_table["name"],
                        candidate["columns"][0],
                    )
                )

    for source_table in table_profiles:
        source_column_names = {
            column["name"].lower(): column["name"]
            for column in source_table["columns"]
        }

        inferred_candidates: list[dict[str, Any]] = []

        for target_table_name, target_column_name in target_keys:
            if source_table["name"] == target_table_name:
                continue

            matching_source_name = source_column_names.get(
                target_column_name.lower()
            )

            if matching_source_name is None:
                continue

            orphan_count = count_foreign_key_orphans(
                connection=connection,
                source_table=source_table["name"],
                source_column=matching_source_name,
                target_table=target_table_name,
                target_column=target_column_name,
            )

            if orphan_count == 0:
                inferred_candidates.append(
                    {
                        "columns": [matching_source_name],
                        "referenced_table": target_table_name,
                        "referenced_columns": [target_column_name],
                        "origin": "inferred_by_name_and_containment",
                        "confidence": 0.85,
                        "orphan_count": 0,
                    }
                )

        source_table["foreign_key_candidates"] = inferred_candidates


def profile_sqlite(
    database_path: str | Path,
    config: ProfilerConfig | None = None,
) -> dict[str, Any]:
    """
    Hàm chính: tạo profile JSON cho một SQLite database.

    Database được mở bằng `mode=ro`, vì profiler chỉ được phép đọc.
    """

    config = config or ProfilerConfig()
    database_path = Path(database_path).resolve()

    if not database_path.exists():
        raise FileNotFoundError(
            f"SQLite database does not exist: {database_path}"
        )

    connection_uri = database_path.as_uri() + "?mode=ro"

    connection = sqlite3.connect(
        connection_uri,
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    try:
        table_profiles: list[dict[str, Any]] = []

        for table_name in list_user_tables(connection):
            row_count = get_row_count(
                connection,
                table_name,
            )

            columns = read_table_columns(
                connection,
                table_name,
            )

            add_column_statistics(
                connection=connection,
                table_name=table_name,
                columns=columns,
                row_count=row_count,
            )

            primary_key_candidates = (
                infer_primary_key_candidates(
                    connection=connection,
                    table_name=table_name,
                    columns=columns,
                    row_count=row_count,
                    config=config,
                )
            )

            table_profile = {
                "name": table_name,
                "row_count": row_count,
                "columns": columns,
                "declared_primary_key": (
                    get_declared_primary_key(columns)
                ),
                "primary_key_candidates": (
                    primary_key_candidates
                ),
                "foreign_keys": read_declared_foreign_keys(
                    connection,
                    table_name,
                ),
                "foreign_key_candidates": [],
                "sample_rows": read_sample_rows(
                    connection=connection,
                    table_name=table_name,
                    columns=columns,
                    primary_key_candidates=(
                        primary_key_candidates
                    ),
                    config=config,
                ),
            }

            table_profiles.append(table_profile)

        if config.infer_foreign_keys:
            infer_foreign_key_candidates(
                connection,
                table_profiles,
            )

        return {
            "profile_version": "1.0",
            "database": {
                # Không đưa absolute path vào context gửi LLM.
                "name": database_path.name,
                "table_count": len(table_profiles),
            },
            "tables": table_profiles,
        }

    finally:
        connection.close()


def save_profile(
    profile: dict[str, Any],
    output_path: str | Path,
) -> None:
    """Ghi profile ra JSON UTF-8 để kiểm tra và audit."""

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            profile,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )