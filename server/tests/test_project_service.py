"""项目核心服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError as PydanticValidationError

from app.infrastructure.database.engine import Base
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.core.errors import AppError


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestCreateProject:
    """创建项目测试。"""

    def test_creates_project_with_valid_input(self, db):
        req = ProjectCreateRequest(name="胃病数据分析", topic="胃病数据分析")
        project = project_service.create_project(db, req)
        assert project.id.startswith("proj_")
        assert project.name == "胃病数据分析"
        assert project.topic == "胃病数据分析"
        assert project.status == ProjectStatus.DRAFT.value
        assert project.workspace_root.endswith(project.id)

    def test_rejects_empty_name_at_contract_layer(self):
        with pytest.raises(PydanticValidationError):
            ProjectCreateRequest(name="", topic="胃病数据分析")

    def test_rejects_whitespace_name(self, db):
        req = ProjectCreateRequest(name="   ", topic="胃病数据分析")
        with pytest.raises(AppError) as exc:
            project_service.create_project(db, req)
        assert exc.value.code == "PROJECT_NAME_REQUIRED"

    def test_rejects_empty_topic_at_contract_layer(self):
        with pytest.raises(PydanticValidationError):
            ProjectCreateRequest(name="胃病数据分析", topic="")


class TestListProjects:
    """项目列表测试。"""

    def test_returns_empty_list_when_no_projects(self, db):
        result = project_service.list_projects(db)
        assert result == []

    def test_returns_projects_in_desc_order(self, db):
        project_service.create_project(db, ProjectCreateRequest(name="A", topic="A"))
        project_service.create_project(db, ProjectCreateRequest(name="B", topic="B"))
        result = project_service.list_projects(db)
        assert len(result) == 2
        assert result[0].name == "B"


class TestGetProject:
    """项目详情测试。"""

    def test_returns_project_by_id(self, db):
        created = project_service.create_project(db, ProjectCreateRequest(name="测试", topic="测试"))
        found = project_service.get_project(db, created.id)
        assert found.name == "测试"

    def test_raises_on_missing_project(self, db):
        with pytest.raises(AppError) as exc:
            project_service.get_project(db, "nonexistent")
        assert exc.value.code == "PROJECT_NOT_FOUND"
