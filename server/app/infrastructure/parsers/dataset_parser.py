"""数据集解析适配器。

使用 pandas 读取 CSV/Excel 文件，推断字段类型，生成字段概览和质量检查结果。
不执行 Excel 公式或宏，只读取单元格值。
"""

from dataclasses import dataclass, field
from typing import Any


class DatasetParseError(Exception):
    """数据集解析失败的结构化错误。

    code 用于映射到 BackgroundJob.error_code 与 DatasetVersion.error_code。
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass
class FieldProfile:
    """字段概览。

    数值字段额外包含 min/max/mean/median/std/q1/q3。
    字符串字段额外包含 top_values（前 10 高频值）。
    """

    name: str
    inferred_type: str  # int, float, string, datetime, bool
    non_null_count: int
    null_count: int
    null_rate: float
    unique_count: int
    sample_values: list[str]  # 前 5 个非空样例
    # 数值字段额外
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    median_value: float | None = None
    std_value: float | None = None
    q1: float | None = None
    q3: float | None = None
    # 字符串字段额外
    top_values: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class DatasetProfile:
    """数据集质量概览。"""

    row_count: int
    column_count: int
    complete_row_count: int  # 无缺失的行数
    incomplete_row_count: int
    duplicate_row_count: int
    field_profiles: list[FieldProfile]
    quality_score: float  # 0-100


@dataclass
class DatasetParseResult:
    """数据集解析结果。"""

    profile: DatasetProfile
    raw_dataframe: Any  # pandas DataFrame，用于后续生成方案


# --- 字段类型推断 ---


def _infer_field_type(series) -> str:
    """推断字段的数据类型。

    优先级：bool → int → float → datetime → string。
    pandas 的 object 类型尝试推断是否为日期。
    """
    # pandas 的 dtype 推断
    dtype_kind = series.dtype.kind

    if dtype_kind == "b":
        return "bool"
    if dtype_kind in ("i", "u"):
        return "int"
    if dtype_kind == "f":
        return "float"
    if dtype_kind == "M":
        return "datetime"

    # object 类型：尝试转换为 datetime 或数值
    if dtype_kind == "O":
        # 尝试 datetime（用 errors="coerce" 避免格式不一致抛异常）
        try:
            converted = __import__("pandas").to_datetime(series, errors="coerce")
            non_nat = converted.notna().sum()
            # 若非空值中至少 50% 能解析为日期，则判定为 datetime
            non_null_count = int(series.notna().sum())
            if non_null_count > 0 and non_nat / non_null_count >= 0.5:
                return "datetime"
        except Exception:
            pass
        return "string"

    # 默认 string
    return "string"


def _safe_str(value: Any) -> str:
    """将任意值转为字符串，处理 NaN/None。"""
    if value is None:
        return ""
    try:
        # 检查 NaN
        if value != value:  # noqa: PLR0124  NaN != NaN
            return ""
    except Exception:
        pass
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def _build_field_profile(name: str, series) -> FieldProfile:
    """构建单个字段的概览。"""
    inferred_type = _infer_field_type(series)

    # 缺失值统计（pandas 的 isna 涵盖 NaN/NaT/None）
    import pandas as pd

    null_count = int(series.isna().sum())
    non_null_series = series.dropna()
    non_null_count = int(len(non_null_series))
    total_count = int(len(series))
    null_rate = (null_count / total_count) if total_count > 0 else 0.0
    unique_count = int(non_null_series.nunique())

    # 样例值：前 5 个非空值
    sample_values = [_safe_str(v) for v in non_null_series.head(5).tolist()]

    profile = FieldProfile(
        name=str(name),
        inferred_type=inferred_type,
        non_null_count=non_null_count,
        null_count=null_count,
        null_rate=round(null_rate, 4),
        unique_count=unique_count,
        sample_values=sample_values,
    )

    # 数值字段统计
    if inferred_type in ("int", "float"):
        numeric_series = __import__("pandas").to_numeric(non_null_series, errors="coerce").dropna()
        if len(numeric_series) > 0:
            profile.min_value = float(numeric_series.min())
            profile.max_value = float(numeric_series.max())
            profile.mean_value = float(numeric_series.mean())
            profile.median_value = float(numeric_series.median())
            profile.std_value = float(numeric_series.std()) if len(numeric_series) > 1 else 0.0
            profile.q1 = float(numeric_series.quantile(0.25))
            profile.q3 = float(numeric_series.quantile(0.75))

    # 字符串字段高频值
    if inferred_type in ("string", "bool"):
        value_counts = non_null_series.value_counts().head(10)
        profile.top_values = [(_safe_str(v), int(c)) for v, c in value_counts.items()]

    return profile


def _build_quality_profile(df) -> DatasetProfile:
    """构建数据集质量概览。"""
    import pandas as pd

    row_count = int(len(df))
    column_count = int(len(df.columns))

    # 完整行（无缺失）
    complete_mask = df.notna().all(axis=1)
    complete_row_count = int(complete_mask.sum())
    incomplete_row_count = row_count - complete_row_count

    # 重复行
    duplicate_row_count = int(df.duplicated().sum())

    # 字段概览
    field_profiles = [
        _build_field_profile(str(col), df[col]) for col in df.columns
    ]

    # 质量评分：基于缺失率和重复率
    if row_count == 0 or column_count == 0:
        quality_score = 0.0
    else:
        # 总体缺失率
        total_cells = row_count * column_count
        missing_cells = int(df.isna().sum().sum())
        missing_rate = missing_cells / total_cells if total_cells > 0 else 0.0
        duplicate_rate = duplicate_row_count / row_count if row_count > 0 else 0.0
        quality_score = round(max(0.0, 100.0 - missing_rate * 50.0 - duplicate_rate * 50.0), 2)

    return DatasetProfile(
        row_count=row_count,
        column_count=column_count,
        complete_row_count=complete_row_count,
        incomplete_row_count=incomplete_row_count,
        duplicate_row_count=duplicate_row_count,
        field_profiles=field_profiles,
        quality_score=quality_score,
    )


def parse_dataset(file_path: str, file_extension: str) -> DatasetParseResult:
    """解析 CSV/Excel 文件，返回 profile 和原始 DataFrame。

    参数：
        file_path: 文件绝对路径
        file_extension: 文件扩展名（不含点，小写），如 "csv"、"xlsx"

    异常：
        DatasetParseError(code=DATASET_EMPTY)
        DatasetParseError(code=DATASET_PARSE_FAILED)
        DatasetParseError(code=DATASET_TOO_LARGE)
    """
    import pandas as pd

    ext = (file_extension or "").lower().lstrip(".")

    try:
        if ext == "csv":
            df = pd.read_csv(file_path)
        elif ext in ("xlsx", "xls"):
            # 默认解析第一个工作表，engine 用 openpyxl
            df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
        else:
            raise DatasetParseError(
                code="DATASET_FILE_UNSUPPORTED",
                message=f"仅支持 CSV 和 XLSX，收到 .{ext}",
            )
    except DatasetParseError:
        raise
    except Exception as exc:
        raise DatasetParseError(
            code="DATASET_PARSE_FAILED",
            message=f"解析失败：{exc}",
        ) from exc

    # 空数据集：无列或无行
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise DatasetParseError(
            code="DATASET_EMPTY",
            message="数据集无数据行",
        )

    profile = _build_quality_profile(df)
    return DatasetParseResult(profile=profile, raw_dataframe=df)


# --- 序列化与反序列化 ---


def profile_to_dict(profile: DatasetProfile) -> dict:
    """将 DatasetProfile 序列化为可 JSON 化的 dict。"""
    return {
        "row_count": profile.row_count,
        "column_count": profile.column_count,
        "complete_row_count": profile.complete_row_count,
        "incomplete_row_count": profile.incomplete_row_count,
        "duplicate_row_count": profile.duplicate_row_count,
        "quality_score": profile.quality_score,
        "field_profiles": [_field_profile_to_dict(f) for f in profile.field_profiles],
    }


def _field_profile_to_dict(fp: FieldProfile) -> dict:
    return {
        "name": fp.name,
        "inferred_type": fp.inferred_type,
        "non_null_count": fp.non_null_count,
        "null_count": fp.null_count,
        "null_rate": fp.null_rate,
        "unique_count": fp.unique_count,
        "sample_values": fp.sample_values,
        "min_value": fp.min_value,
        "max_value": fp.max_value,
        "mean_value": fp.mean_value,
        "median_value": fp.median_value,
        "std_value": fp.std_value,
        "q1": fp.q1,
        "q3": fp.q3,
        "top_values": [[v, c] for v, c in fp.top_values],
    }


def profile_from_dict(data: dict) -> DatasetProfile:
    """从 dict 反序列化为 DatasetProfile 对象。"""
    field_profiles = [
        _field_profile_from_dict(f) for f in data.get("field_profiles", [])
    ]
    return DatasetProfile(
        row_count=data.get("row_count", 0),
        column_count=data.get("column_count", 0),
        complete_row_count=data.get("complete_row_count", 0),
        incomplete_row_count=data.get("incomplete_row_count", 0),
        duplicate_row_count=data.get("duplicate_row_count", 0),
        field_profiles=field_profiles,
        quality_score=data.get("quality_score", 0.0),
    )


def _field_profile_from_dict(data: dict) -> FieldProfile:
    top_values_raw = data.get("top_values", [])
    top_values: list[tuple[str, int]] = []
    for item in top_values_raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            top_values.append((str(item[0]), int(item[1])))
    return FieldProfile(
        name=data.get("name", ""),
        inferred_type=data.get("inferred_type", "string"),
        non_null_count=int(data.get("non_null_count", 0)),
        null_count=int(data.get("null_count", 0)),
        null_rate=float(data.get("null_rate", 0.0)),
        unique_count=int(data.get("unique_count", 0)),
        sample_values=list(data.get("sample_values", [])),
        min_value=data.get("min_value"),
        max_value=data.get("max_value"),
        mean_value=data.get("mean_value"),
        median_value=data.get("median_value"),
        std_value=data.get("std_value"),
        q1=data.get("q1"),
        q3=data.get("q3"),
        top_values=top_values,
    )
