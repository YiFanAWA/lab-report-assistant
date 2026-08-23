# 实验报告助手｜实施计划

> **给后续 agent 的要求：** SPEC 0001 第一开发切片已由项目负责人确认。SPEC 0002 已完成实现、复核验收并由项目负责人确认收口。SPEC 0003 公开资料与证据工作流已完成实现与端到端验收并由项目负责人确认收口。SPEC 0004 数据集工作区已完成实现与端到端验收并由项目负责人确认收口。SPEC 0005 受控 Python 执行已完成实现与端到端验收并由项目负责人确认收口；SPEC 0006 大纲与交付物已完成实现与端到端验收并由项目负责人确认收口；V1.0.0 已发布并打 tag v1.0.0。V1.1.0 阶段：SPEC 0007（真实 DeepSeek LLM 接入）、SPEC 0008（部署文档与运维指南）、SPEC 0009（前端测试覆盖补全）、SPEC 0010（Word 模板支持）、SPEC 0011（PPT 配置选项）、SPEC 0012（数据保留周期配置）均已由项目负责人确认收口；V1.1.0 已发布并打 tag v1.1.0（后端 704 passed + 前端 411 passed，0 warnings）。V1.2.0 阶段：SPEC 0013（Docker 化部署）、SPEC 0014（LLM 调用缓存）、SPEC 0015（GitHub Actions CI 流水线）均已由项目负责人确认收口；V1.2.0 已发布并打 tag v1.2.0（后端 729 passed 新增 25 测试 + 前端 411 passed，0 warnings；CI Run #2/#3 全绿；worker_e2e E2E_RESULT=PASS）。V1.3.0 阶段：SPEC 0016（技术债务清理 TD-004/005/006/008）已由项目负责人确认收口；V1.3.0 已发布并打 tag v1.3.0（后端 736 passed 新增 7 测试 + 前端 411 passed，0 warnings；Docker 容器内科学计算包导入验证通过；当前无活跃可记录债务）。V1.4.0 阶段：SPEC 0017（单用户前端实时编辑反馈）已完成实现与测试验收并由项目负责人确认收口；V1.4.0 已发布并打 tag v1.4.0（前端 434 passed 新增 23 测试 + 后端 736 passed 零回归；纯前端切片不修改后端）。V2.0.0 阶段：SPEC 0018（流式 LLM 输出，任务单生成 SSE 流式化）已完成实现与测试验收并由项目负责人确认收口；V2.0.0 已发布并打 tag v2.0.0（后端 783 passed 新增 47 测试 + 前端 468 passed 新增 34 测试；不引入新依赖，不修改数据库 schema；浏览器验收 PASS，截图未持久化延续 TD-009）。V2.1.0 阶段：SPEC 0019（大纲生成流式化）已完成实现与测试验收并由项目负责人确认收口；V2.1.0 已发布并打 tag v2.1.0（后端 821 passed 新增 38 测试 + 前端 493 passed 新增 25 测试；SSE 端点绕过 Worker，上下文聚合提取到 service 层；不引入新依赖，不修改数据库 schema；浏览器验收 PASS，transient 流式 UI 状态因 LocalRule 同步降级路径过快未被快照捕获，后端 200 OK + 数据库持久化 + 列表自动刷新均验证通过）。V2.2.0 阶段：SPEC 0020（证据卡片生成流式化）已完成实现与测试验收并由项目负责人确认收口；V2.2.0 已发布并打 tag v2.2.0（后端 858 passed 新增 37 测试 + 前端 519 passed 新增 26 测试；SSE 端点绕过 Worker，Provider 输入为单文档 parsed_text 无需上下文聚合提取，复用 SPEC 0018/0019 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema；浏览器验收 PASS，6 步全通过，截图保存至 dev-docs/e2e-screenshots/e2e-spec0020-*.png）。V2.3.0 阶段：SPEC 0021（分析方案生成流式化）已完成实现与测试验收并由项目负责人确认收口；V2.3.0 待发布并打 tag v2.3.0（后端 895 passed 新增 37 测试 + 前端 546 passed 新增 27 测试；SSE 端点绕过 Worker，Provider 输入为 DatasetProfile 无需上下文聚合提取，复用 SPEC 0018/0019/0020 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema；浏览器验收 PASS，截图保存至 dev-docs/e2e-screenshots/e2e-spec0021-*.png；收口复核修复 1 项阻断问题：LocalRuleAnalysisPlanProvider 输出 target_fields 为字符串导致前端 PlanCard TypeError 页面崩溃，修复 6 处输出为数组）。V2.4.0 阶段：SPEC 0022（代码任务生成流式化）已完成实现与测试验收并由项目负责人确认收口（2026-07-30）；V2.4.0 已发布并打 tag v2.4.0（后端 975 passed 新增 80 测试 + 前端 570 passed 新增 19 测试；SSE 端点绕过 Worker，Provider 输入为 AnalysisPlan 无需上下文聚合提取，复用 SPEC 0018/0019/0020/0021 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema；浏览器验收 PASS，截图保存至 dev-docs/e2e-screenshots/spec0022-*.png；收口复核修复 1 项阻断问题：LocalRuleCodeTaskProvider 中 FREQUENCY 类型 target_fields.split() 在 list 上报错，新增 _first_field_name() 辅助函数兼容 list/str/None）。V2.5.0 阶段：SPEC 0024（PPT 渲染器布局与视觉层次改进）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.5.0 待发布并打 tag v2.5.0（16:9 画布 + 空白版式精确定位 + 双栏内容页 40%/60% + 图表自适应布局 + 五级字号体系 + 主题色扩展应用；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法；端到端视觉测评修复图表中文乱码/PPT 页数限制/图片溢出/3 图布局/文本截断 5 项阻断问题；后端 41+142 passed 零回归 + 前端 lint/build 通过；配套修复 code_task_provider 和 deepseek_code_task_provider 中文乱码）。V2.6.0 阶段：SPEC 0025（PPT 三角色彩系统与深浅对比三明治结构）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.6.0 待发布并打 tag v2.6.0（从单一 theme_color 用 colorsys 标准库派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法；新增 16 个专用测试，57+222+83 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过）。V2.7.0 阶段：SPEC 0026（PPT 视觉效果增强，渐变填充 + 圆角矩形 + 外阴影 + 细边框）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.7.0 待发布并打 tag v2.7.0（python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；新增 17 个专用测试，220 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部视觉效果方法）。V2.8.0 阶段：SPEC 0027（图表美化与布局增强，SciencePlots + Seaborn + EasyPPTX）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.8.0 待发布并打 tag v2.8.0（_HEADER 集成 scienceplots 样式 + sns.set_theme，_build_chart_code 升级为 sns.histplot/boxplot/countplot/scatterplot/heatmap，CORRELATION 分析新增热图；ppt_renderer 新增 _pct_to_emu 百分比定位 + _GridHelper N×M 网格辅助类，改造 _place_chart_grid/side_by_side/three 使用 Grid 坐标与原硬编码完全一致；沙箱白名单新增 scienceplots/seaborn；新增 45 个专用测试，204 passed 零回归 + 5 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染 + Grid 布局 8/8 对齐验证；引入 3 个新依赖 scienceplots/seaborn/easypptx，不改变 PptConfig 合同）。V2.8.1 阶段：SPEC 0028（Nature 风格图表集成，移除 SciencePlots，引入 nature-figure 设计规则）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.8.1 待发布并打 tag v2.8.1（_HEADER 移除 `import scienceplots` 和 `plt.style.use(...)`，新增 nature-figure rcParams 配置：`axes.spines.right/top=False` 去右框/顶框 + `axes.linewidth=2.5` 粗轴线 + `legend.frameon=False` 无图例边框 + `savefig.dpi=300` 高分辨率输出；deepseek_code_task_provider 同步更新 _SYSTEM_PROMPT；python_executor 的 DEFAULT_ALLOWED_IMPORTS 移除 scienceplots；pyproject.toml 移除 scienceplots 依赖声明；修改 5 个受影响测试 C1/C2/C3/S1/S4 + 修复遗漏测试 test_default_allowed_imports_content，204 passed 零回归 + 3 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染；移除 1 个依赖 scienceplots，不引入新依赖，不改变 PptConfig 合同，保留 Seaborn + _GridHelper + 中文字体支持）。后续新切片开始前仍需先编写并确认新 SPEC。

**目标：** 构建“实验报告助手”的第一版 Web MVP 闭环：项目创建、要求拆解、证据工作流、数据分析执行、大纲确认、Word/PPT 生成。

**架构：** 遵循 [architecture.md](architecture.md) 中的单一推荐架构：本地单用户 Web MVP、模块化后端唯一归属层、独立 Worker、应用托管的 Python 受控执行环境、统一大模型网关、证据化交付物。

**技术栈：** 已在 [tech-stack.md](tech-stack.md) 锁定，依赖版本和目录规范已在 [dependency-review.md](dependency-review.md) 复核：本地单用户 Web MVP、TypeScript + React + Vite 前端、Python + FastAPI 后端、SQLite 本地单用户存储、本地文件产物仓库、数据库任务表 + 独立 Worker、应用托管的 Python 受控执行环境、DeepSeek 供应商中立接入。

---

## 执行门禁

代码阶段已由项目负责人批准启动，SPEC 0001-0006 全部完成实现、端到端验收并由项目负责人确认收口；V1.0.0 已发布并打 tag v1.0.0。V1.1.0 阶段 SPEC 0007-0012 全部完成实现与测试验收并由项目负责人确认收口；V1.1.0 已发布并打 tag v1.1.0。V1.2.0 阶段 SPEC 0013-0015 全部完成实现与测试验收（含 CI 流水线实际运行）并由项目负责人确认收口；V1.2.0 已发布并打 tag v1.2.0（后端 729 + 前端 411，0 warnings）。V1.3.0 阶段 SPEC 0016 完成实现与测试验收（含 Docker 容器验证）并由项目负责人确认收口；V1.3.0 已发布并打 tag v1.3.0（后端 736 + 前端 411，0 warnings；当前无活跃可记录债务）。V1.4.0 阶段 SPEC 0017 完成实现与测试验收（含浏览器点击验收 PASS，截图未持久化记录为 TD-009）并由项目负责人确认收口；V1.4.0 已发布并打 tag v1.4.0（前端 434 新增 23 + 后端 736 零回归；纯前端切片不修改后端）。V2.0.0 阶段 SPEC 0018（流式 LLM 输出）完成实现与测试验收（含浏览器点击验收 PASS，截图未持久化延续 TD-009）并由项目负责人确认收口；V2.0.0 已发布并打 tag v2.0.0（后端 783 新增 47 + 前端 468 新增 34；不引入新依赖，不修改数据库 schema）。V2.1.0 阶段 SPEC 0019（大纲生成流式化）完成实现与测试验收（含浏览器点击验收 PASS，transient 流式 UI 状态因 LocalRule 同步降级路径过快未被快照捕获，后端 200 OK + 数据库持久化 + 列表自动刷新均验证通过，延续 TD-009 截图限制）并由项目负责人确认收口；V2.1.0 已发布并打 tag v2.1.0（后端 821 新增 38 + 前端 493 新增 25；SSE 端点绕过 Worker，上下文聚合提取到 service 层；不引入新依赖，不修改数据库 schema）。V2.2.0 阶段 SPEC 0020（证据卡片生成流式化）完成实现与测试验收（含浏览器点击验收 PASS，6 步全通过，截图保存至 dev-docs/e2e-screenshots/e2e-spec0020-*.png，延续 TD-009 截图未持久化限制）并由项目负责人确认收口；V2.2.0 已发布并打 tag v2.2.0（后端 858 新增 37 + 前端 519 新增 26；SSE 端点绕过 Worker，Provider 输入为单文档 parsed_text 无需上下文聚合提取，复用 SPEC 0018/0019 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema）。V2.3.0 阶段 SPEC 0021（分析方案生成流式化）完成实现与测试验收（含浏览器点击验收 PASS，截图保存至 dev-docs/e2e-screenshots/e2e-spec0021-*.png，9 张截图覆盖首页/项目详情/分析工作区/流式开始/流式完成/列表刷新/取消/API 响应/持久化验证；TD-009 截图未持久化限制已在本次 SPEC 0021 验收中通过 browser_use agent 主动持久化截图部分缓解），并由项目负责人确认收口；V2.3.0 待发布并打 tag v2.3.0（后端 895 新增 37 + 前端 546 新增 27；SSE 端点绕过 Worker，Provider 输入为 DatasetProfile 无需上下文聚合提取，复用 SPEC 0018/0019/0020 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema；收口复核修复 1 项阻断问题：LocalRuleAnalysisPlanProvider 输出 target_fields 为字符串导致前端 PlanCard TypeError 页面崩溃，修复 6 处输出为数组）。V2.4.0 阶段 SPEC 0022（代码任务生成流式化）完成实现与测试验收（含浏览器点击验收 PASS，截图保存至 dev-docs/e2e-screenshots/spec0022-*.png，5 张截图覆盖执行工作区/方案选择/流式中/流式完成/任务列表刷新）并由项目负责人确认收口（2026-07-30）；V2.4.0 已发布并打 tag v2.4.0（后端 975 新增 80 + 前端 570 新增 19；SSE 端点绕过 Worker，Provider 输入为 AnalysisPlan 无需上下文聚合提取，复用 SPEC 0018/0019/0020/0021 stream-sse.ts 和降级策略；不引入新依赖，不修改数据库 schema；收口复核修复 1 项阻断问题：LocalRuleCodeTaskProvider 中 FREQUENCY 类型 target_fields.split() 在 list 上报错，新增 _first_field_name() 辅助函数兼容 list/str/None）。V2.5.0 阶段 SPEC 0024（PPT 渲染器布局与视觉层次改进）完成实现与测试验收（含端到端视觉测评修复图表中文乱码/PPT 页数限制/图片溢出/3 图布局/文本截断 5 项阻断问题）并由项目负责人确认收口（2026-07-31）；V2.5.0 待发布并打 tag v2.5.0（后端 41+142 passed 零回归 + 前端 lint/build 通过；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法；配套修复 code_task_provider 中文乱码）。V2.6.0 阶段 SPEC 0025（PPT 三角色彩系统与深浅对比三明治结构）完成实现与测试验收（含 6 种预设色真实文件视觉验收）并由项目负责人确认收口（2026-07-31）；V2.6.0 待发布并打 tag v2.6.0（新增 16 个专用测试，57+222+83 passed 零回归 + 前端 lint/build 通过；从单一 theme_color 用 colorsys 标准库派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法）。V2.7.0 阶段 SPEC 0026（PPT 视觉效果增强）完成实现与测试验收（含 6 种预设色真实文件视觉验收）并由项目负责人确认收口（2026-07-31）；V2.7.0 待发布并打 tag v2.7.0（渐变填充 + 圆角矩形 + 外阴影 + 细边框；新增 17 个专用测试，220 passed 零回归 + 前端 lint/build 通过；python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部视觉效果方法）。V2.8.0 阶段 SPEC 0027（图表美化与布局增强）完成实现与测试验收（含 5 张真实图表沙箱执行 + 6 种预设色 PPT 渲染 + Grid 布局 8/8 对齐验证）并由项目负责人确认收口（2026-07-31）；V2.8.0 待发布并打 tag v2.8.0（SciencePlots + Seaborn + EasyPPTX；_HEADER 集成 scienceplots 样式 + sns.set_theme，_build_chart_code 升级为 sns API，CORRELATION 分析新增热图；ppt_renderer 新增 _pct_to_emu + _GridHelper 辅助方法，改造 _place_chart_* 使用 Grid；沙箱白名单新增 scienceplots/seaborn；新增 45 个专用测试，204 passed 零回归 + 前端 lint/build 通过；引入 3 个新依赖 scienceplots/seaborn/easypptx，不改变 PptConfig 合同）。V2.8.1 阶段：SPEC 0028（Nature 风格图表集成，移除 SciencePlots，引入 nature-figure 设计规则）已完成实现与测试验收并由项目负责人确认收口（2026-07-31）；V2.8.1 待发布并打 tag v2.8.1（_HEADER 移除 `import scienceplots` 和 `plt.style.use(...)`，新增 nature-figure rcParams 配置：去右框/顶框 + 粗轴线 + 无图例边框 + 高分辨率输出；deepseek_code_task_provider 同步更新 _SYSTEM_PROMPT；python_executor 的 DEFAULT_ALLOWED_IMPORTS 移除 scienceplots；pyproject.toml 移除 scienceplots 依赖声明；修改 5 个受影响测试 C1/C2/C3/S1/S4 + 修复遗漏测试 test_default_allowed_imports_content，204 passed 零回归 + 3 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染；移除 1 个依赖 scienceplots，不引入新依赖，不改变 PptConfig 合同，保留 Seaborn + _GridHelper + 中文字体支持）。V2.9.0 阶段：SPEC 0029（端到端集成验收：验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通，8 步主路径覆盖项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成）已由项目负责人确认收口（2026-07-31）；V2.9.0 待发布并打 tag v2.9.0（新建 `server/scripts/verify_spec0029_e2e.py` 验收脚本，复用 worker_e2e_verify.py 架构；测试数据 gastric_health_data.csv 200 行 15 列 + gastric_reference.pdf 最小 PDF 放到 server/data/spec0029_e2e/；Provider=local_rule 避免 API 网络波动；E2E_RESULT=PASS，8 步主路径全部通过，项目状态推进到 COMPLETED；Word 332468 bytes/103 段落 + PPT 334411 bytes/8 幻灯片 + 9 图表 + 5 表格；修复 2 项集成断点：pd.to_numeric(errors='ignore') → errors='coerce' + list_execution_runs 元组解包；1100 passed 零回归；不引入新依赖，不改变 owner 边界，不改变 API 合同，不修改数据库 schema；浏览器验收跳过——V2.5.0~V2.8.1 纯后端切片无前端改动，前序 SPEC 0021/0022 已覆盖关键 UI 路径）。后续新切片开始前仍需先编写并确认新 SPEC。

## 规划文件归属

具体文件只能在技术栈确认后的代码阶段创建。规划归属如下：

- `apps/web/`：前端工作台，负责页面、用户输入、状态展示和下载入口。
- `apps/api/`：后端 API 适配层，负责 HTTP 映射，不拥有核心语义。
- `packages/core/` 或 `server/app/core/`：项目、需求、证据、数据、执行、交付物核心归属层。
- `packages/contracts/` 或 `server/app/contracts/`：结构化 schema 和 DTO。
- `server/app/llm/`：统一大模型网关。
- `server/app/ingestion/`：公开 URL 和本地文件资料入口。
- `server/app/parsing/`：PDF、Word、网页、表格解析。
- `server/app/execution/`：受控 Python 执行器。
- `server/app/deliverables/`：Word/PPT 生成。
- `tests/`：合同测试、核心单元测试、集成验收测试。
- `dev-docs/`：架构、验收、实施计划、决策记录。

具体目录必须在技术栈 ADR 中锁定后再创建。

## 任务 0：锁定剩余前置条件

**文件：**

- 修改：`dev-docs/README.md`
- 已创建：`dev-docs/decisions/0004-lock-technology-stack.md`
- 已创建：`dev-docs/decisions/0005-lock-v1-project-identity-and-demo.md`
- 已创建：`dev-docs/decisions/0006-code-stage-approval.md`
- 已创建：`dev-docs/dependency-review.md`

- [x] 确认项目规范目录名为 `lab-report-assistant`。
- [x] 确认采用 V1 技术主线。
- [x] 确认第一版采用本地单用户版本。
- [x] 确认第一版不做注册登录。
- [x] 确认第一版不做在线多用户账号体系。
- [x] 确认首个标准演示课题为“胃病数据分析”。
- [x] 确认“胃病数据分析”的样例数据来源。
- [x] 确认 V1 大模型供应商暂定为 DeepSeek。
- [x] 完成代码阶段前依赖版本和官方目录规范复核。
- [x] 写入技术栈决策记录。
- [x] 写入 V1 项目标识、登录边界与演示课题决策记录。
- [x] 获得代码阶段批准决策记录。
- [x] 记录代码阶段批准当轮暂停执行，并由决策 0007 承接为正式执行。

## 任务 1：仓库与框架脚手架

**文件：** 代码阶段确认后创建。

**执行规格：** [specs/0001-project-workspace-and-scaffold.md](specs/0001-project-workspace-and-scaffold.md)

- [x] 初始化前后端项目结构。
- [x] 建立当前可用的 lint、test、build 命令；第一切片暂无独立 format 命令。
- [x] 建立 `.env.example`，但不写入真实密钥。
- [x] 建立最小健康检查和版本信息。
- [x] 更新 `dev-docs/README.md` 的命令索引。
- [x] 运行测试、构建和前后端联通门禁。

## 任务 2：核心合同

**文件：** 代码阶段确认后创建。

- [x] 定义 `ProjectStatus` 和项目创建/列表/详情最小合同。
- [x] 定义 `RequirementPlan`、`ReplicationLevel`。
- [x] 定义最小 `RequirementSource` 和 `ChangeRecord`。
- [x] 定义 `SourceRecord`、`EvidenceCard`、`DatasetVersion`。（SourceRecord、EvidenceCard 在 SPEC 0003 实现；DatasetVersion 在 SPEC 0004 实现）
- [x] 定义 `AnalysisPlan`、`CodeTask`、`ExecutionRun`。（AnalysisPlan 在 SPEC 0004 实现；CodeTask/ExecutionRun 在 SPEC 0005 实现）
- [x] 定义 `Outline`、`Deliverable`。（SPEC 0006 实现，含 DeliverableVersion）
- [x] 为每个合同写 schema 或类型测试。（各 SPEC 均有 service/API/渲染器测试套件覆盖）
- [x] 在需求任务单中区分模型建议、本地规则候选、未知项和超范围任务。

## 任务 3：项目工作区核心

**文件：** 代码阶段确认后创建。

- [x] 创建实验项目。
- [x] 保存课题和阶段状态。
- [x] 创建受控项目工作区目录。
- [x] 保存需求来源、任务单生成、任务单修改、任务单确认的最小变更记录。
- [x] 支持项目状态查询。
- [x] 支持需求阶段从 `DRAFT` 推进到 `REQUIREMENT_PARSED` 和 `REQUIREMENT_CONFIRMED`。
- [ ] 支持工作流阶段回退。（V2.0 待办：当前架构为单向推进 + STALE 传播，未实现阶段回退）
- [x] 测试状态不能跳过必需人工确认点。（各 SPEC API 测试覆盖状态机前置校验，如 OUTLINE_NOT_GENERATABLE、PROJECT_EVIDENCE_NOT_CONFIRMED、PROJECT_NO_SUCCESSFUL_EXECUTION_RUN 等）

## 任务 4：实验要求拆解

**文件：** 代码阶段确认后创建。

- [x] 支持 Word 要求上传和文本粘贴。
- [x] 保留原始要求内容。
- [x] 通过 LLM Gateway 生成结构化任务单候选。
- [x] 校验任务单 schema。
- [x] 支持用户确认或修改任务单。
- [x] 生成 L0/L1/L2/L3 判断，L3 标记为第一版超范围。

## 任务 5：来源与证据工作流

**文件：** 已在 SPEC 0003 切片中实现。

- [x] 支持公开 URL 资料登记。
- [x] ~~支持本地 PDF、Word、TXT、CSV、Excel 文件登记。~~（SPEC 0003 仅实现 PDF 文件登记；Word/TXT/CSV/Excel 推迟到数据集工作流切片）
- [x] 保存采集状态和原始文件位置。
- [x] 解析公开网页、公开 PDF 和文本资料。
- [x] 通过 LLM Gateway 生成证据卡片候选。
- [x] 保存证据来源位置和用户确认状态。
- [x] 对登录、验证码、付费限制返回结构化拒绝原因。

## 任务 6：数据集工作区

**文件：** 已在 SPEC 0004 切片中实现。

- [x] 上传 CSV 或 Excel。
- [x] 保存原始数据版本。
- [x] 生成字段、类型、样例、缺失值、重复值和基础质量概览。
- [x] 生成清洗建议和分析方案候选。
- [x] 支持用户确认或修改分析方案。
- [x] 保存数据版本和方案版本之间的关联。

## 任务 7：受控 Python 执行

**文件：** `server/app/infrastructure/sandbox/python_executor.py`、`server/app/modules/execution/`、`server/app/api/routers/code_tasks.py`、`server/app/api/routers/execution_runs.py`、`server/worker/handlers.py`、`server/alembic/versions/0005_create_execution_tables.py`。

**对应 SPEC：** [specs/0005-controlled-python-execution.md](specs/0005-controlled-python-execution.md)，已完成实现与端到端验收并由项目负责人确认收口。

- [x] 展示待执行 Python 代码。
- [x] 支持用户编辑代码。
- [x] 限制执行目录、时间、资源和输出位置。
- [x] 保存 stdout、stderr、退出状态、表格和图表产物。
- [x] 失败时保存失败记录，不覆盖为成功。
- [x] 每个结果关联代码版本和数据版本。

## 任务 8：大纲核心

**文件：** `server/app/modules/outlines/`、`server/app/modules/llm/outline_provider.py`、`server/app/api/routers/outlines.py`、`server/worker/handlers.py`、`server/alembic/versions/0006_create_outline_and_deliverable_tables.py`。

**对应 SPEC：** [specs/0006-outline-and-deliverables.md](specs/0006-outline-and-deliverables.md)，实现已完成并由项目负责人确认收口。

- [x] 根据任务单、证据卡片、数据概览、分析方案和执行结果生成统一大纲。
- [x] 标记每个大纲段落的来源类型。
- [x] 支持用户确认或修改大纲。
- [x] 修改要求或分析结果后，标记大纲失效。

## 任务 9：Word 与 PPT 交付物

**文件：** `server/app/infrastructure/renderers/word_renderer.py`、`server/app/infrastructure/renderers/ppt_renderer.py`、`server/app/api/routers/deliverables.py`、`server/worker/handlers.py`。

**对应 SPEC：** [specs/0006-outline-and-deliverables.md](specs/0006-outline-and-deliverables.md)，实现已完成并由项目负责人确认收口。

- [x] 从已确认大纲生成 Word。
- [x] 从同一份已确认大纲生成 PPT。
- [x] Word 和 PPT 共享关键数据、图表和结论来源。
- [x] 生成可下载文件。
- [x] 保存交付物版本和追溯索引。
- [x] 支持重新生成。

## 任务 10：端到端验收

**文件：** `server/worker_e2e_verify.py`、`dev-docs/e2e-acceptance-report-v1.0.md`、`dev-docs/acceptance.md`。

**对应 SPEC：** V1.0 闭环验收（SPEC 0001-0006 端到端），已完成并通过。

- [x] 准备"胃病数据分析"标准实验样例。
- [x] 从创建项目跑到 Word/PPT 下载。
- [x] 验证资料性结论能追溯到来源。
- [x] 验证实验性结论能追溯到执行记录。
- [x] 验证 L3 或受限资源被拒绝或降级。
- [x] 更新 `dev-docs/acceptance.md` 的证据记录。

**验收方式说明：** V1.0 端到端验收通过 `worker_e2e_verify.py` 脚本（proj_6c52304bf9fb 完整流转 RESULT_CONFIRMED → COMPLETED，Word 37032 bytes、PPT 32231 bytes）+ API 测试套件（覆盖 source_type/source_ids 追溯链、SOURCE_URL_NOT_PUBLIC/SOURCE_ACCESS_RESTRICTED 拒绝路径）+ e2e-acceptance-report-v1.0.md（16 项验收全部通过）完成。未做手动 UI 点击端到端（因无 in-app Browser 工具，已记录为非阻断债务，以 Vitest 411 个组件测试作为替代证据）。

## SPEC 0041 实施回写

SPEC 0041 已完成实现与真实文件验收：以 `figure_planner.py` 为唯一图形语义 owner，新增图形家族、异构组合计划和结构化拒绝候选；论文案例实际组合统计、流程、关系、矩阵和证据论证五个图形家族。Word/PDF 与两套 PPT 消费同一套 artifact 编排元数据，分别生成 19 页 A4 PDF 和 17 页答辩 PPT；全量后端 1173 项测试、Alembic、前端 lint/build 均通过。当前等待项目负责人确认成品视觉结果后收口，详细证据见 [acceptance.md](acceptance.md) 的 SPEC 0041 记录。

## 覆盖关系

| 立项要求 | 计划任务 |
| --- | --- |
| 项目空间 | 任务 3 |
| 实验要求输入与拆解 | 任务 4 |
| L0-L3 复刻分级 | 任务 4 |
| 公开 URL 与本地文件 | 任务 5 |
| 证据卡片 | 任务 5 |
| 数据工作区 | 任务 6 |
| 受控 Python 执行 | 任务 7 |
| 实验大纲 | 任务 8 |
| Word/PPT 生成 | 任务 9 |
| 端到端验收 | 任务 10 |

## 停止条件

本计划文档完成的停止条件是：项目负责人能从该计划判断第一阶段如何从文档进入代码，并且每个任务都能映射回 `project-charter.md` 的范围和 `acceptance.md` 的验收门禁。

## SPEC 0042 实施回写

SPEC 0042 已完成本地实现与验收，等待项目负责人查看视觉样例后确认收口。实现建立开放许可科研资产注册表、许可/哈希/SVG 安全闸、CC0 首批资产、`ScientificSchematicSpec` 和确定性 renderer；同一产物已接入正式 Word/PDF 和 academic PPT。定向 81 passed、全量后端 1215 passed、Alembic、前端 lint/build、Windows 与 Docker SVG 转换、PDFium PDF 页面渲染以及 PowerPoint 原生页面导出均通过。禁止把该能力扩展为受限素材抓取、水印绕过、任意 SVG 执行或未经证据确认的医学机制图。

## SPEC 0044 实施回写

SPEC 0044 已完成本地实现、真实成品生成和逐页视觉复核，当前工作项停在项目负责人确认成品风格后收口。

- 唯一 owner 仍为 server/app/modules/outlines/document_planner.py 的论文计划与 server/app/infrastructure/renderers/word_renderer.py 的 DOCX 适配。
- 正式论文采用作者/单位封面、结构化中英文摘要、连续章节分页、分层书签目录、分开的图目录/表目录、全局图/表编号、REF/PAGEREF 回指、图表组合版式和重复表头；正文继续隐藏工程追溯字段。
- SPEC 0044 定向测试 9 passed；后端全量 1235 passed in 67.78s；Alembic、前端 lint/build 通过。
- 真实 spec0043_publication.docx/pdf 来自同一轮生成，PDF 为 A4 19 页；Poppler 已生成 19 张 PNG，并检查联系图及前置第 1—7 页、正文第 8、10、12、14、17 页，未发现空白页、裁切、重叠、题注错位或正文起始页码异常。
- Windows ACL helper 仍不能直接读取 PNG；视觉复核使用 Poppler 实际 PNG 与当前视觉上下文完成，证据位于 server/dev-docs/e2e-screenshots/spec0044_frontmatter_qa_20260821/。
- 停止条件：项目负责人确认成品风格后再进行精确 git 收口；本轮禁止 stage、commit、push。


## SPEC 0045 实施回写

SPEC 0045 已完成统计完整性修订：分析脚本现在按患者首记录形成主队列，排除死亡/临终关怀首记录，区分 HbA1c 已检测/明确未检测/真正缺失，加入主要诊断分层和 HbA1c 交互，并提供患者聚类稳健标准误与两组敏感性分析。正式论文配置统一声明教学性论文复核报告（非独立研究论文），补齐结构化中英文摘要、模型合同、变量编码、软件版本、文献、图表注释和敏感性分析表。

实际生成命令退出码 0；定向测试 10 passed；Word/PDF/manifest 同轮生成，PDF 21 页。由于当前环境缺少 pdf2image/Poppler、LibreOffice，且 Windows ACL/剪贴板替代路径不可用，逐页 PNG 视觉验收未宣称完成。当前不 stage、commit 或 push，等待项目负责人查看 PDF 并确认收口。



## SPEC 0046 实施回写

SPEC 0046 已完成 Windows x64 portable bundle 的首版实现：根目录 one-file 启动器负责用户数据目录、端口、后端/Worker 子进程和浏览器打开；service/ 目录承载 PyInstaller one-directory 服务、Alembic、科学计算依赖和 sandbox_runner.exe；web/ 目录承载前端生产构建；发布 manifest 记录文件哈希。

- [x] 新增 Windows 启动器、服务入口、SPA 静态回退和构建脚本。
- [x] 运行数据隔离到 %LOCALAPPDATA%\\LabReportAssistant，服务绑定 127.0.0.1。
- [x] 启动时自动迁移 SQLite，健康检查通过后打开浏览器。
- [x] 增加可见运行窗口和退出入口，退出时回收本轮服务进程。
- [x] 明确 PyInstaller 为构建期依赖，不改变应用运行时依赖合同。
- [x] 完成服务目录和根 EXE 黑盒冒烟。
- [ ] 在没有 Python、Node.js、Docker 的独立 Windows x64 主机完成最小业务路径和 Word/PPT 下载验收。
- [x] 已修复 one-file 外层自动关闭退出码 1：根因是 ctypes 自定义 WNDPROC/可选浏览器调用，改用系统 STATIC 窗口消息循环后正式 EXE 退出码为 0。
## SPEC 0047 项目进度投影与统一工作台迁移复核（2026-08-23）

本轮锁定并实现项目进度投影合同：项目阶段和顺序由 `server/app/modules/projects/` 负责，投影由 `server/app/modules/projects/projection.py` 负责，HTTP 仅映射现有 `GET /api/projects/{project_id}/workspace-projection`，前端只消费规范投影。`current`、`phases`、`recommended_next_action`、阶段/步骤状态、`is_open`、`open_reason`、`blocking_reasons`、`actions`、`recovery_action`、展示文案和 `command_id` 已加入同一响应；旧的 `current_stage`、`next_action`、`stages` 保留为兼容投影。`COMPLETED` 项目的 `next_action` 与 `recommended_next_action` 均为 `null`，失败/阻断事实不会被完成 rank 覆盖。

前端已将 Sources、Evidence、Dataset、Analysis、Execution、Outline、Deliverable 七个工作区接入统一 `WorkspaceShell`，移除目标生产页面的项目级重复状态顺序和入口门控；RequirementWorkspaceView 仅保留原有项目状态展示，不强行改造。投影合同测试、前端全量测试、lint/build 和 Alembic 迁移已验证；后端全量仍受既有科研资产 hash 漂移影响，浏览器视觉、LibreOffice runtime 和干净 Windows 验收仍未闭合。