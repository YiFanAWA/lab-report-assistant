"""证据卡片 API 端点测试。

使用 TestClient + monkeypatch SessionLocal，覆盖证据卡片的
生成触发、列表、更新、确认、拒绝、完成 API。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import (  # noqa: F401
    RequirementSource,
    RequirementPlan,
    ChangeRecord,
)
from app.modules.sources.models import (
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.jobs.models import BackgroundJob  # noqa: F401
from app.modules.sources.status import (
    SourceKind,
    SourceStatus,
    EvidenceCardStatus,
    CandidateSource,
)


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
    from app.api.routers import requirements as requirement_router
    from app.api.routers import sources as sources_router
    from app.api.routers import evidence as evidence_router
    from app.api.routers import jobs as jobs_router

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(sources_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(evidence_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(jobs_router, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_confirmed_project(client: TestClient) -> str:
    """创建并返回 REQUIREMENT_CONFIRMED 状态的项目 ID。"""
    resp = client.post(
        "/api/projects",
        json={"name": "胃病数据分析", "topic": "胃病数据分析"},
    )
    project_id = resp.json()["id"]

    source_resp = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "需求", "text": "完成数据清洗、统计分析和可视化"},
    )
    source_id = source_resp.json()["id"]
    plan_resp = client.post(
        f"/api/projects/{project_id}/requirements/plans/generate",
        json={"source_id": source_id},
    )
    plan_id = plan_resp.json()["id"]
    client.post(
        f"/api/projects/{project_id}/requirements/plans/{plan_id}/confirm"
    )
    return project_id


def _seed_parsed_source_in_db(
    TestingSessionLocal, project_id: str,
    parsed_text: str = "背景：本节介绍胃病数据分析的研究背景与研究意义。"
                       "方法：采用描述性统计和可视化方法分析数据。"
                       "结果：分析显示关键变量之间存在显著相关。",
) -> tuple[str, str]:
    """直接操作数据库构造一个 PARSED 来源和 ParsedDocument，绕过 Worker。"""
    db = TestingSessionLocal()
    try:
        source = Source(
            id="src_api_parsed",
            project_id=project_id,
            source_kind=SourceKind.URL.value,
            title="API 测试已解析来源",
            url="https://example.com/article.html",
            status=SourceStatus.PARSED.value,
            content_type="text/html",
            content_hash="hash_api_001",
            file_path="/tmp/raw.html",
        )
        db.add(source)
        pd = ParsedDocument(
            id="pd_api_001",
            source_id=source.id,
            project_id=project_id,
            title="API 测试文档",
            parsed_text=parsed_text,
            metadata_json='{"description": "测试"}',
        )
        db.add(pd)
        db.commit()
        return source.id, pd.id
    finally:
        db.close()


def _seed_candidate_card(
    TestingSessionLocal, project_id: str, source_id: str, pd_id: str,
    card_id: str = "card_api_001",
    summary: str = "测试证据卡片。",
    evidence_type: str = "BACKGROUND",
) -> str:
    """直接操作数据库构造一张 CANDIDATE 证据卡片。"""
    db = TestingSessionLocal()
    try:
        card = EvidenceCard(
            id=card_id,
            project_id=project_id,
            source_id=source_id,
            parsed_document_id=pd_id,
            summary=summary,
            evidence_type=evidence_type,
            locator="第1段",
            source_quote=summary[:100],
            status=EvidenceCardStatus.CANDIDATE.value,
            candidate_source=CandidateSource.LOCAL_RULE.value,
        )
        db.add(card)
        db.commit()
        return card.id
    finally:
        db.close()


# --- POST /sources/{source_id}/evidence/generate ---


class TestGenerateEvidenceApi:
    """触发生成证据卡片 API 测试。"""

    def test_generate_creates_job(self, client):
        """对已解析来源触发生成，返回 job_id。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        source_id, _ = _seed_parsed_source_in_db(
            sources_router.SessionLocal, project_id
        )

        response = client.post(
            f"/api/projects/{project_id}/sources/{source_id}/evidence/generate"
        )
        assert response.status_code == 201
        assert response.json()["job_id"]

    def test_rejects_when_source_not_parsed(self, client):
        """来源未解析时返回 EVIDENCE_SOURCE_NOT_PARSED（400）。"""
        project_id = _create_confirmed_project(client)
        # 创建一个 PENDING 来源
        resp = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        source_id = resp.json()["id"]

        response = client.post(
            f"/api/projects/{project_id}/sources/{source_id}/evidence/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EVIDENCE_SOURCE_NOT_PARSED"

    def test_returns_404_when_source_missing(self, client):
        """来源不存在时返回 SOURCE_NOT_FOUND。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/src_missing/evidence/generate"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"


# --- GET /evidence ---


class TestListEvidenceApi:
    """证据卡片列表 API 测试。"""

    def test_lists_evidence_cards(self, client):
        """GET /evidence 返回 EvidenceCardListResponse。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        source_id, pd_id = _seed_parsed_source_in_db(
            sources_router.SessionLocal, project_id
        )
        _seed_candidate_card(
            sources_router.SessionLocal, project_id, source_id, pd_id,
            card_id="card_list_1", summary="卡片一", evidence_type="BACKGROUND",
        )
        _seed_candidate_card(
            sources_router.SessionLocal, project_id, source_id, pd_id,
            card_id="card_list_2", summary="卡片二", evidence_type="METHOD",
        )

        response = client.get(f"/api/projects/{project_id}/evidence")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2

    def test_filters_by_status(self, client):
        """status 查询参数过滤。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        source_id, pd_id = _seed_parsed_source_in_db(
            sources_router.SessionLocal, project_id
        )
        _seed_candidate_card(
            sources_router.SessionLocal, project_id, source_id, pd_id,
            card_id="card_filter_cand", summary="候选",
        )
        # 再插入一张 CONFIRMED 卡片
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        db = SessionLocal()
        try:
            card = EvidenceCard(
                id="card_filter_conf",
                project_id=project_id,
                source_id=source_id,
                parsed_document_id=pd_id,
                summary="已确认卡片",
                evidence_type="METHOD",
                locator="第2段",
                source_quote="已确认",
                status=EvidenceCardStatus.CONFIRMED.value,
                candidate_source=CandidateSource.LOCAL_RULE.value,
            )
            db.add(card)
            db.commit()
        finally:
            db.close()

        cand_resp = client.get(
            f"/api/projects/{project_id}/evidence",
            params={"status": "CANDIDATE"},
        )
        assert cand_resp.status_code == 200
        cand_items = cand_resp.json()["items"]
        assert len(cand_items) == 1
        assert cand_items[0]["status"] == "CANDIDATE"

        conf_resp = client.get(
            f"/api/projects/{project_id}/evidence",
            params={"status": "CONFIRMED"},
        )
        assert conf_resp.status_code == 200
        conf_items = conf_resp.json()["items"]
        assert len(conf_items) == 1
        assert conf_items[0]["status"] == "CONFIRMED"

    def test_filters_by_source_id(self, client):
        """source_id 查询参数过滤。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(
            SessionLocal, project_id
        )
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_src_1", summary="来源1卡片",
        )

        # 创建第二个来源（但无卡片）
        db = SessionLocal()
        try:
            src2 = Source(
                id="src_api_2",
                project_id=project_id,
                source_kind=SourceKind.URL.value,
                title="来源2",
                url="https://example.com/b.html",
                status=SourceStatus.PARSED.value,
            )
            db.add(src2)
            pd2 = ParsedDocument(
                id="pd_api_2",
                source_id=src2.id,
                project_id=project_id,
                title="文档2",
                parsed_text="另一个文档内容。",
            )
            db.add(pd2)
            db.commit()
            src2_id = src2.id
        finally:
            db.close()

        # 查询指定 source_id
        resp = client.get(
            f"/api/projects/{project_id}/evidence",
            params={"source_id": src2_id},
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.get("/api/projects/proj_missing/evidence")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- PUT /evidence/{card_id} ---


class TestUpdateEvidenceApi:
    """更新证据卡片 API 测试。"""

    def test_updates_card_returns_200(self, client):
        """PUT /evidence/{card_id} 更新 CANDIDATE 卡片。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_upd_1", summary="待更新",
        )

        response = client.put(
            f"/api/projects/{project_id}/evidence/card_upd_1",
            json={
                "summary": "更新后摘要",
                "evidence_type": "METHOD",
                "locator": "第3段",
                "source_quote": "摘录",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "更新后摘要"
        assert data["evidence_type"] == "METHOD"
        assert data["locator"] == "第3段"

    def test_returns_404_when_card_missing(self, client):
        """卡片不存在时返回 EVIDENCE_CARD_NOT_FOUND。"""
        project_id = _create_confirmed_project(client)
        response = client.put(
            f"/api/projects/{project_id}/evidence/card_missing",
            json={
                "summary": "x",
                "evidence_type": "BACKGROUND",
                "locator": "第1段",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EVIDENCE_CARD_NOT_FOUND"


# --- POST /evidence/{card_id}/confirm ---


class TestConfirmEvidenceApi:
    """确认证据卡片 API 测试。"""

    def test_confirms_candidate_returns_200(self, client):
        """POST /evidence/{card_id}/confirm 确认 CANDIDATE 卡片。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_conf_1", summary="待确认",
        )

        response = client.post(
            f"/api/projects/{project_id}/evidence/card_conf_1/confirm"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"

    def test_returns_400_when_not_candidate(self, client):
        """非 CANDIDATE 卡片确认时返回 EVIDENCE_CARD_NOT_CONFIRMABLE。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        # 直接插入 CONFIRMED 卡片
        db = SessionLocal()
        try:
            card = EvidenceCard(
                id="card_already_conf",
                project_id=project_id,
                source_id=source_id,
                parsed_document_id=pd_id,
                summary="已确认",
                evidence_type="METHOD",
                locator="第1段",
                source_quote="x",
                status=EvidenceCardStatus.CONFIRMED.value,
                candidate_source=CandidateSource.LOCAL_RULE.value,
            )
            db.add(card)
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/evidence/card_already_conf/confirm"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EVIDENCE_CARD_NOT_CONFIRMABLE"


# --- POST /evidence/{card_id}/reject ---


class TestRejectEvidenceApi:
    """拒绝证据卡片 API 测试。"""

    def test_rejects_candidate_returns_200(self, client):
        """POST /evidence/{card_id}/reject 拒绝 CANDIDATE 卡片。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_rej_1", summary="待拒绝",
        )

        response = client.post(
            f"/api/projects/{project_id}/evidence/card_rej_1/reject"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"

    def test_returns_404_when_card_missing(self, client):
        """卡片不存在时返回 EVIDENCE_CARD_NOT_FOUND。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/evidence/card_missing/reject"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EVIDENCE_CARD_NOT_FOUND"


# --- POST /evidence/complete ---


class TestCompleteEvidenceApi:
    """完成证据确认 API 测试。"""

    def test_completes_when_confirmed_card_exists(self, client):
        """有 CONFIRMED 卡片时完成证据确认。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_complete_1", summary="待确认完成",
        )
        # 确认它
        client.post(
            f"/api/projects/{project_id}/evidence/card_complete_1/confirm"
        )

        response = client.post(f"/api/projects/{project_id}/evidence/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "EVIDENCE_CONFIRMED"

    def test_rejects_when_no_confirmed_card(self, client):
        """无 CONFIRMED 卡片时返回 PROJECT_NO_CONFIRMED_EVIDENCE。"""
        project_id = _create_confirmed_project(client)
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        source_id, pd_id = _seed_parsed_source_in_db(SessionLocal, project_id)
        _seed_candidate_card(
            SessionLocal, project_id, source_id, pd_id,
            card_id="card_only_cand", summary="仅候选",
        )

        response = client.post(f"/api/projects/{project_id}/evidence/complete")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_CONFIRMED_EVIDENCE"
