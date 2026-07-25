# 技术债务总清单（截至 V1.4.0 发布）

> **文档日期：** 2026-07-25  
> **当前版本：** V1.4.0 已发布并打 tag v1.4.0（SPEC 0017 单用户前端实时编辑反馈已收口）  
> **维护规则：** 本文档汇总项目当前所有已知技术债务。每次切片收口后必须更新。债务清理后移入"已关闭债务"章节并保留证据。

---

## 一、债务分级标准

| 级别 | 定义 | 处理时机 |
| --- | --- | --- |
| **阻断问题** | 破坏核心功能、owner 边界、安全、数据真相、构建测试 | 当轮必须收掉 |
| **可记录债务** | 不影响主链路，可暂缓，但必须记录入口和后续处理方案 | 记录并排期 |
| **产品边界限制** | V1 明确不做或推迟的能力，非缺陷 | 按版本规划推进 |
| **历史记录** | 已关闭债务的历史快照，保留追溯 | 不再处理 |

---

## 二、当前活跃债务（可记录债务，非阻断）

> V1.3.0 SPEC 0016 已清理全部 4 个可记录债务（TD-004/005/006/008）。V1.4.0 SPEC 0017 引入 1 个新的非阻断债务 TD-009。

### TD-009：SPEC 0017 浏览器验收截图未持久化

| 字段 | 值 |
| --- | --- |
| **引入切片** | SPEC 0017（V1.4.0） |
| **引入时间** | 2026-07-25 |
| **级别** | 可记录债务（非阻断） |
| **问题描述** | SPEC 0017 浏览器验收使用 browser_use agent 执行真实浏览器点击验收，PASS（保存按钮"已保存 ✓"绿色 #16a34a 提示正常显示，1.5s 后自动消失），但 `browser_take_screenshot` 工具在本环境未真正写入文件到 `dev-docs/e2e-screenshots/` 目录。 |
| **影响** | 不影响功能正确性，仅缺失截图归档。功能正确性已通过 23 个 hooks 单元测试 + browser_use agent 真实点击观察的双重证据确认。 |
| **后续入口** | 后续修复时可用 puppeteer / playwright 等替代工具，或修复 browser_use 的截图持久化机制。修复后应补做 SPEC 0017 截图归档至 `dev-docs/e2e-screenshots/spec-0017/`。 |
| **关联文档** | [acceptance.md](acceptance.md) AC-23、[decisions/0023](decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md) 验收证据章节、[changelog-v1.4.0.md](changelog-v1.4.0.md) §六 |

---

## 三、产品边界限制（非债务，是 V1 明确不做项）

> 以下各项是 V1 产品边界，不属于"缺陷"。列出仅为完整性和版本规划参考。

| # | 限制 | 当前状态 | 计划解决版本 |
| --- | --- | --- | --- |
| L2 | Word 模板完全兼容 | V1.1.0 SPEC 0010 部分解决（支持项目级 .docx 模板上传，Jinja2 风格占位符） | V2.0 考虑复杂样式 |
| L3 | PPT 动画和复杂排版 | V1.1.0 SPEC 0011 支持页数/主题色/图表开关 | V2.0 |
| L4 | 注册登录 | 永久不做（本地单用户） | 永久不做 |
| L5 | L3 完整论文复现 | 永久不做（产品边界排除） | 永久不做 |
| L8 | Docker 化 | ✅ V1.2.0 SPEC 0013 已解决 | 已解决 |
| L1 | 真实 DeepSeek 调用 | ✅ V1.1.0 SPEC 0007 已解决 | 已解决 |
| L6 | 前端测试覆盖 | ✅ V1.1.0 SPEC 0009 已解决（411 测试） | 已解决 |
| L7 | 部署文档 | ✅ V1.1.0 根目录 README.md 已解决 | 已解决 |
| L9 | LLM 调用缓存 | ✅ V1.2.0 SPEC 0014 已解决 | 已解决 |
| L10 | CI/CD 流水线 | ✅ V1.2.0 SPEC 0015 已解决 | 已解决 |
| L11 | 流式 LLM 输出 | 未启动 | V2.0 |
| L12 | E2E 测试框架（Playwright/Cypress） | 未启动 | V2.0 |
| L13 | Notebook 风格代码编辑 | 未启动 | V2.0 |
| L14 | OCR 与扫描文档 | 未启动 | V2.0 |
| L15 | 多用户协作 | 永久不做（本地单用户） | 永久不做 |

---

## 四、已关闭债务（历史快照，保留追溯）

| 编号 | 名称 | 引入切片 | 关闭时间 | 关闭证据 |
| --- | --- | --- | --- | --- |
| TD-001 | fastapi.testclient httpx 弃用提示 | SPEC 0002 | 2026-07-22 | 安装 `httpx2 2.7.0`，`pyproject.toml` dev 依赖新增 `httpx2>=2.0.0`；验证 569 passed, 0 warnings。详见 [tech-debt-cleanup-plan.md](tech-debt-cleanup-plan.md) §六 |
| TD-002 | pandas datetime 推断 UserWarning | SPEC 0004 | 2026-07-22 | `dataset_parser.py:96` 添加 `format="mixed"`；验证 569 passed, 0 warnings。详见 [tech-debt-cleanup-plan.md](tech-debt-cleanup-plan.md) §六 |
| TD-003 | 浏览器点击截图验收未执行 | SPEC 0002 | 2026-07-22 | V1.0 端到端验收用 browser_use agent 完成浏览器验收，截图保存至 `dev-docs/e2e-screenshots/`（home-full.png、home-viewport.png），详见 [e2e-acceptance-report-v1.0.md](e2e-acceptance-report-v1.0.md) |
| TD-007 | openpyxl 未声明在 pyproject.toml dependencies | SPEC 0004 | 2026-07-24 | SPEC 0015 CI 首次推送后 backend job exit code 2，排查发现 `test_dataset_parser.py` 导入 `openpyxl` 失败。修复：`pyproject.toml` dependencies 新增 `openpyxl>=3.1.0`；Docker 容器内验证 729 passed。与 TD-004 同类问题，但 openpyxl 直接被 app 代码导入，故直接补入主 dependencies 而非 optional-dependencies |
| TD-004 | 科学计算包未声明在 `pyproject.toml` dependencies | SPEC 0004 / SPEC 0005 | 2026-07-25 | SPEC 0016 在 `pyproject.toml` 新增 `[project.optional-dependencies] analysis` 段声明 pandas/numpy/scipy/scikit-learn/matplotlib/psutil（版本下限与 Dockerfile 对齐）；Dockerfile 改用 `pip install -e ".[dev,analysis]"` 一次安装；Docker 容器内验证 `import pandas, numpy, scipy, sklearn, matplotlib, psutil` 全部成功；后端 736 passed 0 warnings。详见 [dependency-review.md](dependency-review.md) §9.2 |
| TD-005 | AGENTS.md "当前已知非阻断债务"表述过时 | 立项阶段 | 2026-07-25 | SPEC 0016 更新 AGENTS.md "当前已知非阻断债务"章节：移除"未暴露可调用的 in-app Browser 工具"过时表述，引用 `e2e-acceptance-report-v1.0.md` 作为浏览器验收证据；`git diff` 验证只涉及该章节，规则条款未变。详见 [AGENTS.md](../AGENTS.md) 第 201-204 行 |
| TD-006 | acceptance.md 各 SPEC "可视化点击验收"历史记录与 V1.0 整体验收状态不一致 | SPEC 0001 ~ SPEC 0012 收口记录 | 2026-07-25 | SPEC 0016 在 acceptance.md 顶部"当前限制"之后新增"浏览器验收状态说明"小节，明确 V1.0 已补做浏览器验收；`git diff` 验证各 SPEC 收口记录未回溯修改。详见 [acceptance.md](acceptance.md) 第 6-7 行 |
| TD-008 | worker_e2e_verify.py 硬编码日志标题为"V1.0" | V1.0 端到端验收 | 2026-07-25 | SPEC 0016 为 `server/worker_e2e_verify.py` 添加 `parse_args()` 函数，支持 `--version` 和 `--output` 命令行参数及 `WORKER_E2E_VERSION` 环境变量；默认值 "V1.0" 保持向后兼容；新增 `server/tests/test_worker_e2e_verify.py` 7 个单元测试全部通过。详见 [specs/0016-tech-debt-cleanup-004-005-006-008.md](specs/0016-tech-debt-cleanup-004-005-006-008.md) §六 |

---

## 五、代码层面扫描结果

**扫描方法：** `Get-ChildItem server\app, server\worker, apps\web\src -Recurse -Include *.py,*.ts,*.tsx | Select-String -Pattern "TODO|FIXME|XXX|HACK"`

**扫描日期：** 2026-07-24

**结论：** 项目自身源码无真正的 TODO/FIXME/XXX/HACK 债务。唯一匹配项为 `apps/web/src/routes/__tests__/ExecutionWorkspaceView.test.tsx:8` 的描述性注释（说明测试文件路径），非债务标记。

---

## 六、架构层面待决事项

| # | 待决事项 | 当前状态 | 建议入口 |
| --- | --- | --- | --- |
| A4 | LLM 调用缓存是否进入 | ✅ V1.2.0 SPEC 0014 已实现并收口 | 已解决 |
| A5 | CI/CD 是否进入 | ✅ V1.2.0 SPEC 0015 已实现并收口 | 已解决 |
| A6 | 全局 Word 模板（项目级模板已支持，全局模板推迟） | config.py 中 `word_template_path` 保留但不使用，注释说明 V2.0 | V2.0 |

---

## 七、债务监控规则

1. 每次切片收口验收时，必须检查本文档是否需要更新。
2. 新引入的非阻断问题必须在本文档登记，注明来源、严重程度、后续入口。
3. 债务关闭时移入"已关闭债务"章节，保留关闭证据。
4. `python -m pytest` 的 warnings 数量必须保持为 0。出现新 warning 立即评估是否阻断。
5. 不允许用"后面再说"掩盖有证据的阻断问题；也不允许把可记录债务夸大为阻断问题。

---

## 八、当前债务数量汇总

| 类别 | 数量 | 阻断当前目标 |
| --- | --- | --- |
| 阻断问题 | 0 | — |
| 可记录债务 | 1（TD-009） | 否（浏览器验收截图未持久化，不影响功能正确性） |
| 产品边界限制（L2-L15） | 14 | 否（按版本规划） |
| 已关闭债务（TD-001/002/003/004/005/006/007/008） | 8（均已关闭） | 否 |
| 代码 TODO/FIXME | 0 | 否 |

**结论：** 项目当前无阻断性技术债务，活跃可记录债务为 TD-009（非阻断）。V1.4.0 已发布并打 tag v1.4.0，SPEC 0017 单用户前端实时编辑反馈已收口。下一阶段方向待项目负责人规划。
