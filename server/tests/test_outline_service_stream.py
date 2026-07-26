"""大纲核心服务流式生成测试 (stream_generate_outline)。

SPEC 0019 大纲生成流式化。

测试：
- 流式成功：yield StreamOutlineChunkEvent 多个 + StreamOutlineDoneEvent，Outline 保存
- 中途失败：yield StreamOutlineErrorEvent，不保存 Outline
- 兼容不支持流式的 provider（LocalRule/Fake）：调用 generate() 一次性 yield
- 项目状态不满足：抛 AppError
- 无成功执行记录：抛 AppError
- 项目不存在：抛 AppError
- JSON 校验失败：yield StreamOutlineErrorEvent，不保存 Outline
- gather_outline_context 上下文聚合正确性

mock provider.stream_generate 生成器方法。
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.modules.outlines import service as outline_service
from app.modules.outlines.models import Outline
from app.modules.outlines.status import OutlineStatus
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.status import ProjectStatus
from app.modules.execution.models import CodeTask, ExecutionRun
from app.modules.execution.status import (
    CodeTaskStatus,
    ExecutionRunStatus,
)


TEST_DB = "sqlite:///:memory:"


def _make_valid_outline_json() -> str:
    """构造有效的大纲 JSON（符合 DeepSeekOutlineResponse 校验）。"""
    return json.dumps({
        "sections": [
            {
                "id": "purpose",
                "title": "实验目的",
                "content": "分析胃病数据分布",
                "source_type": "REQUIREMENT",
                "source_ids": ["plan_001"],
            },
            {
                "id": "background",
                "title": "实验背景",
                "content": "胃病发病率上升",
                "source_type": "EVIDENCE",
                "source_ids": ["card_001"],
            },
            {
                "id": "dataset",
                "title": "数据与数据集",
                "content": "100 行 × 3 列",
                "source_type": "DATASET",
                "source_ids": ["ver_001"],
            },
            {
                "id": "analysis",
                "title": "分析方案",
                "content": "描述性统计",
                "source_type": "ANALYSIS",
                "source_ids": ["ap_001"],
            },
            {
                "id": "results",
                "title": "执行结果",
                "content": "执行成功，输出统计结果",
                "source_type": "EXECUTION",
                "source_ids": ["run_001"],
            },
            {
                "id": "conclusion",
                "title": "结论与总结",
                "content": "完成分析目标",
                "source_type": "SUMMARY",
                "source_ids": [],
            },
        ]
    }, ensure_ascii=False)


# --- fixtures ---


@pytest.fixture
def engine_factory(monkeypatch, tmp_path):
    """创建内存 SQLite engine + SessionLocal factory，供 Phase 4 复用。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # patch engine.SessionLocal，让 service Phase 4 用同一 engine
    from app.infrastructure.database import engine as db_engine
    monkeypatch.setattr(db_engine, "SessionLocal", TestingSessionLocal)

    yield engine, TestingSessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(engine_factory):
    _, TestingSessionLocal = engine_factory
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def testing_session_local(engine_factory):
    _, TestingSessionLocal = engine_factory
    return TestingSessionLocal


# --- 辅助函数 ---


def _create_project(db, status: str = ProjectStatus.RESULT_CONFIRMED.value) -> str:
    """创建项目并设置状态。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="流式大纲测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_succeeded_execution_run(
    db, project_id: str, run_id: str = "run_str_001",
    stdout: str = "执行成功，输出统计结果",
    task_id: str = "task_str_001",
) -> str:
    """插入一条成功的 ExecutionRun 和 CodeTask，返回 run_id。"""
    task = CodeTask(
        id=task_id,
        project_id=project_id,
        analysis_plan_id="plan_str_dummy",
        dataset_id="ds_str_dummy",
        dataset_version_id="ver_str_dummy",
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
        dataset_version_id="ver_str_dummy",
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


# --- Mock Provider ---


class _MockStreamProvider:
    """支持流式的大纲 provider 测试替身。"""

    def __init__(self, chunks: list[str], source_label: str = "DEEPSEEK"):
        self._chunks = chunks
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def stream_generate(self, context):
        for c in self._chunks:
            yield c


class _MockSyncProvider:
    """不支持流式的大纲 provider 测试替身（LocalRule/Fake 风格）。"""

    def __init__(self, outline_json: str, source_label: str = "LOCAL_RULE"):
        self._outline_json = outline_json
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def generate(self, context):
        from app.modules.llm.outline_provider import (
            OutlineDraft,
            OutlineDraftSection,
        )
        data = json.loads(self._outline_json)
        sections = [
            OutlineDraftSection(
                id=s["id"],
                title=s["title"],
                content=s["content"],
                source_type=s["source_type"],
                source_ids=s.get("source_ids", []),
            )
            for s in data["sections"]
        ]
        return OutlineDraft(sections=sections)


class _MockFailingStreamProvider:
    """中途失败的流式 provider。"""

    def __init__(self, chunks_before_failure: list[str], exc: Exception):
        self._chunks = chunks_before_failure
        self._exc = exc

    def source_label(self) -> str:
        return "DEEPSEEK"

    def stream_generate(self, context):
        for c in self._chunks:
            yield c
        raise self._exc


# --- 流式成功场景 ---


class TestStreamGenerateOutlineSuccess:
    """流式成功场景。"""

    def test_流式成功yield_chunks_和_done(self, db, testing_session_local, project_id_with_exec):
        """完整流程：yield StreamOutlineChunkEvent 多个 + StreamOutlineDoneEvent。"""
        full_json = _make_valid_outline_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, outline_service.StreamOutlineChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]

        assert len(chunk_events) == len(chunks)
        assert len(done_events) == 1

        # chunk 内容拼接应等于 full_json
        assert "".join(e.text for e in chunk_events) == full_json

        # done 事件应包含 outline_id 和 candidate_source
        done = done_events[0]
        assert done.candidate_source == "DEEPSEEK"
        assert done.outline_id  # 非空

    def test_流式成功后保存Outline(self, db, testing_session_local, project_id_with_exec):
        """流式完成后应保存 Outline 到数据库。"""
        full_json = _make_valid_outline_json()
        provider = _MockStreamProvider(chunks=[full_json])

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]
        assert len(done_events) == 1
        outline_id = done_events[0].outline_id

        # 用新 session 查询数据库，验证 outline 已保存
        verify_db = testing_session_local()
        try:
            outline = verify_db.query(Outline).filter(
                Outline.id == outline_id
            ).first()
            assert outline is not None
            assert outline.status == OutlineStatus.CANDIDATE.value
            assert outline.candidate_source == "DEEPSEEK"
        finally:
            verify_db.close()

    def test_新生成标记旧候选为STALE(self, db, testing_session_local, project_id_with_exec):
        """已有 CANDIDATE 应被标记为 STALE。"""
        # 先用 sync provider 生成一个 outline
        sync_provider = _MockSyncProvider(_make_valid_outline_json())
        old_draft = sync_provider.generate({})
        old_sections = [
            {"id": s.id, "title": s.title, "content": s.content,
             "source_type": s.source_type, "source_ids": s.source_ids}
            for s in old_draft.sections
        ]
        old_outline = outline_service.save_outline_draft(
            db, project_id=project_id_with_exec,
            sections=old_sections, candidate_source="LOCAL_RULE",
        )
        old_outline_id = old_outline.id  # 在 session 关闭前保存 ID
        db.commit()

        # 再用流式生成新的
        provider = _MockStreamProvider(chunks=[_make_valid_outline_json()])
        list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        # 旧 outline 应为 STALE
        verify_db = testing_session_local()
        try:
            old = verify_db.query(Outline).filter(
                Outline.id == old_outline_id
            ).first()
            assert old.status == OutlineStatus.STALE.value
        finally:
            verify_db.close()


# --- 中途失败场景 ---


class TestStreamGenerateOutlineMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败yield_StreamErrorEvent(self, db, testing_session_local, project_id_with_exec):
        """provider 中途失败应 yield StreamOutlineErrorEvent，不保存 Outline。"""
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分内容"],
            exc=Exception("LLM 中断"),
        )

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, outline_service.StreamOutlineChunkEvent)]
        error_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]

        assert len(chunk_events) == 1
        assert len(error_events) == 1
        assert len(done_events) == 0

        err = error_events[0]
        assert err.partial_text == "部分内容"
        assert err.error_code  # 非空

    def test_中途失败不保存Outline(self, db, testing_session_local, project_id_with_exec):
        """中途失败时不应保存 Outline。"""
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分"],
            exc=Exception("中断"),
        )

        list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(Outline).filter(
                Outline.project_id == project_id_with_exec,
                Outline.status == OutlineStatus.CANDIDATE.value,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- JSON 校验失败场景 ---


class TestStreamGenerateOutlineJsonParseFailure:
    """JSON 校验失败场景。"""

    def test_JSON校验失败yield_ErrorEvent(self, db, testing_session_local, project_id_with_exec):
        """流式完成后 JSON 校验失败应 yield StreamOutlineErrorEvent。"""
        # 提供无效 JSON
        provider = _MockStreamProvider(chunks=["{invalid json}"])

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        error_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]

        assert len(error_events) == 1
        assert len(done_events) == 0
        assert error_events[0].error_code == "OUTLINE_JSON_PARSE_ERROR"

    def test_JSON校验失败不保存Outline(self, db, testing_session_local, project_id_with_exec):
        """JSON 校验失败时不应保存 Outline。"""
        provider = _MockStreamProvider(chunks=["{invalid}"])

        list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(Outline).filter(
                Outline.project_id == project_id_with_exec,
                Outline.status == OutlineStatus.CANDIDATE.value,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- 兼容同步 provider 场景 ---


class TestStreamGenerateOutlineSyncProvider:
    """兼容不支持 stream_generate 的 provider。"""

    def test_同步provider一次性yield(self, db, testing_session_local, project_id_with_exec):
        """LocalRule/Fake provider 不支持 stream_generate，应调用 generate() 一次性 yield。"""
        provider = _MockSyncProvider(_make_valid_outline_json())

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, outline_service.StreamOutlineChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]

        # 应有多个 chunk（按 50 字符拆分）+ 1 个 done
        assert len(chunk_events) >= 1
        assert len(done_events) == 1
        assert done_events[0].candidate_source == "LOCAL_RULE"

    def test_同步provider保存Outline(self, db, testing_session_local, project_id_with_exec):
        """同步 provider 流式后应保存 Outline。"""
        provider = _MockSyncProvider(_make_valid_outline_json())

        events = list(outline_service.stream_generate_outline(
            db, project_id_with_exec, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, outline_service.StreamOutlineDoneEvent)]
        assert len(done_events) == 1

        verify_db = testing_session_local()
        try:
            outline = verify_db.query(Outline).filter(
                Outline.id == done_events[0].outline_id
            ).first()
            assert outline is not None
            assert outline.candidate_source == "LOCAL_RULE"
        finally:
            verify_db.close()


# --- 校验失败场景 ---


class TestStreamGenerateOutlineValidation:
    """前置校验失败场景。"""

    def test_项目不存在抛AppError(self, db):
        """项目不存在应抛 AppError。"""
        provider = _MockStreamProvider(chunks=[_make_valid_outline_json()])

        with pytest.raises(AppError) as exc_info:
            list(outline_service.stream_generate_outline(
                db, "nonexistent_project", provider
            ))
        assert exc_info.value.code == "PROJECT_NOT_FOUND"

    def test_项目状态不满足抛AppError(self, db, testing_session_local):
        """项目状态未达 RESULT_CONFIRMED 应抛 AppError。"""
        project_id = _create_project(
            db, status=ProjectStatus.REQUIREMENT_PARSED.value
        )
        _seed_succeeded_execution_run(db, project_id)

        provider = _MockStreamProvider(chunks=[_make_valid_outline_json()])

        with pytest.raises(AppError) as exc_info:
            list(outline_service.stream_generate_outline(
                db, project_id, provider
            ))
        assert exc_info.value.code == "OUTLINE_NOT_GENERATABLE"

    def test_无成功执行记录抛AppError(self, db, testing_session_local):
        """无成功执行记录应抛 AppError。"""
        project_id = _create_project(db)  # RESULT_CONFIRMED，但不插入 ExecutionRun

        provider = _MockStreamProvider(chunks=[_make_valid_outline_json()])

        with pytest.raises(AppError) as exc_info:
            list(outline_service.stream_generate_outline(
                db, project_id, provider
            ))
        assert exc_info.value.code == "OUTLINE_NOT_GENERATABLE"


# --- gather_outline_context 测试 ---


class TestGatherOutlineContext:
    """上下文聚合正确性测试。"""

    def test_空项目返回基本结构(self, db, testing_session_local):
        """无任何已确认内容时应返回基本 context 结构。"""
        project_id = _create_project(db)

        context = outline_service.gather_outline_context(db, project_id)

        # 应包含 project 信息
        assert "project" in context
        assert context["project"]["id"] == project_id
        # 无已确认内容时各字段应为空列表
        assert context["evidence_cards"] == []
        assert context["executions"] == []

    def test_包含成功的执行记录(self, db, testing_session_local):
        """context 应包含成功的执行记录。"""
        project_id = _create_project(db)
        run_id = _seed_succeeded_execution_run(
            db, project_id, stdout="统计结果输出"
        )

        context = outline_service.gather_outline_context(db, project_id)

        assert len(context["executions"]) == 1
        assert context["executions"][0]["run_id"] == run_id
        assert "统计结果输出" in context["executions"][0]["stdout"]

    def test_不包含非成功的执行记录(self, db, testing_session_local):
        """非 SUCCEEDED 状态的执行记录不应进入 context。"""
        project_id = _create_project(db)
        # 插入一条 FAILED 的执行记录
        task = CodeTask(
            id="task_failed_001",
            project_id=project_id,
            analysis_plan_id="plan_fail",
            dataset_id="ds_fail",
            dataset_version_id="ver_fail",
            code="print('error')",
            code_version=1,
            status=CodeTaskStatus.CONFIRMED.value,
            candidate_source="local_rule",
        )
        db.add(task)
        run = ExecutionRun(
            id="run_failed_001",
            project_id=project_id,
            code_task_id=task.id,
            dataset_version_id="ver_fail",
            code_version=1,
            status=ExecutionRunStatus.FAILED.value,
            stdout="",
            stderr="error",
            exit_code=1,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            duration_seconds=1.0,
        )
        db.add(run)
        db.commit()

        context = outline_service.gather_outline_context(db, project_id)

        assert len(context["executions"]) == 0

    def test_多条成功执行记录全部聚合(self, db, testing_session_local):
        """多条 SUCCEEDED 执行记录应全部进入 context。"""
        project_id = _create_project(db)
        _seed_succeeded_execution_run(
            db, project_id, run_id="run_multi_001", task_id="task_multi_001",
            stdout="结果一",
        )
        _seed_succeeded_execution_run(
            db, project_id, run_id="run_multi_002", task_id="task_multi_002",
            stdout="结果二",
        )

        context = outline_service.gather_outline_context(db, project_id)

        assert len(context["executions"]) == 2
        stdout_list = [e["stdout"] for e in context["executions"]]
        assert "结果一" in stdout_list
        assert "结果二" in stdout_list

    def test_执行产物聚合到context(self, db, testing_session_local):
        """执行产物应聚合到 context.executions.artifacts。"""
        from app.modules.execution.models import ExecutionArtifact
        from app.modules.execution.status import ExecutionArtifactType

        project_id = _create_project(db)
        run_id = _seed_succeeded_execution_run(db, project_id)

        art = ExecutionArtifact(
            id="art_ctx_001",
            execution_run_id=run_id,
            project_id=project_id,
            artifact_type=ExecutionArtifactType.CHART_PNG.value,
            file_path="chart.png",
            file_size_bytes=100,
            name="分布图",
        )
        db.add(art)
        db.commit()

        context = outline_service.gather_outline_context(db, project_id)

        assert len(context["executions"]) == 1
        assert len(context["executions"][0]["artifacts"]) == 1
        assert context["executions"][0]["artifacts"][0]["name"] == "分布图"


# --- 共享 fixture ---


@pytest.fixture
def project_id_with_exec(db):
    """创建项目（RESULT_CONFIRMED）+ 成功执行记录，返回 project_id。"""
    project_id = _create_project(db)
    _seed_succeeded_execution_run(db, project_id)
    return project_id
