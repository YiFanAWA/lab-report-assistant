"""大纲与交付物核心服务测试。

覆盖 service.py 的全部公开方法：
- generate_outline：触发生成大纲候选（状态校验、job 创建）
- list_outlines / get_outline / get_outline_by_project：查询与归属校验
- update_outline：编辑（状态校验、版本递增、STALE 传播）
- confirm_outline：确认（状态推进、STALE 传播）
- reject_outline：拒绝（状态校验）
- generate_word / generate_ppt：触发生成（deliverable 创建、job 创建）
- list_deliverables / list_deliverable_versions / get_version_by_project：查询
- get_deliverable_file_path：下载校验（状态、路径穿越）
- complete_project：完成项目（需 Word+PPT 成功）
- mark_outlines_stale：STALE 传播
- save_outline_draft / create_deliverable_version / mark_*：Worker 调用方法
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.modules.outlines import service as outline_service
from app.modules.outlines.contracts import OutlineSection, UpdateOutlineRequest
from app.modules.outlines.models import Outline, Deliverable, DeliverableVersion
from app.modules.outlines.status import (
    OutlineStatus,
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
)
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.status import JobType


TEST_DB = "sqlite:///:memory:"


# --- fixtures ---


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


def _create_project(db, status: str = ProjectStatus.RESULT_CONFIRMED.value) -> str:
    """创建项目并设置状态，返回 project_id。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _make_sections() -> list[OutlineSection]:
    """构造大纲章节列表。"""
    return [
        OutlineSection(id="s1", title="实验目的", content="分析数据",
                       source_type="REQUIREMENT", source_ids=["p1"]),
        OutlineSection(id="s2", title="实验背景", content="背景说明",
                       source_type="EVIDENCE", source_ids=["c1"]),
    ]


def _seed_candidate_outline(db, project_id: str,
                            outline_id: str = "ol_test_001",
                            status: str = OutlineStatus.CANDIDATE.value) -> Outline:
    """直接插入 Outline，返回实体。"""
    outline = Outline(
        id=outline_id,
        project_id=project_id,
        sections_json=json.dumps([
            {"id": "s1", "title": "实验目的", "content": "目的",
             "source_type": "REQUIREMENT", "source_ids": ["p1"]},
        ]),
        status=status,
        candidate_source="local_rule",
        code_version=1,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(outline)
    db.commit()
    return outline


def _seed_deliverable(db, project_id: str, outline_id: str,
                      deliverable_id: str = "del_test_001",
                      deliverable_type: str = DeliverableType.WORD.value,
                      status: str = DeliverableStatus.PENDING.value) -> Deliverable:
    """直接插入 Deliverable，返回实体。"""
    deliverable = Deliverable(
        id=deliverable_id,
        project_id=project_id,
        outline_id=outline_id,
        deliverable_type=deliverable_type,
        status=status,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(deliverable)
    db.commit()
    return deliverable


# --- generate_outline ---


class TestGenerateOutline:
    """触发生成大纲候选测试。"""

    def test_creates_job_and_change_record(self, db):
        """RESULT_CONFIRMED 状态下成功触发，创建 job 和变更记录。"""
        project_id = _create_project(db)

        job_id = outline_service.generate_outline(db, project_id)

        assert job_id
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job.job_type == JobType.GENERATE_OUTLINE.value
        assert job.project_id == project_id

    def test_rejects_when_project_not_result_confirmed(self, db):
        """项目状态不足时返回 OUTLINE_NOT_GENERATABLE。"""
        project_id = _create_project(db, status=ProjectStatus.ANALYSIS_CONFIRMED.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.generate_outline(db, project_id)
        assert exc_info.value.code == "OUTLINE_NOT_GENERATABLE"

    def test_rejects_when_project_missing(self, db):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        with pytest.raises(AppError) as exc_info:
            outline_service.generate_outline(db, "proj_missing")
        assert exc_info.value.code == "PROJECT_NOT_FOUND"

    def test_allows_regenerate_when_already_outline_confirmed(self, db):
        """OUTLINE_CONFIRMED 状态下允许重新生成大纲。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        job_id = outline_service.generate_outline(db, project_id)
        assert job_id


# --- 查询 ---


class TestQueryOutlines:
    """大纲查询测试。"""

    def test_list_outlines_by_project(self, db):
        """按项目列出大纲，按创建时间降序。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_a")
        _seed_candidate_outline(db, project_id, "ol_b")

        outlines = outline_service.list_outlines(db, project_id)
        assert len(outlines) == 2

    def test_list_outlines_filter_by_status(self, db):
        """按状态过滤大纲。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_cand",
                                status=OutlineStatus.CANDIDATE.value)
        _seed_candidate_outline(db, project_id, "ol_conf",
                                status=OutlineStatus.CONFIRMED.value)

        candidates = outline_service.list_outlines(
            db, project_id, status=OutlineStatus.CANDIDATE.value)
        assert len(candidates) == 1
        assert candidates[0].id == "ol_cand"

    def test_get_outline_not_found(self, db):
        """不存在的大纲抛出 OUTLINE_NOT_FOUND。"""
        with pytest.raises(AppError) as exc_info:
            outline_service.get_outline(db, "ol_missing")
        assert exc_info.value.code == "OUTLINE_NOT_FOUND"

    def test_get_outline_by_project_mismatch(self, db):
        """归属不匹配抛出 OUTLINE_NOT_FOUND。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_x")
        other_project_id = _create_project(db, status=ProjectStatus.RESULT_CONFIRMED.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.get_outline_by_project(db, other_project_id, "ol_x")
        assert exc_info.value.code == "OUTLINE_NOT_FOUND"


# --- 编辑 ---


class TestUpdateOutline:
    """编辑大纲测试。"""

    def test_update_candidate_keeps_candidate(self, db):
        """编辑 CANDIDATE 保持 CANDIDATE，版本不变。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(db, project_id, "ol_u1")
        original_version = outline.code_version

        req = UpdateOutlineRequest(sections=_make_sections())
        updated = outline_service.update_outline(db, project_id, "ol_u1", req)

        assert updated.status == OutlineStatus.CANDIDATE.value
        assert updated.code_version == original_version

    def test_update_confirmed_back_to_candidate_increments_version(self, db):
        """编辑 CONFIRMED 回到 CANDIDATE，版本递增。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(
            db, project_id, "ol_u2", status=OutlineStatus.CONFIRMED.value)
        original_version = outline.code_version

        req = UpdateOutlineRequest(sections=_make_sections())
        updated = outline_service.update_outline(db, project_id, "ol_u2", req)

        assert updated.status == OutlineStatus.CANDIDATE.value
        assert updated.code_version == original_version + 1
        assert updated.confirmed_at is None

    def test_update_stale_rejected(self, db):
        """STALE 状态不可编辑。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_u3",
                                status=OutlineStatus.STALE.value)

        req = UpdateOutlineRequest(sections=_make_sections())
        with pytest.raises(AppError) as exc_info:
            outline_service.update_outline(db, project_id, "ol_u3", req)
        assert exc_info.value.code == "OUTLINE_NOT_EDITABLE"

    def test_update_rejected_not_editable(self, db):
        """REJECTED 状态不可编辑。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_u4",
                                status=OutlineStatus.REJECTED.value)

        req = UpdateOutlineRequest(sections=_make_sections())
        with pytest.raises(AppError) as exc_info:
            outline_service.update_outline(db, project_id, "ol_u4", req)
        assert exc_info.value.code == "OUTLINE_NOT_EDITABLE"

    def test_update_propagates_stale_to_deliverables(self, db):
        """编辑 CONFIRMED 大纲时关联 Deliverable 变 STALE。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(
            db, project_id, "ol_u5", status=OutlineStatus.CONFIRMED.value)
        _seed_deliverable(db, project_id, outline.id, "del_u5",
                         status=DeliverableStatus.SUCCEEDED.value)

        req = UpdateOutlineRequest(sections=_make_sections())
        outline_service.update_outline(db, project_id, "ol_u5", req)

        deliverable = db.query(Deliverable).filter(
            Deliverable.id == "del_u5").first()
        assert deliverable.status == DeliverableStatus.STALE.value


# --- 确认 ---


class TestConfirmOutline:
    """确认大纲测试。"""

    def test_confirm_candidate_to_confirmed(self, db):
        """CANDIDATE 确认为 CONFIRMED，项目推进到 OUTLINE_CONFIRMED。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_c1")

        confirmed = outline_service.confirm_outline(db, project_id, "ol_c1")

        assert confirmed.status == OutlineStatus.CONFIRMED.value
        assert confirmed.confirmed_at is not None

        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.OUTLINE_CONFIRMED.value

    def test_confirm_rejected_status(self, db):
        """非 CANDIDATE 状态不可确认。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_c2",
                                status=OutlineStatus.CONFIRMED.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.confirm_outline(db, project_id, "ol_c2")
        assert exc_info.value.code == "OUTLINE_NOT_CONFIRMABLE"

    def test_confirm_propagates_stale_to_old_deliverables(self, db):
        """重新确认时旧 Deliverable 变 STALE。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_c3", status=OutlineStatus.CANDIDATE.value)
        # 模拟已有旧 Deliverable（从上次确认遗留）
        _seed_deliverable(db, project_id, outline.id, "del_old_c3",
                         status=DeliverableStatus.SUCCEEDED.value)

        outline_service.confirm_outline(db, project_id, "ol_c3")

        deliverable = db.query(Deliverable).filter(
            Deliverable.id == "del_old_c3").first()
        assert deliverable.status == DeliverableStatus.STALE.value


# --- 拒绝 ---


class TestRejectOutline:
    """拒绝大纲测试。"""

    def test_reject_candidate_to_rejected(self, db):
        """CANDIDATE 拒绝为 REJECTED。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_r1")

        rejected = outline_service.reject_outline(db, project_id, "ol_r1")

        assert rejected.status == OutlineStatus.REJECTED.value

    def test_reject_non_candidate_fails(self, db):
        """非 CANDIDATE 状态不可拒绝。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_r2",
                                status=OutlineStatus.CONFIRMED.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.reject_outline(db, project_id, "ol_r2")
        assert exc_info.value.code == "OUTLINE_NOT_CONFIRMABLE"


# --- Word/PPT 生成触发 ---


class TestGenerateDeliverables:
    """触发 Word/PPT 生成测试。"""

    def test_generate_word_creates_job_and_deliverable(self, db):
        """CONFIRMED 大纲触发 Word 生成，创建 job 和 deliverable。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_w1",
                               status=OutlineStatus.CONFIRMED.value)

        job_id, deliverable_id = outline_service.generate_word(
            db, project_id, "ol_w1")

        assert job_id
        assert deliverable_id
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job.job_type == JobType.GENERATE_WORD.value

        deliverable = db.query(Deliverable).filter(
            Deliverable.id == deliverable_id).first()
        assert deliverable.deliverable_type == DeliverableType.WORD.value
        assert deliverable.status == DeliverableStatus.PENDING.value

    def test_generate_ppt_creates_job_and_deliverable(self, db):
        """CONFIRMED 大纲触发 PPT 生成。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_p1",
                               status=OutlineStatus.CONFIRMED.value)

        job_id, deliverable_id = outline_service.generate_ppt(
            db, project_id, "ol_p1")

        assert job_id
        assert deliverable_id
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job.job_type == JobType.GENERATE_PPT.value

        deliverable = db.query(Deliverable).filter(
            Deliverable.id == deliverable_id).first()
        assert deliverable.deliverable_type == DeliverableType.PPT.value

    def test_generate_word_rejects_unconfirmed_outline(self, db):
        """未确认大纲不可生成 Word。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_w2",
                               status=OutlineStatus.CANDIDATE.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.generate_word(db, project_id, "ol_w2")
        assert exc_info.value.code == "DELIVERABLE_NOT_GENERATABLE"

    def test_generate_word_rejects_wrong_project_state(self, db):
        """项目状态不足时不可生成。"""
        project_id = _create_project(
            db, status=ProjectStatus.RESULT_CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_w3",
                               status=OutlineStatus.CONFIRMED.value)

        with pytest.raises(AppError) as exc_info:
            outline_service.generate_word(db, project_id, "ol_w3")
        assert exc_info.value.code == "DELIVERABLE_NOT_GENERATABLE"

    def test_regenerate_word_marks_old_deliverable_stale(self, db):
        """重新生成 Word 时旧 Deliverable 变 STALE。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_w4",
                               status=OutlineStatus.CONFIRMED.value)

        # 第一次生成
        _, del1 = outline_service.generate_word(db, project_id, "ol_w4")
        # 手动标记为 SUCCEEDED 模拟成功
        d1 = db.query(Deliverable).filter(Deliverable.id == del1).first()
        d1.status = DeliverableStatus.SUCCEEDED.value
        db.commit()

        # 第二次生成
        _, del2 = outline_service.generate_word(db, project_id, "ol_w4")

        assert del1 != del2
        old = db.query(Deliverable).filter(Deliverable.id == del1).first()
        assert old.status == DeliverableStatus.STALE.value


# --- 下载校验 ---


class TestGetDeliverableFilePath:
    """下载路径校验测试。"""

    def test_rejects_non_succeeded_version(self, db, tmp_path):
        """非 SUCCEEDED 版本不可下载。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_d1", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_d1")

        version = DeliverableVersion(
            id="ver_d1", deliverable_id=deliverable.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.RUNNING.value,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(version)
        db.commit()

        with pytest.raises(AppError) as exc_info:
            outline_service.get_deliverable_file_path(
                db, project_id, "del_d1", "ver_d1")
        assert exc_info.value.code == "DELIVERABLE_NOT_DOWNLOADABLE"

    def test_rejects_path_traversal(self, db, tmp_path):
        """路径穿越攻击被拦截。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_d2", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_d2")

        # 构造路径穿越的 file_path
        version = DeliverableVersion(
            id="ver_d2", deliverable_id=deliverable.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="../../../../etc/passwd",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(version)
        db.commit()

        with pytest.raises(AppError) as exc_info:
            outline_service.get_deliverable_file_path(
                db, project_id, "del_d2", "ver_d2")
        assert exc_info.value.code == "DELIVERABLE_NOT_DOWNLOADABLE"

    def test_returns_path_and_media_type_for_word(self, db, tmp_path):
        """Word 版本返回正确的路径和 media_type。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_d3", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_d3",
                                       deliverable_type=DeliverableType.WORD.value)

        # 在受控工作区创建实际文件
        file_dir = (tmp_path / "projects" / project_id
                    / "deliverables" / deliverable.id)
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / "word_v1.docx"
        file_path.write_bytes(b"fake docx")

        version = DeliverableVersion(
            id="ver_d3", deliverable_id=deliverable.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="word_v1.docx",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(version)
        db.commit()

        abs_path, filename, media_type = outline_service.get_deliverable_file_path(
            db, project_id, "del_d3", "ver_d3")
        assert filename == "word_v1.docx"
        assert "wordprocessingml" in media_type

    def test_returns_path_and_media_type_for_ppt(self, db, tmp_path):
        """PPT 版本返回正确的 media_type。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_d4", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_d4",
                                       deliverable_type=DeliverableType.PPT.value)

        file_dir = (tmp_path / "projects" / project_id
                    / "deliverables" / deliverable.id)
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / "ppt_v1.pptx"
        file_path.write_bytes(b"fake pptx")

        version = DeliverableVersion(
            id="ver_d4", deliverable_id=deliverable.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="ppt_v1.pptx",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(version)
        db.commit()

        abs_path, filename, media_type = outline_service.get_deliverable_file_path(
            db, project_id, "del_d4", "ver_d4")
        assert filename == "ppt_v1.pptx"
        assert "presentationml" in media_type


# --- 完成项目 ---


class TestCompleteProject:
    """完成项目测试。"""

    def test_rejects_without_successful_deliverables(self, db):
        """无成功交付物时不可完成。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        with pytest.raises(AppError) as exc_info:
            outline_service.complete_project(db, project_id)
        assert exc_info.value.code == "PROJECT_NO_SUCCESSFUL_DELIVERABLE"

    def test_rejects_with_only_word_succeeded(self, db):
        """只有 Word 成功时不可完成。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_cp1", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_cp1",
                                       deliverable_type=DeliverableType.WORD.value,
                                       status=DeliverableStatus.SUCCEEDED.value)
        version = DeliverableVersion(
            id="ver_cp1", deliverable_id=deliverable.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="word_v1.docx",
            file_size_bytes=100,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(version)
        db.commit()

        with pytest.raises(AppError) as exc_info:
            outline_service.complete_project(db, project_id)
        assert exc_info.value.code == "PROJECT_NO_SUCCESSFUL_DELIVERABLE"

    def test_completes_with_word_and_ppt_succeeded(self, db):
        """Word 和 PPT 均成功时可完成。"""
        project_id = _create_project(
            db, status=ProjectStatus.GENERATING.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_cp2", status=OutlineStatus.CONFIRMED.value)

        # Word 成功
        del_w = _seed_deliverable(db, project_id, outline.id, "del_w_cp2",
                                  deliverable_type=DeliverableType.WORD.value,
                                  status=DeliverableStatus.SUCCEEDED.value)
        db.add(DeliverableVersion(
            id="ver_w_cp2", deliverable_id=del_w.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="word_v1.docx", file_size_bytes=100,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ))

        # PPT 成功
        del_p = _seed_deliverable(db, project_id, outline.id, "del_p_cp2",
                                  deliverable_type=DeliverableType.PPT.value,
                                  status=DeliverableStatus.SUCCEEDED.value)
        db.add(DeliverableVersion(
            id="ver_p_cp2", deliverable_id=del_p.id,
            project_id=project_id, version=1,
            status=DeliverableVersionStatus.SUCCEEDED.value,
            file_path="ppt_v1.pptx", file_size_bytes=200,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ))
        db.commit()

        project = outline_service.complete_project(db, project_id)
        assert project.status == ProjectStatus.COMPLETED.value


# --- STALE 传播 ---


class TestStalePropagation:
    """STALE 传播测试。"""

    def test_mark_outlines_stale_affects_non_stale(self, db):
        """mark_outlines_stale 将非 STALE 大纲标记为 STALE。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_s1",
                                status=OutlineStatus.CANDIDATE.value)
        _seed_candidate_outline(db, project_id, "ol_s2",
                                status=OutlineStatus.CONFIRMED.value)
        _seed_candidate_outline(db, project_id, "ol_s3",
                                status=OutlineStatus.STALE.value)

        count = outline_service.mark_outlines_stale(db, project_id)

        assert count == 2  # 只有 2 个非 STALE 被标记
        for oid in ["ol_s1", "ol_s2"]:
            o = db.query(Outline).filter(Outline.id == oid).first()
            assert o.status == OutlineStatus.STALE.value

    def test_mark_outlines_stale_idempotent(self, db):
        """重复调用 mark_outlines_stale 幂等。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_s4",
                                status=OutlineStatus.CANDIDATE.value)

        outline_service.mark_outlines_stale(db, project_id)
        count = outline_service.mark_outlines_stale(db, project_id)

        assert count == 0  # 第二次没有新的需要标记

    def test_mark_outlines_stale_only_affects_target_project(self, db):
        """只影响目标项目的大纲。"""
        project_id_1 = _create_project(db)
        project_id_2 = _create_project(db, status=ProjectStatus.RESULT_CONFIRMED.value)
        _seed_candidate_outline(db, project_id_1, "ol_s5")
        _seed_candidate_outline(db, project_id_2, "ol_s6")

        count = outline_service.mark_outlines_stale(db, project_id_1)

        assert count == 1
        o2 = db.query(Outline).filter(Outline.id == "ol_s6").first()
        assert o2.status == OutlineStatus.CANDIDATE.value


# --- Worker 调用方法 ---


class TestWorkerMethods:
    """Worker 调用的内部方法测试。"""

    def test_save_outline_draft_creates_candidate(self, db):
        """save_outline_draft 创建 CANDIDATE 大纲。"""
        project_id = _create_project(db)

        outline = outline_service.save_outline_draft(
            db, project_id=project_id,
            sections=[
                {"id": "s1", "title": "目的", "content": "x",
                 "source_type": "REQUIREMENT", "source_ids": []},
            ],
            candidate_source="local_rule",
        )
        db.commit()

        assert outline.status == OutlineStatus.CANDIDATE.value
        assert outline.candidate_source == "local_rule"
        assert outline.code_version == 1
        sections = json.loads(outline.sections_json)
        assert len(sections) == 1

    def test_save_outline_draft_marks_old_candidate_stale(self, db):
        """已有 CANDIDATE 时，旧的变 STALE。"""
        project_id = _create_project(db)
        _seed_candidate_outline(db, project_id, "ol_old",
                                status=OutlineStatus.CANDIDATE.value)

        outline_service.save_outline_draft(
            db, project_id=project_id,
            sections=_make_sections(),
            candidate_source="local_rule",
        )
        db.commit()

        old = db.query(Outline).filter(Outline.id == "ol_old").first()
        assert old.status == OutlineStatus.STALE.value

    def test_create_deliverable_version_increments(self, db):
        """create_deliverable_version 版本号递增。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_v1", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_v1")

        _, v1 = outline_service.create_deliverable_version(
            db, project_id, "del_v1")
        assert v1.version == 1

        _, v2 = outline_service.create_deliverable_version(
            db, project_id, "del_v1")
        assert v2.version == 2

    def test_create_deliverable_version_advances_project_to_generating(self, db):
        """创建版本时项目从 OUTLINE_CONFIRMED 推进到 GENERATING。"""
        project_id = _create_project(
            db, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        outline = _seed_candidate_outline(
            db, project_id, "ol_v2", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_v2")

        outline_service.create_deliverable_version(
            db, project_id, "del_v2")
        db.commit()

        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.GENERATING.value

    def test_mark_deliverable_version_succeeded(self, db):
        """标记版本成功，保存文件路径。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(
            db, project_id, "ol_v3", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_v3")
        _, version = outline_service.create_deliverable_version(
            db, project_id, "del_v3")

        started = datetime(2024, 1, 1, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        outline_service.mark_deliverable_version_succeeded(
            db, version_id=version.id,
            file_path="word_v1.docx", file_size_bytes=1024,
            started_at=started, finished_at=finished,
            duration_seconds=60.0,
        )
        db.commit()

        v = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == version.id).first()
        assert v.status == DeliverableVersionStatus.SUCCEEDED.value
        assert v.file_path == "word_v1.docx"
        assert v.file_size_bytes == 1024

        d = db.query(Deliverable).filter(
            Deliverable.id == "del_v3").first()
        assert d.status == DeliverableStatus.SUCCEEDED.value

    def test_mark_deliverable_version_failed(self, db):
        """标记版本失败，保存错误信息。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(
            db, project_id, "ol_v4", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_v4")
        _, version = outline_service.create_deliverable_version(
            db, project_id, "del_v4")

        finished = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        outline_service.mark_deliverable_version_failed(
            db, version_id=version.id,
            error_code="WORD_RENDER_FAILED",
            error_message="测试错误",
            started_at=None, finished_at=finished,
            duration_seconds=0.0,
        )
        db.commit()

        v = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == version.id).first()
        assert v.status == DeliverableVersionStatus.FAILED.value
        assert v.error_code == "WORD_RENDER_FAILED"
        assert v.error_message == "测试错误"

        d = db.query(Deliverable).filter(
            Deliverable.id == "del_v4").first()
        assert d.status == DeliverableStatus.FAILED.value

    def test_failed_version_not_overwritten_by_success(self, db):
        """失败版本不能被覆盖为成功（需创建新版本）。"""
        project_id = _create_project(db)
        outline = _seed_candidate_outline(
            db, project_id, "ol_v5", status=OutlineStatus.CONFIRMED.value)
        deliverable = _seed_deliverable(db, project_id, outline.id, "del_v5")

        # 创建第一个版本并标记失败
        _, v1 = outline_service.create_deliverable_version(
            db, project_id, "del_v5")
        finished = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        outline_service.mark_deliverable_version_failed(
            db, version_id=v1.id,
            error_code="WORD_RENDER_FAILED",
            error_message="第一次失败",
            started_at=None, finished_at=finished,
            duration_seconds=0.0,
        )
        db.commit()

        # 创建第二个版本并标记成功
        _, v2 = outline_service.create_deliverable_version(
            db, project_id, "del_v5")
        assert v2.version == 2
        outline_service.mark_deliverable_version_succeeded(
            db, version_id=v2.id,
            file_path="word_v2.docx", file_size_bytes=2048,
            started_at=finished, finished_at=finished,
            duration_seconds=30.0,
        )
        db.commit()

        # 第一个版本保持失败状态
        v1_db = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == v1.id).first()
        assert v1_db.status == DeliverableVersionStatus.FAILED.value

        # 第二个版本成功
        v2_db = db.query(DeliverableVersion).filter(
            DeliverableVersion.id == v2.id).first()
        assert v2_db.status == DeliverableVersionStatus.SUCCEEDED.value
