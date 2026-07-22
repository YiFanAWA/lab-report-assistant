"""大纲与交付物 API 端点测试。

覆盖 outlines 路由 7 个端点 + deliverables 路由 4 个端点：
大纲 API：
  POST /outline/generate
  GET  /outline
  GET  /outline/{outline_id}
  PUT  /outline/{outline_id}
  POST /outline/{outline_id}/confirm
  POST /outline/{outline_id}/reject
  POST /outline/{outline_id}/word/generate
  POST /outline/{outline_id}/ppt/generate
交付物 API：
  GET  /deliverables
  GET  /deliverables/{deliverable_id}/versions
  GET  /deliverables/{deliverable_id}/versions/{version_id}/download
  POST /complete
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.outlines.models import Outline, Deliverable, DeliverableVersion
from app.modules.outlines.status import (
    OutlineStatus,
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
)
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """TestClient + 内存 SQLite + 受控工作区。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.api.routers import projects as project_router
    from app.api.routers import outlines as outlines_router
    from app.api.routers import deliverables as deliverables_router

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(outlines_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(deliverables_router, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_project(client: TestClient,
                    status: str = ProjectStatus.RESULT_CONFIRMED.value) -> str:
    """创建项目并设置状态，返回 project_id。"""
    response = client.post(
        "/api/projects",
        json={"name": "胃病数据分析", "topic": "胃病数据分析"},
    )
    assert response.status_code == 200
    project_id = response.json()["id"]

    from app.api.routers import projects as project_router
    SessionLocal = project_router.SessionLocal
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = status
        db.commit()
    finally:
        db.close()
    return project_id


def _seed_outline(SessionLocal, project_id: str,
                   outline_id: str = "ol_api_001",
                   status: str = OutlineStatus.CANDIDATE.value) -> str:
    """直接插入大纲，返回 outline_id。"""
    db = SessionLocal()
    try:
        outline = Outline(
            id=outline_id,
            project_id=project_id,
            sections_json=json.dumps([
                {"id": "s1", "title": "实验目的", "content": "分析数据",
                 "source_type": "REQUIREMENT", "source_ids": ["p1"]},
                {"id": "s2", "title": "实验背景", "content": "背景说明",
                 "source_type": "EVIDENCE", "source_ids": ["c1"]},
            ]),
            status=status,
            candidate_source="local_rule",
            code_version=1,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(outline)
        db.commit()
        return outline.id
    finally:
        db.close()


# --- POST /outline/generate ---


class TestGenerateOutlineApi:
    """触发生成大纲候选 API 测试。"""

    def test_generate_returns_201_with_job_id(self, client):
        """RESULT_CONFIRMED 状态成功触发。"""
        project_id = _create_project(client)

        response = client.post(
            f"/api/projects/{project_id}/outline/generate"
        )
        assert response.status_code == 201
        assert response.json()["job_id"]

    def test_rejects_when_project_not_result_confirmed(self, client):
        """项目状态不足返回 400。"""
        project_id = _create_project(
            client, status=ProjectStatus.ANALYSIS_CONFIRMED.value)

        response = client.post(
            f"/api/projects/{project_id}/outline/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "OUTLINE_NOT_GENERATABLE"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在返回 404。"""
        response = client.post(
            "/api/projects/proj_missing/outline/generate"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- GET /outline (列表) ---


class TestListOutlinesApi:
    """大纲列表 API 测试。"""

    def test_list_returns_outlines(self, client):
        """返回大纲列表。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_list_1")
        _seed_outline(SessionLocal, project_id, "ol_list_2")

        response = client.get(f"/api/projects/{project_id}/outline")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2

    def test_list_filter_by_status(self, client):
        """按状态过滤。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_f1",
                      status=OutlineStatus.CANDIDATE.value)
        _seed_outline(SessionLocal, project_id, "ol_f2",
                      status=OutlineStatus.CONFIRMED.value)

        response = client.get(
            f"/api/projects/{project_id}/outline?status=CONFIRMED"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == "ol_f2"


# --- GET /outline/{outline_id} (详情) ---


class TestGetOutlineApi:
    """大纲详情 API 测试。"""

    def test_get_returns_outline(self, client):
        """返回大纲详情。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_get_1")

        response = client.get(
            f"/api/projects/{project_id}/outline/ol_get_1"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "ol_get_1"
        assert len(data["sections"]) == 2
        assert data["sections"][0]["title"] == "实验目的"

    def test_returns_404_when_outline_missing(self, client):
        """大纲不存在返回 404。"""
        project_id = _create_project(client)

        response = client.get(
            f"/api/projects/{project_id}/outline/ol_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "OUTLINE_NOT_FOUND"


# --- PUT /outline/{outline_id} (编辑) ---


class TestUpdateOutlineApi:
    """编辑大纲 API 测试。"""

    def test_update_returns_updated_outline(self, client):
        """编辑 CANDIDATE 大纲。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_upd_1")

        response = client.put(
            f"/api/projects/{project_id}/outline/ol_upd_1",
            json={
                "sections": [
                    {"id": "s1", "title": "新目的", "content": "新内容",
                     "source_type": "REQUIREMENT", "source_ids": ["p1"]},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sections"][0]["title"] == "新目的"

    def test_update_stale_returns_400(self, client):
        """STALE 状态不可编辑。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_upd_2",
                      status=OutlineStatus.STALE.value)

        response = client.put(
            f"/api/projects/{project_id}/outline/ol_upd_2",
            json={"sections": []},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "OUTLINE_NOT_EDITABLE"


# --- POST /outline/{outline_id}/confirm ---


class TestConfirmOutlineApi:
    """确认大纲 API 测试。"""

    def test_confirm_returns_confirmed_outline(self, client):
        """确认 CANDIDATE 大纲。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_conf_1")

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_conf_1/confirm"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"

    def test_confirm_non_candidate_returns_400(self, client):
        """非 CANDIDATE 不可确认。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_conf_2",
                      status=OutlineStatus.CONFIRMED.value)

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_conf_2/confirm"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "OUTLINE_NOT_CONFIRMABLE"


# --- POST /outline/{outline_id}/reject ---


class TestRejectOutlineApi:
    """拒绝大纲 API 测试。"""

    def test_reject_returns_rejected_outline(self, client):
        """拒绝 CANDIDATE 大纲。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(client)
        _seed_outline(SessionLocal, project_id, "ol_rej_1")

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_rej_1/reject"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"


# --- POST /outline/{outline_id}/word/generate ---


class TestGenerateWordApi:
    """触发 Word 生成 API 测试。"""

    def test_generate_returns_201(self, client):
        """CONFIRMED 大纲触发 Word 生成。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_outline(SessionLocal, project_id, "ol_word_1",
                      status=OutlineStatus.CONFIRMED.value)

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_word_1/word/generate"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["job_id"]
        assert data["deliverable_id"]

    def test_rejects_when_outline_not_confirmed(self, client):
        """未确认大纲返回 400。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_outline(SessionLocal, project_id, "ol_word_2",
                      status=OutlineStatus.CANDIDATE.value)

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_word_2/word/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DELIVERABLE_NOT_GENERATABLE"


# --- POST /outline/{outline_id}/ppt/generate ---


class TestGeneratePptApi:
    """触发 PPT 生成 API 测试。"""

    def test_generate_returns_201(self, client):
        """CONFIRMED 大纲触发 PPT 生成。"""
        from app.api.routers import outlines as outlines_router
        SessionLocal = outlines_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.OUTLINE_CONFIRMED.value)
        _seed_outline(SessionLocal, project_id, "ol_ppt_1",
                      status=OutlineStatus.CONFIRMED.value)

        response = client.post(
            f"/api/projects/{project_id}/outline/ol_ppt_1/ppt/generate"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["job_id"]
        assert data["deliverable_id"]


# --- GET /deliverables (列表) ---


class TestListDeliverablesApi:
    """交付物列表 API 测试。"""

    def test_list_returns_deliverables(self, client):
        """返回交付物列表。"""
        from app.api.routers import deliverables as deliverables_router
        SessionLocal = deliverables_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)
        outline_id = _seed_outline(SessionLocal, project_id, "ol_dl_1",
                                    status=OutlineStatus.CONFIRMED.value)

        db = SessionLocal()
        try:
            db.add(Deliverable(
                id="del_dl_1", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.WORD.value,
                status=DeliverableStatus.SUCCEEDED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.commit()
        finally:
            db.close()

        response = client.get(f"/api/projects/{project_id}/deliverables")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == "del_dl_1"


# --- GET /deliverables/{deliverable_id}/versions ---


class TestListDeliverableVersionsApi:
    """交付物版本列表 API 测试。"""

    def test_list_returns_versions(self, client):
        """返回版本列表，按版本号降序。"""
        from app.api.routers import deliverables as deliverables_router
        SessionLocal = deliverables_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)
        outline_id = _seed_outline(SessionLocal, project_id, "ol_ver_1",
                                    status=OutlineStatus.CONFIRMED.value)

        db = SessionLocal()
        try:
            db.add(Deliverable(
                id="del_ver_1", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.WORD.value,
                status=DeliverableStatus.SUCCEEDED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_1_a", deliverable_id="del_ver_1",
                project_id=project_id, version=1,
                status=DeliverableVersionStatus.FAILED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_1_b", deliverable_id="del_ver_1",
                project_id=project_id, version=2,
                status=DeliverableVersionStatus.SUCCEEDED.value,
                file_path="word_v2.docx", file_size_bytes=100,
                created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            ))
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"/api/projects/{project_id}/deliverables/del_ver_1/versions"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        # 版本号降序
        assert items[0]["version"] == 2
        assert items[1]["version"] == 1


# --- GET /deliverables/{deliverable_id}/versions/{version_id}/download ---


class TestDownloadDeliverableApi:
    """下载交付物 API 测试。"""

    def test_download_returns_file(self, client, tmp_path):
        """成功下载 SUCCEEDED 版本。"""
        from app.api.routers import deliverables as deliverables_router
        SessionLocal = deliverables_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)
        outline_id = _seed_outline(SessionLocal, project_id, "ol_dw_1",
                                    status=OutlineStatus.CONFIRMED.value)

        db = SessionLocal()
        try:
            db.add(Deliverable(
                id="del_dw_1", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.WORD.value,
                status=DeliverableStatus.SUCCEEDED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_dw_1", deliverable_id="del_dw_1",
                project_id=project_id, version=1,
                status=DeliverableVersionStatus.SUCCEEDED.value,
                file_path="word_v1.docx", file_size_bytes=100,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.commit()
        finally:
            db.close()

        # 创建实际文件
        file_dir = (tmp_path / "projects" / project_id
                    / "deliverables" / "del_dw_1")
        file_dir.mkdir(parents=True, exist_ok=True)
        (file_dir / "word_v1.docx").write_bytes(b"fake docx content")

        response = client.get(
            f"/api/projects/{project_id}/deliverables/del_dw_1"
            f"/versions/ver_dw_1/download"
        )
        assert response.status_code == 200
        assert "wordprocessingml" in response.headers.get(
            "content-type", "")

    def test_download_non_succeeded_returns_400(self, client):
        """非 SUCCEEDED 版本不可下载。"""
        from app.api.routers import deliverables as deliverables_router
        SessionLocal = deliverables_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)
        outline_id = _seed_outline(SessionLocal, project_id, "ol_dw_2",
                                    status=OutlineStatus.CONFIRMED.value)

        db = SessionLocal()
        try:
            db.add(Deliverable(
                id="del_dw_2", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.WORD.value,
                status=DeliverableStatus.RUNNING.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_dw_2", deliverable_id="del_dw_2",
                project_id=project_id, version=1,
                status=DeliverableVersionStatus.RUNNING.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"/api/projects/{project_id}/deliverables/del_dw_2"
            f"/versions/ver_dw_2/download"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DELIVERABLE_NOT_DOWNLOADABLE"


# --- POST /complete ---


class TestCompleteProjectApi:
    """完成项目 API 测试。"""

    def test_complete_returns_completed_status(self, client):
        """Word+PPT 均成功时完成项目。"""
        from app.api.routers import deliverables as deliverables_router
        SessionLocal = deliverables_router.SessionLocal
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)
        outline_id = _seed_outline(SessionLocal, project_id, "ol_cm_1",
                                    status=OutlineStatus.CONFIRMED.value)

        db = SessionLocal()
        try:
            # Word 成功
            db.add(Deliverable(
                id="del_cm_w", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.WORD.value,
                status=DeliverableStatus.SUCCEEDED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_cm_w", deliverable_id="del_cm_w",
                project_id=project_id, version=1,
                status=DeliverableVersionStatus.SUCCEEDED.value,
                file_path="word_v1.docx", file_size_bytes=100,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            # PPT 成功
            db.add(Deliverable(
                id="del_cm_p", project_id=project_id, outline_id=outline_id,
                deliverable_type=DeliverableType.PPT.value,
                status=DeliverableStatus.SUCCEEDED.value,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.add(DeliverableVersion(
                id="ver_cm_p", deliverable_id="del_cm_p",
                project_id=project_id, version=1,
                status=DeliverableVersionStatus.SUCCEEDED.value,
                file_path="ppt_v1.pptx", file_size_bytes=200,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ))
            db.commit()
        finally:
            db.close()

        response = client.post(f"/api/projects/{project_id}/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"

    def test_complete_without_deliverables_returns_400(self, client):
        """无成功交付物时返回 400。"""
        project_id = _create_project(
            client, status=ProjectStatus.GENERATING.value)

        response = client.post(f"/api/projects/{project_id}/complete")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_SUCCESSFUL_DELIVERABLE"
