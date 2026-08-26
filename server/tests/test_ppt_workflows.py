"""SPEC 0032 PPT Master 与上海交大模板适配测试。"""

import pytest
from pydantic import ValidationError

from app.infrastructure.renderers.ppt_renderer import PptRenderer
from app.modules.outlines.ppt_workflows import (
    PPT_WORKFLOW_IDS,
    PPT_WORKFLOWS,
    resolve_ppt_workflow,
)
from app.modules.outlines.contracts import PptConfig


def test_workflow_registry_has_three_stable_modes():
    assert PPT_WORKFLOW_IDS == {
        "native_editable",
        "academic",
        "sjtu_academic",
    }
    assert set(PPT_WORKFLOWS) == set(PPT_WORKFLOW_IDS)
    assert all(spec.source for spec in PPT_WORKFLOWS.values())


def test_missing_workflow_preserves_native_editable_default():
    assert resolve_ppt_workflow(None).workflow_id == "native_editable"
    assert PptConfig().ppt_workflow is None


@pytest.mark.parametrize("workflow_id", sorted(PPT_WORKFLOW_IDS))
def test_valid_workflow_is_accepted(workflow_id: str):
    assert PptConfig(ppt_workflow=workflow_id).ppt_workflow == workflow_id


def test_invalid_workflow_is_rejected():
    with pytest.raises(ValidationError):
        PptConfig(ppt_workflow="campus_magic")


def test_workflow_theme_precedence():
    renderer = PptRenderer()

    # 显式主题仍然最高优先级。
    assert (
        renderer._resolve_theme_preset(
            "MONOCHROME_INK", "#2563eb", "sjtu_academic"
        )
        == "MONOCHROME_INK"
    )
    assert (
        renderer._resolve_theme_preset(None, "#2563eb", "academic")
        == "PACIFIC_DEEP"
    )
    assert (
        renderer._resolve_theme_preset(None, "#2563eb", "sjtu_academic")
        == "CORAL_ENERGY"
    )


def test_native_workflow_keeps_theme_color_mapping():
    renderer = PptRenderer()
    assert (
        renderer._resolve_theme_preset(None, "#2563eb", "native_editable")
        == renderer._map_theme("#2563eb")
    )
