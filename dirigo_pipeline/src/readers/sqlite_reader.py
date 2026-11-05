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
    def __init__(self, db_path):
        self.db_path = db_path

    def read_table(self, table_name):
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
            # remove duplicated column (keep the first one)
            return df.loc[:, ~df.columns.duplicated()]

        except Exception as e:
            print(f"Error joining tables {table1} and {table2}: {e}")
            return None

        finally:
            conn.close()
