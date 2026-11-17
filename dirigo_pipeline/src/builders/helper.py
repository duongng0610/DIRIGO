"""Các hàm dùng chung để builders đọc bảng, tạo ID và resolve object.

Builders không tự viết logic join riêng. Mọi tham chiếu object đều đi qua
``build_object_reference_id`` để bảo đảm ID được tạo nhất quán giữa object,
event/E2O, O2O và các thuộc tính động.
"""

from typing import Any
import pandas as pd
from pandas import DataFrame
from src.readers.sqlite_reader import SQLiteReader
def _source_table_name(source_table: str, table_mapping: dict[str, dict]) -> str:
    """Đổi alias trong mapping thành tên bảng vật lý trong SQLite.

    Nếu alias không được khai báo trong ``tables``, giá trị đầu vào được coi
    là tên bảng thật. Cơ chế này giúp mapping có thể dùng alias ổn định ngay
    cả khi tên bảng nguồn dài hoặc phụ thuộc dataset.
    """
    return table_mapping.get(source_table, {}).get("table", source_table)


def build_data_frame_by_table_name(sqlite_reader: SQLiteReader, table_name:str, table_mapping: dict[str, dict]) -> DataFrame:
    """Đọc một bảng theo alias và trả về DataFrame bắt buộc tồn tại.

    Reader cũ trả ``None`` khi không đọc được bảng. Builders không thể tiếp
    tục an toàn trong trường hợp đó, vì vậy helper chuyển nó thành lỗi ngay
    tại biên đọc dữ liệu thay vì để lỗi xuất hiện ở một vòng lặp phía sau.
    """
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
    """Ghép prefix và các thành phần khóa thành ID có namespace.

    Ví dụ ``employee`` + ``["12"]`` tạo ``employee-12``. Prefix làm ID
    object duy nhất trên toàn log, tránh va chạm khi hai object type dùng
    cùng một giá trị khóa nguồn.
    """
    if not prefix or not columns:
        raise ValueError(
            "columns, and separator must be provided to create an option ID."
        )

    if not separator:
        separator = "-"

    return f"{prefix}{separator}{separator.join(columns)}"

def normalize_id_value(value: Any, column: str) -> str:
    """Chuẩn hóa một thành phần ID sang chuỗi và từ chối giá trị null.

    Pandas thường chuyển cột integer có null thành float. Nhánh ``1.0 -> 1``
    giữ ID ổn định giữa dữ liệu SQLite, DataFrame và CSV.
    """
    if pd.isna(value):
        raise ValueError(
            f"ID column '{column}' cannot be null"
        )

    # Tránh ID dạng EMP-1.0 khi giá trị thực chất là integer
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return str(value)

def build_resolver_index(
    sqlite_reader:SQLiteReader,
    object_mapping: dict[str, Any]|None,
    mapping: dict[str,Any]
) -> dict[tuple, Any]:
    """Tạo index cho object reference cần lookup sang bảng khác.

    Key của index là tuple các ``lookup_column`` theo đúng thứ tự khai báo
    trong ``resolver.on``; value là row đầy đủ của bảng lookup. Index được
    tạo trước vòng lặp source row để không phải scan bảng lookup cho từng
    event, relation hoặc object change.

    Trả ``None`` khi reference là direct và không có resolver.
    """
    
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

    join_mappings = resolver_mapping["on"] 

    for _, lookup_row in lookup_df.iterrows():

        # Ở phía lookup phải dùng lookup_column; source_column chỉ tồn tại
        # trong row đang được builder xử lý.
        lookup_key = tuple(
            normalize_id_value(
                lookup_row[item["lookup_column"]],
                item["lookup_column"],
            )
            for item in join_mappings
        )

        lookup_index[lookup_key] = lookup_row

    return lookup_index

def resolve_lookup_row(
        row,
        resolver_mapping: dict[str, Any],
        lookup_index : dict[tuple, Any]
):
    """Resolve một source row thành đúng một row trong resolver index.

    Source key được tạo bằng ``source_column`` nhưng phải có cùng thứ tự và
    cách chuẩn hóa với lookup key. Không tìm thấy row là lỗi vì callers hiện
    cần một row cụ thể để tạo object ID.
    """
    join_mappings = resolver_mapping["on"]

    # Source key dùng source_column vì row thuộc bảng event/history/O2O.
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


def build_id_from_row (row , id_mapping :dict[str,Any], key_mapping: dict[str,str] | None = None)->str:
      """Tạo canonical ID từ row theo cấu hình ID của object/event.

      ``id_mapping.columns`` dùng tên cột canonical. ``key_mapping`` ánh xạ
      các tên canonical đó sang tên cột thực tế của row hiện tại, nhờ vậy
      cùng một quy tắc ID có thể dùng cho bảng master, history hoặc lookup.
      """
      key_mapping = key_mapping or {}

      mode = id_mapping["mode"]
      id_columns = id_mapping["columns"]

      values : list[str] = []

      for object_id_column in id_columns:
            # Cột canonical của object -> cột trong row hiện tại.
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
            # Mọi thành phần phải được chuẩn hóa trước khi ghép ID.
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

   
def build_object_reference_id(
        row, 
        object_config: dict[str,any],
        object_mapping:dict[str, any],
        lookup_index: dict[tuple, Any] | None = None)->str:
    """Tạo object ID cho một reference direct hoặc lookup.

    ``object_config`` là định nghĩa canonical trong ``mapping.objects``.
    ``object_mapping`` là cách event/E2O, O2O hoặc dynamic attribute tham
    chiếu object đó. Với direct reference, ID được tạo từ row hiện tại. Với
    lookup reference, row hiện tại được resolve sang bảng khác trước, sau đó
    vẫn dùng chính ID config canonical của object.
    """

    resolver_mapping = object_mapping.get("resolver")

    key_mapping =  object_mapping.get("key_mapping")

    id_mapping = object_config["id"]

    # Direct reference: các cột khóa đã có ngay trên row hiện tại.
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

    # Lookup index phải được chuẩn bị một lần trước vòng lặp source rows.
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


