"""V1.0 Worker 端到端验证脚本。

完整验证 SPEC 0006 状态机流转：
1. 创建项目
2. 直接推进到 RESULT_CONFIRMED（跳过前置步骤，聚焦大纲+交付物验证）
3. 插入模拟的已确认 ExecutionRun（大纲生成依赖）
4. 触发大纲生成（API）
5. 启动 Worker 进程处理 GENERATE_OUTLINE 任务
6. 确认大纲
7. 触发 Word 生成（API）
8. 启动 Worker 进程处理 GENERATE_WORD 任务
9. 触发 PPT 生成（API）
10. 启动 Worker 进程处理 GENERATE_PPT 任务
11. 完成项目（API）
12. 验证最终状态：COMPLETED

输出完整运行日志。
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# 确保使用项目 venv
VENV_PYTHON = r"d:\java_project\lab-report-assistant\server\.venv\Scripts\python.exe"
SERVER_DIR = r"d:\java_project\lab-report-assistant\server"
LOG_FILE = r"d:\java_project\lab-report-assistant\dev-docs\worker-e2e-log.md"


def log(msg: str):
    """打印并记录日志。"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    return line


def main():
    log_lines = []
    log_lines.append(log("# V1.0 Worker 端到端验证日志"))
    log_lines.append(log(""))
    log_lines.append(log(f"**执行时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
    log_lines.append(log(f"**Python：** {VENV_PYTHON}"))
    log_lines.append(log(f"**工作目录：** {SERVER_DIR}"))
    log_lines.append(log(""))
    log_lines.append(log("---"))
    log_lines.append(log(""))

    # Step 1: 确保数据库迁移到最新
    log_lines.append(log("## 步骤 1：确保数据库迁移到最新"))
    result = subprocess.run(
        [VENV_PYTHON, "-m", "alembic", "upgrade", "head"],
        cwd=SERVER_DIR, capture_output=True, text=True, timeout=60
    )
    log_lines.append(log(f"退出码：{result.returncode}"))
    if result.returncode == 0:
        log_lines.append(log("✅ 数据库迁移成功"))
    else:
        log_lines.append(log(f"❌ 数据库迁移失败：{result.stderr}"))
        write_log(log_lines)
        return 1
    log_lines.append(log(""))

    # Step 2: 通过 Python 脚本执行完整端到端流程
    log_lines.append(log("## 步骤 2：执行完整端到端流程"))
    log_lines.append(log(""))

    # 编写内联 Python 脚本
    inline_script = '''
import os, sys, time, json
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from app.infrastructure.database.engine import SessionLocal, engine
from app.infrastructure.database.engine import Base
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import RequirementPlan, ChangeRecord
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard
from app.modules.sources.status import SourceStatus, EvidenceCardStatus
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.execution.models import CodeTask, ExecutionRun, ExecutionArtifact
from app.modules.execution.status import CodeTaskStatus, ExecutionRunStatus, ExecutionArtifactType
from app.modules.outlines import service as outline_service
from app.modules.outlines.models import Outline, Deliverable, DeliverableVersion
from app.modules.outlines.status import OutlineStatus, DeliverableStatus, DeliverableType, DeliverableVersionStatus
from app.modules.jobs import service as job_service
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.status import JobType, JobStatus
from worker import handlers as worker_handlers

db = SessionLocal()

def log(msg):
    print(f"[E2E] {msg}", flush=True)

try:
    # 1. 创建项目
    project = project_service.create_project(
        db, ProjectCreateRequest(name="Worker E2E 验证项目", topic="胃病数据分析")
    )
    log(f"1. 创建项目: {project.id}, 状态: {project.status}")

    # 2. 推进到 RESULT_CONFIRMED（直接修改状态，聚焦大纲验证）
    project.status = ProjectStatus.RESULT_CONFIRMED.value
    db.commit()
    log(f"2. 项目推进到 RESULT_CONFIRMED")

    # 3. 插入模拟的已确认 ExecutionRun（大纲生成依赖）
    task = CodeTask(
        id="task_e2e_001",
        project_id=project.id,
        analysis_plan_id="plan_e2e_dummy",
        dataset_id="ds_e2e_dummy",
        dataset_version_id="ver_e2e_dummy",
        code="import pandas\\nprint('胃病数据分析结果')",
        code_version=1,
        status=CodeTaskStatus.CONFIRMED.value,
        candidate_source="local_rule",
    )
    db.add(task)
    run = ExecutionRun(
        id="run_e2e_001",
        project_id=project.id,
        code_task_id=task.id,
        dataset_version_id="ver_e2e_dummy",
        code_version=1,
        status=ExecutionRunStatus.SUCCEEDED.value,
        stdout="胃病数据描述性统计完成\\n均值: 45.2\\n标准差: 12.3",
        stderr="",
        exit_code=0,
        started_at=datetime(2024,1,1,tzinfo=timezone.utc),
        finished_at=datetime(2024,1,1,1,tzinfo=timezone.utc),
        duration_seconds=1.0,
    )
    db.add(run)
    db.commit()
    log(f"3. 插入模拟 ExecutionRun: {run.id}")

    # 4. 触发大纲生成
    job_id = outline_service.generate_outline(db, project.id)
    db.commit()
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    log(f"4. 触发大纲生成: job_id={job_id}, type={job.job_type}, status={job.status}")

    # 5. Worker 处理 GENERATE_OUTLINE 任务
    worker_handlers.handle_generate_outline(db, job)
    db.commit()
    db.refresh(job)
    log(f"5. Worker 执行大纲生成: job status={job.status}")

    # 查找生成的 CANDIDATE 大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project.id,
        Outline.status == OutlineStatus.CANDIDATE.value
    ).first()
    sections = json.loads(outline.sections_json)
    log(f"   大纲 ID: {outline.id}")
    log(f"   章节数: {len(sections)}")
    log(f"   候选来源: {outline.candidate_source}")

    # 6. 确认大纲
    confirmed = outline_service.confirm_outline(db, project.id, outline.id)
    db.commit()
    db.refresh(project)
    log(f"6. 确认大纲: status={confirmed.status}, project={project.status}")

    # 7. 触发 Word 生成
    word_job_id, word_deliverable_id = outline_service.generate_word(db, project.id, outline.id)
    db.commit()
    word_job = db.query(BackgroundJob).filter(BackgroundJob.id == word_job_id).first()
    log(f"7. 触发 Word 生成: job_id={word_job_id}, deliverable_id={word_deliverable_id}")

    # 8. Worker 处理 GENERATE_WORD 任务
    worker_handlers.handle_generate_word(db, word_job)
    db.commit()
    db.refresh(word_job)
    log(f"8. Worker 执行 Word 生成: job status={word_job.status}")

    word_version = db.query(DeliverableVersion).filter(
        DeliverableVersion.deliverable_id == word_deliverable_id
    ).first()
    log(f"   Word 版本: v{word_version.version}, status={word_version.status}, size={word_version.file_size_bytes} bytes")

    # 9. 触发 PPT 生成
    ppt_job_id, ppt_deliverable_id = outline_service.generate_ppt(db, project.id, outline.id)
    db.commit()
    ppt_job = db.query(BackgroundJob).filter(BackgroundJob.id == ppt_job_id).first()
    log(f"9. 触发 PPT 生成: job_id={ppt_job_id}, deliverable_id={ppt_deliverable_id}")

    # 10. Worker 处理 GENERATE_PPT 任务
    worker_handlers.handle_generate_ppt(db, ppt_job)
    db.commit()
    db.refresh(ppt_job)
    log(f"10. Worker 执行 PPT 生成: job status={ppt_job.status}")

    ppt_version = db.query(DeliverableVersion).filter(
        DeliverableVersion.deliverable_id == ppt_deliverable_id
    ).first()
    log(f"   PPT 版本: v{ppt_version.version}, status={ppt_version.status}, size={ppt_version.file_size_bytes} bytes")

    # 11. 完成项目
    completed = outline_service.complete_project(db, project.id)
    db.commit()
    log(f"11. 完成项目: status={completed.status}")

    # 12. 验证最终状态
    db.refresh(project)
    log(f"12. 最终验证: project.status={project.status}")

    # 验证文件实际存在
    from app.core.config import settings
    word_path = settings.project_data_root / project.id / "deliverables" / word_deliverable_id / "word_v1.docx"
    ppt_path = settings.project_data_root / project.id / "deliverables" / ppt_deliverable_id / "ppt_v1.pptx"
    log(f"   Word 文件存在: {word_path.exists()} ({word_path})")
    log(f"   PPT 文件存在: {ppt_path.exists()} ({ppt_path})")

    if project.status == ProjectStatus.COMPLETED.value and word_path.exists() and ppt_path.exists():
        log("")
        log("=== ✅ 端到端验证全部通过 ===")
        log(f"项目 {project.id} 从 RESULT_CONFIRMED 推进到 COMPLETED")
        log(f"Word 文件: {word_path}")
        log(f"PPT 文件: {ppt_path}")
        print("E2E_RESULT=PASS")
    else:
        log("")
        log("=== ❌ 端到端验证失败 ===")
        print("E2E_RESULT=FAIL")

except Exception as e:
    import traceback
    log(f"异常: {e}")
    traceback.print_exc()
    print("E2E_RESULT=ERROR")
finally:
    db.close()
'''

    log_lines.append(log("执行内联 Python 脚本..."))
    result = subprocess.run(
        [VENV_PYTHON, "-c", inline_script],
        cwd=SERVER_DIR, capture_output=True, text=True, timeout=120,
        encoding="utf-8"
    )

    # 记录脚本输出
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            log_lines.append(log(f"  {line}"))

    if result.returncode == 0 and "E2E_RESULT=PASS" in result.stdout:
        log_lines.append(log(""))
        log_lines.append(log("✅ Worker 端到端验证全部通过"))
    else:
        log_lines.append(log(""))
        log_lines.append(log(f"❌ 验证失败（退出码 {result.returncode}）"))
        if result.stderr:
            log_lines.append(log("STDERR:"))
            for line in result.stderr.strip().split("\n")[-10:]:
                log_lines.append(log(f"  {line}"))

    log_lines.append(log(""))
    log_lines.append(log("---"))
    log_lines.append(log(""))
    log_lines.append(log("## 验证结论"))
    log_lines.append(log(""))
    log_lines.append(log("状态机流转路径："))
    log_lines.append(log("``"))
    log_lines.append(log("RESULT_CONFIRMED"))
    log_lines.append(log("  → 生成大纲候选（Worker 执行 GENERATE_OUTLINE）"))
    log_lines.append(log("  → 确认大纲 → OUTLINE_CONFIRMED"))
    log_lines.append(log("  → 触发 Word 生成（Worker 执行 GENERATE_WORD）→ GENERATING"))
    log_lines.append(log("  → 触发 PPT 生成（Worker 执行 GENERATE_PPT）"))
    log_lines.append(log("  → Word+PPT 均 SUCCEEDED → COMPLETED"))
    log_lines.append(log("```"))

    # 写入日志文件
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"\n日志已保存到: {LOG_FILE}")
    return 0 if "E2E_RESULT=PASS" in result.stdout else 1


def write_log(lines):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
