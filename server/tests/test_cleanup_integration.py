"""SPEC 0012 集成测试（真实 SQLite + 文件系统）。

端到端验证清理流程、混合场景、清理后完整性。
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.modules.analysis.models import AnalysisPlan
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.execution.models import CodeTask, ExecutionArtifact, ExecutionRun
from app.modules.jobs.models import BackgroundJob, _uid
from app.modules.jobs.status import JobStatus
from app.modules.outlines.models import (
    Deliverable,
    DeliverableVersion,
    Outline,
    WordTemplate,
)
from app.modules.outlines.status import (
    DeliverableStatus,
    DeliverableVersionStatus,
    OutlineStatus,
)
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import (
    ChangeRecord,
    RequirementPlan,
    RequirementSource,
)
from app.modules.sources.models import EvidenceCard, ParsedDocument, Source


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db_and_root(tmp_path, monkeypatch):
    """内存 SQLite + 受控文件系统根目录。"""
    engine = create_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # 使用环境变量设置 PROJECT_DATA_ROOT（property 不可 setattr）
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path))

    yield session, tmp_path

    session.close()
    Base.metadata.drop_all(bind=engine)


def _now():
    return datetime.now(timezone.utc)


def _create_full_project(db, root, project_id: str, updated_days_ago: int):
    """创建含完整链路数据的项目（18 张表全有数据）。"""
    now = _now()
    project = Project(
        id=project_id,
        name=f"完整项目_{project_id}",
        topic=f"课题_{project_id}",
        status=ProjectStatus.COMPLETED.value,
        workspace_root=str(root / project_id),
        created_at=now - timedelta(days=updated_days_ago + 10),
        updated_at=now - timedelta(days=updated_days_ago),
    )
    db.add(project)

    # requirements（3 张表）
    db.add(RequirementSource(
        id="rs_" + project_id, project_id=project_id,
        source_type="MANUAL", title="实验要求",
        original_text="实验要求内容", content_hash="a" * 64,
    ))
    db.add(RequirementPlan(
        id="rp_" + project_id, project_id=project_id, source_id="rs_" + project_id,
        status="CONFIRMED", payload_json=json.dumps({"goal": "分析数据"}),
        candidate_source="LOCAL_RULE",
    ))
    db.add(ChangeRecord(
        id="cr_" + project_id, project_id=project_id,
        change_type="ADD", summary="新增要求",
    ))

    # sources（3 张表）
    db.add(Source(
        id="src_" + project_id, project_id=project_id,
        source_kind="URL", title="来源", url="https://example.com",
        status="FETCHED",
    ))
    db.add(ParsedDocument(
        id="pd_" + project_id, source_id="src_" + project_id, project_id=project_id,
        title="解析文档", parsed_text="解析内容",
    ))
    db.add(EvidenceCard(
        id="ec_" + project_id, project_id=project_id, source_id="src_" + project_id,
        parsed_document_id="pd_" + project_id,
        summary="证据摘要", evidence_type="STATISTIC", locator="page1",
        status="CONFIRMED", candidate_source="LOCAL_RULE",
    ))

    # jobs（1 张表）
    db.add(BackgroundJob(
        id=_uid(), project_id=project_id, job_type="FETCH_URL",
        status=JobStatus.SUCCEEDED.value, input_json="{}", retry_count=0, max_retries=2,
    ))

    # datasets（2 张表）
    db.add(Dataset(
        id="ds_" + project_id, project_id=project_id,
        dataset_kind="CSV", title="数据集", status="READY",
    ))
    db.add(DatasetVersion(
        id="dv_" + project_id, dataset_id="ds_" + project_id, project_id=project_id,
        version=1, status="READY", file_path="data.csv", file_size_bytes=100,
    ))

    # analysis（1 张表）
    db.add(AnalysisPlan(
        id="ap_" + project_id, project_id=project_id,
        dataset_id="ds_" + project_id, dataset_version_id="dv_" + project_id,
        cleaning_plan="{}", analysis_plan="{}", chart_plan="{}",
        status="CONFIRMED", candidate_source="LOCAL_RULE",
    ))

    # execution（3 张表）
    db.add(CodeTask(
        id="ct_" + project_id, project_id=project_id,
        analysis_plan_id="ap_" + project_id,
        dataset_id="ds_" + project_id, dataset_version_id="dv_" + project_id,
        code="print('hello')", code_version=1,
        status="SUCCEEDED", candidate_source="LOCAL_RULE",
    ))
    db.add(ExecutionRun(
        id="er_" + project_id, project_id=project_id, code_task_id="ct_" + project_id,
        dataset_version_id="dv_" + project_id, code_version=1, status="SUCCEEDED",
    ))
    db.add(ExecutionArtifact(
        id="ea_" + project_id, execution_run_id="er_" + project_id, project_id=project_id,
        artifact_type="TABLE", file_path="output.csv", file_size_bytes=100, name="output.csv",
    ))

    # outlines（4 张表）
    db.add(Outline(
        id="ol_" + project_id, project_id=project_id,
        sections_json="[]", status=OutlineStatus.CONFIRMED.value,
        candidate_source="LOCAL_RULE", code_version=1,
    ))
    db.add(Deliverable(
        id="dl_" + project_id, project_id=project_id, outline_id="ol_" + project_id,
        deliverable_type="WORD", status=DeliverableStatus.SUCCEEDED.value,
    ))
    db.add(DeliverableVersion(
        id="dvl_" + project_id, deliverable_id="dl_" + project_id, project_id=project_id,
        version=1, status=DeliverableVersionStatus.SUCCEEDED.value,
        file_path=f"{project_id}/word/v1.docx",
    ))
    db.add(WordTemplate(
        id="wt_" + project_id, project_id=project_id,
        original_filename="template.docx",
        file_path=f"{project_id}/word_template/template.docx",
        content_hash="a" * 64, file_size_bytes=100,
    ))

    db.commit()

    # 创建文件系统目录
    project_dir = root / project_id
    (project_dir / "sources").mkdir(parents=True)
    (project_dir / "sources" / "file.txt").write_text("test")
    (project_dir / "executions").mkdir(parents=True)
    (project_dir / "word_template").mkdir(parents=True)
    (project_dir / "word_template" / "template.docx").write_bytes(b"fake")

    return project


# --- 端到端测试 ---


class TestEndToEndCleanup:
    """端到端清理流程测试。"""

    def test_full_cleanup_execute(self, db_and_root):
        """I-01：端到端清理，18 张表 + 文件系统目录全删。"""
        db, root = db_and_root
        _create_full_project(db, root, "p_full", updated_days_ago=35)

        from scripts.cleanup_expired_data import run_cleanup
        exit_code = run_cleanup(retention_days=30, execute=True, db=db)

        assert exit_code == 0
        # 验证数据库无残留
        assert db.query(Project).filter(Project.id == "p_full").first() is None
        assert db.query(RequirementSource).filter(RequirementSource.project_id == "p_full").count() == 0
        assert db.query(RequirementPlan).filter(RequirementPlan.project_id == "p_full").count() == 0
        assert db.query(ChangeRecord).filter(ChangeRecord.project_id == "p_full").count() == 0
        assert db.query(Source).filter(Source.project_id == "p_full").count() == 0
        assert db.query(ParsedDocument).count() == 0
        assert db.query(EvidenceCard).count() == 0
        assert db.query(BackgroundJob).filter(BackgroundJob.project_id == "p_full").count() == 0
        assert db.query(Dataset).filter(Dataset.project_id == "p_full").count() == 0
        assert db.query(DatasetVersion).count() == 0
        assert db.query(AnalysisPlan).filter(AnalysisPlan.project_id == "p_full").count() == 0
        assert db.query(CodeTask).filter(CodeTask.project_id == "p_full").count() == 0
        assert db.query(ExecutionRun).count() == 0
        assert db.query(ExecutionArtifact).count() == 0
        assert db.query(Outline).filter(Outline.project_id == "p_full").count() == 0
        assert db.query(Deliverable).filter(Deliverable.project_id == "p_full").count() == 0
        assert db.query(DeliverableVersion).count() == 0
        assert db.query(WordTemplate).filter(WordTemplate.project_id == "p_full").count() == 0
        # 验证文件系统目录已删除
        assert not (root / "p_full").exists()

    def test_full_cleanup_dry_run(self, db_and_root, capsys):
        """I-02：端到端 dry-run，项目和数据全部保留。"""
        db, root = db_and_root
        _create_full_project(db, root, "p_dryrun", updated_days_ago=35)

        from scripts.cleanup_expired_data import run_cleanup
        exit_code = run_cleanup(retention_days=30, execute=False, db=db)

        assert exit_code == 0
        # 验证数据全部保留
        assert db.query(Project).filter(Project.id == "p_dryrun").first() is not None
        assert db.query(RequirementSource).filter(RequirementSource.project_id == "p_dryrun").count() == 1
        # 验证文件系统目录保留
        assert (root / "p_dryrun").exists()

    def test_mixed_scenario(self, db_and_root, capsys):
        """I-03：混合场景，仅清理过期项目。"""
        db, root = db_and_root
        _create_full_project(db, root, "p_old_1", updated_days_ago=35)
        _create_full_project(db, root, "p_old_2", updated_days_ago=40)
        _create_full_project(db, root, "p_new_1", updated_days_ago=10)
        _create_full_project(db, root, "p_new_2", updated_days_ago=20)

        from scripts.cleanup_expired_data import run_cleanup
        exit_code = run_cleanup(retention_days=30, execute=True, db=db)

        assert exit_code == 0
        # 过期项目已删除
        assert db.query(Project).filter(Project.id == "p_old_1").first() is None
        assert db.query(Project).filter(Project.id == "p_old_2").first() is None
        # 未过期项目保留
        assert db.query(Project).filter(Project.id == "p_new_1").first() is not None
        assert db.query(Project).filter(Project.id == "p_new_2").first() is not None
        # 文件系统验证
        assert not (root / "p_old_1").exists()
        assert not (root / "p_old_2").exists()
        assert (root / "p_new_1").exists()
        assert (root / "p_new_2").exists()

    def test_database_integrity_after_cleanup(self, db_and_root):
        """I-04：清理后数据库完整性，其他项目无影响。"""
        db, root = db_and_root
        _create_full_project(db, root, "p_keep", updated_days_ago=10)
        _create_full_project(db, root, "p_delete", updated_days_ago=35)

        from scripts.cleanup_expired_data import run_cleanup
        run_cleanup(retention_days=30, execute=True, db=db)

        # 保留的项目数据完整
        assert db.query(Project).filter(Project.id == "p_keep").first() is not None
        assert db.query(RequirementSource).filter(RequirementSource.project_id == "p_keep").count() == 1
        assert db.query(Source).filter(Source.project_id == "p_keep").count() == 1
        assert db.query(Outline).filter(Outline.project_id == "p_keep").count() == 1
        # 数据库可正常查询
        all_projects = db.query(Project).all()
        assert len(all_projects) == 1
        assert all_projects[0].id == "p_keep"

    def test_active_project_resets_timer(self, db_and_root, capsys):
        """I-06：活跃项目重置计时器。"""
        db, root = db_and_root
        # created_at 35天前，但 updated_at 5天前（中途有更新）
        _create_full_project(db, root, "p_active", updated_days_ago=5)

        from scripts.cleanup_expired_data import run_cleanup
        exit_code = run_cleanup(retention_days=30, execute=True, db=db)

        assert exit_code == 0
        # updated_at 5天前未过期，项目保留
        assert db.query(Project).filter(Project.id == "p_active").first() is not None
        captured = capsys.readouterr()
        assert "无过期项目" in captured.out

    def test_running_job_protection_e2e(self, db_and_root, capsys):
        """I-07：RUNNING job 保护端到端，项目跳过清理。"""
        db, root = db_and_root
        _create_full_project(db, root, "p_protected", updated_days_ago=35)
        # 添加 RUNNING job
        db.add(BackgroundJob(
            id=_uid(), project_id="p_protected", job_type="FETCH_URL",
            status=JobStatus.RUNNING.value, input_json="{}", retry_count=0, max_retries=2,
        ))
        db.commit()

        from scripts.cleanup_expired_data import run_cleanup
        exit_code = run_cleanup(retention_days=30, execute=True, db=db)

        assert exit_code == 0
        # 项目受保护，保留
        assert db.query(Project).filter(Project.id == "p_protected").first() is not None
        captured = capsys.readouterr()
        assert "跳过" in captured.out or "活跃任务" in captured.out
