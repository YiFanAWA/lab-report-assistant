# SPEC 0003 第一阶段修复实施计划

> **供 agent 执行：** 必须使用 superpowers:executing-plans 按任务逐步执行；每个生产代码改动都先运行对应失败测试。步骤使用复选框跟踪。

**目标：** 把当前未闭合的公开资料与证据实现修复为可从已确认任务单，经 URL/文件落盘、解析、候选生成、人工确认，最终刷新后仍可读取的真实闭环。

**架构：** 来源、解析文档、证据状态和项目阶段推进只由 server/app/modules/sources/ 拥有。API、前端、URL 获取器、文档解析器和 Provider 只通过显式合同接线；Skill、Orchestrator、skill_runs 与 feasibility 不进入本计划完成条件。

**技术栈：** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy、Alembic、SQLite、pytest、pypdf、React、TypeScript、Vite、TanStack Query。

---

## 执行边界

- 本计划只执行 SPEC 0003 第一阶段。
- 不删除、不重写、不提交当前用户新增的 Skill、Orchestrator、skill_runs 和 feasibility 文件。
- Alembic 运行到当前 head 时可以经过 0004，但不得把 0004 迁移成功表述为 Skill 验收通过。
- 本仓库不按任务逐个提交。所有任务完成、验收记录回写并由项目负责人确认收口后，才按 AGENTS.md 精确 stage、commit、push。
- 若需要修改 AGENTS.md，只更新已经由项目负责人确认的阶段事实，不改变其他宪法规则。修改前必须说明行为影响和压力测试。

## Owner 与禁止归属

| 概念 | 唯一 owner | 禁止成为 owner 的层 |
| --- | --- | --- |
| 来源登记、状态、项目归属 | server/app/modules/sources/service.py | API、前端、Skill |
| URL 安全和单次获取 | server/app/infrastructure/sources/ | Service、API、前端 |
| 文件安全落盘 | server/app/infrastructure/sources/storage.py | API、Skill |
| 解析文本和位置映射 | server/app/infrastructure/documents/ | API、Provider |
| 证据候选合同和真实性校验 | server/app/modules/sources/ | Provider、前端 |
| 项目阶段推进 | server/app/modules/sources/service.py，消费 ProjectStatus | API、Skill、Provider |
| HTTP 映射和结构化错误 | server/app/api/routers/sources.py、server/app/main.py | Service 中的 HTTPException |
| 页面草稿和操作入口 | apps/web/src/features/sources/、SourceEvidenceWorkspaceView.tsx | 前端业务状态机 |

## 文件结构

新增文件：

- server/app/infrastructure/sources/storage.py：把来源字节写入已存在项目的受控工作区。
- server/tests/test_source_api.py：来源与证据 API 合同、项目隔离和状态推进测试。
- server/tests/test_source_security.py：DNS、重定向、大小和协议安全测试。
- server/tests/test_document_readers.py：HTML、PDF、TXT 的真实解析和位置映射测试。
- server/tests/test_evidence_service.py：证据摘录、位置、状态转换和刷新读取测试。
- apps/web/src/features/sources/types.ts：来源、解析文档、证据和结构化错误类型。
- apps/web/src/features/sources/api.ts：来源与证据 HTTP 客户端。
- apps/web/src/features/sources/hooks.ts：TanStack Query 查询和 mutation。
- apps/web/src/routes/SourceEvidenceWorkspaceView.tsx：公开资料与证据工作台。

修改文件：

- AGENTS.md、dev-docs/README.md、dev-docs/acceptance.md、dev-docs/implementation-plan.md、SPEC 0003：同步真实阶段和验收证据。
- server/pyproject.toml、server/.env.example、server/app/core/config.py：启用 pypdf 和来源上界配置。
- server/app/modules/sources/contracts.py、models.py、service.py、status.py：收敛合同、owner 逻辑和状态推进。
- server/app/infrastructure/sources/url_policy.py、http_fetcher.py：完整 URL 安全链。
- server/app/infrastructure/documents/html_reader.py、pdf_reader.py、text_reader.py：输出可定位块。
- server/app/modules/llm/evidence_gateway.py、local_rule_evidence_provider.py：返回可校验候选。
- server/app/api/routers/sources.py、server/app/main.py：薄 HTTP 接线和统一错误。
- server/tests/test_source_service.py：移除真实网络调用，保留确定性服务测试。
- apps/web/src/app/App.tsx、apps/web/src/routes/ProjectDetailView.tsx、apps/web/src/routes/RequirementWorkspaceView.tsx：增加入口并展示新状态。

## Task 0：恢复可复核的后端测试环境

**Files:**

- Preserve: server/.venv/ 当前损坏环境，仅移动到 server/.tmp/ 下作为现场证据
- Modify: server/pyproject.toml

- [x] **Step 1：记录当前失败证据**

Run:

~~~powershell
server/.venv/Scripts/python.exe --version
~~~

Expected: FAIL，错误包含 did not find executable at '/usr/bin\python.exe'。

- [x] **Step 2：确认移动边界并隔离损坏环境**

先确认两个绝对路径都位于仓库的 server 目录内：

~~~powershell
$source = (Resolve-Path 'server/.venv').Path
$targetRoot = (Resolve-Path 'server/.tmp').Path
$source
$targetRoot
~~~

确认后将损坏环境移动到 server/.tmp/venv-broken-20260618；不得删除用户文件。

Run:

~~~powershell
$target = Join-Path $targetRoot 'venv-broken-20260618'
if (Test-Path -LiteralPath $target) {
    throw "隔离目标已存在，停止并人工确认：$target"
}
Move-Item -LiteralPath $source -Destination $target
~~~

- [x] **Step 3：使用当前可用 CPython 创建 Windows 虚拟环境**

当前桌面运行时入口：

~~~powershell
& 'C:\Users\爹\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv server/.venv
server/.venv/Scripts/python.exe --version
~~~

Expected: Python 3.12.x，退出码 0。

- [x] **Step 4：先把 pypdf 写入项目依赖真源**

在 server/pyproject.toml dependencies 中加入：

~~~toml
  "pypdf>=6.13.2,<7.0.0",
~~~

同时保留现有 FastAPI、Pydantic、SQLAlchemy、Alembic、python-docx、python-multipart 依赖。

- [x] **Step 5：安装项目依赖**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pip install -e "server[dev]"
~~~

如果仅因沙箱网络或权限失败，按工具权限流程请求宿主权限后原命令重试，不得换未记录的依赖来源。

- [x] **Step 6：建立当前测试基线**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest
~~~

Expected: 先记录真实结果。既有失败不得直接修补；逐项映射到后续任务。

## Task 1：纠正阶段真源，锁定“先 SPEC 0003、后 Skill”

**Files:**

- Modify: AGENTS.md
- Modify: dev-docs/README.md
- Modify: dev-docs/acceptance.md
- Modify: dev-docs/implementation-plan.md
- Modify: dev-docs/specs/0003-public-sources-and-evidence-workflow.md

- [x] **Step 1：修改 AGENTS.md 前说明影响**

向项目负责人说明：

- 现有“SPEC 0003 等待确认”已经落后于 2026-06-18 的两阶段确认；
- 修改只允许第一阶段 SPEC 0003 修复，仍禁止 Skill 扩展和后续切片；
- 压力测试是后续 agent 试图修 feasibility、Skill 审计或数据集时，AGENTS.md 必须要求其停止。

- [x] **Step 2：更新阶段事实**

AGENTS.md 当前阶段改为：

~~~markdown
- SPEC 0003 已采用“两阶段修复”主线，当前只批准第一阶段公开资料与证据闭环修复。
- 第一阶段收口前，不得扩展 Skill、Orchestrator、feasibility、数据集、Python 执行或交付物。
~~~

README 当前状态改为：

~~~markdown
- 状态：SPEC 0003 第一阶段修复设计和实施计划已确认，现有实现尚未验收；Skill 轻量层不计入本阶段完成范围。
- 下一阶段入口：完成 SPEC 0003 当前测试、迁移、API、UI 与浏览器验收并由项目负责人确认收口。
~~~

- [x] **Step 3：撤回无法成立的验收表述**

在 acceptance.md 中把“SPEC 0003 沙箱验收通过”和“Skill 层测试通过”改为历史记录：

~~~markdown
| 2026-06-17 | SPEC 0003 早期实现记录 | 曾记录 37 tests 和迁移通过；2026-06-18 复核发现 URL 主链路、SSRF、API 合同、状态推进、UI 和当前 Python 环境未闭合 | 已撤回完成结论 |
| 2026-06-17 | Skill 层早期记录 | 41 个测试函数中只有 4 个浅层 Skill 测试，未覆盖正式注册、run_skill、审计和 Orchestrator 执行闸 | 未验收 |
~~~

implementation-plan.md 中任务 5 的完成勾选全部恢复为未完成，只在真实验收后重新勾选。

- [x] **Step 4：运行漂移扫描**

Run:

~~~powershell
rg -n -S "SPEC 0003 已实现|沙箱验收通过|Skill 轻量层.*测试通过|41 passed" AGENTS.md dev-docs
git -c safe.directory='C:/Users/爹/Documents/VibeCoding' diff --check -- AGENTS.md dev-docs
~~~

Expected: 第一条无超前完成声明；第二条无新增格式错误。

## Task 2：先用失败测试定义来源落盘、项目归属和状态推进

**Files:**

- Modify: server/tests/test_source_service.py
- Create: server/app/infrastructure/sources/storage.py
- Modify: server/app/modules/sources/service.py

- [x] **Step 1：把真实网络测试改成确定性 FetchResult**

在 test_source_service.py 中新增：

~~~python
from app.infrastructure.sources.http_fetcher import FetchResult


def _fetched_html() -> FetchResult:
    return FetchResult(
        content=b"<html><body><p>public evidence</p></body></html>",
        content_type="text/html",
        final_url="https://example.com/public",
        status="FETCHED",
        error_code=None,
        error_message=None,
    )
~~~

删除对 https://www.example.com 的真实网络调用，改为传入返回上述结果的 fake fetcher。

- [x] **Step 2：写 URL 原文落盘失败测试**

~~~python
def test_url_source_persists_original_content(
    db, project_with_plan, monkeypatch, tmp_path
):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))

    source = src_svc.add_url_source(
        db,
        project_with_plan,
        SourceCreateRequest(url="https://example.com/public", title="公开页"),
        fetcher=lambda _: _fetched_html(),
    )

    assert source.collection_status == "FETCHED"
    assert source.original_file_path is not None
    assert Path(source.original_file_path).read_bytes() == _fetched_html().content
    assert Path(source.original_file_path).is_relative_to(tmp_path / "projects")
~~~

- [x] **Step 3：写项目归属和 SOURCES_COLLECTED 失败测试**

~~~python
def test_add_file_source_requires_existing_project(db, tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    with pytest.raises(AppError) as exc:
        src_svc.add_file_source(
            db, "proj_missing", "x", "x.txt", b"text", "text/plain"
        )
    assert exc.value.code == "PROJECT_NOT_FOUND"


def test_first_fetched_source_advances_project_to_sources_collected(
    db, project_with_plan, tmp_path, monkeypatch
):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    src_svc.add_file_source(
        db, project_with_plan, "资料", "source.txt", b"evidence", "text/plain"
    )
    project = proj_svc.get_project(db, project_with_plan)
    assert project.status == "SOURCES_COLLECTED"
~~~

- [x] **Step 4：运行 RED**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_service.py -v
~~~

Expected: URL 路径为空、缺失项目未拒绝、项目状态未推进，三个测试按预期失败。

- [x] **Step 5：实现唯一落盘 helper**

storage.py 的公开接口固定为：

~~~python
from pathlib import Path
import re
import uuid


def save_source_bytes(
    workspace_root: str,
    original_name: str,
    content: bytes,
) -> Path:
    root = Path(workspace_root).resolve()
    source_dir = (root / "sources").resolve()
    source_dir.mkdir(parents=True, exist_ok=True)
    raw_name = original_name.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    safe_name = safe_name or "source.bin"
    destination = (source_dir / f"{uuid.uuid4().hex}_{safe_name}").resolve()
    if source_dir not in destination.parents:
        raise ValueError("source path escaped project workspace")
    destination.write_bytes(content)
    return destination
~~~

service.py 必须先调用 project_service.get_project(db, project_id)，使用 Project.workspace_root，而不是直接拼接用户传入的 project_id。成功获取或上传首个来源时，仅允许 REQUIREMENT_CONFIRMED 推进到 SOURCES_COLLECTED；已经进入后续状态时不得倒退。

- [x] **Step 6：运行 GREEN**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_service.py -v
~~~

Expected: 新增三个测试通过，测试不访问外网。

## Task 3：先用失败测试封住 DNS 和重定向 SSRF

**Files:**

- Create: server/tests/test_source_security.py
- Modify: server/app/infrastructure/sources/url_policy.py
- Modify: server/app/infrastructure/sources/http_fetcher.py
- Modify: server/app/core/config.py
- Modify: server/.env.example

- [x] **Step 1：定义安全策略 RED**

~~~python
import socket
from app.infrastructure.sources.url_policy import validate_public_url


def test_blocks_hostname_resolving_to_private_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    _, error = validate_public_url("https://internal.example/path")
    assert error == "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"


def test_rejects_credentials_before_fetch():
    _, error = validate_public_url("https://user:pass@example.com")
    assert error == "SOURCE_URL_UNSUPPORTED_SCHEME"
~~~

- [x] **Step 2：定义重定向和上界 RED**

在测试文件中定义确定性的传输替身：

~~~python
from dataclasses import dataclass


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    content_type: str = "text/html"


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = iter(responses)

    def request(self, url: str, timeout_seconds: int, max_bytes: int) -> FakeResponse:
        return next(self._responses)


def public_dns(*args, **kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ]


def four_redirect_transport() -> FakeTransport:
    return FakeTransport([
        FakeResponse(302, {"Location": "https://example.com/one"}, b""),
        FakeResponse(302, {"Location": "https://example.com/two"}, b""),
        FakeResponse(302, {"Location": "https://example.com/three"}, b""),
        FakeResponse(302, {"Location": "https://example.com/four"}, b""),
    ])
~~~

然后构造：

~~~python
def test_fetch_revalidates_redirect_target():
    transport = FakeTransport(
        [
            FakeResponse(302, {"Location": "http://127.0.0.1/admin"}, b""),
        ]
    )
    result = fetch_url(
        "https://example.com/start",
        transport=transport,
        resolver=public_dns,
    )
    assert result.status == "BLOCKED"
    assert result.error_code == "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"


def test_fetch_stops_after_three_redirects():
    result = fetch_url(
        "https://example.com/start",
        transport=four_redirect_transport(),
        resolver=public_dns,
    )
    assert result.status == "FAILED"
    assert result.error_code == "SOURCE_URL_TOO_MANY_REDIRECTS"
~~~

- [x] **Step 3：运行 RED**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_security.py -v
~~~

Expected: 当前域名直接放行，fetch_url 不支持 transport/resolver 注入，测试失败。

- [x] **Step 4：实现可注入的安全获取合同**

http_fetcher.py 使用不可变结果：

~~~python
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchResult:
    content: bytes
    content_type: str
    final_url: str
    status: str
    error_code: str | None
    error_message: str | None
~~~

validate_public_url 必须：

- 只允许 http/https；
- 拒绝认证信息；
- 用 socket.getaddrinfo 解析全部 A/AAAA；
- 任一地址不是 ip_address(address).is_global 即拒绝；
- DNS 失败返回 SOURCE_URL_FETCH_FAILED。

fetch_url 必须自己处理每次重定向，最多 3 次；每个 Location 规范化后重新调用同一策略；读取 source_fetch_max_bytes + 1 后拒绝超限；返回最终 URL 和结构化错误码，不抛出裸 urllib 异常。

config.py 新增：

~~~python
@property
def source_fetch_timeout_seconds(self) -> int:
    return int(os.getenv("SOURCE_FETCH_TIMEOUT_SECONDS", "15"))

@property
def source_fetch_max_bytes(self) -> int:
    return int(os.getenv("SOURCE_FETCH_MAX_BYTES", "20971520"))

@property
def source_upload_max_bytes(self) -> int:
    return int(os.getenv("SOURCE_UPLOAD_MAX_BYTES", "20971520"))

@property
def evidence_draft_provider(self) -> str:
    return os.getenv("EVIDENCE_DRAFT_PROVIDER", "local_rule")
~~~

.env.example 加入对应四个变量及默认值。

- [x] **Step 5：运行 GREEN**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_security.py -v
~~~

Expected: 协议、认证、DNS 私网、重定向私网、重定向次数、超时和大小测试全部通过。

## Task 4：让解析器输出真实位置，并持久化失败

**Files:**

- Create: server/tests/test_document_readers.py
- Modify: server/app/infrastructure/documents/html_reader.py
- Modify: server/app/infrastructure/documents/pdf_reader.py
- Modify: server/app/infrastructure/documents/text_reader.py
- Modify: server/app/modules/sources/service.py

- [x] **Step 1：写 HTML 和 TXT 位置 RED**

~~~python
def test_html_reader_excludes_script_and_tracks_paragraphs():
    raw = b"""
    <html><head><title>Public Page</title><script>secret()</script></head>
    <body><h1>Heading</h1><p>First evidence.</p><p>Second evidence.</p></body>
    </html>
    """
    text, location = extract_html(raw)
    assert "secret()" not in text
    assert location["title"] == "Public Page"
    assert [b["label"] for b in location["blocks"]] == [
        "标题 Heading", "段落 1", "段落 2"
    ]
    assert text[location["blocks"][1]["start"]:location["blocks"][1]["end"]] == "First evidence."


def test_txt_reader_tracks_encoding_and_single_block():
    text, location = extract_txt("胃病资料".encode("gb18030"))
    assert text == "胃病资料"
    assert location["encoding"] == "gb18030"
    assert location["blocks"][0]["label"] == "全文"
~~~

- [x] **Step 2：写真实 PDF 页码 RED**

在测试文件中保存固定的两页文本 PDF base64 常量，测试运行时只在内存中解码：

~~~python
PDF_WITH_TEXT_BASE64 = """JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDggMCBSIC9NZWRpYUJveCBbIDAgMCA1OTUuMjc1NiA4NDEuODg5OCBdIC9QYXJlbnQgNyAwIFIgL1Jlc291cmNlcyA8PAovRm9udCAxIDAgUiAvUHJvY1NldCBbIC9QREYgL1RleHQgL0ltYWdlQiAvSW1hZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9Db250ZW50cyA5IDAgUiAvTWVkaWFCb3ggWyAwIDAgNTk1LjI3NTYgODQxLjg4OTggXSAvUGFyZW50IDcgMCBSIC9SZXNvdXJjZXMgPDwKL0ZvbnQgMSAwIFIgL1Byb2NTZXQgWyAvUERGIC9UZXh0IC9JbWFnZUIgL0ltYWdlQyAvSW1hZ2VJIF0KPj4gL1JvdGF0ZSAwIC9UcmFucyA8PAoKPj4gCiAgL1R5cGUgL1BhZ2UKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL1BhZ2VNb2RlIC9Vc2VOb25lIC9QYWdlcyA3IDAgUiAvVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKNiAwIG9iago8PAovQXV0aG9yIChhbm9ueW1vdXMpIC9DcmVhdGlvbkRhdGUgKEQ6MjAyNjA2MTgxMTI1NTErMDgnMDAnKSAvQ3JlYXRvciAoYW5vbnltb3VzKSAvS2V5d29yZHMgKCkgL01vZERhdGUgKEQ6MjAyNjA2MTgxMTI1NTErMDgnMDAnKSAvUHJvZHVjZXIgKFJlcG9ydExhYiBQREYgTGlicmFyeSAtIFwob3BlbnNvdXJjZVwpKSAKICAvU3ViamVjdCAodW5zcGVjaWZpZWQpIC9UaXRsZSAodW50aXRsZWQpIC9UcmFwcGVkIC9GYWxzZQo+PgplbmRvYmoKNyAwIG9iago8PAovQ291bnQgMiAvS2lkcyBbIDMgMCBSIDQgMCBSIF0gL1R5cGUgL1BhZ2VzCj4+CmVuZG9iago4IDAgb2JqCjw8Ci9GaWx0ZXIgWyAvQVNDSUk4NURlY29kZSAvRmxhdGVEZWNvZGUgXSAvTGVuZ3RoIDExNwo+PgpzdHJlYW0KR2FwUWgwRT1GLDBVXEgzVFxwTllUXlFLaz90Yz5JUCw7VyNVMV4yM2loUEVNXz9DVzRLSVNpPCFXN2AjT0Jfc0tKQzo2YmJbY0ZXWkhTUV9dXTwlR0sjSTpcRiZBU185bmVaW0tiLGh1N0trQ0U2IXRNUX4+ZW5kc3RyZWFtCmVuZG9iago5IDAgb2JqCjw8Ci9GaWx0ZXIgWyAvQVNDSUk4NURlY29kZSAvRmxhdGVEZWNvZGUgXSAvTGVuZ3RoIDExNwo+PgpzdHJlYW0KR2FwUWgwRT1GLDBVXEgzVFxwTllUXlFLaz90Yz5JUCw7VyNVMV4yM2loUEVNXz9DVzRLSVNpPCFXN2AjT0JfcXVocGRnSnIiT2s3WkhTUV9dXTwlR0sjSTpcS3ApIlM5bmVaW0tiLGh1N0trQ0U2S2Y2Sn4+ZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgMTAKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDYxIDAwMDAwIG4gCjAwMDAwMDAwOTIgMDAwMDAgbiAKMDAwMDAwMDE5OSAwMDAwMCBuIAowMDAwMDAwNDAyIDAwMDAwIG4gCjAwMDAwMDA2MDUgMDAwMDAgbiAKMDAwMDAwMDY3MyAwMDAwMCBuIAowMDAwMDAwOTM0IDAwMDAwIG4gCjAwMDAwMDA5OTkgMDAwMDAgbiAKMDAwMDAwMTIwNiAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9JRCAKWzw4ZTMzNWNiZjUyNzM5MmQwN2M0NWU2ODg4NGQwNWRlOD48OGUzMzVjYmY1MjczOTJkMDdjNDVlNjg4ODRkMDVkZTg+XQolIFJlcG9ydExhYiBnZW5lcmF0ZWQgUERGIGRvY3VtZW50IC0tIGRpZ2VzdCAob3BlbnNvdXJjZSkKCi9JbmZvIDYgMCBSCi9Sb290IDUgMCBSCi9TaXplIDEwCj4+CnN0YXJ0eHJlZgoxNDEyCiUlRU9GCg=="""
~~~

测试断言：

~~~python
def test_pdf_reader_returns_page_blocks():
    text, location = extract_pdf(base64.b64decode(PDF_WITH_TEXT_BASE64))
    assert "Public evidence page one" in text
    assert "Method evidence page two" in text
    assert [b["label"] for b in location["blocks"]] == ["第 1 页", "第 2 页"]
~~~

- [x] **Step 3：写解析失败持久化 RED**

~~~python
def create_uploaded_pdf(db, project_id: str, content: bytes):
    return src_svc.add_file_source(
        db,
        project_id,
        "PDF 资料",
        "source.pdf",
        content,
        "application/pdf",
    )


def test_pdf_without_text_persists_structured_failure(
    db, project_with_plan, tmp_path, monkeypatch
):
    source = create_uploaded_pdf(db, project_with_plan, b"%PDF-invalid")
    with pytest.raises(AppError) as exc:
        src_svc.parse_source(db, project_with_plan, source.id)
    assert exc.value.code == "SOURCE_PDF_TEXT_EMPTY"
    db.expire_all()
    failed = src_svc.get_parsed_document(db, project_with_plan, source.id)
    assert failed.parse_status == "FAILED"
    assert failed.parse_error_code == "SOURCE_PDF_TEXT_EMPTY"
~~~

- [x] **Step 4：运行 RED**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_document_readers.py server/tests/test_source_service.py -v
~~~

Expected: script 文本泄漏、位置块缺失、PDF 依赖/页码合同和失败记录测试失败。

- [x] **Step 5：实现统一 blocks 位置合同**

三个 reader 返回：

~~~python
{
    "title": "可选标题",
    "encoding": "可选编码",
    "blocks": [
        {"label": "第 1 页或段落 1", "start": 0, "end": 120}
    ],
}
~~~

start/end 必须切到 parsed_text 中的真实片段。HTMLParser 使用 skip_depth 排除 script、style、noscript、iframe、svg；PDF 每页追加文本后立即记录偏移；TXT 至少记录全文块和编码。

parse_source 捕获已知解析失败，写入 ParsedDocument(parse_status="FAILED", parsed_text="", text_hash=空文本哈希, parse_error_code=对应错误码)，同时把 SourceRecord.collection_status 设为 FAILED 并提交，然后抛出 AppError。

- [x] **Step 6：运行 GREEN**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_document_readers.py server/tests/test_source_service.py -v
~~~

Expected: 解析与失败持久化测试全部通过。

## Task 5：先证明证据摘录和位置真实，再允许保存与确认

**Files:**

- Create: server/tests/test_evidence_service.py
- Modify: server/app/modules/sources/contracts.py
- Modify: server/app/modules/sources/service.py
- Modify: server/app/modules/llm/evidence_gateway.py
- Modify: server/app/modules/llm/local_rule_evidence_provider.py

- [x] **Step 1：写伪造摘录 RED**

~~~python
@pytest.fixture
def parsed_source(db, project_with_plan, tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    source = src_svc.add_file_source(
        db,
        project_with_plan,
        "文本资料",
        "source.txt",
        "背景资料。\n\n方法采用公开数据分析。".encode("utf-8"),
        "text/plain",
    )
    parsed = src_svc.parse_source(db, project_with_plan, source.id)
    return source, parsed


class InventedQuoteProvider:
    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, document):
        return [{
            "summary": "伪造候选",
            "source_quote": "原文中不存在",
            "evidence_type": "BACKGROUND",
            "location_label": "段落 1",
            "relevance_to_requirement": "背景",
        }]


def test_rejects_candidate_quote_missing_from_parsed_text(parsed_source, db):
    source, _ = parsed_source
    with pytest.raises(AppError) as exc:
        src_svc.generate_evidence(
            db, source.project_id, source.id, InventedQuoteProvider()
        )
    assert exc.value.code == "EVIDENCE_CARD_INVALID_QUOTE"
    assert src_svc.list_evidence(db, source.project_id) == []
~~~

- [x] **Step 2：写位置和状态转换 RED**

~~~python
@pytest.fixture
def pdf_parsed_source(db, project_with_plan, monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    content = base64.b64decode(PDF_WITH_TEXT_BASE64)
    source = src_svc.add_file_source(
        db,
        project_with_plan,
        "PDF 资料",
        "source.pdf",
        content,
        "application/pdf",
    )
    parsed = src_svc.parse_source(db, project_with_plan, source.id)
    return source, parsed


@pytest.fixture
def candidate_card(db, parsed_source):
    source, _ = parsed_source
    cards = src_svc.generate_evidence(
        db, source.project_id, source.id, LocalRuleEvidenceDraftProvider()
    )
    return cards[0]


@pytest.fixture
def confirmed_card(db, candidate_card):
    return src_svc.confirm_evidence(
        db, candidate_card.project_id, candidate_card.id
    )


def test_local_rule_candidate_uses_real_page_label(pdf_parsed_source, db):
    source, parsed = pdf_parsed_source
    cards = src_svc.generate_evidence(
        db,
        source.project_id,
        source.id,
        LocalRuleEvidenceDraftProvider(),
    )
    assert cards[0].location_label in {"第 1 页", "第 2 页"}
    assert cards[0].source_quote in parsed.parsed_text


def test_confirming_first_candidate_advances_project(db, candidate_card):
    src_svc.confirm_evidence(db, candidate_card.project_id, candidate_card.id)
    project = proj_svc.get_project(db, candidate_card.project_id)
    assert project.status == "EVIDENCE_CONFIRMED"


def test_cannot_reject_confirmed_evidence(db, confirmed_card):
    with pytest.raises(AppError) as exc:
        src_svc.reject_evidence(db, confirmed_card.project_id, confirmed_card.id)
    assert exc.value.code == "EVIDENCE_CARD_NOT_EDITABLE"
~~~

- [x] **Step 3：运行 RED**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_evidence_service.py -v
~~~

Expected: 当前实现会保存伪造摘录、只给“段落 N”、状态推进条件不可达，并允许拒绝已确认证据。

- [x] **Step 4：定义候选合同**

contracts.py 新增：

~~~python
class EvidenceDraftCandidate(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    source_quote: str = Field(min_length=1, max_length=2000)
    evidence_type: EvidenceType
    location_label: str = Field(min_length=1, max_length=500)
    relevance_to_requirement: str = Field(min_length=1, max_length=1000)


class EvidenceDraftDocument(BaseModel):
    parsed_text: str
    title: str
    parser_type: ParserType
    location_map: dict
~~~

EvidenceUpdateRequest.evidence_type 使用 EvidenceType，增加 relevance_to_requirement；不得开放 source_quote 修改。

- [x] **Step 5：实现真实性和位置校验**

generate_evidence 必须先 Pydantic 校验 Provider 输出，再逐项检查：

~~~python
if candidate.source_quote not in parsed.parsed_text:
    raise AppError(
        code="EVIDENCE_CARD_INVALID_QUOTE",
        message="证据摘录不存在于解析原文",
        field="source_quote",
    )
if not location_contains_quote(document.location_map, candidate.location_label, candidate.source_quote):
    raise AppError(
        code="EVIDENCE_CARD_INVALID_LOCATION",
        message="证据位置无法定位到原文摘录",
        field="location_label",
    )
~~~

任何候选失败时必须 rollback，本轮不得留下部分卡片。重新生成前把同一 source_id 的旧 CANDIDATE 标记为 STALE；CONFIRMED 不静默覆盖。

confirm_evidence 只允许 CANDIDATE -> CONFIRMED，并把项目从 SOURCES_COLLECTED 推进到 EVIDENCE_CONFIRMED。reject_evidence 只允许 CANDIDATE -> REJECTED，confirmed_at 必须保持为空。

- [x] **Step 6：运行 GREEN**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_evidence_service.py -v
~~~

Expected: 摘录、位置、原子保存、STALE、确认、拒绝和项目状态测试全部通过。

## Task 6：收敛 API 为薄适配层和统一结构化错误

**Files:**

- Create: server/tests/test_source_api.py
- Modify: server/app/api/routers/sources.py
- Modify: server/app/main.py
- Modify: server/app/modules/sources/service.py

- [x] **Step 1：写结构化错误和项目隔离 RED**

测试 client fixture 必须像 test_requirement_api.py 一样使用 StaticPool，并同时替换 projects、requirements、sources 三个 router 的 SessionLocal。

~~~python
def create_confirmed_project(client, name: str = "胃病数据分析") -> str:
    project = client.post(
        "/api/projects", json={"name": name, "topic": name}
    ).json()
    project_id = project["id"]
    source = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "老师要求", "text": "完成公开资料分析"},
    ).json()
    plan = client.post(
        f"/api/projects/{project_id}/requirements/plans/generate",
        json={"source_id": source["id"]},
    ).json()
    response = client.post(
        f"/api/projects/{project_id}/requirements/plans/{plan['id']}/confirm"
    )
    assert response.status_code == 200
    return project_id


@pytest.fixture
def prepared_source(client):
    project_id = create_confirmed_project(client)
    upload = client.post(
        f"/api/projects/{project_id}/sources/files",
        files={"file": ("source.txt", b"public evidence text", "text/plain")},
    )
    assert upload.status_code == 200
    source = upload.json()
    parsed = client.post(
        f"/api/projects/{project_id}/sources/{source['id']}/parse"
    )
    assert parsed.status_code == 200
    return project_id, source


@pytest.fixture
def candidate_card(client, prepared_source):
    project_id, source = prepared_source
    response = client.post(
        f"/api/projects/{project_id}/sources/{source['id']}/evidence/generate"
    )
    assert response.status_code == 200
    return project_id, response.json()["items"][0]


def test_url_requires_confirmed_plan(client):
    project_id = create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/sources/urls",
        json={"url": "https://example.com/public", "title": "公开资料"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "REQUIREMENT_PLAN_NOT_CONFIRMED",
            "message": "请先确认实验任务单",
            "field": None,
        }
    }


def test_parsed_document_cannot_cross_project_boundary(client, prepared_source):
    _, source = prepared_source
    other_project = create_confirmed_project(client, name="另一个项目")
    response = client.get(
        f"/api/projects/{other_project}/sources/{source['id']}/parsed-document"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOURCE_RECORD_NOT_FOUND"


def test_invalid_evidence_type_is_structured(client, candidate_card):
    project_id, card = candidate_card
    response = client.put(
        f"/api/projects/{project_id}/evidence/{card['id']}",
        json={"evidence_type": "NOT_REAL"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
~~~

- [x] **Step 2：写上传上界 RED**

~~~python
def test_upload_rejects_content_over_limit_without_persisting(client, confirmed_project):
    response = client.post(
        f"/api/projects/{confirmed_project}/sources/files",
        files={"file": ("large.txt", b"x" * (20 * 1024 * 1024 + 1), "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "SOURCE_FILE_TOO_LARGE"
    assert client.get(
        f"/api/projects/{confirmed_project}/sources"
    ).json()["items"] == []
~~~

- [x] **Step 3：运行 RED**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_api.py -v
~~~

Expected: 当前响应是 detail 字符串/JSON 字符串，跨项目读取成功或错误形状不一致。

- [x] **Step 4：实现薄路由**

sources.py 使用 APIRouter(prefix="/api/projects/{project_id}")；JSON 请求参数直接声明 Pydantic 模型，不捕获 AppError：

~~~python
@router.post("/sources/urls", response_model=SourceRecordResponse)
def add_url_source(
    project_id: str,
    req: SourceCreateRequest,
    db: Session = Depends(_db),
):
    source = src_service.add_url_source(db, project_id, req)
    return src_service.source_to_response(source)
~~~

上传只读取 max_bytes + 1：

~~~python
content = await file.read(settings.source_upload_max_bytes + 1)
if len(content) > settings.source_upload_max_bytes:
    raise AppError(
        code="SOURCE_FILE_TOO_LARGE",
        message="文件超过 20 MB 上限",
        field="file",
    )
~~~

get_parsed_document 的 Service 签名改为：

~~~python
def get_parsed_document(
    db: Session, project_id: str, source_id: str
) -> ParsedDocument:
~~~

内部先校验 SourceRecord.project_id，再查询解析文档。

- [x] **Step 5：扩展统一错误状态映射**

main.py 中明确映射：

~~~python
NOT_FOUND_CODES = {
    "PROJECT_NOT_FOUND",
    "SOURCE_RECORD_NOT_FOUND",
    "PARSED_DOCUMENT_NOT_FOUND",
    "EVIDENCE_CARD_NOT_FOUND",
}
PAYLOAD_TOO_LARGE_CODES = {
    "SOURCE_FILE_TOO_LARGE",
    "SOURCE_CONTENT_TOO_LARGE",
}
~~~

其余 AppError 返回 400；RequestValidationError 仍转换为 ErrorResponse，不向前端返回 HTTPException.detail。

- [x] **Step 6：运行 GREEN 和旧 API 回归**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest server/tests/test_source_api.py server/tests/test_requirement_api.py -v
~~~

Expected: 新来源 API 和既有要求 API 全部通过，错误体统一为 error/code/message/field。

## Task 7：补齐前端来源与证据工作台

**Files:**

- Create: apps/web/src/features/sources/types.ts
- Create: apps/web/src/features/sources/api.ts
- Create: apps/web/src/features/sources/hooks.ts
- Create: apps/web/src/routes/SourceEvidenceWorkspaceView.tsx
- Modify: apps/web/src/app/App.tsx
- Modify: apps/web/src/routes/ProjectDetailView.tsx
- Modify: apps/web/src/routes/RequirementWorkspaceView.tsx

- [x] **Step 1：先定义后端镜像类型**

types.ts 至少导出：

~~~typescript
export interface SourceRecord {
  id: string;
  project_id: string;
  source_kind: "PUBLIC_URL" | "LOCAL_FILE";
  source_type: "WEB_PAGE" | "PDF" | "DOCX" | "TXT" | "CSV" | "EXCEL" | "UNKNOWN";
  title: string;
  url: string | null;
  original_file_path: string | null;
  content_hash: string | null;
  collection_status: "REGISTERED" | "FETCHED" | "PARSED" | "BLOCKED" | "FAILED" | "UNSUPPORTED";
  access_reason: string | null;
  content_type: string | null;
  size_bytes: number | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceCard {
  id: string;
  project_id: string;
  source_id: string;
  parsed_document_id: string;
  status: "CANDIDATE" | "CONFIRMED" | "REJECTED" | "STALE";
  evidence_type: string;
  summary: string;
  source_quote: string;
  location_label: string;
  relevance_to_requirement: string;
  candidate_source: "LOCAL_RULE" | "MODEL" | "MANUAL";
  created_at: string;
  confirmed_at: string | null;
}
~~~

- [x] **Step 2：实现 API 客户端和 Query hooks**

api.ts 复用 shared ApiError 形状，提供：

~~~typescript
fetchSourceRecords(projectId)
addUrlSource(projectId, url, title)
uploadSourceFile(projectId, file, title)
parseSource(projectId, sourceId)
fetchParsedDocument(projectId, sourceId)
generateEvidence(projectId, sourceId)
fetchEvidence(projectId, filters)
updateEvidence(projectId, evidenceId, patch)
confirmEvidence(projectId, evidenceId)
rejectEvidence(projectId, evidenceId)
~~~

hooks.ts 在每次 mutation 成功后精确失效：

- sources 列表；
- 对应 parsed-document；
- evidence 列表；
- ["project", projectId]。

- [x] **Step 3：实现工作台页面**

页面只消费后端状态，按顺序展示：

1. 项目名称、项目状态和已确认任务单提示；
2. “仅支持公开可访问资料”的 URL 输入；
3. .pdf/.docx/.txt/.csv/.xlsx 上传；
4. 来源列表及 FETCHED/PARSED/BLOCKED/FAILED；
5. 解析按钮和解析文本摘要；
6. 生成候选按钮；
7. 候选的 evidence_type、summary、source_quote、location_label、relevance；
8. 编辑摘要/类型/相关性、确认、拒绝；
9. 所有错误显示后端 message，不自行推断来源受限或证据真实性。

候选卡片旁固定显示“候选证据需要人工核对”。

- [x] **Step 4：接入路由和入口**

App.tsx 增加：

~~~tsx
<Route
  path="projects/:projectId/sources"
  element={<SourceEvidenceWorkspaceView />}
/>
~~~

ProjectDetailView 在 REQUIREMENT_CONFIRMED 及后续状态展示“进入公开资料与证据工作区”。RequirementWorkspaceView 在任务单已确认后展示同一入口。

状态中文映射至少增加 SOURCES_COLLECTED、EVIDENCE_CONFIRMED。

- [x] **Step 5：运行前端门禁**

Run:

~~~powershell
Set-Location apps/web
npm.cmd run lint
npm.cmd run build
~~~

Expected: TypeScript 无错误、Vite 构建成功、无 warning。

## Task 8：迁移、全链路回归和真实浏览器验收

**Files:**

- Modify only if model/schema drift requires it: server/alembic/versions/0003_create_source_and_evidence_tables.py
- Verify without claiming Skill acceptance: server/alembic/versions/0004_create_skill_runs_table.py

- [x] **Step 1：检查模型和迁移一致性**

若前述实现没有新增列，不修改 0003。若必须新增列，先修改模型，再通过新迁移 0005 表达变化，不回写已存在的 0003/0004 历史。

- [x] **Step 2：使用全新临时 SQLite 跑迁移**

Run:

~~~powershell
$env:DATABASE_URL='sqlite:///C:/Users/爹/Documents/VibeCoding/server/.tmp/spec0003-fresh.db'
server/.venv/Scripts/python.exe -m alembic -c server/alembic.ini upgrade head
server/.venv/Scripts/python.exe -m alembic -c server/alembic.ini current
~~~

Expected: current 为 head；记录经过 0003/0004，但只把 0003 视为本阶段业务迁移。

- [x] **Step 3：运行完整后端回归**

Run:

~~~powershell
server/.venv/Scripts/python.exe -m pytest
~~~

Expected: 全部通过；除 acceptance.md 已记录的第三方弃用债务外无新增 warning。若旧 warning 已消失，删除对应债务记录。

- [x] **Step 4：启动真实应用并做 API 探针**

使用临时数据库和项目目录启动 FastAPI、Vite，完成：

~~~text
创建项目
-> 保存并生成任务单
-> 确认任务单
-> 添加 fixture URL 或上传 TXT/PDF
-> 解析
-> 生成候选
-> 确认一张证据
-> 重新 GET 项目、来源、解析文本和证据
-> 项目状态为 EVIDENCE_CONFIRMED
~~~

URL 探针必须使用受控本地测试服务时，不得放宽生产 URL 策略；API 集成测试通过依赖注入 fake transport，浏览器主链路优先使用本地文件上传。

- [x] **Step 5：使用 in-app Browser 验收 UI（文件选择采用已接受的分段证据）**

验证：

- 页面能从项目进入来源工作台；
- 未确认任务单时显示结构化阻塞；
- 上传 TXT/PDF、解析、生成、确认均可点击；
- 错误信息来自后端；
- 刷新后来源和已确认证据仍存在；
- 截图保存到受控临时验收路径，不纳入 git。

若浏览器工具不可用，记录未执行项和替代 API 证据，不得写“UI 验收通过”。

2026-06-21 已通过 in-app Browser 验证私网 URL 错误展示、解析、候选生成、证据编辑保存、刷新保持、证据确认、状态推进和导航，控制台无 error/warn。Browser 自动化接口不能向本地文件选择器注入文件，因此文件上传采用真实 API 合同与 Browser 下游交互的分段证据；项目负责人于 2026-06-22 明确接受该证据边界并确认收口。

## Task 9：文档回写、漂移锁和 git 边界复核

**Files:**

- Modify: dev-docs/README.md
- Modify: dev-docs/acceptance.md
- Modify: dev-docs/implementation-plan.md
- Modify: dev-docs/specs/0003-public-sources-and-evidence-workflow.md
- Modify if dependency truth changed: dev-docs/dependency-review.md

- [x] **Step 1：只记录本轮实际证据**

acceptance.md 对每条命令记录日期、命令、退出码、通过数、warning 和未执行项。不得恢复“41 passed”旧表述，除非本轮 pytest 的实际输出恰好如此且对应覆盖已完整。

- [x] **Step 2：更新当前阶段**

只有 Task 8 全部闭合后，README 和 implementation-plan 才能写“SPEC 0003 实现完成、等待负责人收口确认”。Skill 状态仍写“待第二阶段单独确认”。

- [x] **Step 3：运行漂移和格式检查**

Run:

~~~powershell
rg -n -S "feasibility|FEASIBILITY_CHECKED|CODE_DRAFTED|CODE_CONFIRMED|Skill.*通过|41 passed" AGENTS.md dev-docs server/app/modules/sources apps/web/src/features/sources
git -c safe.directory='C:/Users/爹/Documents/VibeCoding' diff --check
git -c safe.directory='C:/Users/爹/Documents/VibeCoding' status --short --untracked-files=all
git -c safe.directory='C:/Users/爹/Documents/VibeCoding' diff --name-only
git -c safe.directory='C:/Users/爹/Documents/VibeCoding' diff --cached --name-only
~~~

Expected:

- 第一条只命中明确的第二阶段禁止说明，不在 SPEC 0003 owner/UI/API 中出现 feasibility 语义；
- diff --check 无错误；
- staged 列表为空，直到项目负责人确认收口；
- Skill、Orchestrator、0004 和相关测试保持用户原始未提交状态，不被误纳入第一阶段提交。

- [x] **Step 4：停止并请求项目负责人确认 SPEC 0003 收口**

交付结论必须拆分为：

- 后端代码门禁；
- API 合同链路；
- 数据库迁移；
- 前端 lint/build；
- 浏览器/UI；
- 未验证项和残余风险。

项目负责人于 2026-06-22 明确确认 SPEC 0003 收口并接受分段 Browser 证据。收口在独立干净分支执行，Skill、Orchestrator、feasibility、迁移 0004 和相关测试均不纳入提交；第二阶段仍不得自动启动。

## 计划自审结果

- SPEC 第 14 节每项均映射到 Task 2 至 Task 8。
- URL 落盘、SSRF、项目隔离、结构化错误、位置追溯、证据真实性、状态推进、刷新读取、PDF 依赖、UI 和文档证据均有独立任务。
- Skill、Orchestrator、feasibility 明确排除，没有混入第一阶段 owner。
- 所有生产改动之前都有对应 RED 测试；UI 因项目未配置组件测试框架，以 TypeScript/build 和真实浏览器验收为门禁，不临时引入新测试框架。
- 计划没有 TBD、TODO、“类似前文”或未定义的后续实现占位。
