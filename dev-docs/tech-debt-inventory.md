# 技术债务总清单（截至 V1.2.0 SPEC 0013 收口）

> **文档日期：** 2026-07-24  
> **当前版本：** V1.1.0 已发布（tag v1.1.0），V1.2.0 SPEC 0013 Docker 化已收口（commit `c210911`），SPEC 0014/0015 草案中  
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

### TD-004：科学计算包未声明在 `pyproject.toml` dependencies

| 属性 | 值 |
| --- | --- |
| **引入切片** | SPEC 0004 / SPEC 0005 |
| **严重程度** | 低（不影响本地开发，影响 Docker 镜像构建） |
| **来源** | [dependency-review.md](dependency-review.md) §9.3 |
| **现状** | pandas/numpy/scipy/scikit-learn/matplotlib/psutil 在本地开发环境手动 `pip install`，未写入 `pyproject.toml` 的 `dependencies`。SPEC 0013 Docker 化时通过 Dockerfile 额外固定版本安装弥补，但 `pip install -e .` 不会自动安装 |
| **临时缓解** | Dockerfile 显式 `pip install pandas==3.0.3 ...` |
| **建议处理入口** | V1.2.0 后续或 V1.3.0：在 `pyproject.toml` 新增 `[project.optional-dependencies] analysis` 段，声明科学计算包，让 `pip install -e ".[analysis]"` 一键安装 |
| **阻断当前目标** | 否 |

### TD-005：AGENTS.md "当前已知非阻断债务"表述过时

| 属性 | 值 |
| --- | --- |
| **引入切片** | 立项阶段 |
| **严重程度** | 低（文档准确性问题，不影响代码） |
| **来源** | [AGENTS.md](../AGENTS.md) "测试与验收"章节 |
| **现状** | AGENTS.md 仍记载"当前会话未暴露可调用的 in-app Browser 工具，因此 SPEC 0002 未完成真实浏览器点击截图验收"。但 TD-003 已于 2026-07-22 清理：V1.0 端到端验收时用 browser_use agent 完成浏览器验收，截图在 `dev-docs/e2e-screenshots/`，详见 [e2e-acceptance-report-v1.0.md](e2e-acceptance-report-v1.0.md) |
| **建议处理入口** | 下次 AGENTS.md 修订时更新该章节，引用 e2e-acceptance-report-v1.0.md 作为浏览器验收证据 |
| **阻断当前目标** | 否 |

### TD-006：acceptance.md 各 SPEC "可视化点击验收"历史记录与 V1.0 整体验收状态不一致

| 属性 | 值 |
| --- | --- |
| **引入切片** | SPEC 0001 ~ SPEC 0012 收口记录 |
| **严重程度** | 低（历史快照，非遗漏） |
| **来源** | [acceptance.md](acceptance.md) L148/L157/L175/L187/L199/L213/L243/L259/L273/L282 |
| **现状** | 各 SPEC 收口时记录"可视化点击验收：未执行"是当时的事实快照。V1.0 整体端到端验收（2026-07-22）用 browser_use agent 补做了浏览器验收（TD-003 关闭）。收口记录不回溯修改历史，但可能让读者误以为浏览器验收从未做 |
| **建议处理入口** | 不回溯修改各 SPEC 收口记录（保留历史快照）。在 acceptance.md 顶部"当前限制"说明中明确：V1.0 整体验收已补做浏览器验收，详见 e2e-acceptance-report-v1.0.md |
| **阻断当前目标** | 否 |

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
| L9 | LLM 调用缓存 | SPEC 0014 草案中（V1.2.0） | V1.2.0 |
| L10 | CI/CD 流水线 | SPEC 0015 草案中（V1.2.0） | V1.2.0 |
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

---

## 五、代码层面扫描结果

**扫描方法：** `Get-ChildItem server\app, server\worker, apps\web\src -Recurse -Include *.py,*.ts,*.tsx | Select-String -Pattern "TODO|FIXME|XXX|HACK"`

**扫描日期：** 2026-07-24

**结论：** 项目自身源码无真正的 TODO/FIXME/XXX/HACK 债务。唯一匹配项为 `apps/web/src/routes/__tests__/ExecutionWorkspaceView.test.tsx:8` 的描述性注释（说明测试文件路径），非债务标记。

---

## 六、架构层面待决事项

| # | 待决事项 | 当前状态 | 建议入口 |
| --- | --- | --- | --- |
| A4 | LLM 调用缓存是否进入 | SPEC 0014 草案已编写 | 项目负责人确认 SPEC 0014 |
| A5 | CI/CD 是否进入 | SPEC 0015 草案已编写 | 项目负责人确认 SPEC 0015 |
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
| 可记录债务（TD-004/005/006） | 3 | 否 |
| 产品边界限制（L2-L15） | 14 | 否（按版本规划） |
| 已关闭债务（TD-001/002/003） | 0（均已关闭） | 否 |
| 代码 TODO/FIXME | 0 | 否 |

**结论：** 项目当前无阻断性技术债务。3 个可记录债务均为文档准确性或依赖声明问题，不影响主链路功能。最大的功能缺口是 LLM 调用缓存（L9）和 CI 流水线（L10），已分别通过 SPEC 0014 和 SPEC 0015 草案承接。
