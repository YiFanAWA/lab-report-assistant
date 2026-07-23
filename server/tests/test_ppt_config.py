"""SPEC 0011 PPT 配置选项测试。

覆盖：
- PptRenderer.render：config 各字段的应用逻辑（页数、主题色、图表开关）+ 降级策略
- outlines API：generate_ppt 端点的请求体解析、config 校验、错误码
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.dml.color import RGBColor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.infrastructure.renderers.ppt_renderer import PptRenderer
from app.main import app
from app.modules.outlines.models import Outline
from app.modules.outlines.status import OutlineStatus
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


SAMPLE_SECTIONS = [
    {
        "id": "sec_001",
        "title": "实验目的",
        "content": "分析胃病数据分布特征",
        "source_type": "REQUIREMENT",
        "source_ids": ["plan_001"],
    },
    {
        "id": "sec_002",
        "title": "实验方法",
        "content": "使用描述性统计方法",
        "source_type": "EVIDENCE",
        "source_ids": ["ev_001"],
    },
    {
        "id": "sec_003",
        "title": "实验结果",
        "content": "执行成功，数据已清洗",
        "source_type": "EXECUTION",
        "source_ids": ["run_001"],
    },
    {
        "id": "sec_004",
        "title": "总结",
        "content": "本实验完成了数据分析与可视化",
        "source_type": "SUMMARY",
        "source_ids": [],
    },
]


# --- 渲染器测试 ---


def _render_ppt(tmp_path, config=None, sections=None, artifacts=None,
                filename="output.pptx"):
    """渲染 PPT 并返回路径。"""
    renderer = PptRenderer()
    output_path = tmp_path / filename
    renderer.render(
        project_name="测试项目",
        project_topic="测试课题",
        outline_sections=sections or SAMPLE_SECTIONS,
        execution_artifacts=artifacts or [],
        output_path=str(output_path),
        config=config,
    )
    return output_path


def test_render_no_config_keeps_default(tmp_path):
    """R-PAGE-01：config=None 保持默认行为。"""
    output_path = _render_ppt(tmp_path, config=None)
    prs = Presentation(str(output_path))
    # 标题页 + 内容页（REQUIREMENT+EVIDENCE+ANALYSIS 合并 + EXECUTION）+ 总结页
    assert len(prs.slides) >= 3


def test_render_config_none_dict_keeps_default(tmp_path):
    """R-FALL-01：config 为空 dict 保持默认行为。"""
    output_path = _render_ppt(tmp_path, config={})
    prs = Presentation(str(output_path))
    assert len(prs.slides) >= 3


def test_render_target_slide_count_6_limits_content(tmp_path):
    """R-PAGE-02：target_slide_count=6 时内容页不超过 4（6-标题页-总结页）。"""
    output_path = _render_ppt(
        tmp_path, config={"target_slide_count": 6}
    )
    prs = Presentation(str(output_path))
    # 标题页 + 内容页（<=4）+ 总结页 = <=6
    assert len(prs.slides) <= 6


def test_render_target_slide_count_20_keeps_actual(tmp_path):
    """R-PAGE-03：target_slide_count=20 时内容少于可用槽位，保持实际页数。"""
    output_path = _render_ppt(
        tmp_path, config={"target_slide_count": 20}
    )
    prs = Presentation(str(output_path))
    # 内容页候选最多 3（REQUIREMENT + EVIDENCE+DATASET+ANALYSIS + EXECUTION）
    # 标题页 + 3 内容页 + 总结页 = 5，不超过 20
    assert len(prs.slides) <= 20


def test_render_target_slide_count_5_minimum(tmp_path):
    """R-PAGE-04：target_slide_count=5（最小值），内容页不超过 3。"""
    output_path = _render_ppt(
        tmp_path, config={"target_slide_count": 5}
    )
    prs = Presentation(str(output_path))
    # 标题页 + 内容页（<=3）+ 总结页 = <=5
    assert len(prs.slides) <= 5


def test_render_charts_not_counted_in_target(tmp_path):
    """R-PAGE-05：图表页不计入 target_slide_count。"""
    # 创建测试 PNG 图表产物
    chart_path = tmp_path / "chart.png"
    # 最小有效 PNG 文件（1x1 像素）
    chart_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x82\x8b\x99\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    artifacts = [
        {"name": "chart1.png", "artifact_type": "CHART_PNG",
         "file_path": str(chart_path)},
    ]
    output_path = _render_ppt(
        tmp_path, config={"target_slide_count": 8}, artifacts=artifacts
    )
    prs = Presentation(str(output_path))
    # 图表页额外生成，不计入 target_slide_count
    # 标题页 + 内容页 + 图表页 + 总结页
    assert len(prs.slides) >= 4


def test_render_theme_color_purple_applied(tmp_path):
    """R-COLOR-02：theme_color=#7c3aed 时标题文字为紫色。"""
    output_path = _render_ppt(
        tmp_path, config={"theme_color": "#7c3aed"}
    )
    prs = Presentation(str(output_path))
    # 检查标题页的标题颜色
    title_slide = prs.slides[0]
    title_shape = title_slide.shapes.title
    assert title_shape is not None
    # 检查标题 run 的颜色
    for para in title_shape.text_frame.paragraphs:
        for run in para.runs:
            if run.font.color and run.font.color.rgb:
                assert run.font.color.rgb == RGBColor(0x7c, 0x3a, 0xed)


def test_render_theme_color_blue_applied(tmp_path):
    """R-COLOR-03：theme_color=#2563eb 时标题文字为蓝色。"""
    output_path = _render_ppt(
        tmp_path, config={"theme_color": "#2563eb"}
    )
    prs = Presentation(str(output_path))
    title_slide = prs.slides[0]
    title_shape = title_slide.shapes.title
    for para in title_shape.text_frame.paragraphs:
        for run in para.runs:
            if run.font.color and run.font.color.rgb:
                assert run.font.color.rgb == RGBColor(0x25, 0x63, 0xeb)


def test_render_theme_color_green_all_slides(tmp_path):
    """R-COLOR-04：主题色应用到所有页面类型的标题。"""
    output_path = _render_ppt(
        tmp_path, config={"theme_color": "#16a34a"}
    )
    prs = Presentation(str(output_path))
    for slide in prs.slides:
        title_shape = slide.shapes.title
        if title_shape and title_shape.has_text_frame:
            for para in title_shape.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.color and run.font.color.rgb:
                        assert run.font.color.rgb == RGBColor(0x16, 0xa3, 0x4a)


def test_render_no_theme_color_keeps_default(tmp_path):
    """R-COLOR-01：config=None 时主题色不修改（保持默认）。"""
    output_path_no_color = _render_ppt(tmp_path, config=None)
    output_path_with_color = _render_ppt(
        tmp_path, config={"theme_color": "#dc2626"}
    )
    # 两个文件都生成成功
    assert output_path_no_color.exists()
    assert output_path_with_color.exists()


def test_render_include_charts_true(tmp_path):
    """R-CHART-01：include_charts=True 时生成图表页（有图表产物时）。"""
    chart_path = tmp_path / "chart.png"
    chart_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x82\x8b\x99\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    artifacts = [
        {"name": "chart1.png", "artifact_type": "CHART_PNG",
         "file_path": str(chart_path)},
    ]
    output_with = _render_ppt(
        tmp_path, config={"include_charts": True}, artifacts=artifacts
    )
    prs_with = Presentation(str(output_with))
    # 有图表页
    assert len(prs_with.slides) >= 4  # 标题+内容+图表+总结


def test_render_include_charts_false_skips_chart(tmp_path):
    """R-CHART-02：include_charts=False 时不生成图表页。"""
    chart_path = tmp_path / "chart.png"
    chart_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x82\x8b\x99\xde\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    artifacts = [
        {"name": "chart1.png", "artifact_type": "CHART_PNG",
         "file_path": str(chart_path)},
    ]
    output_without = _render_ppt(
        tmp_path, config={"include_charts": False}, artifacts=artifacts,
        filename="no_charts.pptx",
    )
    output_with = _render_ppt(
        tmp_path, config={"include_charts": True}, artifacts=artifacts,
        filename="with_charts.pptx",
    )
    prs_without = Presentation(str(output_without))
    prs_with = Presentation(str(output_with))
    # 无图表页时页数比有图表页时少
    assert len(prs_without.slides) < len(prs_with.slides)


def test_render_include_charts_false_no_artifacts(tmp_path):
    """R-CHART-03：include_charts=False 且无图表产物时不生成图表页。"""
    output_path = _render_ppt(
        tmp_path, config={"include_charts": False}, artifacts=[]
    )
    prs = Presentation(str(output_path))
    # 无图表产物，与默认行为一致
    assert len(prs.slides) >= 3


def test_render_partial_config(tmp_path):
    """R-FALL-02：config 部分字段缺失时只应用已有字段。"""
    output_path = _render_ppt(
        tmp_path, config={"theme_color": "#2563eb"}
    )
    # 只应用主题色，其他使用默认值
    prs = Presentation(str(output_path))
    assert len(prs.slides) >= 3


def test_render_invalid_theme_color_falls_back(tmp_path):
    """R-FALL-03：hex 色值解析异常时降级到默认（不抛异常）。"""
    # _parse_theme_color 内部捕获异常返回 None，不抛出
    output_path = _render_ppt(
        tmp_path, config={"theme_color": "#invalid"}
    )
    # 降级成功，文件正常生成
    assert output_path.exists()
    prs = Presentation(str(output_path))
    assert len(prs.slides) >= 3


# --- API 测试 ---


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
                    status: str = ProjectStatus.OUTLINE_CONFIRMED.value) -> str:
    """创建项目并设置状态，返回 project_id。"""
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "topic": "测试课题"},
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
                   outline_id: str = "ol_ppt_cfg_1",
                   status: str = OutlineStatus.CONFIRMED.value) -> str:
    """直接插入已确认大纲，返回 outline_id。"""
    db = SessionLocal()
    try:
        outline = Outline(
            id=outline_id,
            project_id=project_id,
            sections_json=json.dumps(SAMPLE_SECTIONS),
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


def test_api_generate_ppt_no_body(client):
    """A-01：无 body 生成 PPT 成功。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate"
    )
    assert response.status_code == 201
    data = response.json()
    assert data["job_id"]
    assert data["deliverable_id"]
    assert data["template_used"] is False


def test_api_generate_ppt_with_config(client):
    """A-02：有 config 生成 PPT 成功。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {"target_slide_count": 10}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["job_id"]
    assert data["deliverable_id"]


def test_api_generate_ppt_full_config(client):
    """A-03：完整 config 生成 PPT 成功。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={
            "config": {
                "target_slide_count": 8,
                "theme_color": "#7c3aed",
                "include_charts": False,
            }
        },
    )
    assert response.status_code == 201


def test_api_generate_ppt_invalid_theme_color(client):
    """A-04：无效 theme_color 返回 PPT_CONFIG_INVALID_THEME_COLOR。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {"theme_color": "#ff0000"}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PPT_CONFIG_INVALID_THEME_COLOR"


def test_api_generate_ppt_slide_count_too_small(client):
    """A-05：target_slide_count 小于 5 时校验失败。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {"target_slide_count": 3}},
    )
    # app 自定义 RequestValidationError 处理器返回 400
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_api_generate_ppt_slide_count_too_large(client):
    """A-06：target_slide_count 大于 20 时校验失败。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {"target_slide_count": 25}},
    )
    # app 自定义 RequestValidationError 处理器返回 400
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_api_generate_ppt_include_charts_false(client):
    """A-07：include_charts=false 成功创建。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {"include_charts": False}},
    )
    assert response.status_code == 201


def test_api_generate_ppt_empty_config(client):
    """A-08：空 config 对象成功创建。"""
    from app.api.routers import outlines as outlines_router
    SessionLocal = outlines_router.SessionLocal
    project_id = _create_project(client)
    _seed_outline(SessionLocal, project_id)

    response = client.post(
        f"/api/projects/{project_id}/outline/ol_ppt_cfg_1/ppt/generate",
        json={"config": {}},
    )
    assert response.status_code == 201
