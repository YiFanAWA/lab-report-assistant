"""SPEC 0047 交付审阅投影合同测试。"""

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.infrastructure.database.engine import Base
from app.modules.delivery_review import service as review_service
from app.modules.outlines.models import Deliverable, DeliverableVersion, Outline
from app.modules.outlines.status import (
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
    OutlineStatus,
)
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest


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


def test_empty_review_is_blocked_and_converter_is_not_run(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="交付审阅", topic="胃病数据分析")
    )

    result = review_service.build_delivery_review(db, project.id)

    assert result.review_status == "BLOCKED"
    assert result.available_actions.can_complete is False
    assert any(g.status == "NOT_RUN" for g in result.quality_gates)
    assert any(
        gate.code == "PDF_CONVERTER_AVAILABLE"
        and gate.status == "NOT_RUN"
        for gate in result.quality_gates
    )


def test_review_reports_failed_deliverable_reason(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="失败交付物", topic="胃病数据分析")
    )
    outline = Outline(
        id="ol_review_failed",
        project_id=project.id,
        sections_json=json.dumps([]),
        status="CONFIRMED",
        candidate_source="local_rule",
        code_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    deliverable = Deliverable(
        id="del_review_failed",
        project_id=project.id,
        outline_id=outline.id,
        deliverable_type=DeliverableType.PDF.value,
        status=DeliverableStatus.FAILED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    version = DeliverableVersion(
        id="ver_review_failed",
        deliverable_id=deliverable.id,
        project_id=project.id,
        version=1,
        status=DeliverableVersionStatus.FAILED.value,
        error_code="DOCX_PDF_CONVERTER_TIMEOUT",
        error_message="PDF 转换超过允许时限。",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([outline, deliverable, version])
    db.commit()

    result = review_service.build_delivery_review(db, project.id)

    item = next(item for item in result.deliverables if item.id == deliverable.id)
    assert item.failure is not None
    assert item.failure.code == "DOCX_PDF_CONVERTER_TIMEOUT"
    assert any(
        gate.code == "PDF_SUCCEEDED" and gate.status == "BLOCKED"
        for gate in result.quality_gates
    )


def test_review_requires_three_same_outline_deliverables(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="同源审阅", topic="胃病数据分析")
    )
    outline = Outline(
        id="ol_review_same",
        project_id=project.id,
        sections_json=json.dumps([]),
        status="CONFIRMED",
        candidate_source="local_rule",
        code_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(outline)
    for index, deliverable_type in enumerate(
        (DeliverableType.WORD.value, DeliverableType.PPT.value),
        start=1,
    ):
        deliverable = Deliverable(
            id=f"del_review_{index}",
            project_id=project.id,
            outline_id=outline.id,
            deliverable_type=deliverable_type,
            status=DeliverableStatus.SUCCEEDED.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(deliverable)
        db.add(DeliverableVersion(
            id=f"ver_review_{index}",
            deliverable_id=deliverable.id,
            project_id=project.id,
            version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path=f"file_{index}",
            file_size_bytes=100,
            created_at=datetime.now(timezone.utc),
        ))
    db.commit()

    result = review_service.build_delivery_review(db, project.id)

    same_outline = next(
        gate for gate in result.quality_gates
        if gate.code == "DELIVERABLES_SAME_OUTLINE"
    )
    assert same_outline.status == "BLOCKED"
    assert result.available_actions.can_complete is False

def test_review_exposes_version_provenance_history_and_unchecked_preview(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="版本审阅", topic="胃病数据分析")
    )
    now = datetime.now(timezone.utc)
    outline = Outline(
        id="ol_review_provenance",
        project_id=project.id,
        sections_json=json.dumps({"sections": []}),
        status=OutlineStatus.CONFIRMED.value,
        candidate_source="local_rule",
        code_version=3,
        created_at=now,
        updated_at=now,
    )
    deliverable = Deliverable(
        id="del_review_provenance",
        project_id=project.id,
        outline_id=outline.id,
        deliverable_type=DeliverableType.WORD.value,
        status=DeliverableStatus.SUCCEEDED.value,
        created_at=now,
        updated_at=now,
    )
    version = DeliverableVersion(
        id="ver_review_provenance",
        deliverable_id=deliverable.id,
        project_id=project.id,
        version=2,
        status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path="word_v2.docx",
        file_size_bytes=512,
        outline_version=3,
        dataset_version_id="dataset_v2",
        dataset_version_ids_json=json.dumps(["dataset_v2"]),
        analysis_plan_id="analysis_v2",
        analysis_plan_ids_json=json.dumps(["analysis_v2"]),
        execution_run_id="run_v2",
        execution_run_ids_json=json.dumps(["run_v2"]),
        file_sha256="a" * 64,
        created_at=now,
    )
    db.add_all([outline, deliverable, version])
    db.commit()

    result = review_service.build_delivery_review(db, project.id)
    item = next(item for item in result.deliverables if item.id == deliverable.id)
    reviewed = item.versions[0]

    assert item.recommended_version_id == version.id
    assert reviewed.is_recommended is True
    assert reviewed.provenance.dataset_version_ids == ["dataset_v2"]
    assert reviewed.provenance.analysis_plan_ids == ["analysis_v2"]
    assert reviewed.provenance.execution_run_ids == ["run_v2"]
    assert reviewed.preview.status == "NOT_AVAILABLE"
    assert reviewed.visual_inspection.status == "NOT_CHECKED"
    assert result.recommended_downloads[0].version_id == version.id


def test_review_marks_legacy_version_provenance_as_unavailable(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="旧版本", topic="胃病数据分析")
    )
    now = datetime.now(timezone.utc)
    outline = Outline(
        id="ol_review_legacy",
        project_id=project.id,
        sections_json=json.dumps([]),
        status=OutlineStatus.CONFIRMED.value,
        candidate_source="local_rule",
        code_version=1,
        created_at=now,
        updated_at=now,
    )
    deliverable = Deliverable(
        id="del_review_legacy",
        project_id=project.id,
        outline_id=outline.id,
        deliverable_type=DeliverableType.WORD.value,
        status=DeliverableStatus.SUCCEEDED.value,
        created_at=now,
        updated_at=now,
    )
    version = DeliverableVersion(
        id="ver_review_legacy",
        deliverable_id=deliverable.id,
        project_id=project.id,
        version=1,
        status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path="word_v1.docx",
        created_at=now,
    )
    db.add_all([outline, deliverable, version])
    db.commit()

    item = review_service.build_delivery_review(db, project.id).deliverables[0]
    assert item.provenance.unavailable_reason is not None
    assert "无法从版本本身回推" in item.provenance.unavailable_reason


def test_review_boundary_checks_block_unsupported_l3_and_causal_claims(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="边界负向", topic="医学数据")
    )
    from app.modules.requirements.models import RequirementPlan

    plan = RequirementPlan(
        id="plan_review_boundary_negative",
        project_id=project.id,
        source_id="requirement_source",
        status="CONFIRMED",
        payload_json=json.dumps({
            "replication_level": {
                "level": "L3",
                "supported_in_v1": False,
            },
            "study_design": "OBSERVATIONAL",
            "causal_claim_allowed": True,
            "domain": "MEDICAL",
            "teaching_analysis_boundary": False,
        }),
        candidate_source="MANUAL",
    )
    db.add(plan)
    db.commit()

    result = review_service.build_delivery_review(db, project.id)
    boundary_gate = next(gate for gate in result.quality_gates if gate.code == "STATISTICAL_BOUNDARIES")
    assert boundary_gate.status == "BLOCKED"
    assert {check.code for check in result.boundary_checks if check.status == "BLOCKED"} == {
        "OBSERVATIONAL_CAUSAL_BOUNDARY",
        "REPLICATION_LEVEL",
        "MEDICAL_TEACHING_BOUNDARY",
    }


def test_review_boundary_checks_pass_when_structured_declarations_are_explicit(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="边界正向", topic="医学数据")
    )
    from app.modules.requirements.models import RequirementPlan

    plan = RequirementPlan(
        id="plan_review_boundary_positive",
        project_id=project.id,
        source_id="requirement_source",
        status="CONFIRMED",
        payload_json=json.dumps({
            "replication_level": {
                "level": "L1",
                "supported_in_v1": True,
            },
            "study_design": "OBSERVATIONAL",
            "causal_claim_allowed": False,
            "domain": "MEDICAL",
            "teaching_analysis_boundary": True,
        }),
        candidate_source="MANUAL",
    )
    db.add(plan)
    db.commit()

    result = review_service.build_delivery_review(db, project.id)
    boundary_gate = next(gate for gate in result.quality_gates if gate.code == "STATISTICAL_BOUNDARIES")
    assert boundary_gate.status == "PASS"
    assert all(check.status == "PASS" for check in result.boundary_checks)

def test_review_keeps_word_pdf_ppt_provenance_consistent(db):
    project = project_service.create_project(
        db, ProjectCreateRequest(name="一致性审阅", topic="胃病数据分析")
    )
    now = datetime.now(timezone.utc)
    outline = Outline(
        id="ol_review_consistent",
        project_id=project.id,
        sections_json=json.dumps([]),
        status=OutlineStatus.CONFIRMED.value,
        candidate_source="local_rule",
        code_version=2,
        created_at=now,
        updated_at=now,
    )
    db.add(outline)
    for deliverable_id, deliverable_type, version_id in (
        ("del_consistent_word", DeliverableType.WORD.value, "ver_consistent_word"),
        ("del_consistent_pdf", DeliverableType.PDF.value, "ver_consistent_pdf"),
        ("del_consistent_ppt", DeliverableType.PPT.value, "ver_consistent_ppt"),
    ):
        db.add(Deliverable(
            id=deliverable_id,
            project_id=project.id,
            outline_id=outline.id,
            deliverable_type=deliverable_type,
            status=DeliverableStatus.SUCCEEDED.value,
            created_at=now,
            updated_at=now,
        ))
        db.add(DeliverableVersion(
            id=version_id,
            deliverable_id=deliverable_id,
            project_id=project.id,
            version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path=f"{deliverable_type.lower()}_v1",
            file_size_bytes=100,
            outline_version=2,
            dataset_version_id="dataset_consistent",
            dataset_version_ids_json=json.dumps(["dataset_consistent"]),
            analysis_plan_id="analysis_consistent",
            analysis_plan_ids_json=json.dumps(["analysis_consistent"]),
            execution_run_id="run_consistent",
            execution_run_ids_json=json.dumps(["run_consistent"]),
            source_word_version_id=(
                "ver_consistent_word" if deliverable_type == DeliverableType.PDF.value else None
            ),
            file_sha256="b" * 64,
            created_at=now,
        ))
    db.commit()

    result = review_service.build_delivery_review(db, project.id)

    assert {item.deliverable_type for item in result.recommended_downloads} == {
        DeliverableType.WORD.value,
        DeliverableType.PDF.value,
        DeliverableType.PPT.value,
    }
    assert result.traceability.dataset_version_ids == ["dataset_consistent"]
    assert result.traceability.analysis_plan_ids == ["analysis_consistent"]
    assert result.traceability.execution_run_ids == ["run_consistent"]
    pdf = next(item for item in result.deliverables if item.type == DeliverableType.PDF.value)
    assert pdf.provenance.source_word_version_id == "ver_consistent_word"
    provenance_gate = next(
        gate for gate in result.quality_gates if gate.code == "VERSION_PROVENANCE"
    )
    assert provenance_gate.status == "PASS"
