"""需求核心服务流式生成测试 (stream_generate_plan)。

测试：
- 流式成功：yield StreamChunkEvent 多个 + StreamDoneEvent，RequirementPlan 保存
- 中途失败：yield StreamErrorEvent，不保存 RequirementPlan
- 兼容不支持流式的 provider（LocalRule）：一次性 yield
- source 不属于项目：抛 AppError
- source 不存在：抛 AppError
- 项目不存在：抛 AppError

mock provider.stream_draft 生成器方法。
"""

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.requirements import service as req_service
from app.modules.requirements.contracts import (
    TextSourceRequest,
    GeneratePlanRequest,
    RequirementPlanPayload,
)
from app.modules.requirements.models import RequirementPlan
from app.modules.requirements.status import PlanStatus
from app.modules.projects.status import ProjectStatus
from app.core.errors import AppError


TEST_DB = "sqlite:///:memory:"


def _make_valid_payload_json() -> str:
    """构造有效的 RequirementPlanPayload JSON。"""
    payload = {
        "topic": "胃病数据分析",
        "experiment_type": "数据分析与可视化",
        "research_subject": "胃病数据",
        "required_tasks": [
            {
                "title": "数据加载",
                "description": "加载数据集",
                "task_type": "REQUIRED",
                "reason": "必要步骤",
                "source_quote": None,
            }
        ],
        "recommended_tasks": [],
        "optional_tasks": [],
        "out_of_scope_tasks": [],
        "unknown_items": [],
        "data_requirements": ["CSV"],
        "method_requirements": ["描述性统计"],
        "chart_requirements": ["直方图"],
        "report_requirements": ["实验报告"],
        "presentation_requirements": ["PPT"],
        "acceptance_criteria": ["可追溯"],
        "replication_level": {
            "level": "L0",
            "label": "不复刻",
            "supported_in_v1": True,
            "reason": "无复刻要求",
            "suggested_scope": "独立分析",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


@pytest.fixture
def engine():
    eng = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def testing_session_local(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def db(testing_session_local):
    session = testing_session_local()
    yield session
    session.close()


@pytest.fixture
def project_id(db):
    p = project_service.create_project(db, ProjectCreateRequest(name="测试项目", topic="测试"))
    return p.id


@pytest.fixture
def source_id(db, project_id):
    src = req_service.add_text_source(
        db, project_id, TextSourceRequest(title="需求", text="完成胃病数据分析")
    )
    return src.id


class _MockStreamProvider:
    """支持流式的 provider 测试替身。"""

    def __init__(self, chunks: list[str], source_label: str = "DEEPSEEK"):
        self._chunks = chunks
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def stream_draft(self, requirement_text: str):
        for c in self._chunks:
            yield c


class _MockSyncProvider:
    """不支持流式的 provider 测试替身（LocalRule 风格）。"""

    def __init__(self, payload_json: str, source_label: str = "LOCAL_RULE"):
        self._payload_json = payload_json
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def draft(self, requirement_text: str) -> RequirementPlanPayload:
        return RequirementPlanPayload.model_validate_json(self._payload_json)


class _MockFailingStreamProvider:
    """中途失败的流式 provider。"""

    def __init__(self, chunks_before_failure: list[str], exc: Exception):
        self._chunks = chunks_before_failure
        self._exc = exc

    def source_label(self) -> str:
        return "DEEPSEEK"

    def stream_draft(self, requirement_text: str):
        for c in self._chunks:
            yield c
        raise self._exc


class TestStreamGeneratePlanSuccess:
    """流式成功场景。"""

    def test_流式成功yield_chunks_和_done(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """完整流程：yield StreamChunkEvent 多个 + StreamDoneEvent，RequirementPlan 保存。"""
        # patch SessionLocal 使 Phase 4 用同一 engine 的 session
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        full_json = _make_valid_payload_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        # 应有多个 chunk 事件 + 1 个 done 事件
        chunk_events = [e for e in events if isinstance(e, req_service.StreamChunkEvent)]
        done_events = [e for e in events if isinstance(e, req_service.StreamDoneEvent)]
        assert len(chunk_events) == len(chunks)
        assert len(done_events) == 1

        # chunk 内容拼接应等于 full_json
        assert "".join(e.text for e in chunk_events) == full_json

        # done 事件应包含 plan_id 和 candidate_source
        done = done_events[0]
        assert done.candidate_source == "DEEPSEEK"
        assert done.plan_id  # 非空

    def test_流式成功后保存RequirementPlan(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """流式完成后应保存 RequirementPlan 到数据库。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        full_json = _make_valid_payload_json()
        provider = _MockStreamProvider(chunks=[full_json])

        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        done_events = [e for e in events if isinstance(e, req_service.StreamDoneEvent)]
        assert len(done_events) == 1
        plan_id = done_events[0].plan_id

        # 用新 session 查询数据库，验证 plan 已保存
        verify_db = testing_session_local()
        try:
            plan = verify_db.query(RequirementPlan).filter(
                RequirementPlan.id == plan_id
            ).first()
            assert plan is not None
            assert plan.status == PlanStatus.CANDIDATE.value
            assert plan.candidate_source == "DEEPSEEK"
        finally:
            verify_db.close()

    def test_流式生成推进project状态(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """流式完成后应推进 project.status 为 REQUIREMENT_PARSED。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        full_json = _make_valid_payload_json()
        provider = _MockStreamProvider(chunks=[full_json])

        list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        verify_db = testing_session_local()
        try:
            project = project_service.get_project(verify_db, project_id)
            assert project.status == ProjectStatus.REQUIREMENT_PARSED.value
        finally:
            verify_db.close()

    def test_新生成标记旧候选为STALE(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """已有 CANDIDATE 应被标记为 STALE。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        # 先生成一个 plan（用 sync provider）
        sync_provider = _MockSyncProvider(_make_valid_payload_json())
        from app.modules.requirements.contracts import GeneratePlanRequest
        old_plan = req_service.generate_plan(
            testing_session_local(), project_id,
            GeneratePlanRequest(source_id=source_id), sync_provider
        )

        # 再用流式生成新的
        provider = _MockStreamProvider(chunks=[_make_valid_payload_json()])
        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        # 旧 plan 应为 STALE
        verify_db = testing_session_local()
        try:
            old = verify_db.query(RequirementPlan).filter(
                RequirementPlan.id == old_plan.id
            ).first()
            assert old.status == PlanStatus.STALE.value
        finally:
            verify_db.close()


class TestStreamGeneratePlanMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败yield_StreamErrorEvent(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """provider 中途失败应 yield StreamErrorEvent，不保存 RequirementPlan。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分内容"],
            exc=Exception("LLM 中断"),
        )

        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        chunk_events = [e for e in events if isinstance(e, req_service.StreamChunkEvent)]
        error_events = [e for e in events if isinstance(e, req_service.StreamErrorEvent)]
        done_events = [e for e in events if isinstance(e, req_service.StreamDoneEvent)]

        # 应有 1 个 chunk + 1 个 error，0 个 done
        assert len(chunk_events) == 1
        assert len(error_events) == 1
        assert len(done_events) == 0

        # error 事件应包含 partial_text
        err = error_events[0]
        assert err.partial_text == "部分内容"
        assert err.error_code  # 非空

    def test_中途失败不保存RequirementPlan(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """中途失败时不应保存 RequirementPlan。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分"],
            exc=Exception("中断"),
        )

        list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        # 验证没有 CANDIDATE plan
        verify_db = testing_session_local()
        try:
            count = verify_db.query(RequirementPlan).filter(
                RequirementPlan.project_id == project_id,
                RequirementPlan.status == PlanStatus.CANDIDATE.value,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


class TestStreamGeneratePlanCompatibleWithSyncProvider:
    """兼容不支持流式的 provider（LocalRule）。"""

    def test_不支持stream_draft时一次性yield(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """provider 没有 stream_draft 方法时，应调用 draft() 并拆分 yield。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        full_json = _make_valid_payload_json()
        provider = _MockSyncProvider(full_json, source_label="LOCAL_RULE")

        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        chunk_events = [e for e in events if isinstance(e, req_service.StreamChunkEvent)]
        done_events = [e for e in events if isinstance(e, req_service.StreamDoneEvent)]

        # 应有多个 chunk（拆分）+ 1 个 done
        assert len(chunk_events) >= 1
        assert len(done_events) == 1
        assert done_events[0].candidate_source == "LOCAL_RULE"


class TestStreamGeneratePlanValidationErrors:
    """校验失败场景。"""

    def test_项目不存在抛AppError(self, db, source_id, testing_session_local, monkeypatch):
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )
        provider = _MockStreamProvider(chunks=["{}"])

        with pytest.raises(AppError) as exc:
            list(req_service.stream_generate_plan(
                db, "proj_missing",
                GeneratePlanRequest(source_id=source_id), provider
            ))
        assert exc.value.code == "PROJECT_NOT_FOUND"

    def test_source不存在抛AppError(self, db, project_id, testing_session_local, monkeypatch):
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )
        provider = _MockStreamProvider(chunks=["{}"])

        with pytest.raises(AppError) as exc:
            list(req_service.stream_generate_plan(
                db, project_id,
                GeneratePlanRequest(source_id="src_missing"), provider
            ))
        assert exc.value.code == "REQUIREMENT_SOURCE_NOT_FOUND"

    def test_source不属于项目抛AppError(self, db, project_id, testing_session_local, monkeypatch):
        """source 属于另一个项目时应抛 AppError。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )
        # 创建另一个项目和 source
        other_project = project_service.create_project(
            testing_session_local(), ProjectCreateRequest(name="其他", topic="其他")
        )
        other_db = testing_session_local()
        try:
            other_src = req_service.add_text_source(
                other_db, other_project.id,
                TextSourceRequest(title="其他需求", text="其他分析")
            )
            other_source_id = other_src.id
        finally:
            other_db.close()

        provider = _MockStreamProvider(chunks=["{}"])

        with pytest.raises(AppError) as exc:
            list(req_service.stream_generate_plan(
                db, project_id,
                GeneratePlanRequest(source_id=other_source_id), provider
            ))
        assert exc.value.code == "REQUIREMENT_SOURCE_NOT_FOUND"


class TestStreamGeneratePlanJSONValidationFailure:
    """流式完成后 JSON 校验失败场景。"""

    def test_JSON校验失败yield_StreamErrorEvent(self, db, project_id, source_id, testing_session_local, monkeypatch):
        """流式 chunk 拼接后 JSON 无效，应 yield StreamErrorEvent，不保存 plan。"""
        monkeypatch.setattr(
            "app.infrastructure.database.engine.SessionLocal", testing_session_local
        )

        provider = _MockStreamProvider(chunks=["{invalid json"])

        events = list(req_service.stream_generate_plan(
            db, project_id, GeneratePlanRequest(source_id=source_id), provider
        ))

        error_events = [e for e in events if isinstance(e, req_service.StreamErrorEvent)]
        done_events = [e for e in events if isinstance(e, req_service.StreamDoneEvent)]

        assert len(error_events) == 1
        assert len(done_events) == 0
        assert error_events[0].error_code == "DEEPSEEK_JSON_PARSE_ERROR"
        assert error_events[0].partial_text == "{invalid json"
