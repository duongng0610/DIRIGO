import sqlite3
from typing import Optional

import pandas as pd


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

            return pd.read_sql_query(query, conn, params=params)

        except Exception as e:
            print(f"Error joining tables {table1} and {table2}: {e}")
            return None

        finally:
            conn.close()
