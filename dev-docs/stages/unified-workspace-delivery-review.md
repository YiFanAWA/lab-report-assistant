# 统一工作台与交付审阅阶段

本阶段承载 SPEC 0047 的可执行计划和阶段状态。产品范围以 [SPEC 0047](../specs/0047-unified-workspace-shell-delivery-review.md) 为准。

## 阶段控制

- schema: sliver-stage/v2
- stage_id: unified-workspace-delivery-review
- primary_route: 开发执行
- operation: 阶段计划
- delivery_kind: design
- task_depth: D3
- materialization_trigger: [cross_owner_drift, ordered_nonclosable_transition]
- risk_lanes: [license_legal_content, privacy_secret_data, public_contract_compatibility, resource_reliability, supply_chain_config]
- evidence_mode: route
- test_level: null
- route_evidence_kind: design
- effect_class: local_reversible
- operational_mode: executing
- scope_authorization: confirmed:项目负责人确认最新 SPEC、PDF 正式交付物、允许新增投影合同和稳定性样式整理，并确认先保守接受较大 portable 包体
- authorization_substage: workspace-shell-ui
- product_decision: confirmed:PDF 为正式交付物；优先随 portable 包提供 PDF 转换运行时，后续再优化体积
- active_substage: acceptance-closeout
- result_status: in_progress
- truth_writeback: complete
- migration_state: not_applicable
- evidence_refs: []

## 阶段目标与用户流程

学生打开项目后看到统一工作台壳层、当前阶段和下一步动作；进入各工作区完成实验要求、资料、数据、分析、执行和大纲；最后在交付审阅台检查 Word/PDF/PPT 的版本、来源和质量门禁并下载正式交付物。

PDF 以最终 DOCX 为唯一源文件，使用随 Windows portable bundle 提供的 LibreOffice headless 转换运行时；不要求用户安装 Word、Python、Node.js 或 Docker。

## 当前真相与 Owner

- 产品与边界：[project-charter.md](../project-charter.md)、[architecture.md](../architecture.md)。
- 当前验收：[acceptance.md](../acceptance.md)。
- 上游切片：[SPEC 0045](../specs/0045-paper-review-statistical-integrity.md)、[SPEC 0046](../specs/0046-windows-one-click-package.md)。
- 产品合同：[SPEC 0047](../specs/0047-unified-workspace-shell-delivery-review.md)。
- 项目阶段 owner：`server/app/modules/projects/`。
- 交付物事实 owner：`server/app/modules/outlines/`。
- PDF 适配 owner：`server/app/infrastructure/documents/` 与 `packaging/windows/`。
- Worker 接线：`server/worker/handlers.py`。
- 前端展示：`apps/web/src/`，新增共享壳层但不拥有业务状态机。
- 当前重复点：`ProjectDetailView.tsx` 和多个 Workspace 各自维护阶段/门控判断。

## 调研决策

- research_status: completed:已审查当前 ProjectDetailView、tokens、outlines service、Worker、SPEC 0046 和本地 Windows 包；已于 2026-08-22 核对 LibreOffice 官方下载页与许可证页。
- LibreOffice 官方稳定 Windows x86-64 26.2.5 MSI 为 372,948,992 bytes；主代码采用 MPL 2.0，同时包含其他开源许可证，发布包必须保留许可证和归属说明。
- 当前已有 portable bundle 约 288 MB；本阶段先按 650–800 MB 解压后预算实现，后续再做体积优化。
- UI 参考采用当前项目同角色的 `ProjectDetailView`，不引入外部 Figma 作为实现真源。

## 范围与非目标

范围：PDF 正式交付物、PDF Worker 和可重试生成、PDF 下载合同、项目阶段投影、交付审阅投影、后端质量门禁、共享 WorkspaceShell、交付审阅台、触达范围内的 token/CSS 整理和全链路验收。

非目标：修改分析统计逻辑、修改 LLM Gateway、引入登录或多人协作、删除现有路由和 Word/PPT API、建立第二套 PDF 排版系统、浏览器内 PDF 编辑器、无关全站 CSS 重构。

## 子阶段计划

| 子阶段 | 结果 | Owner | 完成标准 | 验证 | 不触碰 |
| --- | --- | --- | --- | --- | --- |
| deliverable-contract-pdf | PDF 类型、Worker、转换适配、版本与下载合同 | outlines、documents、worker、packaging | PDF 从最终 DOCX 生成，失败可重试，Word/PPT 零回归 | 后端专项测试、真实 DOCX→PDF、portable 运行时测试 | 统计和 Word/PPT 语义 |
| projection-contracts | 项目进度投影、交付审阅投影和质量门禁 | projects、delivery_review、API | 字段、错误、项目归属和门禁测试通过 | API/服务合同测试 | 前端猜测质量结论 |
| workspace-shell-ui | 统一壳层、导航、审阅台和状态样式 | apps/web | 1280px 真实浏览器可导航，状态齐全 | 前端测试、lint/build、浏览器截图点击 | 业务写操作 |
| acceptance-closeout | 全链路验收、文档回写和 Git 收口 | 全链路 | 所有阻断门禁通过，未验证项清楚，中文 commit | 后端/前端/EXE/浏览器/manifest | 自动 push 或发布 |

## 测试、安全与影响

- `project_id`、`deliverable_id`、`version_id` 由后端校验归属；下载路径保留穿越防护。
- PDF 输入只能来自项目受控工作区内的最终 DOCX；转换有超时、临时目录和输出大小上限。
- 不增加登录权限模型，但必须覆盖项目资源和交付物归属的失败路径。
- 风险通道：`license_legal_content`、`privacy_secret_data`、`public_contract_compatibility`、`resource_reliability`、`supply_chain_config`。
- Test Gate：PDF/API/完成门禁/投影属于 T2；转换器和 portable 运行时属于 T3；共享样式的纯视觉部分属于 T0/T3；最终全链路取各表面最强门禁。

## 验证方法

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

补充验证：PDF 成功/失败/重试、Word/PDF/PPT 同源和完成门禁；项目投影和交付审阅 API 的空/错误/阻断状态；LibreOffice headless 包内 DOCX→PDF；无 Python/Node.js/Docker 的 Windows x64；1280px 浏览器逐页验收；真实 DOCX/PDF/PPT 的版本、下载、manifest 和视觉检查。

## 停止条件与未验证

- LibreOffice 无法在 portable bundle 内稳定执行 DOCX→PDF 时停止 PDF 子阶段，不静默依赖 Microsoft Word。
- PDF 改变 Word 排版或 Word/PPT 同源关系时停止并重新审查 owner。
- 某个门禁没有真实来源时返回 NOT_RUN/BLOCKED，不允许前端猜测。
- 当前代码、数据库迁移、PDF 实际生成和浏览器视觉验收已完成；独立干净 Windows x64 黑盒，以及当前项目同源 Word/PDF/PPT 重新生成后的视觉一致性仍未完成。
- 根 `AGENTS.md` 仍保留早期 SPEC 0002 阶段文字；本阶段不改写项目宪法，作为治理漂移记录。

## Git checkpoint rule

实现期间保留 `codex/before-workspace-shell-20260822` 和 `stash@{0}`；每个子阶段只精确 stage 相关源文件、测试和文档，禁止 `git add .`；不提交 `server/.tmp/`、`apps/web/dist/`、`server/.venv/`、LibreOffice 安装包、用户数据和生成物。

## 实施回写

- actual_result: PDF 正式交付物合同、PDF Worker、LibreOffice headless 适配器、portable runtime 显式注入、项目工作台 projection、交付审阅 projection、质量门禁和统一 WorkspaceShell 已实现；本轮已将壳层迁移至 Sources、Evidence、Dataset、Analysis、Execution、Outline、Deliverable 七个目标工作区。
- changed_owners: server/app/modules/outlines/、server/app/infrastructure/documents/、server/worker/、packaging/windows/、server/app/modules/projects/、server/app/modules/delivery_review/、apps/web/src/components/workspace/、apps/web/src/routes/、apps/web/src/shared/types.ts。
- plan_deviation: 本轮按用户明确目标只迁移七个工作区；ProjectDetailView、RequirementWorkspaceView 不属于本轮目标页面，未扩大迁移。LibreOffice runtime 已在临时目录完成独立 portable 构建和真实 DOCX→PDF；浏览器插件仍因 Windows ACL helper 退出，但已用系统 Chrome + Playwright 完成等价截图验收。2026-08-25 已补充修复两份科研 SVG 的上游换行漂移并完成全量后端回归。
- fresh_evidence: 后端项目投影定向测试 7 passed；科研资产 registry/renderer 定向回归 29 passed；后端从 server/ 目录全量测试 1266 passed；PDF 交付相关回归 92 passed；Windows portable 源合同 4 passed；前端全量 35 个测试文件、550 个测试通过，ProjectDetailView 定向测试 8 passed，npm.cmd run lint 和 npm.cmd run build 通过；Alembic 从 server/ 目录执行 upgrade head 通过；目标生产页面扫描未发现 ORDERED_STATUSES、orderedStatuses、isAtOrAfter、getWorkspaceVisibility、getNextWorkspace、canRegister 或项目级 canComplete。
- remaining_risk: 独立无 Python/Node.js/Docker 的 Windows x64 黑盒，以及当前项目同源 Word/PDF/PPT 重新生成后的视觉一致性仍未完成；浏览器插件连接仍受 Windows ACL helper 影响，但已有系统 Chrome 替代证据。SPEC 0047 不能标记为完整收口。
- next_substage: 先由项目负责人查看并确认保留的 1280px/390px 浏览器截图和当前 PDF 视觉结果；随后再决定是否进入独立 Windows 黑盒及当前项目同源 Word/PDF/PPT 补验，最后才讨论精确 stage、commit、push。
- git_checkpoint: 保留 `codex/before-workspace-shell-20260822` 和 `stash@{0}`；当前不 stage、不 commit、不 push，待项目负责人确认本子阶段收口范围后精确收口。

## 2026-08-23 交付物审阅台最新复核

交付物审阅台实现 checkpoint 已完成：后端投影/API/版本一致性 9 passed，交付物相关回归 97 passed；前端全量 35 个测试文件、550 passed，lint/build 和 Alembic upgrade head 通过。质量与 provenance 仍由后端投影 owner 计算，旧 service 仅保留兼容导出；无真实预览时返回 `NOT_AVAILABLE`，视觉检查未执行时返回 `NOT_CHECKED`。

未闭合项：根目录后端全量 1260 passed、1 failed，失败为既有 `bioicons-cc0-cryo-vial` SVG manifest SHA-256 漂移；浏览器 Node helper 初始化退出，尚无 1280px/窄屏截图；LibreOffice runtime、portable 黑盒和真实 Word/PDF/PPT 逐页视觉一致性仍未验收。本次按项目负责人最新指令完成代码实现 checkpoint 的版本收口，但不将其宣称为完整发布收口。

## 2026-08-25 资产阻断修复后复核

科研资产 registry/renderer 定向回归 29 passed；`cryo_vial.svg` 与 `sequencer.svg` 已按固定 Bioicons commit `d29e766ea7580b8063c4f47b29e872db40a4d979` 恢复为批准上游 raw 字节，manifest hash 漂移已关闭。

后端全量 1266 passed；PDF 交付相关回归 92 passed；Windows portable 源合同 4 passed；前端 550 passed、lint/build 和 Alembic 通过。

浏览器视觉验收仍被两次 Windows ACL helper 初始化退出阻断；本机和 portable 目录均没有 `soffice.exe`，因此 LibreOffice portable 黑盒、干净 Windows x64 和真实 DOCX/PDF/PPT 逐页一致性仍未验收。SPEC 0047 继续保持实现 checkpoint，不宣称完整发布收口。
## 2026-08-25 LibreOffice portable runtime 复核

- actual_result: 从官方 LibreOffice 26.2.5 Windows x86-64 MSI 解压临时 runtime，补齐 source_sha256/许可证文件校验和发布 manifest 字段；独立临时输出生成 portable bundle。
- fresh_evidence: Windows packaging 合同测试 `test_spec0046_windows_packaging.py` 与 `test_spec0047_portable_runtime.py` 共 6 passed；PyInstaller service/launcher、前端 127 modules build 和 release manifest 均生成。
- runtime_evidence: 包内 `soffice.com --headless --version` 返回 26.2.5.2；生产 `DocxPdfExporter` 使用包内 `soffice.exe` 将真实 DOCX 转为 456,765 bytes PDF；Poppler 识别 10 页并生成 10 张 PNG。
- visual_boundary: 10 张 PDF PNG 已由 Poppler 生成并完成逐页检查；未发现空白页、裁切、重叠或异常黑块，当前 PDF 栅格化视觉通过。
- remaining_risk: 浏览器和当前 PDF 视觉已通过；无开发依赖的干净 Windows x64 黑盒，以及当前项目同源 Word/PDF/PPT 重新生成后的视觉一致性仍未闭合。
- next_substage: 由项目负责人查看保留的浏览器截图和当前 PDF 视觉结论；随后再决定是否进入独立 Windows 黑盒及同源交付物补验。
- git_checkpoint: 当前不 stage、不 commit、不 push；LibreOffice MSI、解压 runtime、portable bundle、PDF/PNG 和 `.tmp` runner 均留在临时/忽略边界。
## 2026-08-25 真实浏览器与 PDF 视觉复核

- actual_result: 系统 Chrome + Playwright 已完成首页、项目详情、交付审阅台 1280px 截图，以及交付审阅台 390px 窄屏截图；修复页面级横向溢出和 favicon 404 后，截图结果 events 为空。
- visual_evidence: 1280px 下项目卡片、阶段导航、交付质量门禁和修复动作可读；390px 下内容单列且无页面级横向滚动。证据保存在 dev-docs/e2e-screenshots/spec0047_browser_qa/。
- pdf_evidence: portable LibreOffice 26.2.5.2 完成真实 DOCX→PDF；Poppler 识别 10 页并生成 10 张 PNG，逐页检查未发现裁切、重叠、空白或黑块。临时 PDF 栅格目录已在记录后清理。
- product_boundary: 当前演示项目的 PDF 缺失、交付物不同源、证据覆盖不足和视觉检查未运行均由后端审阅投影正确阻断；本轮不伪造成功状态。
- remaining_risk: 浏览器插件连接仍受 trusted Node process exited unexpectedly 影响，但已有系统 Chrome 替代证据；尚未完成无 Python/Node.js/Docker 的独立 Windows x64 黑盒，也尚未以当前项目大纲重新生成并逐页检查同源 Word/PDF/PPT。
- next_substage: 由项目负责人查看保留的浏览器截图并确认产品视觉；随后再决定是否进入独立 Windows 黑盒和同源交付物补验。
- git_checkpoint: 当前不 stage、不 commit、不 push；本轮只保留浏览器视觉证据和文档记录。
