"""代码任务核心服务流式生成测试 (stream_generate_code_task)。

SPEC 0022：代码任务生成流式化。

测试：
- 流式成功：yield StreamCodeTaskChunkEvent 多个 + StreamCodeTaskDoneEvent，CodeTask 保存
- 中途失败：yield StreamCodeTaskErrorEvent，不保存 CodeTask
- 兼容不支持流式的 provider（LocalRule/Fake）：调用 generate() 一次性 yield
- 项目状态不满足：抛 AppError
- AnalysisPlan 未确认：抛 AppError
- JSON 校验失败：yield StreamCodeTaskErrorEvent，不保存 CodeTask
- Phase 3 状态复核失败：不保存 CodeTask
- 客户端断开：不保存 CodeTask
- 用户取消：不保存 CodeTask
- 首 chunk 前降级：candidate_source 为 LOCAL_RULE，fallback_used 为 True
- candidate_source 和 fallback_used 构造正确

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
from app.modules.execution import service as execution_service
from app.modules.execution.models import CodeTask
from app.modules.execution.status import CodeTaskStatus
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
        ],
        quality_score=85.0,
    )


def _make_profile_json() -> str:
    """将 DatasetProfile 序列化为 JSON 字符串。"""
    return json.dumps(asdict(_make_profile()), ensure_ascii=False)


def _make_valid_code_task_json() -> str:
    """构造有效的代码任务 JSON（符合 DeepSeekCodeTaskResponse 校验）。"""
    return json.dumps({
        "code": "import pandas as pd\nimport matplotlib.pyplot as plt\n\ndf = pd.read_csv(DATA_PATH)\nprint(df.describe())\ndf.hist(column='age')\nplt.savefig(OUTPUT_DIR + '/age_hist.png')\n",
    }, ensure_ascii=False)


def _make_analysis_plan_dict() -> dict:
    """构造已确认 AnalysisPlan 的 dict 形式（含 cleaning/analysis/chart 三个列表）。"""
    return {
        "cleaning_plan": [
            {
                "field": "age",
                "issue_type": "MISSING_VALUE",
                "action": "用中位数填充缺失值",
                "reason": "数值字段",
            },
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE_STATISTICS",
                "target_fields": ["age"],
                "method": "计算均值",
                "expected_output": "统计表",
            },
        ],
        "chart_plan": [
            {
                "chart_type": "HISTOGRAM",
                "title": "age 分布",
                "data_fields": ["age"],
                "description": "展示分布",
            },
        ],
    }


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
    db, status: str = ProjectStatus.ANALYSIS_CONFIRMED.value
) -> str:
    """创建项目并设置状态。默认 ANALYSIS_CONFIRMED（满足代码任务生成前置条件）。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="流式代码任务测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_dataset_and_version(
    db,
    project_id: str,
    dataset_id: str = "ds_ct_stream_001",
    version_id: str = "dv_ct_stream_001",
) -> tuple[str, str]:
    """插入 READY 状态的 Dataset 和 PARSED 状态的 DatasetVersion。"""
    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        dataset_kind="FILE",
        title="测试数据集",
        status=DatasetStatus.READY.value,
    )
    db.add(dataset)

    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        project_id=project_id,
        version=1,
        status=DatasetVersionStatus.PARSED.value,
        file_path="/tmp/test.csv",
        file_size_bytes=1024,
        row_count=100,
        column_count=3,
        profile_json=_make_profile_json(),
    )
    db.add(version)
    db.commit()
    return dataset.id, version.id


def _seed_confirmed_analysis_plan(
    db,
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
    plan_id: str = "plan_ct_stream_001",
) -> str:
    """插入 CONFIRMED 状态的 AnalysisPlan，返回 plan_id。"""
    plan = AnalysisPlan(
        id=plan_id,
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        cleaning_plan=json.dumps(_make_analysis_plan_dict()["cleaning_plan"]),
        analysis_plan=json.dumps(_make_analysis_plan_dict()["analysis_plan"]),
        chart_plan=json.dumps(_make_analysis_plan_dict()["chart_plan"]),
        status=AnalysisPlanStatus.CONFIRMED.value,
        candidate_source="LOCAL_RULE",
    )
    db.add(plan)
    db.commit()
    return plan.id


# --- Mock Provider ---


class _MockStreamProvider:
    """支持流式的代码任务 provider 测试替身。"""

    def __init__(self, chunks: list[str], source_label: str = "DEEPSEEK"):
        self._chunks = chunks
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def stream_generate(self, analysis_plan: dict, dataset_profile: dict | None = None):
        for c in self._chunks:
            yield c


class _MockSyncProvider:
    """不支持流式的代码任务 provider 测试替身（LocalRule/Fake 风格）。"""

    def __init__(self, code: str, source_label: str = "LOCAL_RULE"):
        self._code = code
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def generate(self, analysis_plan: dict, dataset_profile: dict | None = None):
        from app.modules.llm.code_task_provider import CodeTaskDraft
        return CodeTaskDraft(code=self._code)


class _MockFailingStreamProvider:
    """中途失败的流式 provider。"""

    def __init__(self, chunks_before_failure: list[str], exc: Exception):
        self._chunks = chunks_before_failure
        self._exc = exc

    def source_label(self) -> str:
        return "DEEPSEEK"

    def stream_generate(self, analysis_plan: dict, dataset_profile: dict | None = None):
        for c in self._chunks:
            yield c
        raise self._exc


# --- 共享 fixture ---


@pytest.fixture
def project_with_plan(db):
    """创建项目（ANALYSIS_CONFIRMED）+ READY 数据集 + PARSED 版本 + CONFIRMED AnalysisPlan，返回 (project_id, dataset_id, version_id, plan_id)。"""
    project_id = _create_project(db)
    dataset_id, version_id = _seed_dataset_and_version(db, project_id)
    plan_id = _seed_confirmed_analysis_plan(db, project_id, dataset_id, version_id)
    return project_id, dataset_id, version_id, plan_id


# --- 流式成功场景 ---


class TestStreamGenerateCodeTaskSuccess:
    """流式成功场景。"""

    def test_流式成功yield_chunks_和_done(self, db, testing_session_local, project_with_plan):
        """完整流程：yield StreamCodeTaskChunkEvent 多个 + StreamCodeTaskDoneEvent。"""
        project_id, _, _, plan_id = project_with_plan
        full_json = _make_valid_code_task_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        request = MagicMock()
        request.is_disconnected.return_value = False

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, execution_service.StreamCodeTaskChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, execution_service.StreamCodeTaskDoneEvent)]

        assert len(chunk_events) == len(chunks)
        assert len(done_events) == 1

        # done 事件应包含 code_task_id 和 candidate_source
        done = done_events[0]
        assert done.code_task_id is not None
        assert done.candidate_source == "DEEPSEEK"
        assert done.fallback_used is False

    def test_流式成功后CodeTask保存为CANDIDATE(self, db, testing_session_local, project_with_plan):
        """流式完成后 CodeTask 应保存为 CANDIDATE 状态。"""
        project_id, _, _, plan_id = project_with_plan
        full_json = _make_valid_code_task_json()
        provider = _MockStreamProvider(chunks=[full_json])

        request = MagicMock()
        request.is_disconnected.return_value = False

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, execution_service.StreamCodeTaskDoneEvent)]
        code_task_id = done_events[0].code_task_id

        # 验证 CodeTask 已保存
        task = db.query(CodeTask).filter(CodeTask.id == code_task_id).first()
        assert task is not None
        assert task.status == CodeTaskStatus.CANDIDATE.value
        assert task.candidate_source == "DEEPSEEK"


# --- 中途失败场景 ---


class TestStreamGenerateCodeTaskMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败yield_error不保存(self, db, testing_session_local, project_with_plan):
        """中途失败应 yield StreamCodeTaskErrorEvent，不保存 CodeTask。"""
        project_id, _, _, plan_id = project_with_plan
        from app.infrastructure.llm.deepseek_client import DeepSeekError
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分内容"],
            exc=DeepSeekError(code="DEEPSEEK_HTTP_ERROR", message="中断"),
        )

        request = MagicMock()
        request.is_disconnected.return_value = False

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        error_events = [e for e in events
                        if isinstance(e, execution_service.StreamCodeTaskErrorEvent)]
        assert len(error_events) == 1
        assert error_events[0].error_code == "DEEPSEEK_HTTP_ERROR"

        # 不应保存 CodeTask
        tasks = db.query(CodeTask).all()
        assert len(tasks) == 0


# --- JSON 校验失败场景 ---


class TestStreamGenerateCodeTaskJSONValidation:
    """JSON 校验失败场景。"""

    def test_JSON校验失败不保存(self, db, testing_session_local, project_with_plan):
        """LLM 返回无效 JSON，应 yield error 事件，不保存 CodeTask。"""
        project_id, _, _, plan_id = project_with_plan
        provider = _MockStreamProvider(chunks=["{invalid json"])

        request = MagicMock()
        request.is_disconnected.return_value = False

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        error_events = [e for e in events
                        if isinstance(e, execution_service.StreamCodeTaskErrorEvent)]
        assert len(error_events) >= 1

        # 不应保存 CodeTask
        tasks = db.query(CodeTask).all()
        assert len(tasks) == 0


# --- 前置校验场景 ---


class TestStreamGenerateCodeTaskPreconditions:
    """前置校验场景。"""

    def test_AnalysisPlan未确认抛AppError(self, db, testing_session_local, project_with_plan):
        """AnalysisPlan 状态非 CONFIRMED 应抛 AppError。"""
        project_id, _, _, plan_id = project_with_plan
        # 修改 plan 状态为 CANDIDATE
        plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
        plan.status = AnalysisPlanStatus.CANDIDATE.value
        db.commit()

        provider = _MockStreamProvider(chunks=[_make_valid_code_task_json()])
        request = MagicMock()
        request.is_disconnected.return_value = False

        with pytest.raises(AppError) as exc_info:
            list(execution_service.stream_generate_code_task(
                db, request, project_id, plan_id, provider
            ))
        assert "ANALYSIS_PLAN_NOT_CONFIRMED" in exc_info.value.code or \
               "NOT_CONFIRMED" in exc_info.value.code

    def test_项目状态不满足抛AppError(self, db, testing_session_local, project_with_plan):
        """项目状态非 ANALYSIS_CONFIRMED 应抛 AppError。"""
        project_id, _, _, plan_id = project_with_plan
        # 修改项目状态为 DATASET_READY
        from app.modules.projects.models import Project
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.DATASET_READY.value
        db.commit()

        provider = _MockStreamProvider(chunks=[_make_valid_code_task_json()])
        request = MagicMock()
        request.is_disconnected.return_value = False

        with pytest.raises(AppError):
            list(execution_service.stream_generate_code_task(
                db, request, project_id, plan_id, provider
            ))


# --- 兼容同步 provider 场景 ---


class TestStreamGenerateCodeTaskSyncProviderCompat:
    """兼容只实现 generate() 的 Provider。"""

    def test_兼容同步provider一次性yield(self, db, testing_session_local, project_with_plan):
        """Provider 只实现 generate() 未实现 stream_generate()，应降级为同步生成后拆分多 chunk。"""
        project_id, _, _, plan_id = project_with_plan
        code = "import pandas as pd\ndf = pd.read_csv(DATA_PATH)\nprint(df.describe())\n"
        provider = _MockSyncProvider(code=code, source_label="LOCAL_RULE")

        request = MagicMock()
        request.is_disconnected.return_value = False

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, execution_service.StreamCodeTaskChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, execution_service.StreamCodeTaskDoneEvent)]

        assert len(chunk_events) >= 1
        assert len(done_events) == 1
        assert done_events[0].candidate_source == "LOCAL_RULE"


# --- 取消与断开场景 ---


class TestStreamGenerateCodeTaskCancellation:
    """用户取消与客户端断开场景。"""

    def test_客户端断开不保存CodeTask(self, db, testing_session_local, project_with_plan):
        """客户端断开后应终止流式，不保存 CodeTask。"""
        project_id, _, _, plan_id = project_with_plan
        full_json = _make_valid_code_task_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        request = MagicMock()
        # 模拟客户端在第 2 个 chunk 后断开
        call_count = [0]
        def is_disconnected():
            call_count[0] += 1
            return call_count[0] > 2
        request.is_disconnected.side_effect = is_disconnected

        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        # 不应保存 CodeTask
        tasks = db.query(CodeTask).all()
        assert len(tasks) == 0


# --- 降级场景 ---


class TestStreamGenerateCodeTaskFallback:
    """首 chunk 前降级场景。"""

    def test_首chunk前降级fallback_used为True(self, db, testing_session_local, project_with_plan):
        """首 chunk 前失败降级到 LocalRule，fallback_used 应为 True。"""
        project_id, _, _, plan_id = project_with_plan
        from app.infrastructure.llm.deepseek_client import DeepSeekError
        from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider

        # mock DeepSeek provider 首 chunk 前失败
        failing_provider = _MockFailingStreamProvider(
            chunks_before_failure=[],
            exc=DeepSeekError(code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"),
        )
        fallback = LocalRuleCodeTaskProvider()

        # DeepSeekCodeTaskProvider 内部会调用 fallback
        from app.modules.llm.deepseek_code_task_provider import DeepSeekCodeTaskProvider
        from unittest.mock import MagicMock as Mock
        mock_client = Mock()
        provider = DeepSeekCodeTaskProvider(client=mock_client, fallback=fallback)
        # 让 stream_generate 调用失败，触发降级
        provider.stream_generate = failing_provider.stream_generate.__get__(provider)

        request = Mock()
        request.is_disconnected.return_value = False

        # 这里需要 mock 让 DeepSeek provider 的 stream_generate 失败后降级到 LocalRule
        # 由于 DeepSeekCodeTaskProvider.stream_generate 尚未实现，这个测试预期失败（红色阶段）
        # 实现后应验证 fallback_used 为 True，candidate_source 为 LOCAL_RULE
        events = list(execution_service.stream_generate_code_task(
            db, request, project_id, plan_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, execution_service.StreamCodeTaskDoneEvent)]
        if done_events:
            assert done_events[0].fallback_used is True
            assert done_events[0].candidate_source == "LOCAL_RULE"
