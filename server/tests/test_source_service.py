"""来源落盘、项目归属和状态推进测试。"""

import socket
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.infrastructure.sources.http_fetcher import FetchResult
from app.modules.projects import service as project_service
from app.modules.sources import service as source_service
from app.modules.sources.contracts import SourceCreateRequest


def _fetched_html() -> FetchResult:
    return FetchResult(
        content=b"<html><body><p>public evidence</p></body></html>",
        content_type="text/html",
        final_url="https://example.com/public",
        status="FETCHED",
        error_code=None,
        error_message=None,
    )


def _blocked_fetch() -> FetchResult:
    return FetchResult(
        content=b"",
        content_type="",
        final_url="https://example.com/private",
        status="BLOCKED",
        error_code="SOURCE_URL_BLOCKED_PRIVATE_NETWORK",
        error_message=None,
    )


def _public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_url_source_persists_original_content(
    db, project_with_plan, monkeypatch, tmp_path
):
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    source = source_service.add_url_source(
        db,
        project_with_plan,
        SourceCreateRequest(url="https://example.com/public", title="公开页"),
        fetcher=lambda _: _fetched_html(),
    )

    saved_path = Path(source.original_file_path or "")
    assert source.collection_status == "FETCHED"
    assert saved_path.read_bytes() == _fetched_html().content
    assert saved_path.is_relative_to(tmp_path / "projects")


def test_add_file_source_requires_existing_project(db):
    with pytest.raises(AppError) as exc:
        source_service.add_file_source(
            db, "proj_missing", "x", "x.txt", b"text", "text/plain"
        )
    assert exc.value.code == "PROJECT_NOT_FOUND"


def test_first_fetched_source_advances_project_to_sources_collected(
    db, project_with_plan
):
    source_service.add_file_source(
        db,
        project_with_plan,
        "资料",
        "source.txt",
        b"evidence",
        "text/plain",
    )
    project = project_service.get_project(db, project_with_plan)
    assert project.status == "SOURCES_COLLECTED"


def test_blocked_url_does_not_advance_project(db, project_with_plan, monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    source = source_service.add_url_source(
        db,
        project_with_plan,
        SourceCreateRequest(url="https://example.com/private", title="受限页"),
        fetcher=lambda _: _blocked_fetch(),
    )
    assert source.collection_status == "BLOCKED"
    assert source.original_file_path is None
