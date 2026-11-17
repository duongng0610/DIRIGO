"""Adapter đọc SQLite và áp dụng các filter đã compile từ mapping YAML."""

import sqlite3
from typing import Optional

import pandas as pd


CONDITIONS = {
    "is_not_null": lambda s, v: s.notna(),
    "is_null": lambda s, v: s.isna(),
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "gte": lambda s, v: s >= v,
    "lt": lambda s, v: s < v,
    "lte": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v),
    "not_in": lambda s, v: ~s.isin(v),
}


class SQLiteReader:
    """Cung cấp các thao tác DataFrame tối thiểu mà builders cần.

    Mapping validator chịu trách nhiệm kiểm tra bảng/cột trước khi build;
    reader tập trung vào đọc dữ liệu, lọc row và join. Các method đọc hiện
    trả ``None``/danh sách rỗng sau khi in lỗi để tương thích code cũ.
    """

    def __init__(self, db_path):
        """Lưu đường dẫn database; connection chỉ mở khi có thao tác đọc."""
        self.db_path = db_path

    def read_table(self, table_name):
        """Đọc toàn bộ bảng thành DataFrame.

        Tên bảng đến từ mapping đã qua MAP-QC, không phải input trực tiếp từ
        người dùng cuối. Khi đọc lỗi, method hiện in thông báo và trả ``None``.
        """
        try:
            conn = sqlite3.connect(self.db_path)

            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            return df
        except Exception as e:
            print(f"Error reading table {table_name}: {e}")
            return None
        finally:
            conn.close()

    def apply_where(self, df: pd.DataFrame, where: list[dict]) -> pd.DataFrame:
        """Áp dụng danh sách điều kiện mapping theo phép AND.

        Mỗi rule đã được compiler đổi về ``column``, ``condition`` và
        ``value``. Mask khởi tạo True để danh sách rule rỗng giữ nguyên mọi
        row; từng rule tiếp theo thu hẹp tập source row hợp lệ.
        """
        if not where:
            return df

        mask = pd.Series(True, index=df.index)
        for rule in where:
            col = rule["column"]
            cond = rule["condition"]
            value = rule.get("value")

            if cond not in CONDITIONS:
                raise ValueError(f"Unsupported condition: {cond}")
            if col not in df.columns:
                raise KeyError(f"Column '{col}' not in dataframe")

            mask &= CONDITIONS[cond](df[col], value)

        return df[mask]

    def get_all_tables(self):
        """Liệt kê toàn bộ table name trong SQLite schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            return tables
        except Exception as e:
            print(f"Error retrieving tables: {e}")
            return []
        finally:
            conn.close()

    def get_joined_data(
        self,
        table1: str,
        table2: str,
        join_columns: list[tuple[str, str]],
        filter_column: list[str] = None,
        filter_value=None,
    ):
        """Inner join hai bảng theo một hay nhiều cặp cột.

        Hàm thuộc flow builder cũ; resolver flow mới ưu tiên tạo lookup index
        một lần bằng ``build_resolver_index``. Nó được giữ để tương thích cho
        tới khi legacy code được loại bỏ.
        """

        try:
            conn = sqlite3.connect(self.db_path)

            conditions = " AND ".join(
                f"{table1}.{col1} = {table2}.{col2}"
                for col1, col2 in join_columns
            )

            filter_clause = ""
            params = None
            if filter_column is not None:
                filter_clause = f"WHERE {table1}.{filter_column} = ?"
                params = [filter_value]

            query = f"""
                SELECT *
                FROM {table1}
                INNER JOIN {table2}
                    ON {conditions}
                {filter_clause}
            """

            df = pd.read_sql_query(query, conn, params=params)
            # SELECT * tạo hai cột trùng tên cho join key; giữ cột bên trái để
            # DataFrame downstream không trả Series khi truy cập theo tên.
            return df.loc[:, ~df.columns.duplicated()]

        except Exception as e:
            print(f"Error joining tables {table1} and {table2}: {e}")
            return None

        finally:
            conn.close()
