# SPEC 0047：统一工作台壳层、项目进度投影与交付审阅台

> 状态：已确认进入实现。
>
> 确认依据：项目负责人确认以 SPEC 0045、SPEC 0046 为最新有效切片；两者已收口；允许新增本切片合同；PDF 作为正式交付物；允许为稳定性整理共享 UI 样式。

## 1. 目标

为实验报告助手建立统一的项目工作台体验：学生进入任意工作区时，都能看到一致的项目上下文、阶段进度、下一步动作、阻塞原因和交付质量状态；在交付物页面能够审阅 Word、PDF、PPT 的当前版本、来源追溯和质量门禁。

本切片不是一次视觉换肤。核心目标是把重复散落在 `ProjectDetailView` 和各 Workspace 中的阶段判断，收敛为后端真实事实驱动的只读投影；前端只消费投影并负责展示与导航。

## 2. 用户可见结果

- 项目详情页与各工作区使用统一的 `WorkspaceShell`。
- 顶部或侧边稳定显示项目名称、项目状态、当前阶段和最近更新时间。
- 工作流入口显示完成、进行中、待开始、失败或被阻塞状态。
- 用户能够看到明确的下一步动作，并可直接跳转到对应工作区。
- 交付物审阅台同时展示 Word、PDF、PPT 三类正式交付物。
- 每个交付物显示当前版本、生成状态、失败原因、是否过期以及下载入口。
- 质量门禁显示通过、警告、阻断和未运行状态，并能说明依据。
- 交付物页面能够展示大纲、数据集、分析方案、执行记录和图表产物的追溯关系。
- 1280px 桌面宽度下不出现壳层挤压、内容贴边或横向溢出。

## 3. 当前真源与已确认前提

- [project-charter.md](../project-charter.md)：本地单用户 Web MVP、学生实验报告分析工作台和数据可追溯边界。
- [architecture.md](../architecture.md)：项目、要求、资料与证据、数据集与分析、执行、大纲与交付物的 owner 划分。
- [acceptance.md](../acceptance.md)：当前验收和停止条件。
- [specs/0045-paper-review-statistical-integrity.md](0045-paper-review-statistical-integrity.md)：教学性论文复核报告和正式 DOCX/PDF 产出边界。
- [specs/0046-windows-one-click-package.md](0046-windows-one-click-package.md)：Windows x64 portable bundle、无 Python/Node/Docker 前置条件和用户数据目录边界。
- `server/app/modules/outlines/`：当前大纲与交付物核心 owner。
- `server/worker/handlers.py`：当前 Word/PPT 后台生成 owner 接线。
- `apps/web/src/app/App.tsx`：当前平铺路由入口。
- `apps/web/src/routes/ProjectDetailView.tsx`：当前项目阶段投影的重复实现。

当前 `Deliverable` 仅有 `WORD`、`PPT`；PDF 导出器已存在，但通过本机 Microsoft Word COM 工作。为保持 SPEC 0046 的免配置目标，本切片采用随 Windows 包提供的 LibreOffice headless 运行时作为 PDF 转换适配器。DOCX 仍是唯一正文源，PDF 不另建一套排版 owner。

## 4. 范围

### 4.1 PDF 正式交付物

- 在 `DeliverableType` 中增加 `PDF`，复用现有 `deliverables` 与 `deliverable_versions` 表，不新增并行文件记录表。
- Word 成功生成后，由 Worker 使用同一份最终 DOCX 创建 PDF 生成任务；PDF 失败不得回写为 Word 失败。
- PDF 版本沿用现有 `PENDING/RUNNING/SUCCEEDED/FAILED` 状态、版本递增、错误信息和下载路径边界。
- 增加 PDF 失败后的可恢复生成入口；保留现有 Word/PPT 生成接口不变。
- 下载接口增加 PDF media type 和文件名映射。
- 未完成项目的完成门禁调整为当前非 STALE 的 Word、PDF、PPT 均至少有一个成功版本；已经 `COMPLETED` 的历史项目不回退状态。
- PDF 生成失败时，前端必须显示结构化原因和重试入口，不得显示“已完成”。

### 4.2 项目工作区投影

新增只读投影接口：

```text
GET /api/projects/{project_id}/workspace-projection
```

投影由项目核心负责阶段语义，读取各领域的真实状态，不复制数据集、执行、大纲或交付物的业务 owner。

最小字段：

```json
{
  "project_id": "string",
  "project": {"id": "string", "name": "string", "status": "string", "updated_at": "datetime"},
  "current_stage": {"id": "string", "label": "string", "route": "string", "state": "string"},
  "next_action": {"stage_id": "string", "label": "string", "route": "string", "reason": "string"},
  "stages": [
    {
      "id": "string",
      "label": "string",
      "route": "string",
      "state": "COMPLETED|IN_PROGRESS|READY|LOCKED|BLOCKED|FAILED",
      "blocking_reasons": [{"code": "string", "message": "string", "source": "string"}]
    }
  ],
  "projection_generated_at": "datetime"
}
```

### 4.3 交付审阅投影

新增只读投影接口：

```text
GET /api/projects/{project_id}/delivery-review
```

交付审阅投影由交付审阅查询 owner 汇总真实事实；现有 outlines service 继续拥有交付物写入、版本推进和下载校验。

最小字段：

```json
{
  "project_id": "string",
  "review_status": "READY|NEEDS_REVIEW|BLOCKED|STALE",
  "deliverables": [
    {
      "id": "string",
      "type": "WORD|PDF|PPT",
      "status": "PENDING|RUNNING|SUCCEEDED|FAILED|STALE",
      "current_version_id": "string|null",
      "version_number": "integer|null",
      "outline_id": "string",
      "source_execution_id": "string|null",
      "is_stale": "boolean",
      "failure": {"code": "string", "message": "string"}
    }
  ],
  "traceability": {
    "outline_id": "string|null",
    "dataset_version_id": "string|null",
    "analysis_version_id": "string|null",
    "execution_run_id": "string|null",
    "evidence_ids": ["string"]
  },
  "quality_gates": [
    {
      "code": "string",
      "label": "string",
      "status": "PASS|WARN|BLOCKED|NOT_RUN",
      "severity": "INFO|WARNING|BLOCKING",
      "reason": "string|null",
      "source": "string",
      "checked_at": "datetime"
    }
  ],
  "available_actions": {
    "can_download": "boolean",
    "can_regenerate": "boolean",
    "can_complete": "boolean",
    "blocked_reasons": ["string"]
  }
}
```

质量门禁至少包括：实验大纲已确认、数据集可用、分析方案已确认、执行成功、图表可追溯、Word/PDF/PPT 同源、当前版本非 STALE、三类正式交付物均成功、PDF 转换器可用、文件路径和 manifest 校验通过。质量门禁首版为只读实时计算，不新增门禁持久化表。

### 4.4 统一壳层与样式

- 新增共享 `WorkspaceShell` 和共享阶段导航/状态/错误/下一步组件。
- 壳层消费 `workspace-projection`，不再在 UI 复制 `ORDERED_STATUSES`、`isAtOrAfter`、`getNextWorkspace` 或完成门禁。
- 现有路由、TanStack Query、业务写操作和 URL 结构保持不变。
- 仅整理本切片触达的工作区样式，优先迁移内联的颜色、间距、状态标签和卡片结构到现有 tokens/CSS；不进行无关全站重构。
- 参考当前 `ProjectDetailView` 的深蓝、青绿色、浅灰工作台风格；不引入第二套设计系统。

## 5. Owner 与边界

| 概念 | 唯一 owner | UI/API 禁止拥有的内容 |
|---|---|---|
| 项目阶段与下一步投影 | `server/app/modules/projects/` | 前端不得复制阶段状态机 |
| 交付物和版本事实 | `server/app/modules/outlines/` | UI 不得自行判断版本真相 |
| PDF 转换适配 | `server/app/infrastructure/documents/` 与 Windows packaging adapter | 业务服务不得散落调用 PowerShell/LibreOffice |
| 质量门禁与交付审阅投影 | 新增交付审阅查询 owner，具体目录在实现前固定 | 前端不得拼接 PASS/BLOCKED |
| 壳层与视觉展示 | `apps/web/src/components/workspace/` | 不拥有业务状态、权限或质量结论 |

推荐的交付审阅 owner 是 `server/app/modules/delivery_review/`；如果当前架构复核证明不需要新模块，可以在 `server/app/modules/outlines/` 内建立只读 query service，但不得把门禁判断散落到路由或 React 页面。

## 6. 子阶段计划

| 子阶段 | 内容 | 主要 owner | 完成标准 | 停止点 |
|---|---|---|---|---|
| `deliverable-contract-pdf` | PDF 类型、PDF Worker、LibreOffice 适配器、版本与下载合同 | outlines、documents、worker、packaging | PDF 可从最终 DOCX 生成，失败可重试，Word/PPT 现有路径零回归 | PDF 运行时在 portable 包中无法稳定启动时停止 |
| `projection-contracts` | 项目进度投影、交付审阅投影、质量门禁服务与 API 测试 | projects、delivery_review、API | API 字段、错误、项目归属和门禁测试通过 | 真实来源无法提供某个门禁事实时返回 NOT_RUN，不允许猜测 |
| `workspace-shell-ui` | 统一壳层、路由接线、工作区导航、交付审阅台、状态样式 | apps/web | 1280px 下真实浏览器可导航，加载/空/失败/成功状态齐全 | 路由或业务写操作发生回归时停止 UI 迁移 |
| `acceptance-closeout` | 后端/前端测试、构建、PDF/Word/PPT 真实产物、浏览器逐页验收、文档和 Git 收口 | 全链路 | 所有阻断门禁通过，未验证项明确记录，形成中文 commit | 任何关键视觉或正式交付物验收缺失，不得宣称完成 |

## 7. 非目标

- 不修改实验分析方法、统计模型、数据清洗和 DeepSeek Gateway。
- 不新增登录、权限、多用户协作或云端数据同步。
- 不删除或重命名现有路由和现有 Word/PPT API。
- 不用第二套 PDF 正文渲染器重写论文版式；PDF 必须从最终 DOCX 派生。
- 不在本切片实现浏览器内 PDF 编辑器或页级预览器；首版提供真实文件状态、追溯和下载。
- 不把质量门禁结果写成静态假数据或永久缓存。
- 不把所有 Workspace 一次性重构为新组件库；只迁移本切片需要的共享样式和壳层。
- 不把 LibreOffice 安装器、临时构建产物、用户数据、密钥和浏览器缓存提交到 Git。

## 8. 安全、许可与可靠性

- `project_id`、`deliverable_id`、`version_id` 必须在后端真实 owner 校验归属，不能相信前端传入的项目关系。
- 下载路径必须保留现有路径穿越防护；PDF 转换输入只能来自项目受控工作区内的最终 DOCX。
- PDF 转换过程必须设置超时、临时目录和输出大小上限；失败返回结构化错误，不返回 PowerShell 或转换器堆栈。
- portable 包需要记录 LibreOffice 版本、SHA-256、许可证和归属说明；不得静默下载运行时。
- LibreOffice 官方下载页（2026-08-22）显示 Windows x86-64 26.2.5 MSI 为 372,948,992 bytes；官方许可证页说明主代码为 MPL 2.0，并包含其他开源许可证，发布包必须随附许可证清单。
- 当前包体约 288 MB；加入完整 PDF 运行时后以 650–800 MB 解压后体积作为初始预算，最终以真实构建清单为准。

## 9. 测试与验收

### 后端/API

- PDF 类型、生成任务、Worker 成功/失败/重试和版本递增测试。
- Word 成功而 PDF 失败时，两者状态独立；PPT 路径回归通过。
- 项目完成门禁对 Word/PDF/PPT 的成功、失败、STALE、历史已完成项目分别测试。
- 两个投影接口的正常、空数据、阻断、失败和项目归属错误合同测试。
- 质量门禁全部由真实源事实计算；缺少事实时为 `NOT_RUN` 或 `BLOCKED`。
- 下载 PDF 的 media type、路径边界和失败状态拒绝测试。

### 前端

- 壳层当前阶段高亮、下一步跳转、阻塞原因和路由回退。
- 交付物三类型展示、版本状态、失败原因、重试、下载和质量门禁。
- 加载、空数据、接口错误、生成中、成功和 STALE 状态。
- 现有工作区业务交互和 API query invalidation 回归。

### 构建与真实验收

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

必须补充：

- LibreOffice headless 从 portable bundle 启动并完成 DOCX→PDF 的真实 Windows 验收。
- 无 Python、Node.js、Docker 的 Windows x64 干净环境验收。
- 1280px 浏览器逐页检查项目详情、requirements、sources/evidence、datasets、analysis、execution、outline、deliverables。
- 交付物真实 DOCX/PDF/PPT 的版本、下载、manifest 和视觉检查。

## 10. 阶段控制

- `schema`: `sliver-stage/v2`
- `stage_id`: `unified-workspace-delivery-review`
- `primary_route`: `开发执行`
- `operation`: `阶段计划`
- `delivery_kind`: `design`
- `task_depth`: `D3`
- `materialization_trigger`: `cross_owner_drift, ordered_nonclosable_transition`
- `risk_lanes`: `public_contract_compatibility, privacy_secret_data, supply_chain_config, license_legal_content, resource_reliability`
- `evidence_mode`: `route`
- `test_level`: `null`
- `route_evidence_kind`: `design`
- `effect_class`: `local_reversible`
- `operational_mode`: `planned`
- `scope_authorization`: `confirmed: 项目负责人确认最新 SPEC、PDF 正式交付物、允许新增投影合同和稳定性样式整理，并确认先保守接受较大 portable 包体`
- `authorization_substage`: `deliverable-contract-pdf`
- `product_decision`: `confirmed: PDF 为正式交付物；优先随 portable 包提供 PDF 转换运行时，后续再优化体积`
- `active_substage`: `deliverable-contract-pdf`
- `result_status`: `not_started`
- `truth_writeback`: `pending`
- `migration_state`: `not_applicable`
- `evidence_refs`: `[]`

## 11. 调研决策

- `research_status`: `completed: 当前项目的 ProjectDetailView、tokens、outlines service、Worker 和 SPEC 0046 已完成同类本地方案审查；LibreOffice 官方下载页与许可证页已于 2026-08-22 核对`
- 本切片使用当前项目的 `ProjectDetailView` 作为同角色布局参考，不复制外部品牌或页面内容。
- LibreOffice 只作为 PDF 转换运行时，不承担项目业务语义；许可证、版本和哈希随发布 manifest 记录。
- 外部 Figma 模板不是本切片的实现真源；如果后续引入新的视觉参考，必须先建立版本化设计真源并重新走 UI 交付形状验收。

## 12. 停止条件与未验证

- 如果 LibreOffice 不能在 portable bundle 内稳定执行 DOCX→PDF，停止 PDF 子阶段，不以 Microsoft Word 作为静默前置条件。
- 如果 PDF 生成改变了已有 Word 排版或 Word/PPT 同源关系，停止并重新审查渲染 owner。
- 如果投影接口只能通过前端猜测某个质量结论，返回 `NOT_RUN` 并停止质量门禁扩展。
- 当前尚未完成 SPEC 0047 代码、数据库迁移、PDF 真实生成、浏览器视觉验收和干净 Windows 验收，均不得提前宣称通过。
- 根目录 `AGENTS.md` 仍保留早期 SPEC 0002 阶段文字；本轮不直接改写项目宪法，作为治理漂移记录，后续需单独确认是否更新。

## 13. Git 规则

- 实现期间继续保留 `codex/before-workspace-shell-20260822` 和 `stash@{0}`。
- 每个子阶段只精确 stage 相关源文件、测试和文档；禁止 `git add .`。
- 不提交 `server/.tmp/`、`apps/web/dist/`、`server/.venv/`、LibreOffice 安装包、用户数据、浏览器缓存和生成物。
- 子阶段验收完成后先查看状态、暂存列表和关键 diff，再创建中文 commit；本切片全部收口后才讨论 push。
## 14. 2026-08-23 锁定版项目进度投影合同补充

本节是对第 4.2 节最小字段的实现补充；不新增接口，仍使用：

```text
GET /api/projects/{project_id}/workspace-projection
```

响应在保留 `current_stage`、`next_action`、`stages` 兼容字段的同时，增加以下规范投影：

- `project` 摘要包含 `id`、`name`、`topic`、`status`、`status_label` 和 `updated_at`。
- `current` 包含当前 `phase_id`、`phase_label`、`step_id`、`label` 和 `status`。
- `phases[]` 包含顶层阶段状态、`is_open`、锁定时的 `open_reason`、已开放阶段的 `blocking_reasons`、展示文案、动作和 `steps[]`。
- `steps[]` 包含 `status`、`is_open`、`open_reason`、`blocking_reasons`、`display`、`route`、稳定 `command_id`、`actions[]` 和可选 `recovery_action`；资料来源与证据卡片作为同一 `sources_evidence` 阶段的子步骤。
- `recommended_next_action` 是后端推荐动作；项目为 `COMPLETED` 时必须为 `null`，不得继续推荐正式交付物入口。
- 状态语义固定为：`LOCKED` 入口不可访问；`READY` 入口可访问、等待用户开始；`IN_PROGRESS` 已开始但未完成；`BLOCKED` 入口可访问但存在待处理问题；`FAILED` 入口可访问并提供恢复动作；`COMPLETED` 已完成。`is_open` 只表达可访问性，`open_reason` 只表达锁定原因，开放工作区的问题统一进入 `blocking_reasons`。
- `actions[].command_id` 只是稳定动作标识；前端继续调用现有 mutation/API，后端写入接口继续做最终校验，不创建通用 command bus。

唯一 owner 维持为：项目阶段与顺序在 `server/app/modules/projects/`，投影在 `server/app/modules/projects/projection.py`，领域真实状态由各自模块负责，HTTP 映射在 `server/app/api/routers/projects.py`，展示和动作接线在 `apps/web/src/`。目标生产页面不得重新定义状态顺序、项目级入口门控或业务语义。

本轮复核证据：后端投影合同测试 7 passed；前端全量 548 passed，lint/build 通过；Alembic 从 `server/` 目录执行通过。后端全量尚有既有科研资产 `bioicons-cc0-cryo-vial` manifest SHA-256 漂移，浏览器视觉、LibreOffice runtime 和干净 Windows 验收未完成，因此本 SPEC 仍不得标记为完整收口。
## 15. 2026-08-23 交付物审阅台实现回写

本轮完成“交付物审阅台”代码切片。交付审阅业务判断唯一位于 `server/app/modules/delivery_review/projection.py`；`service.py` 仅保留旧导入路径兼容导出，HTTP 仍复用 `GET /api/projects/{project_id}/delivery-review`，前端只消费结构化审阅投影。

交付物版本新增可空 provenance 字段并由 Alembic `0008_add_deliverable_version_provenance.py` 管理：大纲版本、数据集版本、分析方案、执行记录、PDF 源 Word 版本和文件 SHA-256。Word/PPT Worker 记录实际参与渲染的成功执行记录；PDF 从实际 Word 版本继承绑定，不从当前项目状态回推历史事实。没有历史绑定时，投影返回 `N/A` 和具体不可用原因。

审阅投影现在覆盖：Word/PDF/PPT 身份和版本历史、推荐下载版本、大纲变化导致的失效、结构化版本差异说明、失败错误码与恢复动作、内容质量检查、观察性/因果边界、L3 复现边界、医学教学边界、真实图表/表格和引用覆盖。预览在当前生成链没有真实缩略图时返回 `NOT_AVAILABLE`；视觉检查返回 `NOT_CHECKED`，不得显示为通过。质量结论由后端真实事实计算，前端不承担门禁 owner。

前端新增 `DeliverableReviewPanel` 和 `DeliverableReviewPanel.css`，保留现有下载、PDF 重试、完成项目 mutation/API；补充项目、交付物列表、版本列表和审阅投影的 loading、empty、error、STALE、失败恢复、disabled 和成功状态。没有真实预览时只显示不可用说明，不生成假缩略图。

本轮代码验证：交付审阅服务/API/版本一致性 9 passed；交付物与生成链相关回归 97 passed；前端全量 35 个测试文件、550 passed；`npm.cmd run lint`、`npm.cmd run build`、`server` 目录 `alembic upgrade head` 通过。根目录后端全量为 1260 passed、1 failed，唯一失败为既有科研资产 `bioicons-cc0-cryo-vial` 的 SVG manifest SHA-256 漂移；该测试不经过本切片调用链。浏览器 Node helper 仍在初始化阶段退出，未取得 1280px/窄屏截图；LibreOffice runtime、portable 黑盒和真实 DOCX/PDF/PPT 视觉验收仍未完成。

因此，本节状态为“实现 checkpoint”，不是完整发布收口。停止条件仍包括真实浏览器视觉验收、LibreOffice portable runtime、干净 Windows x64 验收和既有科研资产 hash 风险单独处理。
