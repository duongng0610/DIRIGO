from typing import Any
import pandas as pd
from pandas import DataFrame
from src.readers.sqlite_reader import SQLiteReader
#Lấy tên thật của bảng trong data , source_table chỉ là alias
def _source_table_name(source_table: str, table_mapping: dict[str, dict]) -> str:
    return table_mapping.get(source_table, {}).get("table", source_table)


def build_data_frame_by_table_name(sqlite_reader: SQLiteReader, table_name:str, table_mapping: dict[str, dict]) -> DataFrame:
    normalize_table = _source_table_name(
                 table_name,
                 table_mapping,
            )

    df = sqlite_reader.read_table(normalize_table)

    if df is None:
                raise ValueError(
                    f"Cannot read lookup table: {normalize_table}"
                )   
    return df

def create_option_id(prefix: str, columns: list[str], separator) -> str:
    if not prefix or not columns:
        raise ValueError(
            "columns, and separator must be provided to create an option ID."
        )

    if not separator:
        separator = "-"

    return f"{prefix}{separator}{separator.join(columns)}"

#chuẩn hóa id => string
def normalize_id_value(value: Any, column: str) -> str:
    if pd.isna(value):
        raise ValueError(
            f"ID column '{column}' cannot be null"
        )

    # Tránh ID dạng EMP-1.0 khi giá trị thực chất là integer
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return str(value)

#Đọc bảng lookup 1 lần và tạo index theo giá trị key của row :row[key] 
def build_resolver_index(
    sqlite_reader:SQLiteReader,
    object_mapping: dict[str, Any]|None,
    mapping: dict[str,Any]
) -> dict[tuple, Any]:
    
    resolver_mapping = object_mapping.get("resolver")
    
    if resolver_mapping is None:
        return None

    lookup_df = build_data_frame_by_table_name(
                    sqlite_reader, 
                    resolver_mapping["table"], 
                    mapping["tables"])
    
    if resolver_mapping is None :
        return None
    lookup_index = {}

    # on:
        #     - source_column
        #       lookup_column
    join_mappings = resolver_mapping["on"] 

    for _, lookup_row in lookup_df.iterrows():

        #lookup_key build bởi lookup_column (vì ở trong bảng lookup)
        lookup_key = tuple(
            normalize_id_value(
                lookup_row[item["lookup_column"]],
                item["lookup_column"],
            )
            for item in join_mappings
        )

        lookup_index[lookup_key] = lookup_row

    return lookup_index

#Tra lookup row
def resolve_lookup_row(
        row,
        resolver_mapping: dict[str, Any],
        lookup_index : dict[tuple, Any]
):
    join_mappings = resolver_mapping["on"]

    #source key build bởi giá trị source_column (vì trong bảng chứa events)
    source_key = tuple(
        normalize_id_value(
            row[item["source_column"]], 
            item["source_column"]
        )
        for item in join_mappings
    )

    lookup_row = lookup_index.get(source_key)

    if lookup_row is None:
        raise ValueError(
            f"Cannot resolve lookup key: {source_key}"
        )

    return lookup_row


#key_mapping: khi tên key trong bảng khác với tên cột key gốc được cấu hình ở object
def build_id_from_row (row , id_mapping :dict[str,Any], key_mapping: dict[str,str] | None = None)->str:
      key_mapping = key_mapping or {}

      mode = id_mapping["mode"]
      id_columns = id_mapping["columns"]

      values : list[str] = []

      for object_id_column in id_columns:
             # cột canonical của object -> cột trong row hiện tại
            row_column = key_mapping.get(
                object_id_column,
                object_id_column,
            )
            if row_column not in row.index:
                raise KeyError(
                    f"Column '{row_column}' required for "
                    f"object ID column '{object_id_column}' "
                    "does not exist"
                )
            value = row[row_column]
            #value có thể là số nguyên => cần chuẩn hóa sang str
            values.append(normalize_id_value(value, row_column))

     
      if mode == "option":
        return create_option_id(
            prefix= id_mapping["prefix"],
            columns = values,
            separator=id_mapping.get("separator"),
            )
    
      else:
        if len(values) != 1:
            raise ValueError(
                "Raw ID mode requires exactly one column"
            )
        return values[0]

   
#object_config : cấu hình yaml object ở phần objects 
#object_mapping: cấu hình yaml object trong relationships / e2o .
#Trường hợp cần tìm giá trị id của object ở bảng khác : lookup_index: map[key]value (key-tạo bởi row[cột khóa ngoại],  value- row ở bảng tìm kiếm  )
def build_object_reference_id(
        row, 
        object_config: dict[str,any],
        object_mapping:dict[str, any],
        lookup_index: dict[tuple, Any] | None = None)->str:

    resolver_mapping = object_mapping.get("resolver")

    key_mapping =  object_mapping.get("key_mapping")

    id_mapping = object_config["id"]

     # Trường hợp direct
    if resolver_mapping is None:
        return build_id_from_row(
            row=row,
            id_mapping=id_mapping ,
            key_mapping= key_mapping
        )

    resolver_mode = resolver_mapping.get("mode")
    
    if resolver_mode != "lookup":
        raise ValueError(
            f"Unsupported resolver mode: {resolver_mode}"
        )

    #lookup_index luôn được build trước khi duyệt từng row 
    if lookup_index is None:
        raise ValueError(
            "Lookup index is required for lookup resolver"
        )

    lookup_row = resolve_lookup_row(
        row=row,
        resolver_mapping=resolver_mapping,
        lookup_index=lookup_index,
    )

    return build_id_from_row(
        row= lookup_row, 
        id_mapping= id_mapping,
        key_mapping= key_mapping
    )


