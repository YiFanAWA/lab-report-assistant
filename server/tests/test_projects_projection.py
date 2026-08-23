"""SPEC 0047 项目工作台 projection 合同与 API 测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import pytest

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects import projection as projection_service
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.status import ProjectStatus


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_draft_projection_exposes_next_action(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="投影测试", topic="胃病数据分析")
    )

    result = projection_service.build_workspace_projection(db, project.id)

    assert result.project_id == project.id
    assert result.project.status == ProjectStatus.DRAFT.value
    assert result.current_stage.id == "requirements"
    assert result.current_stage.state == "READY"
    assert result.next_action.route.endswith("/requirements")
    assert result.current_stage.blocking_reasons[0].code == (
        "REQUIREMENT_SOURCE_MISSING"
    )
    assert result.stages[1].state == "LOCKED"
    assert result.stages[1].phase_id == "sources_evidence"
    assert result.stages[1].phase_label == "资料与证据"
    assert result.stages[1].is_substep is True
    assert result.stages[2].phase_id == "sources_evidence"
    assert result.stages[2].is_substep is True


def test_execution_failed_projection_is_failed_and_actionable(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="失败投影", topic="胃病数据分析")
    )
    project.status = ProjectStatus.EXECUTION_FAILED.value
    db.commit()

    result = projection_service.build_workspace_projection(db, project.id)

    assert result.current_stage.id == "execution"
    assert result.current_stage.state == "FAILED"
    assert result.next_action.stage_id == "execution"
    assert result.next_action.route.endswith("/execution")


def test_completed_project_projection_suppresses_next_action(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="完成投影", topic="胃病数据分析")
    )
    project.status = ProjectStatus.COMPLETED.value
    db.commit()

    result = projection_service.build_workspace_projection(db, project.id)

    assert result.current.step_id == "deliverables"
    assert result.recommended_next_action is None
    assert result.next_action is None
    assert result.project.topic == "胃病数据分析"
    assert result.project.status_label == "项目已完成"

def test_projection_rejects_unknown_project(db):
    with pytest.raises(AppError) as exc_info:
        projection_service.build_workspace_projection(db, "proj_missing")

    assert exc_info.value.code == "PROJECT_NOT_FOUND"


def test_projection_api_returns_typed_projection(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    from app.api.routers import projects as projects_router

    original_session_local = projects_router.SessionLocal
    projects_router.SessionLocal = SessionLocal
    try:
        project = project_service.create_project(
            db, ProjectCreateRequest(name="API 投影", topic="胃病数据分析")
        )
        with TestClient(app) as client:
            response = client.get(
                f"/api/projects/{project.id}/workspace-projection"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["project_id"] == project.id
        assert body["project"]["topic"] == "胃病数据分析"
        assert body["project"]["status_label"] == "草稿"
        assert body["current"]["step_id"] == "requirements"
        assert body["phases"][1]["id"] == "sources_evidence"
        assert body["phases"][1]["steps"][0]["status"] == "LOCKED"
        assert body["phases"][1]["steps"][0]["is_open"] is False
        assert body["phases"][1]["steps"][0]["open_reason"]["kind"] == "LOCKED"
        assert body["recommended_next_action"]["command_id"] == "workspace.open.requirements"
        assert body["current_stage"]["id"] == "requirements"
        assert body["next_action"]["route"].endswith("/requirements")
    finally:
        projects_router.SessionLocal = original_session_local
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_progress_contract_exposes_phases_steps_lock_reason_and_actions(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="规范合同", topic="胃病数据分析")
    )

    result = projection_service.build_workspace_projection(db, project.id)

    assert result.current.step_id == "requirements"
    assert result.phases[1].id == "sources_evidence"
    assert [step.id for step in result.phases[1].steps] == ["sources", "evidence"]
    locked_step = result.phases[1].steps[0]
    assert locked_step.status == "LOCKED"
    assert locked_step.is_open is False
    assert locked_step.open_reason is not None
    assert locked_step.open_reason.kind == "LOCKED"
    assert locked_step.blocking_reasons == []
    assert locked_step.actions[0].enabled is False
    assert locked_step.actions[0].command_id == "workspace.open.sources"
    assert result.recommended_next_action is not None
    assert result.recommended_next_action.enabled is True
    assert result.recommended_next_action.command_id == "workspace.open.requirements"


def test_failed_or_blocked_reason_precedes_completed_rank():
    execution = next(
        definition
        for definition in projection_service._STAGE_DEFINITIONS
        if definition["id"] == "execution"
    )

    failed = projection_service._reason(
        "EXECUTION_FAILED", "执行失败", "execution", "FAILED"
    )
    blocked = projection_service._reason(
        "DELIVERABLE_MISSING", "交付物缺失", "deliverables", "BLOCKED"
    )

    assert (
        projection_service._stage_state(
            12, ProjectStatus.COMPLETED.value, execution, [failed]
        )
        == "FAILED"
    )
    assert (
        projection_service._stage_state(
            12, ProjectStatus.COMPLETED.value, execution, [blocked]
        )
        == "BLOCKED"
    )