# 实验报告助手｜开发真源索引

本文档是项目内部真源入口。后续产品设计、任务拆解、技术选型、代码实现和验收工作，必须先读取本索引和当前有效文档。

## 当前阶段

- 阶段：代码阶段
- 状态：V1.0.0 已发布并打 tag v1.0.0。V1.1.0 已发布并打 tag v1.1.0：SPEC 0007（真实 DeepSeek LLM 接入）、SPEC 0009（前端测试覆盖补全，411 个测试全部通过）、SPEC 0010（Word 模板支持，后端 623 + 前端 411）、SPEC 0011（PPT 配置选项，后端 646 + 前端 411，新增 23 个后端测试）、SPEC 0012（数据保留周期配置，后端 704 passed，新增 58 个测试）均已由项目负责人确认收口。V1.1.0 端到端回归验收三道门禁全部通过（commit `e0d37ec`）。V1.2.0 已发布并打 tag v1.2.0：SPEC 0013（Docker 化部署，commit `c210911`）、SPEC 0014（LLM 调用缓存，commit `31ec6cd`，后端 729 passed 新增 25 测试）、SPEC 0015（GitHub Actions CI 流水线，commit `e203ac2`，CI Run #2/#3 全绿）均已由项目负责人确认收口。V1.2.0 端到端回归验收三道门禁全部通过（后端 729 + 前端 411 + worker_e2e E2E_RESULT=PASS + 关键回归点 63 passed）。V1.3.0 已发布并打 tag v1.3.0：SPEC 0016（技术债务清理 TD-004/005/006/008，后端 736 passed 新增 7 测试，Docker 容器内科学计算包导入验证通过）已由项目负责人确认收口。V1.4.0 已发布并打 tag v1.4.0：SPEC 0017（单用户前端实时编辑反馈，纯前端切片，前端 434 passed 新增 23 测试 + 后端 736 passed 零回归）已由项目负责人确认收口。V2.0.0 已发布并打 tag v2.0.0：SPEC 0018（流式 LLM 输出，任务单生成 SSE 流式化，后端 783 passed 新增 47 测试 + 前端 468 passed 新增 34 测试，不引入新依赖，不修改数据库 schema）已由项目负责人确认收口。V2.1.0 已发布并打 tag v2.1.0：SPEC 0019（大纲生成流式化，后端 821 passed 新增 38 测试 + 前端 493 passed 新增 25 测试，SSE 端点绕过 Worker，上下文聚合提取到 service 层，复用 SPEC 0018 stream-sse.ts，不引入新依赖，不修改数据库 schema）已由项目负责人确认收口。V2.2.0 已发布并打 tag v2.2.0：SPEC 0020（证据卡片生成流式化，后端 858 passed 新增 37 测试 + 前端 519 passed 新增 26 测试，SSE 端点绕过 Worker，Provider 输入为单文档 parsed_text 无需上下文聚合提取，复用 SPEC 0018/0019 stream-sse.ts 和降级策略，不引入新依赖，不修改数据库 schema）已由项目负责人确认收口。V2.3.0 SPEC 0021（分析方案生成流式化，后端 895 passed 新增 37 测试 + 前端 546 passed 新增 27 测试，SSE 端点绕过 Worker，Provider 输入为 DatasetProfile 无需上下文聚合提取，复用 SPEC 0018/0019/0020 stream-sse.ts 和降级策略，不引入新依赖，不修改数据库 schema；收口复核修复 LocalRuleAnalysisPlanProvider 输出 target_fields 为字符串导致前端 PlanCard TypeError 阻断问题）已由项目负责人确认收口。V2.4.0 已发布并打 tag v2.4.0：SPEC 0022（代码任务生成流式化，后端 975 passed 新增 80 测试 + 前端 570 passed 新增 19 测试，SSE 端点绕过 Worker，Provider 输入为 AnalysisPlan 无需上下文聚合提取，复用 SPEC 0018/0019/0020/0021 stream-sse.ts 和降级策略，不引入新依赖，不修改数据库 schema；收口复核修复 LocalRuleCodeTaskProvider 中 FREQUENCY 类型 target_fields.split() 在 list 上报错阻断问题）已由项目负责人确认收口（2026-07-30）。V2.5.0 SPEC 0024（PPT 渲染器布局与视觉层次改进，16:9 画布 + 空白版式精确定位 + 双栏内容页 40%/60% + 图表自适应布局 + 五级字号体系 + 主题色扩展应用；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法；端到端视觉测评修复图表中文乱码/PPT 页数限制/图片溢出/3 图布局/文本截断 5 项阻断问题；后端 41+142 passed 零回归 + 前端 lint/build 通过）已由项目负责人确认收口（2026-07-31）。V2.6.0 SPEC 0025（PPT 三角色彩系统与深浅对比三明治结构，从单一 theme_color 用 colorsys 标准库派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法；新增 16 个专用测试，57+222+83 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过）已由项目负责人确认收口（2026-07-31）。V2.7.0 SPEC 0026（PPT 视觉效果增强，渐变填充 + 圆角矩形 + 外阴影 + 细边框；python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；新增 17 个专用测试，220 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部视觉效果方法）已由项目负责人确认收口（2026-07-31）。V2.8.0 SPEC 0027（图表美化与布局增强，SciencePlots + Seaborn + EasyPPTX；_HEADER 集成 scienceplots 样式 + sns.set_theme，_build_chart_code 升级为 sns.histplot/boxplot/countplot/scatterplot/heatmap，CORRELATION 分析新增热图；ppt_renderer 新增 _pct_to_emu 百分比定位 + _GridHelper N×M 网格辅助类，改造 _place_chart_grid/side_by_side/three 使用 Grid 坐标与原硬编码完全一致；沙箱白名单新增 scienceplots/seaborn；新增 45 个专用测试，204 passed 零回归 + 5 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染 + Grid 布局 8/8 对齐验证；引入 3 个新依赖 scienceplots/seaborn/easypptx，不改变 PptConfig 合同）已由项目负责人确认收口（2026-07-31）。V2.8.1 SPEC 0028（Nature 风格图表集成，移除 SciencePlots，引入 nature-figure 设计规则；用 matplotlib rcParams 手动配置替换 plt.style.use，保留 Seaborn + _GridHelper；移除 1 个依赖 scienceplots，不引入新依赖，不改变 PptConfig 合同；修改 5 个受影响测试 C1/C2/C3/S1/S4 + 修复遗漏测试 test_default_allowed_imports_content，204 passed 零回归 + 3 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染）已由项目负责人确认收口（2026-07-31）。V2.9.0 SPEC 0029（端到端集成验收：验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通，8 步主路径覆盖项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成；新建 verify_spec0029_e2e.py 验收脚本，E2E_RESULT=PASS，8 步主路径全部通过，1100 passed 零回归，Word/PPT 真实文件验证通过；修复 2 项集成断点：pd.to_numeric(errors='coerce') + list_execution_runs 元组解包；不引入新依赖，不改变 owner 边界，不改变 API 合同，不修改数据库 schema；浏览器验收跳过——纯后端切片无前端改动）已由项目负责人确认收口（2026-07-31）。当前活跃可记录债务：TD-009（浏览器验收截图未持久化，非阻断）。
- 下一阶段入口：V2.8.0 SPEC 0027（图表美化与布局增强：SciencePlots + Seaborn + EasyPPTX）已由项目负责人确认收口（2026-07-31，详见 [决策 0036](decisions/0036-start-spec-0027-chart-beautification.md)）。V2.8.1 SPEC 0028（Nature 风格图表集成：移除 SciencePlots，引入 nature-figure 设计规则；用 rcParams 替换 plt.style.use，保留 Seaborn + _GridHelper；修改 5 个测试，不引入新依赖，不改变 PptConfig 合同）已由项目负责人确认收口（2026-07-31，详见 [决策 0037](decisions/0037-start-spec-0028-nature-figure.md)）。V2.9.0 SPEC 0029（端到端集成验收：验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通，8 步主路径覆盖项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成；不引入新功能，不改变 owner 边界）已由项目负责人确认收口（2026-07-31，详见 [决策 0038](decisions/0038-start-spec-0029-e2e-acceptance.md)，E2E_RESULT=PASS，1100 passed 零回归）。项目当前活跃可记录债务为 TD-009（非阻断）。技术债务总清单见 [tech-debt-inventory.md](tech-debt-inventory.md)

## 工程入口

当前并行推进：V2.10.0 SPEC 0030、SPEC 0031、SPEC 0032 已完成实现与验收；SPEC 0033 论文级自适应版式与语义布局规划器已完成实现与验收；SPEC 0034 正式论文 Word/PDF 与高级答辩 PPT 已获项目负责人确认并完成实现与验收；SPEC 0035 大样本公开论文解读案例已完成实现与预览验收，见决策 0044；SPEC 0036 论文解读深度整改已完成实现与验收，见决策 0045；SPEC 0037 语义图表选择与 PPT 组件优化已完成实现与验收，见决策 0046；SPEC 0038 正式学术论文规范化改造已完成实现与视觉验收，待项目负责人确认收口，见决策 0047；SPEC 0039 论文级多语义图形系统已完成实现与真实视觉验收，待项目负责人确认收口，见决策 0048；SPEC 0040 期刊级论证图表与论文视觉语法改造已完成实现与真实视觉验收，待项目负责人确认收口，见决策 0049；SPEC 0041 论文级异构图形编排与语义选图系统已完成实现与真实视觉验收，待项目负责人确认收口，见决策 0050；SPEC 0042 开放许可科研图形资产库与科研示意图组件系统已完成实现与本地验收，待项目负责人查看视觉样例后确认收口，见决策 0051。
当前切片：SPEC 0045 已完成统计完整性修订、真实 DOCX/PDF/manifest 生成和定向测试；本轮明确把案例定位为教学性论文复核报告，不是独立研究论文。PDF 共 21 页，Word→PDF 导出和结构验收通过；因环境缺少 pdf2image/Poppler、LibreOffice，且 Windows ACL/剪贴板替代路径不可用，21 页 PNG 逐页视觉验收仍待项目负责人查看或补充渲染工具后完成。详见 acceptance.md 和 SPEC 0045。

- [../server/](../server/)：后端 FastAPI 服务
- [../apps/web/](../apps/web/)：前端 React 工作台
- [commands.md](commands.md)：实际运行命令索引
- [../skills/VENDOR.md](../skills/VENDOR.md)：外部 vendored skill/plugin 说明

## 当前真源

- [project-charter.md](project-charter.md)：已确认锁定的项目立项文档，是当前最高优先级产品真源。
- [project-initiation.md](project-initiation.md)：Sliver 启动门禁兼容入口，只指向 `project-charter.md`，不维护第二份产品真相。
- [architecture.md](architecture.md)：当前架构主线、唯一归属层、核心合同、禁止路径和技术主线建议。
- [tech-stack.md](tech-stack.md)：已确认锁定的 V1 技术栈、框架边界、Worker、Python 受控执行环境和重新评估条件。
- [dependency-review.md](dependency-review.md)：代码阶段开始前的依赖版本、DeepSeek 模型、样例数据和官方目录规范复核。
- [commands.md](commands.md)：实际运行命令索引，由代码阶段脚手架创建后维护。
- [acceptance.md](acceptance.md)：阶段门禁、证据要求、停止条件和漂移锁。
- [implementation-plan.md](implementation-plan.md)：进入代码阶段后的任务拆解计划，已用于执行 SPEC 0001；后续切片仍需先确认范围。
- [specs/0001-project-workspace-and-scaffold.md](specs/0001-project-workspace-and-scaffold.md)：第一开发切片 SPEC，限定脚手架与项目工作区最小闭环。
- [specs/0002-requirement-input-and-task-plan.md](specs/0002-requirement-input-and-task-plan.md)：第二开发切片 SPEC，限定实验要求输入、结构化任务单和 L0-L3 判断。
- [specs/0003-sources-and-evidence-workflow.md](specs/0003-sources-and-evidence-workflow.md)：第三开发切片 SPEC，限定公开 URL 与 PDF 来源、后台任务、证据卡片工作流。
- [specs/0004-dataset-workspace.md](specs/0004-dataset-workspace.md)：第四开发切片 SPEC，限定数据集上传与解析、字段概览、分析方案候选、用户确认状态。
- [specs/0005-controlled-python-execution.md](specs/0005-controlled-python-execution.md)：第五开发切片 SPEC，限定受控 Python 执行环境、CodeTask/ExecutionRun/ExecutionArtifact 核心合同、状态推进到 RESULT_CONFIRMED。
- [specs/0006-outline-and-deliverables.md](specs/0006-outline-and-deliverables.md)：第六开发切片 SPEC，限定统一实验大纲、Word/PPT 交付物生成、Deliverable/DeliverableVersion 核心合同、状态推进到 COMPLETED。
- [decisions/0001-lock-project-charter.md](decisions/0001-lock-project-charter.md)：锁定立项文档为后续工作依据的决策记录。
- [decisions/0002-enter-architecture-planning.md](decisions/0002-enter-architecture-planning.md)：进入架构与开发计划阶段的决策记录。
- [decisions/0003-document-language.md](decisions/0003-document-language.md)：项目自有文档必须使用中文的决策记录。
- [decisions/0004-lock-technology-stack.md](decisions/0004-lock-technology-stack.md)：锁定 V1 技术栈和本地单用户部署主线的决策记录。
- [decisions/0005-lock-v1-project-identity-and-demo.md](decisions/0005-lock-v1-project-identity-and-demo.md)：锁定项目规范目录名、V1 不做注册登录和首个演示课题的决策记录。
- [decisions/0006-code-stage-approval.md](decisions/0006-code-stage-approval.md)：记录代码阶段曾获批准但当轮暂停执行的历史决策，已由决策 0007 承接为正式执行。
- [decisions/0007-code-stage-execution-started.md](decisions/0007-code-stage-execution-started.md)：记录代码阶段正式启动执行的决策记录。
- [decisions/0008-confirm-spec-0001-acceptance.md](decisions/0008-confirm-spec-0001-acceptance.md)：确认 SPEC 0001 第一开发切片验收通过的决策记录。
- [decisions/0009-start-spec-0002-requirements.md](decisions/0009-start-spec-0002-requirements.md)：启动 SPEC 0002 实验要求输入与结构化任务单切片的决策记录。
- [decisions/0010-project-specific-agent-constitution.md](decisions/0010-project-specific-agent-constitution.md)：将根目录 `AGENTS.md` 从通用模板收敛为项目级宪法的决策记录。
- [decisions/0011-version-control-after-version-completion.md](decisions/0011-version-control-after-version-completion.md)：规定每完成一版或一个已确认开发切片后，必须进行一次 git 提交与远程上传收口。
- [decisions/0012-lock-git-remote.md](decisions/0012-lock-git-remote.md)：锁定当前项目远程仓库为 GitHub 上的 `YiFanAWA/lab-report-assistant`。
- [decisions/0013-confirm-spec-0002-acceptance.md](decisions/0013-confirm-spec-0002-acceptance.md)：确认 SPEC 0002 第二开发切片复核验收通过并进入版本控制收口。
- [decisions/0014-start-spec-0003-sources-and-evidence.md](decisions/0014-start-spec-0003-sources-and-evidence.md)：启动 SPEC 0003 公开资料与证据工作流切片的决策记录。
- [decisions/0015-start-spec-0004-dataset-workspace.md](decisions/0015-start-spec-0004-dataset-workspace.md)：启动 SPEC 0004 数据集工作区切片的决策记录。
- [decisions/0016-start-spec-0005-controlled-python-execution.md](decisions/0016-start-spec-0005-controlled-python-execution.md)：启动 SPEC 0005 受控 Python 执行切片的决策记录。
- [decisions/0017-start-spec-0006-outline-and-deliverables.md](decisions/0017-start-spec-0006-outline-and-deliverables.md)：启动 SPEC 0006 大纲与交付物切片的决策记录。
- [decisions/0018-frontend-test-framework.md](decisions/0018-frontend-test-framework.md)：引入 Vitest + React Testing Library 前端测试框架的决策记录。
- [decisions/0019-deepseek-llm-integration.md](decisions/0019-deepseek-llm-integration.md)：接入真实 DeepSeek LLM 的决策记录（V1.1.0 SPEC 0007）。
- [decisions/0020-start-spec-0014-llm-cache.md](decisions/0020-start-spec-0014-llm-cache.md)：启动 SPEC 0014 LLM 调用缓存切片的决策记录。
- [decisions/0021-start-spec-0015-github-actions-ci.md](decisions/0021-start-spec-0015-github-actions-ci.md)：启动 SPEC 0015 GitHub Actions CI 流水线切片的决策记录。
- [decisions/0022-start-spec-0016-tech-debt-cleanup.md](decisions/0022-start-spec-0016-tech-debt-cleanup.md)：启动 SPEC 0016 技术债务清理切片（TD-004/005/006/008）的决策记录。
- [decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md](decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md)：启动 SPEC 0017 单用户前端实时编辑反馈切片的决策记录（方向 A，不引入多用户协作、不引入 WebSocket/SSE 实时通信基础设施）。
- [decisions/0024-start-spec-0018-streaming-llm-output.md](decisions/0024-start-spec-0018-streaming-llm-output.md)：启动 SPEC 0018 流式 LLM 输出切片的决策记录（API SSE + Gateway 直调，仅任务单生成流式化，保留同步端点兼容，不引入新依赖，不修改数据库 schema）。
- [decisions/0025-start-spec-0019-outline-streaming.md](decisions/0025-start-spec-0019-outline-streaming.md)：启动 SPEC 0019 大纲生成流式化切片的决策记录（SSE 端点绕过 Worker，上下文聚合提取到 service 层，复用 SPEC 0018 流式架构，保留 Worker 异步端点兼容）。
- [decisions/0026-start-spec-0020-evidence-streaming.md](decisions/0026-start-spec-0020-evidence-streaming.md)：启动 SPEC 0020 证据卡片生成流式化切片的决策记录（SSE 端点绕过 Worker，Provider 输入为单文档 parsed_text 无需上下文聚合提取，复用 SPEC 0018/0019 流式架构，保留 Worker 异步端点兼容）。
- [decisions/0027-start-spec-0021-analysis-plan-streaming.md](decisions/0027-start-spec-0021-analysis-plan-streaming.md)：启动 SPEC 0021 分析方案生成流式化切片的决策记录（SSE 端点绕过 Worker，Provider 输入为 DatasetProfile 无需上下文聚合提取，复用 SPEC 0018/0019/0020 流式架构，保留 Worker 异步端点兼容）。
- [decisions/0028-start-spec-0022-code-task-streaming.md](decisions/0028-start-spec-0022-code-task-streaming.md)：启动 SPEC 0022 代码任务生成流式化切片的决策记录（SSE 端点绕过 Worker，Provider 输入为 AnalysisPlan 无需上下文聚合提取，复用 SPEC 0018/0019/0020/0021 流式架构，保留 Worker 异步端点兼容，新增并发保护 active_streams + 服务端取消 request.is_disconnected + 错误分层 + Phase 3 状态复核）。
- [decisions/0029-deepseek-json-tolerance-fix.md](decisions/0029-deepseek-json-tolerance-fix.md)：DeepSeek 任务单 JSON 解析失败容错修复决策记录（Prompt 强化 + Pydantic field_validator 容错，修复 `*_requirements` 返回对象数组与 `suggested_scope` 返回 null 的高频间歇性失败，真实 DeepSeek 5 次复测失败率 60%→0%）。
- [decisions/0030-confirm-spec-0022-acceptance.md](decisions/0030-confirm-spec-0022-acceptance.md)：确认 SPEC 0022 代码任务生成流式化收口的决策记录（V2.4.0，引用决策 0028 验收证据与决策 0029 同期补充验证，本地 commit c4b5fdf + tag v2.4.0 已建，push 待用户确认）。
- [decisions/0031-code-task-execution-link-fixes.md](decisions/0031-code-task-execution-link-fixes.md)：SPEC 0022 代码任务执行链路关键修复决策记录（commit 93f1f13，修复 prompt 换行双重转义、import 白名单缺失、python_executor 路径解析三项阻断问题，整理 httpx 代理/CSV 列匹配/Worker 进程三项链路验证环境注意事项，补充 Worker 执行与文档生成模块单元测试 35 个）。
- [decisions/0032-start-spec-0024-ppt-renderer-layout.md](decisions/0032-start-spec-0024-ppt-renderer-layout.md)：启动 SPEC 0024 PPT 渲染器布局与视觉层次改进切片的决策记录（V2.5.0，16:9 画布 + 空白版式精确定位 + 双栏内容页 + 图表自适应 + 五级字号体系 + 主题色扩展应用；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法）。
- [decisions/0033-confirm-spec-0024-acceptance.md](decisions/0033-confirm-spec-0024-acceptance.md)：确认 SPEC 0024 PPT 渲染器布局与视觉层次改进收口的决策记录（V2.5.0，端到端视觉测评修复图表中文乱码/PPT 页数限制/图片溢出/3 图布局/文本截断 5 项阻断问题；后端 41+142 passed 零回归 + 前端 lint/build 通过；配套修复 code_task_provider 中文乱码）。
- [decisions/0034-start-spec-0025-ppt-color-system.md](decisions/0034-start-spec-0025-ppt-color-system.md)：启动 SPEC 0025 PPT 三角色彩系统与深浅对比三明治结构切片的决策记录（V2.6.0，从单一 theme_color 算法派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；使用 colorsys 标准库，不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法）。
- [decisions/0035-start-spec-0026-ppt-visual-effects.md](decisions/0035-start-spec-0026-ppt-visual-effects.md)：启动 SPEC 0026 PPT 视觉效果增强切片的决策记录（V2.7.0，渐变填充 + 圆角矩形 + 外阴影 + 细边框；python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部视觉效果方法）。
- [decisions/0036-start-spec-0027-chart-beautification.md](decisions/0036-start-spec-0027-chart-beautification.md)：启动 SPEC 0027 图表美化与布局增强切片的决策记录（V2.8.0，SciencePlots + Seaborn + EasyPPTX；_HEADER 集成 scienceplots 样式 + sns.set_theme，_build_chart_code 升级为 seaborn API；ppt_renderer 新增 _pct_to_emu + _GridHelper 辅助方法，改造 _place_chart_* 使用 Grid；沙箱白名单新增 scienceplots/seaborn；引入 3 个新依赖，不改变 PptConfig 合同）。
- [decisions/0037-start-spec-0028-nature-figure.md](decisions/0037-start-spec-0028-nature-figure.md)：启动 SPEC 0028 Nature 风格图表集成切片的决策记录（V2.8.1，移除 scienceplots 依赖，用 nature-figure rcParams 替换 plt.style.use；保留 seaborn + _GridHelper；修改 5 个受影响测试 C1/C2/C3/S1/S4；不引入新依赖，不改变 PptConfig 合同，回归零容忍）。
- [decisions/0038-start-spec-0029-e2e-acceptance.md](decisions/0038-start-spec-0029-e2e-acceptance.md)：启动 SPEC 0029 端到端集成验收切片的决策记录（V2.9.0，验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通；8 步主路径覆盖项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成；新建 verify_spec0029_e2e.py 验收脚本；不引入新功能，不改变 owner 边界，不引入新依赖，不修改数据库 schema；已由项目负责人确认收口，E2E_RESULT=PASS，1100 passed 零回归）。
- [decisions/0039-start-spec-0030-pptxforge-chart-beautification.md](decisions/0039-start-spec-0030-pptxforge-chart-beautification.md)：启动 SPEC 0030 pptxforge 集成与图表美化增强切片的决策记录（V2.10.0，引入 pptxforge 10 主题 + 视觉原语 + Morph 转场；图表美化 NPG 期刊配色 + a/b/c 面板标签 + fill_between 误差带 + 多面板布局；修复 SPEC 0028 dpi 不一致缺陷；PptConfig 扩展为四字段合同（方案 B，新增 theme_preset 可选字段）；不改变 render() 签名，不改变 Provider 接口；引入 1 个新依赖 pptxforge MIT；实现中）。
- [decisions/0040-start-spec-0031-academic-document-visual-quality.md](decisions/0040-start-spec-0031-academic-document-visual-quality.md)：启动 SPEC 0031 论文级 Word/PPT 视觉质量切片（统一 Word 页面/字体/标题/图题/表题/页眉页脚，PPT 图表图注与正文层级，图表字体回退与真实渲染验收；不改变 API、Worker、数据库和渲染入口合同）。
- [decisions/0041-start-spec-0032-ppt-master-sjtu-adapter.md](decisions/0041-start-spec-0032-ppt-master-sjtu-adapter.md)：启动 SPEC 0032 PPT Master 与上海交大模板适配（能力适配，不整仓库嵌入；增加 PPT 工作流模式注册表；不接入校园账号和无关校园功能）。
- [decisions/0042-start-spec-0033-paper-adaptive-layout.md](decisions/0042-start-spec-0033-paper-adaptive-layout.md)：启动 SPEC 0033 论文级自适应版式与语义布局规划器（共享规划器 + PPT/Word 薄渲染适配，不回档已有渲染能力）。
- [decisions/0043-start-spec-0034-formal-thesis-defense-deck.md](decisions/0043-start-spec-0034-formal-thesis-defense-deck.md)：确认并实施 SPEC 0034 正式论文 Word/PDF 与高级答辩 PPT（共享论文/答辩结构规划、正式章节编号、图表追溯和逐页视觉验收）。
- [decisions/0044-start-spec-0035-large-sample-paper-review.md](decisions/0044-start-spec-0035-large-sample-paper-review.md)：启动 SPEC 0035 大样本公开论文解读案例（Diabetes 130-US Hospitals + Strack 2014 开放论文，区分原文结论与本地复核）。
- [decisions/0045-start-spec-0036-paper-review-depth-remediation.md](decisions/0045-start-spec-0036-paper-review-depth-remediation.md)：启动 SPEC 0036 论文解读深度整改（真实复核分析、论文级章节和 12–15 页答辩叙事）。
- [decisions/0046-start-spec-0037-semantic-chart-selection.md](decisions/0046-start-spec-0037-semantic-chart-selection.md)：启动 SPEC 0037 语义图表选择与论文级 PPT 组件优化（按数据语义选择图表，复用现有 `pptxforge` 组件）。
- [decisions/0047-start-spec-0038-formal-academic-paper-normalization.md](decisions/0047-start-spec-0038-formal-academic-paper-normalization.md)：启动 SPEC 0038 正式学术论文规范化改造（论文结构、引用、参考文献、题注和三线表）。
- [decisions/0048-start-spec-0039-semantic-figure-system.md](decisions/0048-start-spec-0039-semantic-figure-system.md)：启动 SPEC 0039 论文级多语义图形系统（共享 `FigurePlan`、研究框架/流程/关系/证据链/数据图语义选择，复用现有 PPT 组件，不新增运行时依赖）。
- [decisions/0049-start-spec-0040-journal-argumentation.md](decisions/0049-start-spec-0040-journal-argumentation.md)：启动 SPEC 0040 期刊级论证图表与论文视觉语法改造（共享 `ArgumentPlan`、证据/结果/边界合同、期刊论证图和双交付物适配，不新增运行时依赖）。
- [decisions/0050-start-spec-0041-heterogeneous-figure-orchestration.md](decisions/0050-start-spec-0041-heterogeneous-figure-orchestration.md)：启动并完成 SPEC 0041 论文级异构图形编排与语义选图系统（以 `FigurePlan`/`ChartPlan` 为唯一 owner，按数据前提组合流程、关系、矩阵、统计、时间线和论证图；已完成实现与真实视觉验收，待项目负责人确认收口）。
- [decisions/0051-start-spec-0042-open-scientific-assets.md](decisions/0051-start-spec-0042-open-scientific-assets.md)：启动 SPEC 0042 开放许可科研图形资产库与科研示意图组件系统（开放许可证与 SVG 安全门禁、资产注册表、自动署名、确定性科研示意图渲染；禁止绕过水印或复制受限素材）。
- [specs/0009-frontend-test-coverage.md](specs/0009-frontend-test-coverage.md)：V1.1.0 前端测试覆盖补全规划（8 模块 API + 9 组件，预计新增 ~189 测试）。
- [specs/0010-word-template-support.md](specs/0010-word-template-support.md)：V1.1.0 Word 模板支持 SPEC（项目级上传、Jinja2 风格占位符、章节循环渲染、无模板降级）。
- [specs/0011-ppt-config-options.md](specs/0011-ppt-config-options.md)：V1.1.0 PPT 配置选项 SPEC（目标页数、预设色板主题色、图表全局开关、配置不持久化）。
- [specs/0012-data-retention.md](specs/0012-data-retention.md)：V1.1.0 数据保留周期配置 SPEC（DATA_RETENTION_DAYS 环境变量、清理脚本、RUNNING job 保护、级联删除）。
- [specs/0013-docker-deployment.md](specs/0013-docker-deployment.md)：V1.2.0 Docker 化部署 SPEC（多阶段镜像构建、docker-compose 三服务编排、volume 数据持久化、nginx 前端托管、不改变业务代码），已由项目负责人确认收口（commit `c210911`）。
- [specs/0014-llm-call-cache.md](specs/0014-llm-call-cache.md)：V1.2.0 LLM 调用缓存 SPEC（独立 SQLite 存储、DeepSeekClient 接入、SHA256 key、默认关闭、不走 Alembic），已完成实现与验收。
- [specs/0015-github-actions-ci.md](specs/0015-github-actions-ci.md)：V1.2.0 GitHub Actions CI 流水线 SPEC（master 触发、后端 pytest + 前端 lint/build 两 Job 并行、不触碰业务代码），已完成实现与 CI 验收（AC-1~6 全部通过）。
- [specs/0016-tech-debt-cleanup-004-005-006-008.md](specs/0016-tech-debt-cleanup-004-005-006-008.md)：V1.3.0 技术债务清理 SPEC（TD-004 科学计算包声明、TD-005 AGENTS.md 债务清单更新、TD-006 acceptance.md 浏览器验收说明、TD-008 worker_e2e_verify.py 参数化），已完成实现与验收（AC-1~20 全部通过）。
- [specs/0017-frontend-realtime-edit-feedback.md](specs/0017-frontend-realtime-edit-feedback.md)：V1.4.0 单用户前端实时编辑反馈 SPEC（三个 update mutation 乐观更新 + 错误回滚 + onSettled invalidate；保存按钮新增"已保存 ✓"成功提示；§3.4 短时轮询经实现前调研保持现状不重复实现；纯前端切片不修改后端），已完成实现与验收（前端 434 passed 新增 23 测试 + 后端 736 零回归）。
- [specs/0018-streaming-llm-output.md](specs/0018-streaming-llm-output.md)：V2.0.0 流式 LLM 输出 SPEC（任务单生成 SSE 流式化，API SSE + Gateway 直调，DeepSeekClient.stream_chat_completion + Provider.stream_draft + Service.stream_generate_plan + 前端 streamSSE + useStreamGeneratePlan；降级策略：首 chunk 前降级 LocalRule，中途失败保留 partial_text；分段持有 db session 避免 SQLite 锁；不引入新依赖，不修改数据库 schema），已完成实现与验收（后端 783 passed 新增 47 测试 + 前端 468 passed 新增 34 测试）。
- [specs/0019-outline-streaming.md](specs/0019-outline-streaming.md)：V2.1.0 大纲生成流式化 SPEC（SSE 端点绕过 Worker，DeepSeekOutlineProvider.stream_generate + Service.stream_generate_outline + 上下文聚合提取到 service 层 + 前端 useStreamGenerateOutline；复用 SPEC 0018 stream-sse.ts 工具和降级策略；保留 Worker 异步端点兼容；不引入新依赖，不修改数据库 schema），已完成实现与验收（后端 821 passed 新增 38 测试 + 前端 493 passed 新增 25 测试）。
- [specs/0020-evidence-streaming.md](specs/0020-evidence-streaming.md)：V2.2.0 证据卡片生成流式化 SPEC（SSE 端点绕过 Worker，DeepSeekEvidenceCardProvider.stream_draft + Service.stream_generate_evidence_cards + 前端 useStreamGenerateEvidence；Provider 输入为单文档 parsed_text 无需上下文聚合提取；复用 SPEC 0018/0019 stream-sse.ts 工具和降级策略；保留 Worker 异步端点兼容；不引入新依赖，不修改数据库 schema），已完成实现与验收（后端 858 passed 新增 37 测试 + 前端 519 passed 新增 26 测试）。
- [specs/0021-analysis-plan-streaming.md](specs/0021-analysis-plan-streaming.md)：V2.3.0 分析方案生成流式化 SPEC（SSE 端点绕过 Worker，DeepSeekAnalysisPlanProvider.stream_generate + Service.stream_generate_analysis_plan + 前端 useStreamGenerateAnalysisPlan；Provider 输入为 DatasetProfile 无需上下文聚合提取；复用 SPEC 0018/0019/0020 stream-sse.ts 工具和降级策略；保留 Worker 异步端点兼容；不引入新依赖，不修改数据库 schema；收口复核修复 LocalRuleAnalysisPlanProvider 输出 target_fields 为字符串导致前端 PlanCard TypeError 阻断问题），已完成实现与验收（后端 895 passed 新增 37 测试 + 前端 546 passed 新增 27 测试）。
- [specs/0022-code-task-streaming.md](specs/0022-code-task-streaming.md)：V2.4.0 代码任务生成流式化 SPEC（SSE 端点绕过 Worker，DeepSeekCodeTaskProvider.stream_generate + Service.stream_generate_code_task + 前端 useStreamGenerateCodeTask；Provider 输入为 AnalysisPlan 无需上下文聚合提取；复用 SPEC 0018/0019/0020/0021 stream-sse.ts 工具和降级策略；新增并发保护 active_streams + 服务端取消 request.is_disconnected + 错误分层 + Phase 3 状态复核；保留 Worker 异步端点兼容；不引入新依赖，不修改数据库 schema；收口复核修复 LocalRuleCodeTaskProvider 中 FREQUENCY 类型 target_fields.split() 在 list 上报错阻断问题），已完成实现与验收（后端 975 passed 新增 80 测试 + 前端 570 passed 新增 19 测试）。
- [specs/0023-multi-source-evidence-batch-streaming.md](specs/0023-multi-source-evidence-batch-streaming.md)：V2.4.0 多来源证据批量流式生成 SPEC 草案（待项目负责人审批；扩展 SPEC 0020 支持跨来源批量流式生成）。
- [specs/0024-ppt-renderer-layout-and-visual-hierarchy.md](specs/0024-ppt-renderer-layout-and-visual-hierarchy.md)：V2.5.0 PPT 渲染器布局与视觉层次改进 SPEC（16:9 画布 + 空白版式精确定位 + 双栏内容页 40%/60% + 图表自适应布局 + 五级字号体系 + 主题色扩展应用到色块/分隔线/要点标记；不引入新依赖，不改变 PptConfig 合同，不改变 API/service/Worker 接线，仅重构 ppt_renderer.py 内部布局方法），已完成实现与验收（142 PPT/outline/renderer 测试通过 + 真实 PPT 文件视觉验证 16:9 画布/五级字号/主题色 4/4 页面/双栏布局）。
- [specs/0025-ppt-color-system-and-sandwich-layout.md](specs/0025-ppt-color-system-and-sandwich-layout.md)：V2.6.0 PPT 三角色彩系统与深浅对比三明治结构 SPEC（从单一 theme_color 算法派生主色/辅助色/强调色三角色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；使用 colorsys 标准库，不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法），已完成实现与验收（57+222+83 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过；决策 0034）。
- [specs/0026-ppt-visual-effects-enhancement.md](specs/0026-ppt-visual-effects-enhancement.md)：V2.7.0 PPT 视觉效果增强 SPEC（渐变填充 + 圆角矩形 + 外阴影 + 细边框；python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部视觉效果方法），已完成实现与验收（17 个新增测试 + 220 passed 零回归 + 6 种预设色真实文件视觉验收 + 前端 lint/build 通过；决策 0035）。
- [specs/0027-chart-beautification-and-layout-enhancement.md](specs/0027-chart-beautification-and-layout-enhancement.md)：V2.8.0 图表美化与布局增强 SPEC（SciencePlots + Seaborn + EasyPPTX；_HEADER 集成 scienceplots 样式 + sns.set_theme，_build_chart_code 升级为 sns.histplot/boxplot/countplot/scatterplot/heatmap；ppt_renderer 新增 _pct_to_emu 百分比定位 + _GridHelper N×M 网格辅助类，改造 _place_chart_grid/side_by_side/three 使用 Grid；沙箱白名单新增 scienceplots/seaborn；引入 3 个新依赖，不改变 PptConfig 合同），已完成实现与验收（45 个新增测试 + 204 passed 零回归 + 5 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染 + Grid 布局 8/8 对齐验证；决策 0036）。
- [specs/0028-nature-figure-integration.md](specs/0028-nature-figure-integration.md)：V2.8.1 Nature 风格图表集成 SPEC（移除 SciencePlots，引入 nature-figure 设计规则；用 matplotlib rcParams 手动配置替换 plt.style.use，保留 Seaborn + _GridHelper；移除 1 个依赖 scienceplots，不引入新依赖，不改变 PptConfig 合同），已完成实现与验收（修改 5 个受影响测试 C1/C2/C3/S1/S4 + 修复遗漏测试 test_default_allowed_imports_content + 204 passed 零回归 + 3 张真实图表沙箱执行验收 + 6 种预设色 PPT 渲染；决策 0037）。
- [specs/0029-e2e-integration-acceptance.md](specs/0029-e2e-integration-acceptance.md)：V2.9.0 端到端集成验收 SPEC（已由项目负责人确认收口；验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通，8 步主路径覆盖项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成；新建 verify_spec0029_e2e.py 验收脚本，E2E_RESULT=PASS，1100 passed 零回归，Word 332KB/103 段落 + PPT 334KB/8 幻灯片；修复 2 项集成断点：pd.to_numeric(errors='coerce') + list_execution_runs 元组解包；不引入新功能，不改变 owner 边界，不引入新依赖，不修改数据库 schema；决策 0038）。
- [specs/0030-pptxforge-and-chart-beautification.md](specs/0030-pptxforge-and-chart-beautification.md)：V2.10.0 pptxforge 集成与图表美化增强 SPEC（已批准进入实现；引入 pptxforge 10 主题 + 视觉原语 + Morph 转场；图表美化 NPG 期刊配色 + a/b/c 面板标签 + fill_between 误差带 + 多面板布局；修复 SPEC 0028 dpi 不一致缺陷；PptConfig 扩展为四字段合同（方案 B，新增 theme_preset 可选字段），不改变 render() 签名，不改变 Provider 接口；引入 1 个新依赖 pptxforge MIT；决策 0039）。
- [specs/0031-academic-document-visual-quality.md](specs/0031-academic-document-visual-quality.md)：SPEC 0031 论文级 Word/PPT 视觉质量与真实渲染验收（A4 Word 版式、论文式图题/来源、轻量表格、PPT 图注与中文窄栏换行、图表字体/DPI/布局保护；不改变业务合同）。
- [specs/0032-ppt-master-sjtu-presentation-adapter.md](specs/0032-ppt-master-sjtu-presentation-adapter.md)：SPEC 0032 PPT Master 与上海交大模板适配（`native_editable`、`academic`、`sjtu_academic` 工作流模式；模板来源、许可边界、真实 PPTX 渲染验收）。
- [specs/0033-paper-adaptive-layout-planner.md](specs/0033-paper-adaptive-layout-planner.md)：SPEC 0033 论文级自适应版式与语义布局规划器（叙事、数据概览、方法流程、单图重点、多图对比、总结六类版式）。
- [specs/0034-formal-thesis-and-defense-deck.md](specs/0034-formal-thesis-and-defense-deck.md)：SPEC 0034 正式论文 Word/PDF 与高级答辩 PPT（A4 论文结构、编号/题注/追溯、答辩叙事与逐页视觉验收）。
- [specs/0035-large-sample-paper-review-case.md](specs/0035-large-sample-paper-review-case.md)：SPEC 0035 大样本公开论文解读案例（论文全文来源、101,766 条公开数据、原文/复核口径分离）。
- [specs/0036-paper-review-depth-remediation.md](specs/0036-paper-review-depth-remediation.md)：SPEC 0036 论文解读深度整改（样本流程、缺失结构、效应量、简化 Logistic、分层结果与 13 页答辩成品）。
- [specs/0037-semantic-chart-selection-and-ppt-component-polish.md](specs/0037-semantic-chart-selection-and-ppt-component-polish.md)：SPEC 0037 语义图表选择与论文级 PPT 组件优化（按数据语义选择流程图、构成图、Dumbbell、点区间图、趋势图和森林图；复用现有 `pptxforge` 组件）。
- [specs/0038-formal-academic-paper-normalization.md](specs/0038-formal-academic-paper-normalization.md)：SPEC 0038 正式学术论文规范化改造（A4 论文结构、文内引用、参考文献、章节化题注、三线表与 PDF 视觉验收）。
- [specs/0039-semantic-figure-system.md](specs/0039-semantic-figure-system.md)：SPEC 0039 论文级多语义图形系统（数据图、研究框架、流程、变量关系、证据链、数据管线、时间线和机制路径的共享语义规划与双交付物适配）。
- [specs/0040-journal-argumentation-and-visual-grammar.md](specs/0040-journal-argumentation-and-visual-grammar.md)：SPEC 0040 期刊级论证图表与论文视觉语法改造（`ArgumentPlan`、真实证据/结果/边界、无交叉变量关系图和期刊级 Word/PDF/PPT 适配）。
- [specs/0041-heterogeneous-figure-orchestration.md](specs/0041-heterogeneous-figure-orchestration.md)：SPEC 0041 论文级异构图形编排与语义选图系统（流程、关系、矩阵、统计、时间线和论证图按数据前提组合，禁止用单一模板覆盖整篇论文；已完成实现与真实视觉验收，待项目负责人确认收口）。
- [specs/0042-open-scientific-asset-library-and-schematic-components.md](specs/0042-open-scientific-asset-library-and-schematic-components.md)：SPEC 0042 开放许可科研图形资产库与科研示意图组件系统（资产/许可证唯一 owner、SVG 安全清洗与哈希、自动署名、具象科研组件和 Word/PDF/PPT 同源渲染；实现与本地验收完成，待视觉确认收口）。
- [specs/0044-standardized-paper-presentation-and-layout.md](specs/0044-standardized-paper-presentation-and-layout.md)：SPEC 0044 标准化论文成品展示与排版，规定读者优先正文、统一版式、图表部署、可回指字段和逐页视觉验收。
- [specs/0045-paper-review-statistical-integrity.md](specs/0045-paper-review-statistical-integrity.md)：SPEC 0045 论文复核统计完整性，固定患者级样本、死亡/临终关怀排除、HbA1c 三态缺失语义、主要诊断交互、聚类稳健标准误、敏感性分析和正式论文定位。

## 当前复核与方向决策

- [paper-quality-review-spec0043-2026-08-14.md](paper-quality-review-spec0043-2026-08-14.md)：SPEC 0043 当前论文质量审查，记录当前成品的优点、正文工程追溯泄漏、学术论证与方法缺口、视觉验收限制和收口门槛；不代表 SPEC 0043 已收口。
- [decisions/0053-package-distribution-and-local-mcp.md](decisions/0053-package-distribution-and-local-mcp.md)：确认未来采用 Windows 安装包 + 本地 MCP stdio bridge 的分发方向，明确 MCP 只做协议适配、现有模块继续拥有业务语义，并记录进入实现前的验收合同。
- [decisions/0054-start-spec-0044-standardized-paper-presentation.md](decisions/0054-start-spec-0044-standardized-paper-presentation.md)：确认先编写并确认 SPEC 0044，再修改 ManuscriptPlan 到 WordRenderer；暂不推进 MCP 或新增图表类型。

## V2.0 发布文档

- [changelog-v2.0.0.md](changelog-v2.0.0.md)：V2.0.0 详细发布说明（SPEC 0018 流式 LLM 输出：SSE 流式任务单生成、降级策略、分段 db session、前端流式展示与取消；CI P0 修复：前端单元测试参与 CI + 后端依赖声明安装）。

## V2.1 发布文档

- [changelog-v2.1.0.md](changelog-v2.1.0.md)：V2.1.0 详细发布说明（SPEC 0019 大纲生成流式化：SSE 端点绕过 Worker、上下文聚合提取到 service 层、DeepSeekOutlineProvider.stream_generate、前端 useStreamGenerateOutline、原 Worker 路径零回归）。

## V2.2 发布文档

- [changelog-v2.2.0.md](changelog-v2.2.0.md)：V2.2.0 详细发布说明（SPEC 0020 证据卡片生成流式化：SSE 端点绕过 Worker、DeepSeekEvidenceCardProvider.stream_draft、前端 useStreamGenerateEvidence、原 Worker 路径零回归、复用 SPEC 0018/0019 stream-sse.ts 和降级策略）。

## V2.3 发布文档

- [changelog-v2.3.0.md](changelog-v2.3.0.md)：V2.3.0 详细发布说明（SPEC 0021 分析方案生成流式化：SSE 端点绕过 Worker、DeepSeekAnalysisPlanProvider.stream_generate、前端 useStreamGenerateAnalysisPlan、原 Worker 路径零回归、复用 SPEC 0018/0019/0020 stream-sse.ts 和降级策略；收口复核修复 LocalRuleAnalysisPlanProvider 输出 target_fields 类型不一致导致前端 PlanCard TypeError 阻断问题）。

## V2.4 发布文档

- [changelog-v2.4.0.md](changelog-v2.4.0.md)：V2.4.0 详细发布说明（SPEC 0022 代码任务生成流式化：SSE 端点绕过 Worker、DeepSeekCodeTaskProvider.stream_generate、前端 useStreamGenerateCodeTask、原 Worker 路径零回归、复用 SPEC 0018/0019/0020/0021 stream-sse.ts 和降级策略；新增并发保护 active_streams + 服务端取消 request.is_disconnected + 错误分层 + Phase 3 状态复核；收口复核修复 LocalRuleCodeTaskProvider 中 FREQUENCY 类型 target_fields.split() 在 list 上报错阻断问题）。

## V2.5 发布文档

- [changelog-v2.5.0.md](changelog-v2.5.0.md)：V2.5.0 详细发布说明（SPEC 0024 PPT 渲染器布局与视觉层次改进：16:9 画布 + 空白版式精确定位 + 双栏内容页 40%/60% + 图表自适应布局 + 五级字号体系 + 主题色扩展应用；端到端视觉测评修复图表中文乱码/PPT 页数限制/图片溢出/3 图布局/文本截断 5 项阻断问题；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法）。

## V1.4 发布文档

- [changelog-v1.4.0.md](changelog-v1.4.0.md)：V1.4.0 详细变更日志（SPEC 0017 单用户前端实时编辑反馈：乐观更新、错误回滚、保存成功提示）。

## V1.0 发布文档

- [release-checklist-v1.0.0.md](release-checklist-v1.0.0.md)：V1.0.0 发布清单（发布前状态检查、发布物清单、标签操作）。
- [changelog-v1.0.0.md](changelog-v1.0.0.md)：V1.0.0 详细变更日志（新增功能、Bug 修复、技术债务清理、架构改进）。
- [v1.1.0-planning.md](v1.1.0-planning.md)：V1.1.0 版本功能迭代规划（遗留债务分析、6 个 SPEC 规划、实施顺序）。

## V1.1 发布文档

- [release-checklist-v1.1.0.md](release-checklist-v1.1.0.md)：V1.1.0 发布清单（发布前状态检查、发布物清单、6 个 SPEC 摘要、标签操作）。
- [changelog-v1.1.0.md](changelog-v1.1.0.md)：V1.1.0 详细变更日志（6 个 SPEC 新增功能、5 个 Bug 修复、架构改进、升级指南）。
- [v1.1.0-regression-test-plan.md](v1.1.0-regression-test-plan.md)：V1.1.0 回归测试执行计划（三道门禁 + 6 个 SPEC 专项回归 + 执行记录）。
- [worker-e2e-log-v1.1.0-regression.md](worker-e2e-log-v1.1.0-regression.md)：V1.1.0 发布后端到端回归验证日志（worker_e2e_verify.py 临时数据库运行结果）。

## V1.2 发布文档

- [release-checklist-v1.2.0.md](release-checklist-v1.2.0.md)：V1.2.0 发布清单（发布前状态检查、发布物清单、3 个 SPEC 摘要、标签操作、下一阶段方向）。
- [changelog-v1.2.0.md](changelog-v1.2.0.md)：V1.2.0 详细变更日志（3 个 SPEC 新增功能、3 个 Bug 修复、架构改进、升级指南）。
- [v1.2.0-regression-test-plan.md](v1.2.0-regression-test-plan.md)：V1.2.0 回归测试执行计划（三道门禁 + 3 个 SPEC 专项回归 + TD-007 修复验证 + 执行记录）。
- [worker-e2e-log-v1.2.0-regression.md](worker-e2e-log-v1.2.0-regression.md)：V1.2.0 发布后端到端回归验证日志（worker_e2e_verify.py 临时数据库运行结果，E2E_RESULT=PASS）。

## 变更规则

- 项目方向、功能边界、技术路线或验收标准发生变化时，必须先更新 `project-charter.md`。
- 每次影响范围、边界或验收标准的变更，必须新增或更新 `dev-docs/decisions/` 下的决策记录。
- 不允许只在对话中口头修改项目真源。
- 后续每个新切片开始前，必须先确认对应 SPEC 或任务范围。
- 每完成一版或一个已确认开发切片，必须按根目录 `AGENTS.md` 的“版本收口上传规则”完成验收、文档回写、精确提交和远程上传；未配置远程仓库或上传失败时，必须记录原因。

## 真源优先级

事实冲突时按以下顺序处理：

1. 当前代码、测试、脚本、运行证据和 git 状态。
2. 根目录 `AGENTS.md`。
3. 本索引和 active 真源文档。
4. 决策记录。
5. 历史对话、旧草稿和未索引文档。



## SPEC 0046 Windows 一键运行封装

- [specs/0046-windows-one-click-package.md](specs/0046-windows-one-click-package.md)：Windows x64 portable bundle 的目标、运行合同、验收门禁和边界；当前已确认进入实现。
- [decisions/0055-start-spec-0046-windows-one-click-package.md](decisions/0055-start-spec-0046-windows-one-click-package.md)：本轮 Windows EXE 分发决策、owner、构建期 PyInstaller 依赖和未闭合风险。
- [../packaging/windows/README.md](../packaging/windows/README.md)：用户运行和开发机构建说明。

当前状态：服务包与根 EXE 已构建并完成本机黑盒启动、页面、真实窗口、关闭和退出码验收；仅剩独立干净 Windows x64 主机验收缺口。

## SPEC 0047 统一工作台与交付审阅

- [specs/0047-unified-workspace-shell-delivery-review.md](specs/0047-unified-workspace-shell-delivery-review.md)：PDF 正式交付物、项目进度投影、交付审阅台、质量门禁和统一 WorkspaceShell 的合同与边界。
- [decisions/0056-start-spec-0047-unified-workspace-delivery-review.md](decisions/0056-start-spec-0047-unified-workspace-delivery-review.md)：本切片授权、PDF/LibreOffice 包体决策和 owner 约束。
- [stages/unified-workspace-delivery-review.md](stages/unified-workspace-delivery-review.md)：当前阶段执行计划、子阶段状态、验证证据和停止条件。

当前状态：PDF/投影/交付审阅代码合同已实现；统一 WorkspaceShell 已迁移 Sources、Evidence、Dataset、Analysis、Execution、Outline、Deliverable 七个工作区，并补充 `phase_id/phase_label/is_substep` 子步骤投影；交付物审阅台已接入版本 provenance、质量/边界检查和真实预览状态；前端 550 个测试、lint/build 通过，交付物相关后端回归 97 passed；科研资产定向回归 29 passed，后端全量 1266 passed，PDF 交付定向回归 92 passed，Windows portable 源合同 6 passed，LibreOffice 26.2.5 runtime 已完成独立 portable 构建和真实 DOCX→PDF 适配器验证，SVG hash 漂移已关闭。1280px/390px 浏览器视觉和当前 10 页 PDF 栅格化视觉复核已完成并留存浏览器截图；仅剩无 Python/Node.js/Docker 的独立 Windows x64 黑盒验收，且演示项目自身仍按真实事实阻断交付审阅。
