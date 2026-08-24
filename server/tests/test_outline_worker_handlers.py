"""大纲与交付物 Worker 处理器测试。

覆盖 3 个新 handler：
- handle_generate_outline：基于已确认内容生成大纲候选
- handle_generate_word：从已确认大纲渲染 .docx 文件
- handle_generate_ppt：从同一份大纲渲染 .pptx 文件
- HANDLERS 注册表扩展
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.modules.execution.models import CodeTask, ExecutionRun, ExecutionArtifact
from app.modules.execution.status import (
    CodeTaskStatus,
    ExecutionRunStatus,
    ExecutionArtifactType,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.outlines.models import Outline, Deliverable, DeliverableVersion
from app.modules.outlines.status import (
    OutlineStatus,
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
)
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from worker import handlers as worker_handlers


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db(monkeypatch, tmp_path):
    """内存 SQLite + 受控 PROJECT_DATA_ROOT。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# --- 辅助函数 ---


def _create_project(db, status: str = ProjectStatus.RESULT_CONFIRMED.value) -> str:
    """创建项目并设置状态。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="大纲测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_succeeded_execution_run(
    db, project_id: str, run_id: str = "run_ol_001",
    stdout: str = "执行成功，输出统计结果",
) -> str:
    """插入一条成功的 ExecutionRun 和 CodeTask，返回 run_id。"""
    task = CodeTask(
        id="task_ol_001",
        project_id=project_id,
        analysis_plan_id="plan_ol_dummy",
        dataset_id="ds_ol_dummy",
        dataset_version_id="ver_ol_dummy",
        code="print('hello')",
        code_version=1,
        status=CodeTaskStatus.CONFIRMED.value,
        candidate_source="local_rule",
    )
    db.add(task)

    run = ExecutionRun(
        id=run_id,
        project_id=project_id,
        code_task_id=task.id,
        dataset_version_id="ver_ol_dummy",
        code_version=1,
        status=ExecutionRunStatus.SUCCEEDED.value,
        stdout=stdout,
        stderr="",
        exit_code=0,
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        duration_seconds=1.0,
    )
    db.add(run)
    db.commit()
    return run.id


def _seed_execution_artifact(
    db, project_id: str, run_id: str,
    artifact_id: str = "art_ol_001",
    name: str = "chart.png",
    file_path: str = "chart.png",
    artifact_type: str = ExecutionArtifactType.CHART_PNG.value,
) -> str:
    """插入一条执行产物，返回 artifact_id。"""
    art = ExecutionArtifact(
        id=artifact_id,
        execution_run_id=run_id,
        project_id=project_id,
        artifact_type=artifact_type,
        file_path=file_path,
        file_size_bytes=100,
        name=name,
    )
    db.add(art)
    db.commit()
    return art.id


def _seed_confirmed_outline(
    db, project_id: str, outline_id: str = "ol_wh_001",
) -> str:
    """插入一条 CONFIRMED 状态的大纲，返回 outline_id。"""
    outline = Outline(
        id=outline_id,
        project_id=project_id,
        sections_json=json.dumps([
            {"id": "s1", "title": "实验目的", "content": "分析胃病数据",
             "source_type": "REQUIREMENT", "source_ids": ["p1"]},
            {"id": "s2", "title": "实验背景", "content": "背景说明",
             "source_type": "EVIDENCE", "source_ids": ["c1"]},
            {"id": "s3", "title": "数据描述", "content": "100 行 × 3 列",
             "source_type": "DATASET", "source_ids": ["v1"]},
            {"id": "s4", "title": "分析方案", "content": "描述性统计",
             "source_type": "ANALYSIS", "source_ids": ["pa1"]},
            {"id": "s5", "title": "实验结果", "content": "执行成功",
             "source_type": "EXECUTION", "source_ids": ["run_ol_001"]},
            {"id": "s6", "title": "结论与讨论", "content": "完成分析目标",
             "source_type": "SUMMARY", "source_ids": []},
        ]),
        status=OutlineStatus.CONFIRMED.value,
        candidate_source="local_rule",
        code_version=1,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(outline)
    db.commit()
    return outline.id


def _seed_pending_deliverable(
    db, project_id: str, outline_id: str,
    deliverable_id: str = "del_wh_001",
    deliverable_type: str = DeliverableType.WORD.value,
) -> str:
    """插入一条 PENDING 状态的交付物，返回 deliverable_id。"""
    deliverable = Deliverable(
        id=deliverable_id,
        project_id=project_id,
        outline_id=outline_id,
        deliverable_type=deliverable_type,
        status=DeliverableStatus.PENDING.value,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(deliverable)
    db.commit()
    return deliverable.id


# --- handle_generate_outline ---


class TestHandleGenerateOutline:
    """生成大纲候选处理器测试。"""

    def test_success_path(self, db, monkeypatch):
        """成功路径：生成 Outline(CANDIDATE)，6 个章节。"""
        from app.modules.llm.outline_provider import FakeOutlineProvider

        project_id = _create_project(db)
        _seed_succeeded_execution_run(db, project_id)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_OUTLINE.value,
            {"project_id": project_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_outline_provider",
            lambda: FakeOutlineProvider(),
        )

        result = worker_handlers.handle_generate_outline(db, job)

        # 验证返回值
        assert result["outline_id"]
        assert result["section_count"] == 6

        # 验证 Outline 创建
        outline = db.query(Outline).filter(
            Outline.id == result["outline_id"]).first()
        assert outline is not None
        assert outline.status == OutlineStatus.CANDIDATE.value
        assert outline.candidate_source == "fake"
        sections = json.loads(outline.sections_json)
        assert len(sections) == 6

    def test_missing_project_id_raises(self, db):
        """任务缺少 project_id 时抛 JOB_INPUT_INVALID。

        job.project_id 为 NOT NULL，使用 mock 对象模拟缺失场景。
        """
        from types import SimpleNamespace
        mock_job = SimpleNamespace(
            input_json=json.dumps({}),  # 无 project_id
            project_id="",  # 空字符串，falsy
        )

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_outline(db, mock_job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_no_succeeded_execution_raises(self, db, monkeypatch):
        """没有成功的执行记录时抛 OUTLINE_NOT_GENERATABLE。"""
        from app.modules.llm.outline_provider import FakeOutlineProvider

        project_id = _create_project(db)
        # 不插入任何 ExecutionRun

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_OUTLINE.value,
            {"project_id": project_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_outline_provider",
            lambda: FakeOutlineProvider(),
        )

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_outline(db, job)
        assert exc_info.value.code == "OUTLINE_NOT_GENERATABLE"

    def test_regenerates_marks_old_candidate_stale(self, db, monkeypatch):
        """重新生成时旧 CANDIDATE 大纲变 STALE。"""
        from app.modules.llm.outline_provider import FakeOutlineProvider

        project_id = _create_project(db)
        _seed_succeeded_execution_run(db, project_id)

        # 第一次生成
        job1 = job_service.create_job(
            db, project_id, JobType.GENERATE_OUTLINE.value,
            {"project_id": project_id},
        )
        db.commit()
        monkeypatch.setattr(
            worker_handlers, "get_outline_provider",
            lambda: FakeOutlineProvider(),
        )
        result1 = worker_handlers.handle_generate_outline(db, job1)

        # 第二次生成
        job2 = job_service.create_job(
            db, project_id, JobType.GENERATE_OUTLINE.value,
            {"project_id": project_id},
        )
        db.commit()
        result2 = worker_handlers.handle_generate_outline(db, job2)

        # 第一次的大纲应变 STALE
        old_outline = db.query(Outline).filter(
            Outline.id == result1["outline_id"]).first()
        assert old_outline.status == OutlineStatus.STALE.value

        # 新大纲为 CANDIDATE
        new_outline = db.query(Outline).filter(
            Outline.id == result2["outline_id"]).first()
        assert new_outline.status == OutlineStatus.CANDIDATE.value


# --- handle_generate_word ---


class TestHandleGenerateWord:
    """Word 生成处理器测试。"""

    def test_success_path(self, db):
        """成功路径：生成 .docx 文件，DeliverableVersion(SUCCEEDED)。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_type=DeliverableType.WORD.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        result = worker_handlers.handle_generate_word(db, job)

        # 验证返回值
        assert result["deliverable_id"] == deliverable_id
        assert result["version_id"]
        assert result["version"] == 1
        assert result["file_size_bytes"] > 0

        # 验证 DeliverableVersion 状态
        version = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == result["version_id"]).first()
        assert version.status == DeliverableVersionStatus.SUCCEEDED.value
        assert version.file_path == "word_v1.docx"

        # 验证 Deliverable 状态
        deliverable = db.query(Deliverable).filter(
            Deliverable.id == deliverable_id).first()
        assert deliverable.status == DeliverableStatus.SUCCEEDED.value

        # 验证文件实际存在
        from app.core.config import settings
        file_path = (settings.project_data_root / project_id
                     / "deliverables" / deliverable_id / "word_v1.docx")
        assert file_path.exists()

    def test_outline_not_confirmed_raises(self, db):
        """大纲未 CONFIRMED 时抛 DELIVERABLE_NOT_GENERATABLE。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        # 创建 CANDIDATE 状态的大纲（非 CONFIRMED）
        outline_id = _seed_confirmed_outline(db, project_id)
        outline = db.query(Outline).filter(Outline.id == outline_id).first()
        outline.status = OutlineStatus.CANDIDATE.value
        db.commit()
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_word(db, job)
        assert exc_info.value.code == "DELIVERABLE_NOT_GENERATABLE"

    def test_missing_input_raises(self, db):
        """缺少 outline_id 或 deliverable_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": "ol_xxx"},  # 缺少 deliverable_id
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_word(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_project_advances_to_generating(self, db):
        """OUTLINE_CONFIRMED 项目生成 Word 后推进到 GENERATING。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        worker_handlers.handle_generate_word(db, job)

        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.GENERATING.value

    def test_second_generation_creates_new_version(self, db):
        """第二次生成创建新版本，旧版本保留。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        # 第一次生成
        job1 = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        result1 = worker_handlers.handle_generate_word(db, job1)

        # 第二次生成
        job2 = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        result2 = worker_handlers.handle_generate_word(db, job2)

        assert result1["version"] == 1
        assert result2["version"] == 2
        assert result1["version_id"] != result2["version_id"]

    def test_render_failure_marks_version_failed(self, db, monkeypatch):
        """渲染器抛异常时 DeliverableVersion 标记 FAILED，抛 WORD_RENDER_FAILED。"""
        from app.infrastructure.renderers.word_renderer import WordRenderer

        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        # mock WordRenderer.render 抛异常
        def _boom(self, **kwargs):
            raise RuntimeError("模拟渲染失败")

        monkeypatch.setattr(WordRenderer, "render", _boom)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_word(db, job)
        assert exc_info.value.code == "WORD_RENDER_FAILED"

        # 验证 DeliverableVersion FAILED
        version = (
            db.query(DeliverableVersion)
            .filter(DeliverableVersion.deliverable_id == deliverable_id)
            .first()
        )
        assert version.status == DeliverableVersionStatus.FAILED.value
        assert version.error_code == "WORD_RENDER_FAILED"

    def test_failed_generation_does_not_overwrite_success(self, db, monkeypatch):
        """失败生成不覆盖成功版本：v1 SUCCEEDED，v2 FAILED，v1 仍 SUCCEEDED。

        覆盖 project_memory 硬约束：失败生成不覆盖成功版本。
        """
        from app.infrastructure.renderers.word_renderer import WordRenderer

        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        # 第一次成功生成
        job1 = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        result1 = worker_handlers.handle_generate_word(db, job1)
        assert result1["version"] == 1

        # 第二次失败生成
        def _boom(self, **kwargs):
            raise RuntimeError("模拟渲染失败")

        monkeypatch.setattr(WordRenderer, "render", _boom)

        job2 = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        with pytest.raises(AppError):
            worker_handlers.handle_generate_word(db, job2)

        # 验证两个版本都存在，v1 仍 SUCCEEDED，v2 FAILED
        versions = (
            db.query(DeliverableVersion)
            .filter(DeliverableVersion.deliverable_id == deliverable_id)
            .order_by(DeliverableVersion.version)
            .all()
        )
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[0].status == DeliverableVersionStatus.SUCCEEDED.value
        assert versions[1].version == 2
        assert versions[1].status == DeliverableVersionStatus.FAILED.value

        # 验证 v1 的文件仍存在（未被覆盖）
        from app.core.config import settings
        v1_file = (settings.project_data_root / project_id
                   / "deliverables" / deliverable_id / "word_v1.docx")
        assert v1_file.exists(), "成功版本的文件不应被失败生成删除"

    def test_outline_not_found_raises(self, db):
        """outline_id 在数据库找不到时抛 OUTLINE_NOT_FOUND。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": "ol_nonexist", "deliverable_id": "del_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_word(db, job)
        assert exc_info.value.code == "OUTLINE_NOT_FOUND"

    def test_deliverable_not_found_raises(self, db):
        """deliverable_id 在数据库找不到时抛 DELIVERABLE_NOT_FOUND。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": "del_nonexist"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_word(db, job)
        assert exc_info.value.code == "DELIVERABLE_NOT_FOUND"

    def test_template_render_failure_falls_back(self, db, monkeypatch):
        """Word 模板渲染失败时降级到默认渲染，版本仍 SUCCEEDED（SPEC 0010 降级链）。"""
        from types import SimpleNamespace
        from app.infrastructure.renderers.word_renderer import WordRenderer
        from app.modules.outlines import service as outline_service

        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(db, project_id, outline_id)

        # mock 项目有 Word 模板
        monkeypatch.setattr(
            outline_service, "get_word_template",
            lambda db, pid: SimpleNamespace(file_path="templates/tpl.docx"),
        )

        call_log = {}

        def _render_with_template(self, **kwargs):
            call_log["template_called"] = True
            raise AppError(code="WORD_TEMPLATE_PARSE_FAILED",
                           message="模板解析失败")

        def _render(self, **kwargs):
            call_log["default_called"] = True
            output_path = kwargs.get("output_path")
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(b"fake docx content")

        monkeypatch.setattr(WordRenderer, "render_with_template",
                            _render_with_template)
        monkeypatch.setattr(WordRenderer, "render", _render)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_WORD.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        result = worker_handlers.handle_generate_word(db, job)

        # 验证降级：模板渲染被调用且失败，默认渲染被调用
        assert call_log.get("template_called") is True
        assert call_log.get("default_called") is True

        # 验证版本仍 SUCCEEDED（降级成功）
        version = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == result["version_id"]).first()
        assert version.status == DeliverableVersionStatus.SUCCEEDED.value
        assert result["template_used"] is True


# --- handle_generate_ppt ---


class TestHandleGeneratePpt:
    """PPT 生成处理器测试。"""

    def test_success_path(self, db):
        """成功路径：生成 .pptx 文件，DeliverableVersion(SUCCEEDED)。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_id="del_ppt_001",
            deliverable_type=DeliverableType.PPT.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        result = worker_handlers.handle_generate_ppt(db, job)

        # 验证返回值
        assert result["deliverable_id"] == deliverable_id
        assert result["version_id"]
        assert result["version"] == 1
        assert result["file_size_bytes"] > 0

        # 验证 DeliverableVersion 状态
        version = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == result["version_id"]).first()
        assert version.status == DeliverableVersionStatus.SUCCEEDED.value
        assert version.file_path == "ppt_v1.pptx"

        # 验证文件实际存在
        from app.core.config import settings
        file_path = (settings.project_data_root / project_id
                     / "deliverables" / deliverable_id / "ppt_v1.pptx")
        assert file_path.exists()

    def test_outline_not_confirmed_raises(self, db):
        """大纲未 CONFIRMED 时抛 DELIVERABLE_NOT_GENERATABLE。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        outline_id = _seed_confirmed_outline(db, project_id)
        outline = db.query(Outline).filter(Outline.id == outline_id).first()
        outline.status = OutlineStatus.CANDIDATE.value
        db.commit()
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_type=DeliverableType.PPT.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_ppt(db, job)
        assert exc_info.value.code == "DELIVERABLE_NOT_GENERATABLE"

    def test_missing_input_raises(self, db):
        """缺少 outline_id 或 deliverable_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"deliverable_id": "del_xxx"},  # 缺少 outline_id
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_ppt(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_project_advances_to_generating(self, db):
        """OUTLINE_CONFIRMED 项目生成 PPT 后推进到 GENERATING。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_id="del_ppt_adv",
            deliverable_type=DeliverableType.PPT.value)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        worker_handlers.handle_generate_ppt(db, job)

        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.GENERATING.value

    def test_second_generation_creates_new_version(self, db):
        """第二次生成 PPT 创建新版本，旧版本保留。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_id="del_ppt_v2",
            deliverable_type=DeliverableType.PPT.value)

        # 第一次生成
        job1 = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        result1 = worker_handlers.handle_generate_ppt(db, job1)

        # 第二次生成
        job2 = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()
        result2 = worker_handlers.handle_generate_ppt(db, job2)

        assert result1["version"] == 1
        assert result2["version"] == 2
        assert result1["version_id"] != result2["version_id"]

        # 验证两个版本文件都存在
        from app.core.config import settings
        base = (settings.project_data_root / project_id
                / "deliverables" / deliverable_id)
        assert (base / "ppt_v1.pptx").exists()
        assert (base / "ppt_v2.pptx").exists()

    def test_render_failure_marks_version_failed(self, db, monkeypatch):
        """PPT 渲染器抛异常时 DeliverableVersion 标记 FAILED，抛 PPT_RENDER_FAILED。"""
        from app.infrastructure.renderers.ppt_renderer import PptRenderer

        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_id="del_ppt_fail",
            deliverable_type=DeliverableType.PPT.value)

        # mock PptRenderer.render 抛异常
        def _boom(self, **kwargs):
            raise RuntimeError("模拟 PPT 渲染失败")

        monkeypatch.setattr(PptRenderer, "render", _boom)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_ppt(db, job)
        assert exc_info.value.code == "PPT_RENDER_FAILED"

        # 验证 DeliverableVersion FAILED
        version = (
            db.query(DeliverableVersion)
            .filter(DeliverableVersion.deliverable_id == deliverable_id)
            .first()
        )
        assert version.status == DeliverableVersionStatus.FAILED.value
        assert version.error_code == "PPT_RENDER_FAILED"

    def test_config_render_failure_falls_back(self, db, monkeypatch):
        """PPT 配置渲染失败时降级到默认渲染，版本仍 SUCCEEDED（SPEC 0011 降级链）。"""
        from app.infrastructure.renderers.ppt_renderer import PptRenderer

        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_succeeded_execution_run(db, project_id)
        outline_id = _seed_confirmed_outline(db, project_id)
        deliverable_id = _seed_pending_deliverable(
            db, project_id, outline_id,
            deliverable_id="del_ppt_cfg",
            deliverable_type=DeliverableType.PPT.value)

        call_log = {"render_calls": []}

        def _render(self, **kwargs):
            call_log["render_calls"].append(kwargs.get("config"))
            # 第一次（带 config）抛 AppError 触发降级
            if kwargs.get("config") is not None and len(call_log["render_calls"]) == 1:
                raise AppError(code="PPT_CONFIG_INVALID",
                               message="配置无效")
            # 降级调用（无 config）正常执行
            output_path = kwargs.get("output_path")
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(b"fake pptx content")

        monkeypatch.setattr(PptRenderer, "render", _render)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_PPT.value,
            {"outline_id": outline_id, "deliverable_id": deliverable_id,
             "config": {"target_pages": 10}},
        )
        db.commit()

        result = worker_handlers.handle_generate_ppt(db, job)

        # 验证降级：第一次带 config 失败，第二次无 config 成功
        assert len(call_log["render_calls"]) == 2
        assert call_log["render_calls"][0] is not None  # 第一次带 config
        assert call_log["render_calls"][1] is None      # 降级无 config

        # 验证版本 SUCCEEDED（降级成功）
        version = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == result["version_id"]).first()
        assert version.status == DeliverableVersionStatus.SUCCEEDED.value


class TestHandleGeneratePdf:
    """PDF 派生处理器测试。"""

    def test_success_path_from_word_version(self, db, monkeypatch):
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value
        )
        outline_id = _seed_confirmed_outline(db, project_id, "ol_pdf_001")
        word_id = _seed_pending_deliverable(
            db,
            project_id,
            outline_id,
            "del_pdf_word_001",
            deliverable_type=DeliverableType.WORD.value,
        )
        word = db.query(Deliverable).filter(Deliverable.id == word_id).one()
        word.status = DeliverableStatus.SUCCEEDED.value
        word_version = DeliverableVersion(
            id="ver_pdf_word_001",
            deliverable_id=word_id,
            project_id=project_id,
            version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="word_v1.docx",
            file_size_bytes=128,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(word_version)
        pdf_id = _seed_pending_deliverable(
            db,
            project_id,
            outline_id,
            "del_pdf_001",
            deliverable_type=DeliverableType.PDF.value,
        )
        db.commit()

        from app.core.config import settings
        source_path = (
            settings.project_data_root
            / project_id
            / "deliverables"
            / word_id
            / "word_v1.docx"
        )
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"PK\\x03\\x04fixture")

        def fake_export(self, source, target):
            assert source == source_path.resolve()
            target.write_bytes(b"%PDF-1.7\\n%%EOF")

        from app.infrastructure.documents.docx_pdf_exporter import DocxPdfExporter
        monkeypatch.setattr(DocxPdfExporter, "export", fake_export)

        job = job_service.create_job(
            db,
            project_id,
            JobType.GENERATE_PDF.value,
            {
                "outline_id": outline_id,
                "deliverable_id": pdf_id,
                "source_word_deliverable_id": word_id,
                "source_word_version_id": word_version.id,
            },
        )
        db.commit()

        result = worker_handlers.handle_generate_pdf(db, job)

        assert result["source_word_version_id"] == word_version.id
        version = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == result["version_id"]
        ).one()
        assert version.status == DeliverableVersionStatus.SUCCEEDED.value
        assert version.file_path == "report_v1.pdf"


# --- HANDLERS 注册表扩展 ---


class TestHandlersRegistryOutline:
    """HANDLERS 注册表扩展测试：覆盖新增的 4 个大纲相关 handler。"""

    def test_handlers_registry_includes_outline_handlers(self):
        """HANDLERS 包含 GENERATE_OUTLINE、GENERATE_WORD、GENERATE_PDF、GENERATE_PPT 映射。"""
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_OUTLINE.value]
            is worker_handlers.handle_generate_outline
        )
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_WORD.value]
            is worker_handlers.handle_generate_word
        )
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_PPT.value]
            is worker_handlers.handle_generate_ppt
        )
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_PDF.value]
            is worker_handlers.handle_generate_pdf
        )
