"""SPEC 0012 数据保留周期清理脚本。

手动执行，按 DATA_RETENTION_DAYS 配置清理过期项目数据。

用法：
    # 默认 dry-run，只输出清理报告，不删除
    python -m scripts.cleanup_expired_data

    # 显式 dry-run
    python -m scripts.cleanup_expired_data --dry-run

    # 实际执行清理
    python -m scripts.cleanup_expired_data --execute

    # 查看帮助
    python -m scripts.cleanup_expired_data --help

设计要点：
- 以项目为单位级联清理（18 张表关联记录 + 文件系统目录）
- 基于 Project.updated_at 判断过期（活跃项目自动重置计时器）
- RUNNING job 保护：有 PENDING/RUNNING 任务的项目跳过清理
- 默认 dry-run，必须显式 --execute 才删除
- 文件系统删除失败不阻塞数据库清理（记录 warning）
"""

import argparse
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.modules.jobs.service import has_active_jobs

# 导入所有 ORM 模型（级联删除需要）
from app.modules.projects.models import Project
from app.modules.requirements.models import (
    RequirementSource,
    RequirementPlan,
    ChangeRecord,
)
from app.modules.sources.models import (
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.jobs.models import BackgroundJob
from app.modules.datasets.models import (
    Dataset,
    DatasetVersion,
)
from app.modules.analysis.models import AnalysisPlan
from app.modules.execution.models import (
    CodeTask,
    ExecutionRun,
    ExecutionArtifact,
)
from app.modules.outlines.models import (
    Outline,
    Deliverable,
    DeliverableVersion,
    WordTemplate,
)

from app.infrastructure.database.engine import Base


# 级联删除顺序（叶子 -> 根，按外键依赖）
# 每个元素：(模型类, 表名, 说明)
CASCADE_DELETE_ORDER: list[tuple[type, str, str]] = [
    (ExecutionArtifact, "execution_artifacts", "执行产物"),
    (ExecutionRun, "execution_runs", "执行记录"),
    (CodeTask, "code_tasks", "代码任务"),
    (DeliverableVersion, "deliverable_versions", "交付物版本"),
    (Deliverable, "deliverables", "交付物"),
    (Outline, "outlines", "大纲"),
    (WordTemplate, "word_templates", "Word 模板"),
    (AnalysisPlan, "analysis_plans", "分析方案"),
    (DatasetVersion, "dataset_versions", "数据集版本"),
    (Dataset, "datasets", "数据集"),
    (EvidenceCard, "evidence_cards", "证据卡片"),
    (ParsedDocument, "parsed_documents", "解析文档"),
    (Source, "sources", "来源"),
    (ChangeRecord, "change_records", "变更记录"),
    (RequirementPlan, "requirement_plans", "要求任务单"),
    (RequirementSource, "requirement_sources", "要求来源"),
    (BackgroundJob, "background_jobs", "后台任务"),
    (Project, "projects", "项目"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def find_expired_projects(db, retention_days: int) -> list[Project]:
    """查询过期项目列表。

    基于 Project.updated_at 判断：updated_at < now - retention_days。
    retention_days <= 0 时返回空列表（永久保留）。
    """
    if retention_days <= 0:
        return []
    cutoff = _now() - timedelta(days=retention_days)
    return (
        db.query(Project)
        .filter(Project.updated_at < cutoff)
        .order_by(Project.updated_at.asc())
        .all()
    )


def delete_project_filesystem(project_id: str) -> tuple[bool, str]:
    """删除项目的文件系统目录。

    返回 (成功标志, 消息)。
    目录不存在时视为成功（warning）。
    删除失败时返回 False + 错误消息。
    """
    project_dir = settings.project_data_root / project_id
    if not project_dir.exists():
        return True, f"目录不存在，跳过文件系统清理：{project_dir}"
    try:
        shutil.rmtree(project_dir, ignore_errors=True)
        # 检查是否删除完整
        if project_dir.exists():
            return True, f"部分文件未删除（可能被占用），目录残留：{project_dir}"
        return True, f"文件系统目录已删除：{project_dir}"
    except Exception as exc:
        return False, f"文件系统删除失败：{exc}"


def delete_project_database_records(db, project_id: str) -> tuple[int, list[str]]:
    """按级联顺序删除项目的所有数据库记录。

    返回 (删除记录总数, 错误消息列表)。
    Project 表使用 id 字段（而非 project_id），单独处理。
    """
    total_deleted = 0
    errors: list[str] = []

    for model_class, table_name, desc in CASCADE_DELETE_ORDER:
        try:
            if model_class is Project:
                # Project 表使用 id 字段
                count = (
                    db.query(model_class)
                    .filter(model_class.id == project_id)
                    .delete(synchronize_session=False)
                )
            else:
                count = (
                    db.query(model_class)
                    .filter(model_class.project_id == project_id)
                    .delete(synchronize_session=False)
                )
            total_deleted += count
        except Exception as exc:
            errors.append(f"{table_name}({desc})删除失败：{exc}")

    db.commit()
    return total_deleted, errors


def cleanup_project(db, project: Project, execute: bool) -> dict:
    """清理单个项目。

    返回清理结果字典：
    - project_id, project_name, status, message
    """
    result = {
        "project_id": project.id,
        "project_name": project.name,
        "updated_at": project.updated_at.isoformat(),
        "status": "skipped",
        "message": "",
        "db_deleted": 0,
        "fs_deleted": False,
    }

    # RUNNING job 保护
    if has_active_jobs(db, project.id):
        result["status"] = "skipped"
        result["message"] = "项目有活跃任务（PENDING/RUNNING），跳过清理"
        return result

    if not execute:
        result["status"] = "dry_run"
        result["message"] = "dry-run 模式，不实际删除"
        return result

    # execute 模式：先删文件系统，后删数据库
    fs_ok, fs_msg = delete_project_filesystem(project.id)
    result["fs_deleted"] = fs_ok
    result["message"] = fs_msg

    db_deleted, db_errors = delete_project_database_records(db, project.id)
    result["db_deleted"] = db_deleted
    if db_errors:
        result["status"] = "partial"
        result["message"] += f"；数据库部分删除失败：{db_errors}"
    else:
        result["status"] = "success"
        result["message"] += f"；数据库记录已删除（{db_deleted} 条）"

    return result


def run_cleanup(retention_days: int, execute: bool, db: Session | None = None) -> int:
    """执行清理流程。

    返回退出码：0=成功，1=有错误。

    参数 db：可选的数据库会话。传入时直接使用（用于测试注入）；
    不传时从 settings.database_url 创建新会话（用于 CLI 执行）。
    """
    print(f"=== 数据保留周期清理（SPEC 0012）===")
    print(f"保留天数：{retention_days}（0=永久保留）")
    print(f"执行模式：{'execute（实际删除）' if execute else 'dry-run（只报告）'}")
    print()

    if retention_days <= 0:
        print("保留期为永久（0 天），无过期项目，退出。")
        return 0

    # 使用传入的 db 会话，或创建新会话
    should_close = False
    if db is None:
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        should_close = True

    try:
        expired = find_expired_projects(db, retention_days)
        print(f"过期项目数量：{len(expired)}")
        print()

        if not expired:
            print("无过期项目，退出。")
            return 0

        results = []
        for project in expired:
            result = cleanup_project(db, project, execute)
            results.append(result)
            status_label = {
                "skipped": "跳过",
                "dry_run": "预览",
                "success": "成功",
                "partial": "部分失败",
            }.get(result["status"], result["status"])
            print(f"[{status_label}] {result['project_id']} ({result['project_name']})")
            print(f"  updated_at: {result['updated_at']}")
            print(f"  消息: {result['message']}")
            if result["db_deleted"]:
                print(f"  数据库删除: {result['db_deleted']} 条")
            print()

        # 汇总
        success_count = sum(1 for r in results if r["status"] == "success")
        skipped_count = sum(1 for r in results if r["status"] == "skipped")
        dry_run_count = sum(1 for r in results if r["status"] == "dry_run")
        partial_count = sum(1 for r in results if r["status"] == "partial")

        print("=== 清理汇总 ===")
        print(f"总过期项目：{len(results)}")
        print(f"成功：{success_count}")
        print(f"跳过（活跃任务）：{skipped_count}")
        print(f"预览（dry-run）：{dry_run_count}")
        print(f"部分失败：{partial_count}")

        if partial_count > 0:
            return 1
        return 0

    finally:
        if should_close:
            db.close()


def main():
    """命令行入口。"""
    # 当作为脚本直接运行时（python scripts/cleanup_expired_data.py），
    # 需要把 server/ 目录加入 sys.path 以便导入 app 包
    server_root = Path(__file__).resolve().parent.parent
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))

    parser = argparse.ArgumentParser(
        description="数据保留周期清理脚本（SPEC 0012）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python -m scripts.cleanup_expired_data              # 默认 dry-run
  python -m scripts.cleanup_expired_data --dry-run    # 显式 dry-run
  python -m scripts.cleanup_expired_data --execute    # 实际删除
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出清理报告，不实际删除（默认模式）",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行清理（删除过期项目数据）",
    )
    args = parser.parse_args()

    # dry-run 和 execute 同时指定时，dry-run 优先（安全优先）
    execute = args.execute and not args.dry_run
    if args.dry_run and args.execute:
        print("提示：--dry-run 和 --execute 同时指定，采用 dry-run（安全优先）")
        print()

    retention_days = settings.data_retention_days
    exit_code = run_cleanup(retention_days, execute)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
