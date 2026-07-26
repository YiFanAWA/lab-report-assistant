"""分析方案核心服务流式生成测试 (stream_generate_analysis_plan)。

SPEC 0021：分析方案生成流式化。

测试：
- 流式成功：yield StreamAnalysisChunkEvent 多个 + StreamAnalysisDoneEvent，AnalysisPlan 保存
- 中途失败：yield StreamAnalysisErrorEvent，不保存 AnalysisPlan
- 兼容不支持流式的 provider（LocalRule/Fake）：调用 generate() 一次性 yield
- 项目状态不满足：抛 AppError
- 数据集未解析：抛 AppError
- 数据集版本未解析：抛 AppError
- 项目不存在：抛 AppError
- 数据集不存在：抛 AppError
- JSON 校验失败：yield StreamAnalysisErrorEvent，不保存 AnalysisPlan

mock provider.stream_generate 生成器方法。
"""

import json
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.infrastructure.parsers.dataset_parser import DatasetProfile, FieldProfile
from app.modules.analysis import service as analysis_service
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


def _make_profile() -> DatasetProfile:
    """构造有效的 DatasetProfile。"""
    return DatasetProfile(
        row_count=100,
        column_count=3,
        complete_row_count=85,
        incomplete_row_count=15,
        duplicate_row_count=2,
        field_profiles=[
            FieldProfile(
                name="age",
                inferred_type="int",
                non_null_count=95,
                null_count=5,
                null_rate=0.05,
                unique_count=63,
                sample_values=["25", "30", "45"],
                min_value=18.0,
                max_value=80.0,
                mean_value=45.0,
            ),
            FieldProfile(
                name="gender",
                inferred_type="string",
                non_null_count=98,
                null_count=2,
                null_rate=0.02,
                unique_count=2,
                sample_values=["男", "女"],
            ),
            FieldProfile(
                name="diagnosis",
                inferred_type="string",
                non_null_count=100,
                null_count=0,
                null_rate=0.0,
                unique_count=5,
                sample_values=["胃炎", "胃溃疡"],
            ),
        ],
        quality_score=85.0,
    )


def _make_profile_json() -> str:
    """将 DatasetProfile 序列化为 JSON 字符串（存入 DatasetVersion.profile_json）。"""
    return json.dumps(asdict(_make_profile()), ensure_ascii=False)


def _make_valid_analysis_plan_json() -> str:
    """构造有效的分析方案 JSON（符合 DeepSeekAnalysisPlanResponse 校验）。"""
    return json.dumps({
        "cleaning_plan": [
            {
                "field": "age",
                "issue_type": "MISSING_VALUE",
                "action": "用中位数填充缺失值",
                "reason": "数值字段，中位数对异常值稳健",
            },
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE_STATISTICS",
                "target_fields": "age",
                "method": "计算均值、中位数、标准差",
                "expected_output": "描述性统计表",
                "dependencies": ["age"],
            },
        ],
        "chart_plan": [
            {
                "chart_type": "HISTOGRAM",
                "title": "age 分布直方图",
                "data_fields": ["age"],
                "description": "展示年龄分布",
            },
        ],
    }, ensure_ascii=False)


# --- fixtures ---


@pytest.fixture
def engine_factory(monkeypatch, tmp_path):
    """创建内存 SQLite engine + SessionLocal factory，供 Phase 3 复用。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # patch engine.SessionLocal，让 service Phase 3 用同一 engine
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


def _create_project(
    db, status: str = ProjectStatus.DATASET_READY.value
) -> str:
    """创建项目并设置状态。默认 DATASET_READY（满足分析方案生成前置条件）。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="流式分析方案测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_dataset_and_version(
    db,
    project_id: str,
    dataset_id: str = "ds_stream_001",
    version_id: str = "dv_stream_001",
    dataset_status: str = DatasetStatus.READY.value,
    version_status: str = DatasetVersionStatus.PARSED.value,
    profile_json: str | None = None,
) -> tuple[str, str]:
    """插入 READY 状态的 Dataset 和 PARSED 状态的 DatasetVersion，返回 (dataset_id, version_id)。"""
    if profile_json is None:
        profile_json = _make_profile_json()

    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        dataset_kind="FILE",
        title="测试数据集",
        status=dataset_status,
    )
    db.add(dataset)

    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        project_id=project_id,
        version=1,
        status=version_status,
        file_path="/tmp/test.csv",
        file_size_bytes=1024,
        row_count=100,
        column_count=3,
        profile_json=profile_json,
    )
    db.add(version)
    db.commit()
    return dataset.id, version.id


# --- Mock Provider ---


class _MockStreamProvider:
    """支持流式的分析方案 provider 测试替身。"""

    def __init__(self, chunks: list[str], source_label: str = "DEEPSEEK"):
        self._chunks = chunks
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def stream_generate(self, profile):
        for c in self._chunks:
            yield c


class _MockSyncProvider:
    """不支持流式的分析方案 provider 测试替身（LocalRule/Fake 风格）。"""

    def __init__(self, plan_json: str, source_label: str = "LOCAL_RULE"):
        self._plan_json = plan_json
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def generate(self, profile):
        """同步返回 AnalysisPlanDraft。"""
        from app.modules.llm.analysis_plan_provider import AnalysisPlanDraft
        data = json.loads(self._plan_json)
        return AnalysisPlanDraft(
            cleaning_plan=data["cleaning_plan"],
            analysis_plan=data["analysis_plan"],
            chart_plan=data["chart_plan"],
        )


class _MockFailingStreamProvider:
    """中途失败的流式 provider。"""

    def __init__(self, chunks_before_failure: list[str], exc: Exception):
        self._chunks = chunks_before_failure
        self._exc = exc

    def source_label(self) -> str:
        return "DEEPSEEK"

    def stream_generate(self, profile):
        for c in self._chunks:
            yield c
        raise self._exc


# --- 共享 fixture ---


@pytest.fixture
def project_with_dataset(db):
    """创建项目（DATASET_READY）+ READY 数据集 + PARSED 版本，返回 (project_id, dataset_id, version_id)。"""
    project_id = _create_project(db)
    dataset_id, version_id = _seed_dataset_and_version(db, project_id)
    return project_id, dataset_id, version_id


# --- 流式成功场景 ---


class TestStreamGenerateAnalysisPlanSuccess:
    """流式成功场景。"""

    def test_流式成功yield_chunks_和_done(self, db, testing_session_local, project_with_dataset):
        """完整流程：yield StreamAnalysisChunkEvent 多个 + StreamAnalysisDoneEvent。"""
        project_id, dataset_id, _ = project_with_dataset
        full_json = _make_valid_analysis_plan_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, analysis_service.StreamAnalysisChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]

        assert len(chunk_events) == len(chunks)
        assert len(done_events) == 1

        # chunk 内容拼接应等于 full_json
        assert "".join(e.text for e in chunk_events) == full_json

        # done 事件应包含 plan_id 和 candidate_source
        done = done_events[0]
        assert done.candidate_source == "DEEPSEEK"
        assert done.plan_id  # 非空
        assert done.fallback_used is False

    def test_流式成功后保存AnalysisPlan(self, db, testing_session_local, project_with_dataset):
        """流式完成后应保存 AnalysisPlan 到数据库（CANDIDATE 状态）。"""
        project_id, dataset_id, _ = project_with_dataset
        full_json = _make_valid_analysis_plan_json()
        provider = _MockStreamProvider(chunks=[full_json])

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]
        assert len(done_events) == 1
        plan_id = done_events[0].plan_id

        # 用新 session 查询数据库，验证 AnalysisPlan 已保存
        verify_db = testing_session_local()
        try:
            plan = verify_db.query(AnalysisPlan).filter(
                AnalysisPlan.id == plan_id,
            ).first()
            assert plan is not None
            assert plan.status == AnalysisPlanStatus.CANDIDATE.value
            assert plan.candidate_source == "DEEPSEEK"
            assert plan.project_id == project_id
            assert plan.dataset_id == dataset_id
            # cleaning_plan/analysis_plan/chart_plan 应为有效 JSON 字符串
            cleaning = json.loads(plan.cleaning_plan)
            assert len(cleaning) == 1
            assert cleaning[0]["field"] == "age"
        finally:
            verify_db.close()

    def test_流式成功后推进项目状态(self, db, testing_session_local, project_with_dataset):
        """流式完成后应推进 project.status 到 ANALYSIS_PLANNED。"""
        project_id, dataset_id, _ = project_with_dataset
        full_json = _make_valid_analysis_plan_json()
        provider = _MockStreamProvider(chunks=[full_json])

        list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        # 用新 session 查询项目状态
        verify_db = testing_session_local()
        try:
            from app.modules.projects.models import Project
            project = verify_db.query(Project).filter(Project.id == project_id).first()
            assert project.status == ProjectStatus.ANALYSIS_PLANNED.value
        finally:
            verify_db.close()

    def test_流式成功后写变更记录(self, db, testing_session_local, project_with_dataset):
        """流式完成后应写变更记录（ANALYSIS_PLAN_GENERATED）。"""
        project_id, dataset_id, _ = project_with_dataset
        full_json = _make_valid_analysis_plan_json()
        provider = _MockStreamProvider(chunks=[full_json])

        list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        # 用新 session 查询变更记录
        verify_db = testing_session_local()
        try:
            from app.modules.requirements.models import ChangeRecord
            changes = verify_db.query(ChangeRecord).filter(
                ChangeRecord.project_id == project_id,
                ChangeRecord.change_type == "ANALYSIS_PLAN_GENERATED",
            ).all()
            assert len(changes) >= 1
        finally:
            verify_db.close()


# --- 中途失败场景 ---


class TestStreamGenerateAnalysisPlanMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败yield_StreamErrorEvent(self, db, testing_session_local, project_with_dataset):
        """provider 中途失败应 yield StreamAnalysisErrorEvent，不保存 AnalysisPlan。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分内容"],
            exc=Exception("LLM 中断"),
        )

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, analysis_service.StreamAnalysisChunkEvent)]
        error_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]

        assert len(chunk_events) == 1
        assert len(error_events) == 1
        assert len(done_events) == 0

        err = error_events[0]
        assert err.partial_text == "部分内容"
        assert err.error_code  # 非空

    def test_中途失败不保存AnalysisPlan(self, db, testing_session_local, project_with_dataset):
        """中途失败时不应保存 AnalysisPlan。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分"],
            exc=Exception("中断"),
        )

        list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(AnalysisPlan).filter(
                AnalysisPlan.project_id == project_id,
                AnalysisPlan.dataset_id == dataset_id,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- JSON 校验失败场景 ---


class TestStreamGenerateAnalysisPlanJsonParseFailure:
    """JSON 校验失败场景。"""

    def test_JSON校验失败yield_ErrorEvent(self, db, testing_session_local, project_with_dataset):
        """流式完成后 JSON 校验失败应 yield StreamAnalysisErrorEvent。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockStreamProvider(chunks=["{invalid json}"])

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        error_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]

        assert len(error_events) == 1
        assert len(done_events) == 0
        assert error_events[0].error_code == "ANALYSIS_PLAN_JSON_PARSE_ERROR"

    def test_JSON校验失败不保存AnalysisPlan(self, db, testing_session_local, project_with_dataset):
        """JSON 校验失败时不应保存 AnalysisPlan。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockStreamProvider(chunks=["{invalid}"])

        list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(AnalysisPlan).filter(
                AnalysisPlan.project_id == project_id,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- 兼容同步 provider 场景 ---


class TestStreamGenerateAnalysisPlanSyncProvider:
    """兼容不支持 stream_generate 的 provider。"""

    def test_同步provider一次性yield(self, db, testing_session_local, project_with_dataset):
        """LocalRule/Fake provider 不支持 stream_generate，应调用 generate() 一次性 yield。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockSyncProvider(_make_valid_analysis_plan_json())

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, analysis_service.StreamAnalysisChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]

        # 应有多个 chunk（按 50 字符拆分）+ 1 个 done
        assert len(chunk_events) >= 1
        assert len(done_events) == 1
        assert done_events[0].candidate_source == "LOCAL_RULE"

    def test_同步provider保存AnalysisPlan(self, db, testing_session_local, project_with_dataset):
        """同步 provider 流式后应保存 AnalysisPlan。"""
        project_id, dataset_id, _ = project_with_dataset
        provider = _MockSyncProvider(_make_valid_analysis_plan_json())

        events = list(analysis_service.stream_generate_analysis_plan(
            db, project_id, dataset_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, analysis_service.StreamAnalysisDoneEvent)]
        assert len(done_events) == 1

        verify_db = testing_session_local()
        try:
            plan = verify_db.query(AnalysisPlan).filter(
                AnalysisPlan.project_id == project_id,
                AnalysisPlan.candidate_source == "LOCAL_RULE",
            ).first()
            assert plan is not None
            assert plan.status == AnalysisPlanStatus.CANDIDATE.value
        finally:
            verify_db.close()


# --- 校验失败场景 ---


class TestStreamGenerateAnalysisPlanValidation:
    """前置校验失败场景。"""

    def test_项目不存在抛AppError(self, db):
        """项目不存在应抛 AppError。"""
        provider = _MockStreamProvider(chunks=[_make_valid_analysis_plan_json()])

        with pytest.raises(AppError) as exc_info:
            list(analysis_service.stream_generate_analysis_plan(
                db, "nonexistent_project", "ds_001", provider
            ))
        assert exc_info.value.code == "PROJECT_NOT_FOUND"

    def test_项目状态不满足抛AppError(self, db, testing_session_local):
        """项目状态未达 DATASET_READY 应抛 AppError。"""
        project_id = _create_project(
            db, status=ProjectStatus.DRAFT.value
        )
        dataset_id, _ = _seed_dataset_and_version(db, project_id)

        provider = _MockStreamProvider(chunks=[_make_valid_analysis_plan_json()])

        with pytest.raises(AppError) as exc_info:
            list(analysis_service.stream_generate_analysis_plan(
                db, project_id, dataset_id, provider
            ))
        assert exc_info.value.code == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_数据集不存在抛AppError(self, db, testing_session_local):
        """数据集不存在应抛 AppError。"""
        project_id = _create_project(db)

        provider = _MockStreamProvider(chunks=[_make_valid_analysis_plan_json()])

        with pytest.raises(AppError) as exc_info:
            list(analysis_service.stream_generate_analysis_plan(
                db, project_id, "nonexistent_dataset", provider
            ))
        assert exc_info.value.code == "DATASET_NOT_FOUND"

    def test_数据集未解析抛AppError(self, db, testing_session_local):
        """数据集状态不是 READY 应抛 AppError（DATASET_NOT_PARSED）。"""
        project_id = _create_project(db)
        dataset_id, _ = _seed_dataset_and_version(
            db, project_id,
            dataset_status=DatasetStatus.PENDING.value,
        )

        provider = _MockStreamProvider(chunks=[_make_valid_analysis_plan_json()])

        with pytest.raises(AppError) as exc_info:
            list(analysis_service.stream_generate_analysis_plan(
                db, project_id, dataset_id, provider
            ))
        assert exc_info.value.code == "DATASET_NOT_PARSED"

    def test_数据集版本未解析抛AppError(self, db, testing_session_local):
        """数据集版本状态不是 PARSED 应抛 AppError（DATASET_NOT_PARSED）。"""
        project_id = _create_project(db)
        dataset_id, _ = _seed_dataset_and_version(
            db, project_id,
            version_status=DatasetVersionStatus.PENDING.value,
        )

        provider = _MockStreamProvider(chunks=[_make_valid_analysis_plan_json()])

        with pytest.raises(AppError) as exc_info:
            list(analysis_service.stream_generate_analysis_plan(
                db, project_id, dataset_id, provider
            ))
        assert exc_info.value.code == "DATASET_NOT_PARSED"
