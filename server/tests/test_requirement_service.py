"""需求核心服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.modules.projects.models import Project
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.requirements import service as req_service
from app.modules.requirements.models import ChangeRecord
from app.modules.requirements.contracts import (
    TextSourceRequest,
    GeneratePlanRequest,
    UpdatePlanRequest,
    RequirementTask,
    RequirementPlanPayload,
    ReplicationLevel,
)
from app.modules.requirements.status import PlanStatus, CandidateSource
from app.modules.projects.status import ProjectStatus
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
from app.core.errors import AppError


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def provider():
    return LocalRuleRequirementDraftProvider()


@pytest.fixture
def db():
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def project_id(db):
    p = project_service.create_project(db, ProjectCreateRequest(name="测试项目", topic="测试"))
    return p.id


class TestTextSource:
    """粘贴文本要求测试。"""

    def test_adds_text_source(self, db, project_id):
        req = TextSourceRequest(title="老师要求", text="请完成数据清洗和统计分析")
        src = req_service.add_text_source(db, project_id, req)
        assert src.source_type == "PASTED_TEXT"
        assert "数据清洗" in src.original_text

    def test_rejects_missing_project(self, db):
        req = TextSourceRequest(title="老师要求", text="请完成数据清洗")
        with pytest.raises(AppError) as exc:
            req_service.add_text_source(db, "proj_missing", req)
        assert exc.value.code == "PROJECT_NOT_FOUND"

    def test_rejects_empty_text_at_contract_layer(self):
        from pydantic import ValidationError as PydanticValidationError
        with pytest.raises(PydanticValidationError):
            TextSourceRequest(title="空", text="")

    def test_lists_sources(self, db, project_id, provider):
        req_service.add_text_source(db, project_id, TextSourceRequest(title="A", text="test A"))
        req_service.add_text_source(db, project_id, TextSourceRequest(title="B", text="test B"))
        items = req_service.list_sources(db, project_id)
        assert len(items) == 2


class TestGeneratePlan:
    """任务单生成测试。"""

    def test_generates_candidate_plan(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="完成数据清洗、统计分析和可视化"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        assert plan.status == PlanStatus.CANDIDATE.value
        assert plan.candidate_source == CandidateSource.LOCAL_RULE.value

        project = project_service.get_project(db, project_id)
        assert project.status == ProjectStatus.REQUIREMENT_PARSED.value

        import json
        payload = RequirementPlanPayload.model_validate(json.loads(plan.payload_json))
        assert len(payload.required_tasks) > 0
        assert len(payload.unknown_items) > 0
        assert payload.replication_level is not None

    def test_generating_new_candidate_stales_old(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="数据分析和报告"))
        plan1 = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        plan2 = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)

        # 重新取 plan1
        from app.modules.requirements.models import RequirementPlan
        stale = db.query(RequirementPlan).filter(RequirementPlan.id == plan1.id).first()
        assert stale.status == PlanStatus.STALE.value
        assert plan2.status == PlanStatus.CANDIDATE.value

    def test_plan_requires_analysis_keywords(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求",
                                                            text="完成数据清洗、统计分析和可视化，生成 Word 报告和 PPT 汇报"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        import json
        payload = RequirementPlanPayload.model_validate(json.loads(plan.payload_json))
        tasks = [t.title for t in payload.required_tasks]
        assert any("报告" in t for t in tasks)
        assert any("PPT" in t for t in tasks)

    def test_l3_goes_to_out_of_scope(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="完整复刻论文全部实验并验证"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        import json
        payload = RequirementPlanPayload.model_validate(json.loads(plan.payload_json))
        assert payload.replication_level is not None
        assert payload.replication_level.level == "L3"
        assert payload.replication_level.supported_in_v1 is False
        assert any("复现" in t.title for t in payload.out_of_scope_tasks)

    def test_writes_change_records_for_source_and_generation(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="数据分析"))
        req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        records = db.query(ChangeRecord).filter(ChangeRecord.project_id == project_id).all()
        change_types = [r.change_type for r in records]
        assert "REQUIREMENT_SOURCE_CREATED" in change_types
        assert "REQUIREMENT_PLAN_GENERATED" in change_types


class TestUpdateAndConfirm:
    """任务单编辑和确认测试。"""

    def test_updates_candidate_plan(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="数据分析"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        import json
        payload = RequirementPlanPayload.model_validate(json.loads(plan.payload_json))

        # 修改课题
        payload.topic = "修改后的课题"
        updated = req_service.update_plan(db, project_id, plan.id,
                                          UpdatePlanRequest(payload=payload))
        payload2 = RequirementPlanPayload.model_validate(json.loads(updated.payload_json))
        assert payload2.topic == "修改后的课题"

    def test_confirms_plan_and_advances_project(self, db, project_id, provider):
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="数据分析"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        confirmed = req_service.confirm_plan(db, project_id, plan.id)
        assert confirmed.status == PlanStatus.CONFIRMED.value
        assert confirmed.confirmed_at is not None

        # 项目状态应推进
        project = project_service.get_project(db, project_id)
        assert project.status == "REQUIREMENT_CONFIRMED"

    def test_cannot_confirm_twice(self, db, project_id, provider):
        from app.core.errors import AppError
        src = req_service.add_text_source(db, project_id,
                                          TextSourceRequest(title="需求", text="数据分析"))
        plan = req_service.generate_plan(db, project_id, GeneratePlanRequest(source_id=src.id), provider)
        req_service.confirm_plan(db, project_id, plan.id)
        with pytest.raises(AppError) as exc:
            req_service.confirm_plan(db, project_id, plan.id)
        assert exc.value.code == "REQUIREMENT_PLAN_NOT_EDITABLE"
