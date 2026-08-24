"""SPEC 0047 PDF 正式交付物合同测试（T2 RED 基线）。"""

from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.status import JobType
from app.modules.outlines import service as outline_service
from app.modules.outlines.models import Deliverable, DeliverableVersion, Outline
from app.modules.outlines.status import (
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
    OutlineStatus,
)
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _seed_project(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="PDF 合同测试", topic="教学实验")
    )
    project.status = ProjectStatus.OUTLINE_CONFIRMED.value
    outline = Outline(
        id="outline_pdf_001",
        project_id=project.id,
        sections_json=json.dumps([]),
        status=OutlineStatus.CONFIRMED.value,
        candidate_source="local_rule",
        code_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        confirmed_at=datetime.now(timezone.utc),
    )
    word = Deliverable(
        id="deliverable_word_001",
        project_id=project.id,
        outline_id=outline.id,
        deliverable_type=DeliverableType.WORD.value,
        status=DeliverableStatus.SUCCEEDED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    word_version = DeliverableVersion(
        id="version_word_001",
        deliverable_id=word.id,
        project_id=project.id,
        version=1,
        status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path="word_v1.docx",
        file_size_bytes=128,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([outline, word, word_version])
    db.commit()
    return project.id, outline.id, word.id, word_version.id


def test_pdf_type_and_job_type_are_registered():
    assert DeliverableType.PDF.value == "PDF"
    assert JobType.GENERATE_PDF.value == "GENERATE_PDF"


def test_generate_pdf_queues_from_successful_word(db):
    project_id, outline_id, word_id, word_version_id = _seed_project(db)

    job_id, pdf_id = outline_service.generate_pdf(
        db,
        project_id,
        outline_id,
        source_word_deliverable_id=word_id,
        source_word_version_id=word_version_id,
    )

    pdf = db.query(Deliverable).filter(Deliverable.id == pdf_id).one()
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).one()
    assert pdf.deliverable_type == DeliverableType.PDF.value
    assert job.job_type == JobType.GENERATE_PDF.value
    assert json.loads(job.input_json)["source_word_version_id"] == word_version_id


def test_complete_project_requires_pdf(db):
    project_id, outline_id, word_id, word_version_id = _seed_project(db)
    ppt = Deliverable(
        id="deliverable_ppt_001",
        project_id=project_id,
        outline_id=outline_id,
        deliverable_type=DeliverableType.PPT.value,
        status=DeliverableStatus.SUCCEEDED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ppt_version = DeliverableVersion(
        id="version_ppt_001",
        deliverable_id=ppt.id,
        project_id=project_id,
        version=1,
        status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path="ppt_v1.pptx",
        file_size_bytes=128,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([ppt, ppt_version])
    db.commit()

    with pytest.raises(AppError) as exc_info:
        outline_service.complete_project(db, project_id)
    assert exc_info.value.code == "PROJECT_NO_SUCCESSFUL_DELIVERABLE"

    pdf = Deliverable(
        id="deliverable_pdf_001",
        project_id=project_id,
        outline_id=outline_id,
        deliverable_type=DeliverableType.PDF.value,
        status=DeliverableStatus.SUCCEEDED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pdf_version = DeliverableVersion(
        id="version_pdf_001",
        deliverable_id=pdf.id,
        project_id=project_id,
        version=1,
        status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path="pdf_v1.pdf",
        file_size_bytes=128,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([pdf, pdf_version])
    db.commit()
    assert outline_service.complete_project(db, project_id).status == ProjectStatus.COMPLETED.value
