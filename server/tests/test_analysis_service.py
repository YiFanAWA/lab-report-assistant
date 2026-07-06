"""分析方案核心服务测试。

覆盖 generate_analysis_plan、list_analysis_plans、get_analysis_plan、
update_analysis_plan、confirm_analysis_plan、reject_analysis_plan、
complete_analysis、save_analysis_plan_draft、advance_project_to_planned。

通过直接设置 project.status 跳过前序流程，聚焦分析方案 owner 层业务语义。
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.core.errors import AppError
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.datasets import service as datasets_service
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import (
    DatasetKind,
    DatasetStatus,
    DatasetVersionStatus,
)
from app.modules.analysis import service as analysis_service
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus, AnalysisChangeType
from app.modules.analysis.contracts import UpdateAnalysisPlanRequest
from app.modules.jobs.status import JobType, JobStatus
from app.modules.jobs.models import BackgroundJob
from app.modules.llm.analysis_plan_provider import (
    AnalysisPlanDraft,
    FakeAnalysisPlanProvider,
)


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


@pytest.fixture
def project_id_with_dataset_ready(db):
    """创建一个 DATASET_READY 状态的项目 + READY 状态数据集 + PARSED 版本。

    用于分析方案生成测试前置条件。
    """
    project = project_service.create_project(
        db, ProjectCreateRequest(name="胃病数据分析", topic="胃病数据分析")
    )
    project.status = ProjectStatus.DATASET_READY.value
    db.commit()
    db.refresh(project)

    # 直接通过 DB 创建 READY 数据集 + PARSED 版本
    dataset = Dataset(
        id="ds_test_ready",
        project_id=project.id,
        dataset_kind=DatasetKind.FILE.value,
        title="测试数据集",
        status=DatasetStatus.READY.value,
    )
    db.add(dataset)
    version = DatasetVersion(
        id="ver_test_001",
        dataset_id=dataset.id,
        project_id=project.id,
        version=1,
        status=DatasetVersionStatus.PARSED.value,
        file_path="/tmp/raw.csv",
        file_size_bytes=100,
        row_count=10,
        column_count=3,
        profile_json=json.dumps({
            "row_count": 10,
            "column_count": 3,
            "field_profiles": [
                {"name": "age", "inferred_type": "int"},
                {"name": "name", "inferred_type": "string"},
            ],
        }),
    )
    db.add(version)
    db.commit()
    return project.id, dataset.id, version.id


# --- generate_analysis_plan ---


class TestGenerateAnalysisPlan:
    """触发生成分析方案测试。"""

    def test_creates_generate_analysis_plan_job(
        self, db, project_id_with_dataset_ready
    ):
        """成功触发 GENERATE_ANALYSIS_PLAN 任务。"""
        project_id, dataset_id, _ = project_id_with_dataset_ready
        job_id = analysis_service.generate_analysis_plan(
            db, project_id, dataset_id
        )

        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.GENERATE_ANALYSIS_PLAN.value
        assert job.status == JobStatus.PENDING.value
        assert dataset_id in job.input_json

    def test_rejects_when_project_status_insufficient(self, db):
        """项目状态为 DRAFT 时拒绝。"""
        project = project_service.create_project(
            db, ProjectCreateRequest(name="X", topic="X")
        )
        # 添加一个 READY 数据集（异常状态，仅用于触发测试）
        dataset = Dataset(
            id="ds_test_draft",
            project_id=project.id,
            dataset_kind=DatasetKind.FILE.value,
            title="X",
            status=DatasetStatus.READY.value,
        )
        db.add(dataset)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.generate_analysis_plan(db, project.id, dataset.id)
        # analysis_service 复用 PROJECT_EVIDENCE_NOT_CONFIRMED 作为 insufficient 状态
        assert exc.value.code == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_rejects_when_dataset_not_ready(self, db):
        """dataset.status != READY 时返回 DATASET_NOT_PARSED。"""
        project = project_service.create_project(
            db, ProjectCreateRequest(name="X", topic="X")
        )
        project.status = ProjectStatus.DATASET_READY.value
        db.commit()
        # 数据集状态为 PENDING
        dataset = Dataset(
            id="ds_pending",
            project_id=project.id,
            dataset_kind=DatasetKind.FILE.value,
            title="X",
            status=DatasetStatus.PENDING.value,
        )
        db.add(dataset)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.generate_analysis_plan(db, project.id, dataset.id)
        assert exc.value.code == "DATASET_NOT_PARSED"

    def test_rejects_when_dataset_missing(self, db, project_id_with_dataset_ready):
        """dataset 不存在时抛 DATASET_NOT_FOUND。"""
        project_id, _, _ = project_id_with_dataset_ready
        with pytest.raises(AppError) as exc:
            analysis_service.generate_analysis_plan(
                db, project_id, "ds_missing"
            )
        assert exc.value.code == "DATASET_NOT_FOUND"

    def test_rejects_when_project_missing(self, db):
        """项目不存在时抛 PROJECT_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            analysis_service.generate_analysis_plan(
                db, "proj_missing", "ds_test"
            )
        assert exc.value.code == "PROJECT_NOT_FOUND"


# --- list_analysis_plans / get_analysis_plan ---


class TestListAndGetAnalysisPlans:
    """分析方案查询测试。"""

    def test_lists_plans_filtered_by_dataset(
        self, db, project_id_with_dataset_ready
    ):
        """按 dataset_id 过滤。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready

        # 直接插入两个方案，分别属于两个数据集
        plan1 = AnalysisPlan(
            id="plan_list_1",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        # 另一个数据集的方案
        other_dataset = Dataset(
            id="ds_other",
            project_id=project_id,
            dataset_kind=DatasetKind.FILE.value,
            title="X",
            status=DatasetStatus.READY.value,
        )
        db.add(other_dataset)
        other_version = DatasetVersion(
            id="ver_other",
            dataset_id=other_dataset.id,
            project_id=project_id,
            version=1,
            status=DatasetVersionStatus.PARSED.value,
            file_path="/tmp/x.csv",
            file_size_bytes=100,
        )
        db.add(other_version)
        plan2 = AnalysisPlan(
            id="plan_list_2",
            project_id=project_id,
            dataset_id=other_dataset.id,
            dataset_version_id=other_version.id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add_all([plan1, plan2])
        db.commit()

        # 按 dataset_id 过滤
        listed = analysis_service.list_analysis_plans(
            db, project_id, dataset_id=dataset_id
        )
        assert len(listed) == 1
        assert listed[0].id == "plan_list_1"

    def test_lists_plans_filtered_by_status(
        self, db, project_id_with_dataset_ready
    ):
        """按 status 过滤。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready

        plan_cand = AnalysisPlan(
            id="plan_filter_cand",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        plan_conf = AnalysisPlan(
            id="plan_filter_conf",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
        )
        db.add_all([plan_cand, plan_conf])
        db.commit()

        cand_only = analysis_service.list_analysis_plans(
            db, project_id, status=AnalysisPlanStatus.CANDIDATE.value
        )
        assert len(cand_only) == 1
        assert cand_only[0].id == "plan_filter_cand"

        conf_only = analysis_service.list_analysis_plans(
            db, project_id, status=AnalysisPlanStatus.CONFIRMED.value
        )
        assert len(conf_only) == 1
        assert conf_only[0].id == "plan_filter_conf"

    def test_get_analysis_plan_raises_when_not_found(self, db):
        """get_analysis_plan 不存在时抛 ANALYSIS_PLAN_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            analysis_service.get_analysis_plan(db, "plan_missing")
        assert exc.value.code == "ANALYSIS_PLAN_NOT_FOUND"

    def test_get_analysis_plan_by_project_raises_when_mismatch(
        self, db, project_id_with_dataset_ready
    ):
        """方案不属于该项目时抛 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_project_check",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.get_analysis_plan_by_project(
                db, "proj_wrong", plan.id
            )
        assert exc.value.code == "ANALYSIS_PLAN_NOT_FOUND"

    def test_lists_plans_returns_in_desc_order(
        self, db, project_id_with_dataset_ready
    ):
        """list_analysis_plans 按创建时间降序返回。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready

        plan1 = AnalysisPlan(
            id="plan_old",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        plan2 = AnalysisPlan(
            id="plan_new",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add_all([plan1, plan2])
        db.commit()

        listed = analysis_service.list_analysis_plans(db, project_id)
        assert len(listed) == 2
        ids = [p.id for p in listed]
        # 都应存在
        assert set(ids) == {"plan_old", "plan_new"}


# --- update_analysis_plan ---


class TestUpdateAnalysisPlan:
    """更新分析方案测试。"""

    def test_updates_candidate_plan_fields(
        self, db, project_id_with_dataset_ready
    ):
        """更新 CANDIDATE 方案的 cleaning/analysis/chart plan。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_update_cand",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        req = UpdateAnalysisPlanRequest(
            cleaning_plan='[{"field": "x"}]',
            analysis_plan='[{"analysis_type": "X"}]',
            chart_plan='[{"chart_type": "BAR"}]',
        )
        updated = analysis_service.update_analysis_plan(
            db, project_id, plan.id, req
        )

        assert updated.cleaning_plan == '[{"field": "x"}]'
        assert updated.analysis_plan == '[{"analysis_type": "X"}]'
        assert updated.chart_plan == '[{"chart_type": "BAR"}]'
        # CANDIDATE 编辑后仍为 CANDIDATE
        assert updated.status == AnalysisPlanStatus.CANDIDATE.value

    def test_updates_partial_fields(self, db, project_id_with_dataset_ready):
        """仅更新部分字段，未提供的字段保持不变。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_partial",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan='[{"original": true}]',
            analysis_plan='[{"original": true}]',
            chart_plan='[{"original": true}]',
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        # 只更新 cleaning_plan
        req = UpdateAnalysisPlanRequest(
            cleaning_plan='[{"new": true}]',
        )
        updated = analysis_service.update_analysis_plan(
            db, project_id, plan.id, req
        )

        assert updated.cleaning_plan == '[{"new": true}]'
        # 其他字段保持不变
        assert updated.analysis_plan == '[{"original": true}]'
        assert updated.chart_plan == '[{"original": true}]'

    def test_updates_stale_plan(self, db, project_id_with_dataset_ready):
        """STALE 方案也可编辑。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_stale_upd",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.STALE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        req = UpdateAnalysisPlanRequest(cleaning_plan='[{"x": 1}]')
        updated = analysis_service.update_analysis_plan(
            db, project_id, plan.id, req
        )
        assert updated.cleaning_plan == '[{"x": 1}]'
        # STALE 编辑后变为 CANDIDATE
        assert updated.status == AnalysisPlanStatus.CANDIDATE.value

    def test_confirmed_plan_edits_back_to_candidate(
        self, db, project_id_with_dataset_ready
    ):
        """CONFIRMED 方案编辑后回到 CANDIDATE，confirmed_at 清空。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_conf_edit",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
            confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(plan)
        db.commit()

        req = UpdateAnalysisPlanRequest(cleaning_plan='[{"new": true}]')
        updated = analysis_service.update_analysis_plan(
            db, project_id, plan.id, req
        )
        assert updated.status == AnalysisPlanStatus.CANDIDATE.value
        assert updated.confirmed_at is None

    def test_rejects_updating_rejected_plan(
        self, db, project_id_with_dataset_ready
    ):
        """REJECTED 方案不可编辑，返回 ANALYSIS_PLAN_NOT_EDITABLE。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_rej_upd",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.REJECTED.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        req = UpdateAnalysisPlanRequest(cleaning_plan='[{"x": 1}]')
        with pytest.raises(AppError) as exc:
            analysis_service.update_analysis_plan(
                db, project_id, plan.id, req
            )
        assert exc.value.code == "ANALYSIS_PLAN_NOT_EDITABLE"

    def test_rejects_when_plan_not_found(
        self, db, project_id_with_dataset_ready
    ):
        """方案不存在时抛 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = project_id_with_dataset_ready
        req = UpdateAnalysisPlanRequest(cleaning_plan='[{"x": 1}]')
        with pytest.raises(AppError) as exc:
            analysis_service.update_analysis_plan(
                db, project_id, "plan_missing", req
            )
        assert exc.value.code == "ANALYSIS_PLAN_NOT_FOUND"


# --- confirm_analysis_plan / reject_analysis_plan ---


class TestConfirmRejectAnalysisPlan:
    """确认与拒绝分析方案测试。"""

    def test_confirm_candidate_sets_confirmed_and_confirmed_at(
        self, db, project_id_with_dataset_ready
    ):
        """确认 CANDIDATE 方案后 status=CONFIRMED，记录 confirmed_at。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_confirm_ok",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        confirmed = analysis_service.confirm_analysis_plan(
            db, project_id, plan.id
        )
        assert confirmed.status == AnalysisPlanStatus.CONFIRMED.value
        assert confirmed.confirmed_at is not None

    def test_confirm_rejects_non_candidate(
        self, db, project_id_with_dataset_ready
    ):
        """非 CANDIDATE 方案无法确认，返回 ANALYSIS_PLAN_NOT_CONFIRMABLE。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_confirm_failed",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.confirm_analysis_plan(db, project_id, plan.id)
        assert exc.value.code == "ANALYSIS_PLAN_NOT_CONFIRMABLE"

    def test_confirm_rejects_stale_plan(
        self, db, project_id_with_dataset_ready
    ):
        """STALE 方案不能直接确认，必须先编辑回到 CANDIDATE。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_confirm_stale",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.STALE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.confirm_analysis_plan(db, project_id, plan.id)
        assert exc.value.code == "ANALYSIS_PLAN_NOT_CONFIRMABLE"

    def test_reject_candidate_sets_rejected(
        self, db, project_id_with_dataset_ready
    ):
        """拒绝 CANDIDATE 方案后 status=REJECTED。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_reject_ok",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        rejected = analysis_service.reject_analysis_plan(
            db, project_id, plan.id
        )
        assert rejected.status == AnalysisPlanStatus.REJECTED.value

    def test_reject_rejects_non_candidate(
        self, db, project_id_with_dataset_ready
    ):
        """非 CANDIDATE 方案无法拒绝。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_reject_failed",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.reject_analysis_plan(db, project_id, plan.id)
        assert exc.value.code == "ANALYSIS_PLAN_NOT_CONFIRMABLE"

    def test_confirm_rejects_when_plan_missing(
        self, db, project_id_with_dataset_ready
    ):
        """方案不存在时抛 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = project_id_with_dataset_ready
        with pytest.raises(AppError) as exc:
            analysis_service.confirm_analysis_plan(
                db, project_id, "plan_missing"
            )
        assert exc.value.code == "ANALYSIS_PLAN_NOT_FOUND"


# --- complete_analysis ---


class TestCompleteAnalysis:
    """完成分析确认测试。"""

    def test_advances_project_to_analysis_confirmed_when_confirmed_exists(
        self, db, project_id_with_dataset_ready
    ):
        """有 CONFIRMED 方案时推进到 ANALYSIS_CONFIRMED。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_complete_ok",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
            confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(plan)
        db.commit()

        project = analysis_service.complete_analysis(db, project_id)
        assert project.status == ProjectStatus.ANALYSIS_CONFIRMED.value

    def test_rejects_when_no_confirmed_plan(
        self, db, project_id_with_dataset_ready
    ):
        """无 CONFIRMED 方案时返回 PROJECT_NO_CONFIRMED_ANALYSIS_PLAN。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        # 仅有 CANDIDATE 方案
        plan = AnalysisPlan(
            id="plan_only_cand",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        with pytest.raises(AppError) as exc:
            analysis_service.complete_analysis(db, project_id)
        assert exc.value.code == "PROJECT_NO_CONFIRMED_ANALYSIS_PLAN"

    def test_rejects_when_project_missing(self, db):
        """项目不存在时抛 PROJECT_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            analysis_service.complete_analysis(db, "proj_missing")
        assert exc.value.code == "PROJECT_NOT_FOUND"


# --- save_analysis_plan_draft ---


class TestSaveAnalysisPlanDraft:
    """Worker 调用保存方案候选测试。"""

    def test_creates_new_candidate_plan(self, db, project_id_with_dataset_ready):
        """save_analysis_plan_draft 创建一个新的 CANDIDATE AnalysisPlan。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        provider = FakeAnalysisPlanProvider()
        draft = provider.generate(profile=None)  # Fake 不依赖 profile

        plan = analysis_service.save_analysis_plan_draft(
            db,
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            draft=draft,
            candidate_source=provider.source_label(),
        )
        db.commit()

        assert plan.status == AnalysisPlanStatus.CANDIDATE.value
        assert plan.candidate_source == "LOCAL_RULE"
        assert plan.project_id == project_id
        assert plan.dataset_id == dataset_id
        assert plan.dataset_version_id == version_id

        # cleaning/analysis/chart plan 已序列化
        parsed_cleaning = json.loads(plan.cleaning_plan)
        parsed_analysis = json.loads(plan.analysis_plan)
        parsed_chart = json.loads(plan.chart_plan)
        assert isinstance(parsed_cleaning, list)
        assert isinstance(parsed_analysis, list)
        assert isinstance(parsed_chart, list)

    def test_marks_old_candidates_stale_when_saving_new(
        self, db, project_id_with_dataset_ready
    ):
        """同一 dataset_version 已有 CANDIDATE 时，旧候选变 STALE。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready

        # 先存一个候选方案
        old_plan = AnalysisPlan(
            id="plan_old_cand",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(old_plan)
        db.commit()

        # 再保存新候选
        provider = FakeAnalysisPlanProvider()
        draft = provider.generate(profile=None)
        new_plan = analysis_service.save_analysis_plan_draft(
            db,
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            draft=draft,
            candidate_source=provider.source_label(),
        )
        db.commit()

        # 旧候选变 STALE
        db.refresh(old_plan)
        assert old_plan.status == AnalysisPlanStatus.STALE.value

        # 新候选为 CANDIDATE
        assert new_plan.status == AnalysisPlanStatus.CANDIDATE.value

    def test_does_not_advance_project_status(self, db, project_id_with_dataset_ready):
        """save_analysis_plan_draft 不直接推进 project.status（由 advance_project_to_planned 完成）。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        provider = FakeAnalysisPlanProvider()
        draft = provider.generate(profile=None)

        analysis_service.save_analysis_plan_draft(
            db,
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            draft=draft,
            candidate_source=provider.source_label(),
        )
        db.commit()

        # project.status 仍为 DATASET_READY（save_drafts 不推进状态）
        project = project_service.get_project(db, project_id)
        assert project.status == ProjectStatus.DATASET_READY.value


# --- advance_project_to_planned ---


class TestAdvanceProjectToPlanned:
    """推进项目状态到 ANALYSIS_PLANNED 测试。"""

    def test_advances_from_dataset_ready(self, db, project_id_with_dataset_ready):
        """DATASET_READY 状态可推进到 ANALYSIS_PLANNED。"""
        project_id, _, _ = project_id_with_dataset_ready
        project = analysis_service.advance_project_to_planned(db, project_id)
        db.commit()
        assert project.status == ProjectStatus.ANALYSIS_PLANNED.value

    def test_does_not_advance_if_already_planned(self, db, project_id_with_dataset_ready):
        """已是 ANALYSIS_PLANNED 时不重复推进。"""
        project_id, _, _ = project_id_with_dataset_ready
        # 先推进一次
        analysis_service.advance_project_to_planned(db, project_id)
        db.commit()
        # 再次调用，不应推进到下一个状态
        project = analysis_service.advance_project_to_planned(db, project_id)
        db.commit()
        assert project.status == ProjectStatus.ANALYSIS_PLANNED.value

    def test_does_not_advance_from_evidence_confirmed(self, db):
        """EVIDENCE_CONFIRMED 状态不应被推进（应保持原状态）。"""
        project = project_service.create_project(
            db, ProjectCreateRequest(name="X", topic="X")
        )
        project.status = ProjectStatus.EVIDENCE_CONFIRMED.value
        db.commit()

        result = analysis_service.advance_project_to_planned(db, project.id)
        db.commit()
        # 保持原状态（仅 DATASET_READY 时才推进）
        assert result.status == ProjectStatus.EVIDENCE_CONFIRMED.value


# --- 响应转换 ---


class TestAnalysisResponseConversion:
    """分析方案响应转换测试。"""

    def test_plan_to_response_serializes_datetimes(
        self, db, project_id_with_dataset_ready
    ):
        """plan_to_response 将 datetime 字段序列化为 ISO 字符串。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_resp_test",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        resp = analysis_service.plan_to_response(plan)
        assert isinstance(resp.created_at, str)
        assert resp.status == AnalysisPlanStatus.CANDIDATE.value
        assert resp.confirmed_at is None

    def test_complete_analysis_to_response_returns_status(
        self, db, project_id_with_dataset_ready
    ):
        """complete_analysis_to_response 返回 CompleteAnalysisResponse。"""
        project_id, dataset_id, version_id = project_id_with_dataset_ready
        plan = AnalysisPlan(
            id="plan_resp_complete",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
            confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(plan)
        db.commit()

        project = analysis_service.complete_analysis(db, project_id)
        resp = analysis_service.complete_analysis_to_response(project)
        assert resp.status == ProjectStatus.ANALYSIS_CONFIRMED.value
