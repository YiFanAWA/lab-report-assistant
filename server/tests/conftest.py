"""来源与证据测试的共享 fixture。"""

import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
import app.modules.projects.models  # noqa: F401
import app.modules.requirements.models  # noqa: F401
import app.modules.sources.models  # noqa: F401
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.requirements import service as requirement_service
from app.modules.requirements.contracts import GeneratePlanRequest, TextSourceRequest


PDF_WITH_TEXT_BASE64 = """JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUiA1IDAgUl0gL0NvdW50IDIgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSAvUmVzb3VyY2VzIDw8IC9Gb250IDw8IC9GMSA0IDAgUiA+PiA+PiAvQ29udGVudHMgNiAwIFIgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL1R5cGUgL0ZvbnQgL1N1YnR5cGUgL1R5cGUxIC9CYXNlRm9udCAvSGVsdmV0aWNhID4+CmVuZG9iago1IDAgb2JqCjw8IC9UeXBlIC9QYWdlIC9QYXJlbnQgMiAwIFIgL01lZGlhQm94IFswIDAgNjEyIDc5Ml0gL1Jlc291cmNlcyA8PCAvRm9udCA8PCAvRjEgNCAwIFIgPj4gPj4gL0NvbnRlbnRzIDcgMCBSID4+CmVuZG9iago2IDAgb2JqCjw8IC9MZW5ndGggNDkgPj4Kc3RyZWFtCkJUIC9GMSAxMiBUZiA3MiA3MjAgVGQgKFBhZ2Ugb25lIGV2aWRlbmNlLikgVGogRVQKZW5kc3RyZWFtCmVuZG9iago3IDAgb2JqCjw8IC9MZW5ndGggNDkgPj4Kc3RyZWFtCkJUIC9GMSAxMiBUZiA3MiA3MjAgVGQgKFBhZ2UgdHdvIGV2aWRlbmNlLikgVGogRVQKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgOAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA1OCAwMDAwMCBuIAowMDAwMDAwMTIxIDAwMDAwIG4gCjAwMDAwMDAyNDcgMDAwMDAgbiAKMDAwMDAwMDMxNyAwMDAwMCBuIAowMDAwMDAwNDQzIDAwMDAwIG4gCjAwMDAwMDA1NDIgMDAwMDAgbiAKdHJhaWxlcgo8PCAvU2l6ZSA4IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo2NDEKJSVFT0YK"""


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def project_with_plan(db, monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    project = project_service.create_project(
        db, ProjectCreateRequest(name="测试项目", topic="胃病数据分析")
    )
    source = requirement_service.add_text_source(
        db,
        project.id,
        TextSourceRequest(title="老师要求", text="完成公开资料分析"),
    )
    plan = requirement_service.generate_plan(
        db,
        project.id,
        GeneratePlanRequest(source_id=source.id),
        LocalRuleRequirementDraftProvider(),
    )
    requirement_service.confirm_plan(db, project.id, plan.id)
    return project.id


@pytest.fixture
def pdf_with_text_bytes():
    return base64.b64decode(PDF_WITH_TEXT_BASE64)
