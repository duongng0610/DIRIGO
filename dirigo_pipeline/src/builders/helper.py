def _source_table_name(source_table: str, table_mapping: dict[str, dict]) -> str:
    return table_mapping.get(source_table, {}).get("table", source_table)


def create_option_id(prefix: str, columns: list[str], separator) -> str:
    if not prefix or not columns:
        raise ValueError(
            "columns, and separator must be provided to create an option ID."
        )

    if not separator:
        separator = "-"

    return f"{prefix}{separator}{separator.join(columns)}"
