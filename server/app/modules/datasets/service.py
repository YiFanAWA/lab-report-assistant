"""数据集核心服务。

拥有数据集登记、版本管理、解析状态、字段概览和质量检查的业务语义。
API、Worker、提示词只能调用本服务，不能直接修改数据集状态。

文件保存路径：projects/{project_id}/datasets/{dataset_id}/v{version}/raw.{ext}
URL 公开性校验复用 sources/service._validate_public_url，但错误码独立。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.infrastructure.fetchers.http_fetcher import fetch_url, FetchError
from app.modules.datasets.contracts import (
    DatasetResponse,
    DatasetListResponse,
    DatasetVersionResponse,
    DatasetVersionListResponse,
    CompleteDatasetsResponse,
)
from app.modules.datasets.models import Dataset, DatasetVersion, _uid, _now
from app.modules.datasets.status import (
    DatasetKind,
    DatasetStatus,
    DatasetVersionStatus,
    DatasetChangeType,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import ChangeRecord
from app.modules.sources.service import _validate_public_url


# --- 内部辅助 ---

# 允许登记数据集的项目状态：EVIDENCE_CONFIRMED 或之后
_POST_EVIDENCE_CONFIRMED_STATUSES = [
    ProjectStatus.EVIDENCE_CONFIRMED.value,
    ProjectStatus.DATASET_READY.value,
    ProjectStatus.ANALYSIS_PLANNED.value,
    ProjectStatus.ANALYSIS_CONFIRMED.value,
    ProjectStatus.EXECUTING.value,
    ProjectStatus.RESULT_CONFIRMED.value,
    ProjectStatus.OUTLINE_CONFIRMED.value,
    ProjectStatus.GENERATING.value,
    ProjectStatus.COMPLETED.value,
]


# CSV/Excel 支持的扩展名（小写，不含点）
_SUPPORTED_EXTENSIONS = {"csv", "xlsx"}

# CSV/Excel 允许的 Content-Type 前缀
_ALLOWED_CONTENT_TYPES = (
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",  # 部分 CSV 服务器返回 text/plain
    "application/octet-stream",  # 部分 URL 返回二进制流
)


def _ensure_project(db: Session, project_id: str):
    return project_service.get_project(db, project_id)


def _ensure_project_ready_for_datasets(project) -> None:
    """校验项目状态是 EVIDENCE_CONFIRMED 或之后。"""
    if project.status not in _POST_EVIDENCE_CONFIRMED_STATUSES:
        raise AppError(
            code="PROJECT_EVIDENCE_NOT_CONFIRMED",
            message="项目证据未确认，无法登记数据集",
        )


def _add_change(db: Session, project_id: str, change_type: str,
                summary: str) -> None:
    """写入变更记录，复用 requirements.models.ChangeRecord。"""
    rec = ChangeRecord(
        project_id=project_id,
        change_type=change_type,
        summary=summary,
    )
    db.add(rec)


def _dataset_dir(project_id: str, dataset_id: str, version: int) -> Path:
    """返回数据集版本的受控工作区目录。"""
    return (settings.project_data_root / project_id
            / "datasets" / dataset_id / f"v{version}")


def _infer_extension(filename: str) -> str:
    """从文件名提取扩展名（小写，不含点）。"""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _validate_dataset_url(url: str) -> str:
    """校验数据集 URL 公开性，返回清洗后的 URL。

    错误码使用 DATASET_* 前缀。
    """
    url = url.strip()
    if not url:
        raise AppError(code="DATASET_URL_REQUIRED", message="URL 不能为空",
                       field="url")
    is_valid, error_code = _validate_public_url(url)
    if not is_valid:
        if error_code == "SOURCE_URL_SCHEME_UNSUPPORTED":
            raise AppError(code="DATASET_URL_SCHEME_UNSUPPORTED",
                           message="仅支持 http 和 https 协议", field="url")
        if error_code == "SOURCE_URL_NOT_PUBLIC":
            raise AppError(code="DATASET_URL_NOT_PUBLIC",
                           message="URL 指向非公开地址", field="url")
        raise AppError(code="DATASET_URL_INVALID", message="URL 格式不正确",
                       field="url")
    return url


def _infer_extension_from_content_type(content_type: str, url: str) -> str:
    """根据 Content-Type 或 URL 后缀推断文件扩展名。"""
    ct = (content_type or "").lower()
    if "spreadsheet" in ct or "excel" in ct or "openxml" in ct:
        return "xlsx"
    if "csv" in ct:
        return "csv"
    # 回退到 URL 后缀
    return _infer_extension(url)


# --- 响应转换 ---


def _dataset_to_response(d: Dataset, job_id: str | None = None) -> DatasetResponse:
    """将 Dataset ORM 模型转换为 DatasetResponse。"""
    return DatasetResponse(
        id=d.id,
        project_id=d.project_id,
        dataset_kind=d.dataset_kind,
        title=d.title,
        description=d.description,
        status=d.status,
        error_code=d.error_code,
        error_message=d.error_message,
        created_at=d.created_at.isoformat(),
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
        job_id=job_id,
    )


def _dataset_list_to_response(datasets: list[Dataset]) -> DatasetListResponse:
    return DatasetListResponse(items=[_dataset_to_response(d) for d in datasets])


def _version_to_response(v: DatasetVersion) -> DatasetVersionResponse:
    """将 DatasetVersion ORM 模型转换为 DatasetVersionResponse。"""
    return DatasetVersionResponse(
        id=v.id,
        dataset_id=v.dataset_id,
        project_id=v.project_id,
        version=v.version,
        status=v.status,
        file_path=v.file_path,
        file_size_bytes=v.file_size_bytes,
        row_count=v.row_count,
        column_count=v.column_count,
        profile_json=v.profile_json,
        error_code=v.error_code,
        error_message=v.error_message,
        created_at=v.created_at.isoformat(),
        parsed_at=v.parsed_at.isoformat() if v.parsed_at else None,
    )


def _version_list_to_response(versions: list[DatasetVersion]) -> DatasetVersionListResponse:
    return DatasetVersionListResponse(
        items=[_version_to_response(v) for v in versions],
    )


# --- 内部创建逻辑 ---


def _create_version_and_job(
    db: Session,
    project_id: str,
    dataset: Dataset,
    file_path: str,
    file_size_bytes: int,
    file_extension: str,
) -> str:
    """为已存在的 Dataset 创建新版本并触发解析任务。

    旧版本状态变为 SUPERSEDED。
    返回 job_id。
    """
    # 旧版本变 SUPERSEDED（仅 PENDING/PARSING/PARSED 状态）
    old_versions = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.status.in_([
                DatasetVersionStatus.PENDING.value,
                DatasetVersionStatus.PARSING.value,
                DatasetVersionStatus.PARSED.value,
            ]),
        )
        .all()
    )
    for old in old_versions:
        old.status = DatasetVersionStatus.SUPERSEDED.value

    # 计算新版本号
    latest = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )
    new_version = (latest.version + 1) if latest else 1

    version = DatasetVersion(
        id=_uid(),
        dataset_id=dataset.id,
        project_id=project_id,
        version=new_version,
        status=DatasetVersionStatus.PENDING.value,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        created_at=_now(),
    )
    db.add(version)

    # Dataset 状态回退到 PENDING 等待解析
    dataset.status = DatasetStatus.PENDING.value
    dataset.error_code = None
    dataset.error_message = None
    dataset.updated_at = _now()

    # 触发解析任务
    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.PARSE_DATASET.value,
        input_data={
            "dataset_id": dataset.id,
            "version_id": version.id,
            "file_extension": file_extension,
        },
    )

    # 若是重新上传，将关联 AnalysisPlan 变 STALE
    if new_version > 1:
        _mark_analysis_stale(db, dataset.id)

    _add_change(db, project_id, DatasetChangeType.DATASET_CREATED.value,
                f"登记数据集版本 v{new_version}：{dataset.title}")
    db.commit()
    db.refresh(version)
    return job.id


def _mark_analysis_stale(db: Session, dataset_id: str) -> int:
    """将关联 AnalysisPlan 标记为 STALE，返回受影响行数。

    延迟导入以避免循环依赖。
    """
    from app.modules.analysis.models import AnalysisPlan
    from app.modules.analysis.status import AnalysisPlanStatus

    plans = (
        db.query(AnalysisPlan)
        .filter(
            AnalysisPlan.dataset_id == dataset_id,
            AnalysisPlan.status.in_([
                AnalysisPlanStatus.CANDIDATE.value,
                AnalysisPlanStatus.CONFIRMED.value,
                AnalysisPlanStatus.REJECTED.value,
            ]),
        )
        .all()
    )
    for plan in plans:
        plan.status = AnalysisPlanStatus.STALE.value
        plan.updated_at = _now()
    return len(plans)


# --- 数据集登记 ---


def create_file_dataset(
    db: Session,
    project_id: str,
    title: str | None,
    description: str | None,
    file_content: bytes,
    original_filename: str,
    existing_dataset_id: str | None = None,
) -> tuple[Dataset, str]:
    """上传 CSV/Excel 文件，保存到受控工作区，创建 PARSE_DATASET 任务。

    若 existing_dataset_id 提供，视为重新上传（创建新版本，旧版本 SUPERSEDED）。
    返回 (dataset, job_id)。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_datasets(project)

    # 校验文件
    if not file_content:
        raise AppError(code="DATASET_FILE_EMPTY", message="文件不能为空",
                       field="file")
    if len(file_content) > settings.dataset_max_size_bytes:
        raise AppError(code="DATASET_FILE_TOO_LARGE",
                       message=f"文件大小超过 {settings.dataset_max_size_bytes // (1024 * 1024)} MB 上限",
                       field="file")

    ext = _infer_extension(original_filename)
    if ext not in _SUPPORTED_EXTENSIONS:
        raise AppError(code="DATASET_FILE_UNSUPPORTED",
                       message="仅支持 CSV 和 XLSX 文件", field="file")

    # 处理 dataset：新建或复用
    if existing_dataset_id:
        dataset = get_dataset_by_id_and_project(db, project_id, existing_dataset_id)
        if dataset.status == DatasetStatus.DELETED.value:
            raise AppError(code="DATASET_NOT_FOUND",
                           message=f"未找到数据集 {existing_dataset_id}")
        # 重新上传变更记录
        change_type = DatasetChangeType.DATASET_REUPLOADED.value
        change_summary_prefix = "重新上传数据集"
    else:
        dataset_id = _uid()
        display_title = (title.strip() if title and title.strip()
                         else original_filename or f"数据集 {dataset_id[:8]}")
        dataset = Dataset(
            id=dataset_id,
            project_id=project_id,
            dataset_kind=DatasetKind.FILE.value,
            title=display_title,
            description=description.strip() if description else None,
            status=DatasetStatus.PENDING.value,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(dataset)
        change_type = DatasetChangeType.DATASET_CREATED.value
        change_summary_prefix = "上传数据集"

    # 保存文件到受控工作区
    # 先用临时版本号占位，实际版本号在 _create_version_and_job 中分配
    # 这里需要先确定版本号才能创建目录，因此先查询
    latest = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    dest_dir = _dataset_dir(project_id, dataset.id, next_version)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"raw.{ext}"
    with open(dest_path, "wb") as f:
        f.write(file_content)

    job_id = _create_version_and_job(
        db, project_id, dataset,
        file_path=str(dest_path),
        file_size_bytes=len(file_content),
        file_extension=ext,
    )

    # 更新变更记录类型（重新上传场景）
    if existing_dataset_id:
        _add_change(db, project_id, change_type,
                    f"{change_summary_prefix}：{dataset.title}")

    db.refresh(dataset)
    return (dataset, job_id)


def create_url_dataset(
    db: Session,
    project_id: str,
    url: str,
    title: str | None,
    description: str | None,
    existing_dataset_id: str | None = None,
) -> tuple[Dataset, str]:
    """登记公开 CSV/Excel URL，下载并保存到受控工作区，创建 PARSE_DATASET 任务。

    若 existing_dataset_id 提供，视为重新采集。
    返回 (dataset, job_id)。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_datasets(project)

    validated_url = _validate_dataset_url(url)

    # 处理 dataset：新建或复用
    if existing_dataset_id:
        dataset = get_dataset_by_id_and_project(db, project_id, existing_dataset_id)
        if dataset.status == DatasetStatus.DELETED.value:
            raise AppError(code="DATASET_NOT_FOUND",
                           message=f"未找到数据集 {existing_dataset_id}")
    else:
        dataset_id = _uid()
        display_title = (title.strip() if title and title.strip()
                         else validated_url)
        dataset = Dataset(
            id=dataset_id,
            project_id=project_id,
            dataset_kind=DatasetKind.URL.value,
            title=display_title,
            description=description.strip() if description else None,
            status=DatasetStatus.PENDING.value,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(dataset)

    # 下载文件
    try:
        result = fetch_url(
            url=validated_url,
            timeout_seconds=settings.source_fetch_timeout_seconds,
            max_size_bytes=settings.dataset_max_size_bytes,
        )
    except FetchError as err:
        # 映射错误码
        if err.code == "SOURCE_ACCESS_RESTRICTED":
            raise AppError(code="DATASET_ACCESS_RESTRICTED",
                           message="URL 需要登录或付费", field="url") from err
        if err.code == "FETCH_TOO_LARGE":
            raise AppError(code="DATASET_FILE_TOO_LARGE",
                           message="采集内容过大", field="url") from err
        if err.code == "FETCH_TIMEOUT":
            raise AppError(code="DATASET_URL_INVALID",
                           message="采集超时", field="url") from err
        raise AppError(code="DATASET_URL_INVALID",
                       message=f"采集失败：{err.message}", field="url") from err

    # 校验 Content-Type（允许 text/plain/octet-stream 等宽松类型，回退到 URL 后缀）
    content_type = result.content_type or ""
    ext = _infer_extension_from_content_type(content_type, validated_url)
    if ext not in _SUPPORTED_EXTENSIONS:
        raise AppError(code="DATASET_FILE_UNSUPPORTED",
                       message="仅支持 CSV 和 XLSX，URL 返回内容不支持",
                       field="url")

    # 校验文件大小（下载后再次确认）
    if len(result.content) > settings.dataset_max_size_bytes:
        raise AppError(code="DATASET_FILE_TOO_LARGE",
                       message="文件大小超过上限", field="url")
    if not result.content:
        raise AppError(code="DATASET_FILE_EMPTY",
                       message="采集内容为空", field="url")

    # 保存文件
    latest = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    dest_dir = _dataset_dir(project_id, dataset.id, next_version)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"raw.{ext}"
    with open(dest_path, "wb") as f:
        f.write(result.content)

    job_id = _create_version_and_job(
        db, project_id, dataset,
        file_path=str(dest_path),
        file_size_bytes=len(result.content),
        file_extension=ext,
    )

    if existing_dataset_id:
        _add_change(db, project_id, DatasetChangeType.DATASET_REUPLOADED.value,
                    f"重新采集数据集 URL：{validated_url}")

    db.refresh(dataset)
    return (dataset, job_id)


# --- 数据集查询 ---


def list_datasets(db: Session, project_id: str) -> list[Dataset]:
    """按创建时间降序列出数据集（不含已软删除）。"""
    _ensure_project(db, project_id)
    return (
        db.query(Dataset)
        .filter(
            Dataset.project_id == project_id,
            Dataset.status != DatasetStatus.DELETED.value,
        )
        .order_by(Dataset.created_at.desc())
        .all()
    )


def get_dataset(db: Session, dataset_id: str) -> Dataset:
    """查询单个数据集，不存在时抛出 DATASET_NOT_FOUND。"""
    d = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not d or d.status == DatasetStatus.DELETED.value:
        raise AppError(code="DATASET_NOT_FOUND",
                       message=f"未找到数据集 {dataset_id}")
    return d


def get_dataset_by_id_and_project(db: Session, project_id: str,
                                   dataset_id: str) -> Dataset:
    """查询数据集并校验归属，不匹配时抛出 DATASET_NOT_FOUND。"""
    d = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.project_id == project_id,
        )
        .first()
    )
    if not d or d.status == DatasetStatus.DELETED.value:
        raise AppError(code="DATASET_NOT_FOUND",
                       message=f"未找到数据集 {dataset_id}")
    return d


# --- 数据集版本查询 ---


def list_dataset_versions(db: Session, dataset_id: str) -> list[DatasetVersion]:
    """按版本号降序列出数据集版本。"""
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
        .all()
    )


def get_latest_version(db: Session, dataset_id: str) -> DatasetVersion:
    """取最新版本，不存在时抛出 DATASET_VERSION_NOT_FOUND。"""
    v = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )
    if not v:
        raise AppError(code="DATASET_VERSION_NOT_FOUND",
                       message=f"未找到数据集 {dataset_id} 的版本")
    return v


def get_version_by_id(db: Session, version_id: str) -> DatasetVersion:
    """按 ID 查询版本，不存在时抛出 DATASET_VERSION_NOT_FOUND。"""
    v = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if not v:
        raise AppError(code="DATASET_VERSION_NOT_FOUND",
                       message=f"未找到数据集版本 {version_id}")
    return v


# --- 数据集删除 ---


def delete_dataset(db: Session, project_id: str, dataset_id: str) -> Dataset:
    """软删除数据集：status=DELETED，关联 AnalysisPlan 变 STALE。"""
    dataset = get_dataset_by_id_and_project(db, project_id, dataset_id)
    dataset.status = DatasetStatus.DELETED.value
    dataset.updated_at = _now()
    _mark_analysis_stale(db, dataset_id)
    _add_change(db, project_id, DatasetChangeType.DATASET_DELETED.value,
                f"删除数据集：{dataset.title}")
    db.commit()
    db.refresh(dataset)
    return dataset


# --- 完成数据集收集 ---


def complete_datasets(db: Session, project_id: str):
    """推进 project.status 到 DATASET_READY。

    前置条件：至少一个 Dataset.status=READY。
    """
    project = _ensure_project(db, project_id)

    ready_count = (
        db.query(Dataset)
        .filter(
            Dataset.project_id == project_id,
            Dataset.status == DatasetStatus.READY.value,
        )
        .count()
    )
    if ready_count == 0:
        raise AppError(code="PROJECT_NO_READY_DATASET",
                       message="没有已就绪的数据集，无法完成数据集收集")

    project.status = ProjectStatus.DATASET_READY.value
    _add_change(db, project_id, DatasetChangeType.DATASETS_COMPLETED.value,
                f"完成数据集收集（已就绪数据集 {ready_count} 个）")
    db.commit()
    db.refresh(project)
    return project


# --- Worker 调用的内部方法 ---


def mark_dataset_parsing(db: Session, version_id: str) -> DatasetVersion:
    """更新 DatasetVersion status=PARSING。不提交事务。"""
    version = get_version_by_id(db, version_id)
    version.status = DatasetVersionStatus.PARSING.value
    db.flush()
    return version


def mark_dataset_parsed(
    db: Session,
    version_id: str,
    profile_data: dict,
    row_count: int,
    column_count: int,
) -> tuple[DatasetVersion, Dataset]:
    """更新 DatasetVersion status=PARSED，Dataset status=READY。不提交事务。"""
    version = get_version_by_id(db, version_id)
    version.status = DatasetVersionStatus.PARSED.value
    version.profile_json = json.dumps(profile_data, ensure_ascii=False,
                                       default=str)
    version.row_count = row_count
    version.column_count = column_count
    version.parsed_at = _now()
    version.error_code = None
    version.error_message = None

    dataset = get_dataset(db, version.dataset_id)
    dataset.status = DatasetStatus.READY.value
    dataset.error_code = None
    dataset.error_message = None
    dataset.updated_at = _now()

    _add_change(db, dataset.project_id,
                DatasetChangeType.DATASET_PARSED.value,
                f"解析数据集：{dataset.title}（{row_count} 行 × {column_count} 列）")
    db.flush()
    return (version, dataset)


def mark_dataset_failed(
    db: Session,
    version_id: str,
    error_code: str,
    error_message: str,
) -> tuple[DatasetVersion, Dataset]:
    """更新 DatasetVersion status=FAILED。

    若该 Dataset 所有版本都 FAILED，则 Dataset.status=FAILED。不提交事务。
    """
    version = get_version_by_id(db, version_id)
    version.status = DatasetVersionStatus.FAILED.value
    version.error_code = error_code
    version.error_message = error_message

    dataset = get_dataset(db, version.dataset_id)
    # 检查是否还有非 FAILED 的活跃版本（PENDING/PARSING/PARSED）
    active_count = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.status.in_([
                DatasetVersionStatus.PENDING.value,
                DatasetVersionStatus.PARSING.value,
                DatasetVersionStatus.PARSED.value,
            ]),
        )
        .count()
    )
    if active_count == 0:
        dataset.status = DatasetStatus.FAILED.value
        dataset.error_code = error_code
        dataset.error_message = error_message
        dataset.updated_at = _now()

    db.flush()
    return (version, dataset)


def trigger_analysis_plan_generation(
    db: Session,
    project_id: str,
    dataset_id: str,
    version_id: str,
) -> str:
    """自动触发生成分析方案候选，返回 job_id。不提交事务。"""
    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_ANALYSIS_PLAN.value,
        input_data={
            "dataset_id": dataset_id,
            "dataset_version_id": version_id,
        },
    )
    db.flush()
    return job.id


# --- 响应转换的对外方法（供 API 层使用） ---


def dataset_to_response(d: Dataset, job_id: str | None = None) -> DatasetResponse:
    """对外暴露的 Dataset 转 response 方法。"""
    return _dataset_to_response(d, job_id=job_id)


def dataset_list_to_response(datasets: list[Dataset]) -> DatasetListResponse:
    return _dataset_list_to_response(datasets)


def version_to_response(v: DatasetVersion) -> DatasetVersionResponse:
    return _version_to_response(v)


def version_list_to_response(versions: list[DatasetVersion]) -> DatasetVersionListResponse:
    return _version_list_to_response(versions)


def complete_datasets_to_response(project) -> CompleteDatasetsResponse:
    return CompleteDatasetsResponse(status=project.status)
