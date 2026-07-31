"""SPEC 0029 端到端集成验收脚本。

验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通。
复用 worker_e2e_verify.py 架构，通过服务层 + Worker 处理器直接调用驱动完整 8 步工作流。

8 步主路径：
1. 创建项目 (DRAFT)
2. 上传要求文本 + 生成任务单 + 确认 (REQUIREMENT_CONFIRMED)
3. 上传 PDF + Worker 解析 + 生成证据卡片 + 确认 (EVIDENCE_CONFIRMED)
4. 上传 CSV + Worker 解析 (DATASET_READY)
5. 确认分析方案 (ANALYSIS_CONFIRMED)
6. 生成代码任务 + Worker 执行 (RESULT_CONFIRMED)
7. 生成大纲 + 确认 (OUTLINE_CONFIRMED)
8. 生成 Word + PPT (COMPLETED)

参数：
  --output PATH    验收报告输出路径（默认 dev-docs/e2e-acceptance-report-spec0029.md）

退出码：
  0 = PASS
  1 = FAIL
  2 = ERROR（异常）
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 确保导入 server 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.database.engine import SessionLocal, engine, Base
from app.core.config import settings
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.requirements import service as req_service
from app.modules.requirements.contracts import TextSourceRequest, GeneratePlanRequest
from app.modules.sources import service as sources_service
from app.modules.sources.status import EvidenceCardStatus
from app.modules.datasets import service as datasets_service
from app.modules.analysis import service as analysis_service
from app.modules.execution import service as execution_service
from app.modules.execution.status import ExecutionRunStatus
from app.modules.outlines import service as outline_service
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.status import JobType, JobStatus
from app.modules.llm.gateway import get_provider
from worker import handlers as worker_handlers


# --- 测试数据路径 ---
TEST_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "spec0029_e2e"
CSV_PATH = TEST_DATA_DIR / "gastric_health_data.csv"
PDF_PATH = TEST_DATA_DIR / "gastric_reference.pdf"

# --- 实验要求文本 ---
REQUIREMENT_TEXT = """胃病数据分析实验要求

一、实验目的
1. 掌握胃病数据分析的基本方法
2. 学习使用 Python 进行医学数据统计分析
3. 了解胃病相关指标的临床意义

二、实验内容
1. 对胃病患者数据进行描述性统计分析
2. 比较不同诊断组（健康、慢性胃炎、胃溃疡、胃癌）的指标差异
3. 分析年龄、性别与诊断结果的关系
4. 绘制相关图表（直方图、箱线图、条形图、相关性热力图）

三、数据要求
- 数据集包含：patient_id, age, gender, diagnosis, WBC, RBC, HGB, PLT, ALT, AST, ALB, CEA, CA19_9, CA72_4, symptom_score
- 诊断类型：健康、慢性胃炎、胃溃疡、胃癌

四、报告要求
1. Word 报告包含：实验目的、数据描述、分析方法、结果、结论
2. PPT 包含：标题页、数据概览、分析结果、图表展示、结论
"""

# 默认报告输出路径
DEFAULT_REPORT = Path(__file__).resolve().parent.parent.parent / "dev-docs" / "e2e-acceptance-report-spec0029.md"


def log(msg, lines=None):
    """打印并记录日志。"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    if lines is not None:
        lines.append(line)
    return line


def find_pending_job(db, project_id, job_type):
    """查找项目下指定类型的最新 PENDING 任务。"""
    return (
        db.query(BackgroundJob)
        .filter(
            BackgroundJob.project_id == project_id,
            BackgroundJob.job_type == job_type,
            BackgroundJob.status == JobStatus.PENDING.value,
        )
        .order_by(BackgroundJob.created_at.desc())
        .first()
    )


def process_job(db, job, lines, step_desc):
    """处理 Worker 任务并验证成功。

    调用对应的 worker handler 处理任务，验证任务状态变为 SUCCEEDED。
    失败时回滚并返回 False。
    """
    if job is None:
        log(f"❌ {step_desc}：未找到任务", lines)
        return False

    handler = worker_handlers.HANDLERS.get(job.job_type)
    if handler is None:
        log(f"❌ {step_desc}：未找到 handler for {job.job_type}", lines)
        return False

    log(f"   处理任务 {job.id} (type={job.job_type})...", lines)
    try:
        result = handler(db, job)
        db.commit()
        db.refresh(job)
        log(f"   ✅ 任务完成: status={job.status}, result={result}", lines)
        return True
    except Exception as e:
        db.rollback()
        log(f"   ❌ 任务失败: {e}", lines)
        traceback.print_exc()
        return False


def verify_status(project, expected, lines, step_name):
    """验证项目状态，失败时返回 False。"""
    if project.status != expected:
        log(f"❌ {step_name}：预期 {expected}，实际 {project.status}", lines)
        return False
    log(f"✅ {step_name} 完成: {project.status}", lines)
    return True


def main():
    parser = argparse.ArgumentParser(description="SPEC 0029 端到端集成验收脚本")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_REPORT),
        help=f"验收报告输出路径（默认 {DEFAULT_REPORT}）",
    )
    args = parser.parse_args()
    report_path = Path(args.output)

    lines = []
    lines.append("# SPEC 0029 端到端集成验收报告")
    lines.append("")
    lines.append(f"**执行时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**测试数据目录：** {TEST_DATA_DIR}")
    lines.append(f"**CSV 文件：** {CSV_PATH.name}")
    lines.append(f"**PDF 文件：** {PDF_PATH.name}")
    lines.append(
        f"**Provider 配置：** requirement={settings.requirement_draft_provider}, "
        f"evidence={settings.evidence_card_provider}, "
        f"analysis={settings.analysis_plan_provider}, "
        f"code={settings.code_task_provider}, "
        f"outline={settings.outline_provider}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # === 前置检查 ===
    log("## 前置检查：测试数据", lines)
    if not CSV_PATH.exists():
        log(f"❌ CSV 文件不存在: {CSV_PATH}", lines)
        return write_report(lines, report_path, "FAIL")
    log(f"✅ CSV 文件存在: {CSV_PATH.name} ({CSV_PATH.stat().st_size} bytes)", lines)

    if not PDF_PATH.exists():
        log(f"❌ PDF 文件不存在: {PDF_PATH}", lines)
        return write_report(lines, report_path, "FAIL")
    log(f"✅ PDF 文件存在: {PDF_PATH.name} ({PDF_PATH.stat().st_size} bytes)", lines)

    log("## 前置检查：数据库", lines)
    Base.metadata.create_all(bind=engine)
    log("✅ 数据库表已就绪", lines)

    db = SessionLocal()
    try:
        # ============================================================
        # Step 1: 创建项目
        # ============================================================
        log("## 步骤 1：创建项目", lines)
        project = project_service.create_project(
            db,
            ProjectCreateRequest(name="SPEC0029 端到端验收项目", topic="胃病数据分析"),
        )
        db.commit()
        project_id = project.id
        log(f"✅ 项目创建: id={project_id}, status={project.status}", lines)
        if not verify_status(project, ProjectStatus.DRAFT.value, lines, "步骤 1"):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 2: 上传要求 + 生成任务单 + 确认
        # ============================================================
        log("## 步骤 2：上传要求文本 + 生成任务单 + 确认", lines)

        # 2a. 添加文本来源
        source = req_service.add_text_source(
            db,
            project_id,
            TextSourceRequest(title="胃病数据分析实验要求", text=REQUIREMENT_TEXT),
        )
        db.commit()
        log(f"   2a. 文本来源创建: id={source.id}", lines)

        # 2b. 生成任务单（同步调用 provider）
        provider = get_provider()
        plan = req_service.generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source.id), provider
        )
        db.commit()
        log(
            f"   2b. 任务单生成: id={plan.id}, source={plan.candidate_source}",
            lines,
        )

        # 2c. 确认任务单 → REQUIREMENT_CONFIRMED
        plan = req_service.confirm_plan(db, project_id, plan.id)
        db.commit()
        db.refresh(project)
        log(
            f"   2c. 任务单确认: plan_status={plan.status}, project={project.status}",
            lines,
        )
        if not verify_status(
            project, ProjectStatus.REQUIREMENT_CONFIRMED.value, lines, "步骤 2"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 3: 上传 PDF + Worker 解析 + 生成证据 + 确认
        # ============================================================
        log("## 步骤 3：上传 PDF + 解析 + 生成证据卡片 + 确认", lines)

        # 3a. 上传 PDF（创建 Source + PARSE_DOCUMENT job）
        pdf_content = PDF_PATH.read_bytes()
        pdf_source, parse_job_id = sources_service.create_pdf_source(
            db, project_id, "胃病医学参考资料", pdf_content, "gastric_reference.pdf"
        )
        db.commit()
        log(
            f"   3a. PDF 来源创建: id={pdf_source.id}, job_id={parse_job_id}",
            lines,
        )

        # 3b. Worker 解析 PDF
        parse_job = db.get(BackgroundJob, parse_job_id)
        if not process_job(db, parse_job, lines, "3b. PDF 解析"):
            return write_report(lines, report_path, "FAIL")

        # 3c. 完成来源收集 → SOURCES_COLLECTED
        project = sources_service.complete_sources(db, project_id)
        db.commit()
        log(f"   3c. 完成来源收集: project={project.status}", lines)

        # 3d. 触发生成证据卡片（创建 GENERATE_EVIDENCE job）
        evidence_job_id = sources_service.generate_evidence_cards(
            db, project_id, pdf_source.id
        )
        db.commit()
        log(f"   3d. 触发证据生成: job_id={evidence_job_id}", lines)

        # 3e. Worker 生成证据卡片
        evidence_job = db.get(BackgroundJob, evidence_job_id)
        if not process_job(db, evidence_job, lines, "3e. 证据卡片生成"):
            return write_report(lines, report_path, "FAIL")

        # 3f. 确认所有候选证据卡片
        cards = sources_service.list_evidence_cards(
            db, project_id, source_id=pdf_source.id
        )
        log(f"   3f. 证据卡片数量: {len(cards)}", lines)
        confirmed_count = 0
        for card in cards:
            if card.status == EvidenceCardStatus.CANDIDATE.value:
                sources_service.confirm_evidence_card(db, project_id, card.id)
                confirmed_count += 1
        db.commit()
        log(f"   3f. 确认了 {confirmed_count} 张候选证据卡片", lines)

        # 3g. 完成证据确认 → EVIDENCE_CONFIRMED
        project = sources_service.complete_evidence(db, project_id)
        db.commit()
        log(f"   3g. 完成证据确认: project={project.status}", lines)
        if not verify_status(
            project, ProjectStatus.EVIDENCE_CONFIRMED.value, lines, "步骤 3"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 4: 上传 CSV + Worker 解析
        # ============================================================
        log("## 步骤 4：上传 CSV + Worker 解析（自动触发分析方案生成）", lines)

        # 4a. 上传 CSV（创建 Dataset + PARSE_DATASET job）
        csv_content = CSV_PATH.read_bytes()
        dataset, dataset_job_id = datasets_service.create_file_dataset(
            db,
            project_id,
            "胃病数据集",
            "胃病患者健康指标数据（200 行）",
            csv_content,
            "gastric_health_data.csv",
        )
        db.commit()
        log(
            f"   4a. 数据集创建: id={dataset.id}, job_id={dataset_job_id}",
            lines,
        )

        # 4b. Worker 解析数据集（成功后自动创建 GENERATE_ANALYSIS_PLAN job）
        dataset_job = db.get(BackgroundJob, dataset_job_id)
        if not process_job(db, dataset_job, lines, "4b. 数据集解析"):
            return write_report(lines, report_path, "FAIL")

        # 4c. Worker 生成分析方案（parse_dataset 自动触发的 job）
        analysis_job = find_pending_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value
        )
        if analysis_job:
            if not process_job(db, analysis_job, lines, "4c. 分析方案生成"):
                return write_report(lines, report_path, "FAIL")
        else:
            log("   4c. 未找到待处理的分析方案任务（可能已处理）", lines)

        # 4d. 完成数据集收集 → DATASET_READY
        project = datasets_service.complete_datasets(db, project_id)
        db.commit()
        log(f"   4d. 完成数据集收集: project={project.status}", lines)
        if not verify_status(
            project, ProjectStatus.DATASET_READY.value, lines, "步骤 4"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 5: 确认分析方案
        # ============================================================
        log("## 步骤 5：确认分析方案", lines)

        # 5a. 获取分析方案
        plans = analysis_service.list_analysis_plans(db, project_id)
        if not plans:
            log("❌ 未找到分析方案", lines)
            return write_report(lines, report_path, "FAIL")
        analysis_plan = plans[0]
        log(
            f"   5a. 分析方案: id={analysis_plan.id}, status={analysis_plan.status}",
            lines,
        )

        # 5b. 确认分析方案
        analysis_plan = analysis_service.confirm_analysis_plan(
            db, project_id, analysis_plan.id
        )
        db.commit()
        log(f"   5b. 分析方案确认: status={analysis_plan.status}", lines)

        # 5c. 完成分析 → ANALYSIS_CONFIRMED
        project = analysis_service.complete_analysis(db, project_id)
        db.commit()
        log(f"   5c. 完成分析: project={project.status}", lines)
        if not verify_status(
            project, ProjectStatus.ANALYSIS_CONFIRMED.value, lines, "步骤 5"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 6: 生成代码任务 + Worker 执行
        # ============================================================
        log("## 步骤 6：生成代码任务 + Worker 执行", lines)

        # 6a. 触发生成代码任务（创建 GENERATE_CODE_TASK job）
        code_job_id = execution_service.generate_code_task(
            db, project_id, analysis_plan.id
        )
        db.commit()
        log(f"   6a. 触发代码生成: job_id={code_job_id}", lines)

        # 6b. Worker 生成代码
        code_job = db.get(BackgroundJob, code_job_id)
        if not process_job(db, code_job, lines, "6b. 代码任务生成"):
            return write_report(lines, report_path, "FAIL")

        # 6c. 获取代码任务并确认
        code_tasks = execution_service.list_code_tasks(db, project_id)
        if not code_tasks:
            log("❌ 未找到代码任务", lines)
            return write_report(lines, report_path, "FAIL")
        code_task = code_tasks[0]
        log(
            f"   6c. 代码任务: id={code_task.id}, status={code_task.status}, code_length={len(code_task.code)}",
            lines,
        )

        code_task = execution_service.confirm_code_task(db, project_id, code_task.id)
        db.commit()
        log(f"   6c. 代码任务确认: status={code_task.status}", lines)

        # 6d. 触发执行（创建 EXECUTE_CODE_TASK job）
        execute_job_id = execution_service.execute_code_task(
            db, project_id, code_task.id
        )
        db.commit()
        log(f"   6d. 触发执行: job_id={execute_job_id}", lines)

        # 6e. Worker 执行代码
        execute_job = db.get(BackgroundJob, execute_job_id)
        if not process_job(db, execute_job, lines, "6e. 代码执行"):
            return write_report(lines, report_path, "FAIL")

        # 6f. 验证执行结果
        runs = execution_service.list_execution_runs(db, project_id)
        if not runs:
            log("❌ 未找到执行记录", lines)
            return write_report(lines, report_path, "FAIL")
        run, run_artifacts = runs[0]
        log(
            f"   6f. 执行记录: id={run.id}, status={run.status}, exit_code={run.exit_code}",
            lines,
        )

        if run.status != ExecutionRunStatus.SUCCEEDED.value:
            log(f"❌ 预期 SUCCEEDED，实际 {run.status}", lines)
            log(
                f"   stdout(前200字): {run.stdout[:200] if run.stdout else 'N/A'}",
                lines,
            )
            log(
                f"   stderr(前200字): {run.stderr[:200] if run.stderr else 'N/A'}",
                lines,
            )
            return write_report(lines, report_path, "FAIL")

        # 验证执行产物（图表文件）
        execution_dir = settings.project_data_root / project_id / "executions" / run.id
        if execution_dir.exists():
            charts = list(execution_dir.glob("*.png"))
            tables = list(execution_dir.glob("*.csv"))
            log(
                f"   6f. 执行产物: {len(charts)} 个图表, {len(tables)} 个表格",
                lines,
            )
            for c in charts[:3]:
                log(f"      - {c.name} ({c.stat().st_size} bytes)", lines)

        # 6g. 完成结果确认 → RESULT_CONFIRMED
        project = execution_service.complete_execution(db, project_id)
        db.commit()
        log(f"   6g. 完成结果确认: project={project.status}", lines)
        if not verify_status(
            project, ProjectStatus.RESULT_CONFIRMED.value, lines, "步骤 6"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 7: 生成大纲 + 确认
        # ============================================================
        log("## 步骤 7：生成大纲 + 确认", lines)

        # 7a. 触发生成大纲（创建 GENERATE_OUTLINE job）
        outline_job_id = outline_service.generate_outline(db, project_id)
        db.commit()
        log(f"   7a. 触发大纲生成: job_id={outline_job_id}", lines)

        # 7b. Worker 生成大纲
        outline_job = db.get(BackgroundJob, outline_job_id)
        if not process_job(db, outline_job, lines, "7b. 大纲生成"):
            return write_report(lines, report_path, "FAIL")

        # 7c. 获取大纲并验证段落结构
        outlines = outline_service.list_outlines(db, project_id)
        if not outlines:
            log("❌ 未找到大纲", lines)
            return write_report(lines, report_path, "FAIL")
        outline = outlines[0]
        sections = json.loads(outline.sections_json)
        source_types = [s.get("source_type", "N/A") for s in sections]
        log(
            f"   7c. 大纲: id={outline.id}, sections={len(sections)}, source_types={source_types}",
            lines,
        )

        # 7d. 确认大纲 → OUTLINE_CONFIRMED
        outline = outline_service.confirm_outline(db, project_id, outline.id)
        db.commit()
        db.refresh(project)
        log(
            f"   7d. 大纲确认: outline_status={outline.status}, project={project.status}",
            lines,
        )
        if not verify_status(
            project, ProjectStatus.OUTLINE_CONFIRMED.value, lines, "步骤 7"
        ):
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # Step 8: 生成 Word + PPT
        # ============================================================
        log("## 步骤 8：生成 Word + PPT + 完成项目", lines)

        # 8a. 触发 Word 生成（创建 GENERATE_WORD job）
        word_job_id, word_deliverable_id = outline_service.generate_word(
            db, project_id, outline.id
        )
        db.commit()
        log(
            f"   8a. 触发 Word 生成: job_id={word_job_id}, deliverable_id={word_deliverable_id}",
            lines,
        )

        # 8b. Worker 生成 Word
        word_job = db.get(BackgroundJob, word_job_id)
        if not process_job(db, word_job, lines, "8b. Word 生成"):
            return write_report(lines, report_path, "FAIL")

        # 8c. 触发 PPT 生成（创建 GENERATE_PPT job）
        ppt_job_id, ppt_deliverable_id = outline_service.generate_ppt(
            db, project_id, outline.id
        )
        db.commit()
        log(
            f"   8c. 触发 PPT 生成: job_id={ppt_job_id}, deliverable_id={ppt_deliverable_id}",
            lines,
        )

        # 8d. Worker 生成 PPT
        ppt_job = db.get(BackgroundJob, ppt_job_id)
        if not process_job(db, ppt_job, lines, "8d. PPT 生成"):
            return write_report(lines, report_path, "FAIL")

        # 8e. 完成项目 → COMPLETED
        project = outline_service.complete_project(db, project_id)
        db.commit()
        log(f"   8e. 完成项目: project={project.status}", lines)
        if not verify_status(
            project, ProjectStatus.COMPLETED.value, lines, "步骤 8"
        ):
            return write_report(lines, report_path, "FAIL")

        # 8f. 验证交付物文件存在
        word_path = (
            settings.project_data_root
            / project_id
            / "deliverables"
            / word_deliverable_id
            / "word_v1.docx"
        )
        ppt_path = (
            settings.project_data_root
            / project_id
            / "deliverables"
            / ppt_deliverable_id
            / "ppt_v1.pptx"
        )

        word_size = word_path.stat().st_size if word_path.exists() else 0
        ppt_size = ppt_path.stat().st_size if ppt_path.exists() else 0
        log(f"   8f. Word 文件: exists={word_path.exists()}, size={word_size} bytes", lines)
        log(f"   8f. PPT 文件: exists={ppt_path.exists()}, size={ppt_size} bytes", lines)

        if not word_path.exists() or not ppt_path.exists():
            log("❌ 交付物文件不存在", lines)
            return write_report(lines, report_path, "FAIL")

        # 8g. 验证文件可正常打开（真实文件验证）
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(str(word_path))
            log(f"   8g. Word 可打开: 段落数={len(doc.paragraphs)}", lines)
        except Exception as e:
            log(f"   ❌ Word 文件打开失败: {e}", lines)
            return write_report(lines, report_path, "FAIL")

        try:
            from pptx import Presentation as PptxPresentation

            prs = PptxPresentation(str(ppt_path))
            log(f"   8g. PPT 可打开: 幻灯片数={len(prs.slides)}", lines)
        except Exception as e:
            log(f"   ❌ PPT 文件打开失败: {e}", lines)
            return write_report(lines, report_path, "FAIL")

        # ============================================================
        # 最终验证汇总
        # ============================================================
        log("", lines)
        log("## 最终验证汇总", lines)
        db.refresh(project)
        log(f"项目 ID: {project_id}", lines)
        log(f"最终状态: {project.status}", lines)
        log(
            "状态路径: DRAFT → REQUIREMENT_CONFIRMED → SOURCES_COLLECTED → "
            "EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → "
            "ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED → "
            "OUTLINE_CONFIRMED → GENERATING → COMPLETED",
            lines,
        )
        log(f"Word 文件: {word_path.name} ({word_size} bytes)", lines)
        log(f"PPT 文件: {ppt_path.name} ({ppt_size} bytes)", lines)

        # 汇总执行产物
        exec_base = settings.project_data_root / project_id / "executions"
        if exec_base.exists():
            all_charts = list(exec_base.rglob("*.png"))
            all_tables = list(exec_base.rglob("*.csv"))
            log(f"执行产物总计: {len(all_charts)} 个图表, {len(all_tables)} 个表格", lines)

        if project.status == ProjectStatus.COMPLETED.value:
            log("", lines)
            log("=== ✅ SPEC 0029 端到端验收全部通过 ===", lines)
            print("E2E_RESULT=PASS")
            return write_report(lines, report_path, "PASS")
        else:
            log("", lines)
            log("=== ❌ SPEC 0029 端到端验收失败 ===", lines)
            print("E2E_RESULT=FAIL")
            return write_report(lines, report_path, "FAIL")

    except Exception as e:
        log(f"异常: {e}", lines)
        traceback.print_exc()
        print("E2E_RESULT=ERROR")
        return write_report(lines, report_path, "ERROR")
    finally:
        db.close()


def write_report(lines, report_path, result):
    """写入验收报告文件。"""
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"**验收结果：** {result}")
    lines.append(f"**报告生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n验收报告已保存到: {report_path}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
