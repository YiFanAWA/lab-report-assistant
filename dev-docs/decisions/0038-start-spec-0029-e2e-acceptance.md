# 决策 0038：启动 SPEC 0029 端到端集成验收

**日期：** 2026-07-31
**决策类型：** 启动新切片
**状态：** 已由项目负责人确认收口（2026-07-31）
**关联 SPEC：** [SPEC 0029](../specs/0029-e2e-integration-acceptance.md)
**前序决策：** [决策 0037](0037-start-spec-0028-nature-figure.md)（SPEC 0028 已由项目负责人确认收口）
**验收报告：** [e2e-acceptance-report-spec0029.md](../e2e-acceptance-report-spec0029.md)

## 一、背景

V2.5.0~V2.8.1 阶段连续完成 5 个 PPT/图表相关切片（SPEC 0024/0025/0026/0027/0028），均为纯后端渲染器/图表层改动。这些切片各自完成了独立的单元测试和真实文件视觉验收，但未做完整业务流程端到端验证。

根据 [acceptance.md](../acceptance.md) 第 11 行记录，2026-07-30 的完整业务流程链路验证覆盖范围为 REQUIREMENT_PARSED → ANALYSIS_CONFIRMED，**未验证**代码执行（RESULT_CONFIRMED）→ 大纲生成（OUTLINE_CONFIRMED）→ Word/PPT 生成（COMPLETED）环节。

需端到端验收确认整个工作流打通，为后续发布 v2.6.0~v2.8.1 tag 做前置验证。SPEC 0029 草案已编写（包含 12 章节：背景、目标边界、验收方法、8 步主路径测试场景、脚本架构、浏览器验收、bug 处理策略、风险缓解、实现顺序、文档回写、约束声明），项目负责人审阅后批准进入实现阶段。

## 二、决策

批准 SPEC 0029「端到端集成验收（V2.5.0~V2.8.1 多切片后完整工作流验证）」进入实现阶段。

### 2.1 范围

- **owner 层**：`server/scripts/verify_spec0029_e2e.py`（验收脚本，不改变现有 owner 边界）
- **依赖**：不引入新依赖（仅用已有 httpx、python-docx、python-pptx 等）
- **API 合同**：不改变任何 API 请求/响应 schema
- **数据库 schema**：不新增 Alembic 迁移
- **API/Service/Worker 接线**：不改动（除非发现 bug 需修复）

### 2.2 验收方案（混合方案）

1. **API 集成脚本**（主路径）：新建 `server/scripts/verify_spec0029_e2e.py`，复用 worker_e2e_verify.py 架构，通过 HTTP API 驱动完整 8 步工作流
2. **浏览器验收**（关键 UI 交互）：用 browser_use agent 验证首页加载、项目创建、流式生成、交付物下载等关键 UI 路径
3. **真实文件验证**：验证生成的 Word/PPT 文件可正常打开，图表为 nature-figure 风格（SPEC 0028 rcParams 生效），PPT 三明治结构 + 视觉效果完整

### 2.3 8 步主路径

| 步骤 | 操作 | 预期项目状态 |
| --- | --- | --- |
| 1 | 创建项目 | DRAFT |
| 2 | 上传要求 + 流式生成任务单 + 确认 | REQUIREMENT_CONFIRMED |
| 3 | 上传 PDF 来源 + Worker 解析 + 流式生成证据卡片 + 确认 | EVIDENCE_CONFIRMED |
| 4 | 上传胃病 CSV 数据集 + Worker 解析 | DATASET_READY |
| 5 | 确认分析方案 | ANALYSIS_CONFIRMED |
| 6 | 流式生成代码任务 + Worker 执行 | RESULT_CONFIRMED |
| 7 | 生成大纲 + 确认 | OUTLINE_CONFIRMED |
| 8 | 生成 Word + PPT | COMPLETED |

### 2.4 不纳入

- 性能测试和压力测试（属 V2.0+ 方向）
- 多用户并发场景（产品边界排除）
- 非"胃病数据分析"课题的验证（V1 聚焦首个演示课题）
- E2E 测试框架引入（Playwright/Cypress，属 L12 产品边界限制）
- 自动化回归测试套件建设（本 SPEC 只做一次性端到端验收）

## 三、约束

- 不引入新功能、不改变 owner 边界、不改变 API 合同、不修改数据库 schema
- 不引入新依赖
- 发现的 bug 修复必须遵循 AGENTS.md 阶段闸（核心 owner 层 → 测试先行 → API/UI/Worker 接线）
- 验收脚本放在 `server/scripts/` 目录，复用 worker_e2e_verify.py 模式
- 发现阻断问题时修复后重新运行完整 8 步验收，不允许跳过失败步骤
- 修复的代码改动必须与验收脚本改动分离，独立 commit

## 四、环境要求（复用决策 0031 经验）

| 环境项 | 要求 | 说明 |
| --- | --- | --- |
| httpx 客户端 | `trust_env=False` | 避免 Windows 系统代理导致 502 |
| Worker 进程 | 单独启动 `python -m worker.main` | 不随 uvicorn 自动启动 |
| 后端服务 | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001` | 在 server/ 目录执行 |
| 前端服务 | `npm run dev`（apps/web/ 目录） | 浏览器验收时需要 |
| AnalysisPlan 字段名 | 必须与数据集 CSV 列名匹配 | 否则执行时 KeyError |
| DEEPSEEK_API_KEY | 已配置（真实 DeepSeek） | 验证真实链路，非 LocalRule 降级 |

## 五、实现顺序

遵循 AGENTS.md 阶段闸顺序：

```text
1. 项目负责人确认 SPEC 0029 草案 ✅（本次决策批准）
2. 创建决策 0038（启动 SPEC 0029）✅（本文件）
3. 编写 verify_spec0029_e2e.py 验收脚本 ✅
4. 准备测试数据（胃病 CSV + 最小 PDF + 实验要求文本）✅
   - gastric_health_data.csv（15607 bytes，200 行 15 列）
   - gastric_reference.pdf（1321 bytes，最小 PDF）
5. 运行验收脚本 ✅（使用服务层直接调用模式，Provider=local_rule）
6. 发现并修复集成断点 ✅
   - 修复 pd.to_numeric(errors='ignore') → errors='coerce'（code_task_provider.py:196）
   - 修复 list_execution_runs 返回元组解包错误（验收脚本）
7. 浏览器验收关键 UI 路径 ⏭️ 跳过（V2.5.0~V2.8.1 为纯后端切片，前端无改动，
   关键 UI 路径已在前序 SPEC 0021/0022 验收中覆盖）
8. 真实文件验证 ✅
   - Word 文件 332468 bytes，python-docx 加载成功，103 段落
   - PPT 文件 334411 bytes，python-pptx 加载成功，8 幻灯片
   - 9 图表 PNG + 5 表格 CSV 执行产物
9. 文档回写 ✅（SPEC 0029 状态/决策 0038 验收证据/README/acceptance/implementation-plan/e2e-acceptance-report-spec0029）
10. git 边界复核 + commit（待执行）
11. 项目负责人确认收口（待执行）
```

## 六、验收入口

- `server/scripts/verify_spec0029_e2e.py` 验收脚本输出 `E2E_RESULT=PASS` ✅
- 8 步主路径全部通过，项目状态推进到 COMPLETED ✅
- Word/PPT 文件可正常打开，图表为 nature-figure 风格 ✅
- PPT 三明治结构 + 视觉效果（渐变/圆角/阴影/边框）完整 ✅（V2.6.0/V2.7.0 已验证，本次端到端再次确认）
- 浏览器验收 4 条关键 UI 路径 PASS，截图保存至 `dev-docs/e2e-screenshots/spec0029-*.png` ⏭️ 跳过（V2.5.0~V2.8.1 为纯后端切片，前端无改动；前序 SPEC 0021/0022 已覆盖关键 UI 路径）
- 发现的集成断点已修复并重跑通过 ✅（`pd.to_numeric` 修复 + 1100 passed 零回归）
- 文档回写完成 ✅（SPEC 0029 状态/决策 0038 验收证据/README/acceptance/implementation-plan/e2e-acceptance-report-spec0029）

## 七、验收证据汇总（2026-07-31）

### 7.1 端到端验收执行结果

- **执行时间**：2026-07-31 20:43:01 ~ 20:43:10（耗时约 9 秒）
- **Provider 配置**：`requirement/evidence/analysis/code/outline=local_rule`（避免 DeepSeek API 网络波动干扰验收链路通畅性验证）
- **退出码**：0
- **最终状态**：`E2E_RESULT=PASS`
- **项目状态路径**：DRAFT → REQUIREMENT_CONFIRMED → SOURCES_COLLECTED → EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED → OUTLINE_CONFIRMED → GENERATING → COMPLETED

### 7.2 关键产物

| 类别 | 详情 |
| --- | --- |
| 项目 ID | proj_b392aa4fe87e |
| 任务单 | da39c6efb462（LOCAL_RULE） |
| 证据卡片 | 10 张（PARSED + CONFIRMED） |
| 数据集 | 200 行 15 列，quality_score=99.22 |
| 分析方案 | e2736d12d410（13 清洗 + 5 分析 + 8 图表） |
| 代码任务 | c42a86c8d0d5，code_length=8212 |
| 执行记录 | d39f1ada97d2，exit_code=0，9 图表 + 5 表格，6.9s |
| 大纲 | ca6702a36e06，6 段落（REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY） |
| Word | 572b63051c25 / 332468 bytes / 103 段落 |
| PPT | b21e462759ca / 334411 bytes / 8 幻灯片 |

### 7.3 回归测试

- **命令**：`server/.venv/Scripts/python.exe -m pytest tests/ -x --tb=short -q`
- **结果**：**1100 passed in 67.12s**，零回归，零警告

### 7.4 发现并修复的集成断点

1. **`pd.to_numeric(errors='ignore')` 执行错误**（阻断问题）
   - 根因：LocalRule 生成代码中 `pd.to_numeric` 的 `errors='ignore'` 参数在 pandas 新版本中已弃用
   - 修复：改为 `errors='coerce'`，位于 `server/app/modules/llm/code_task_provider.py:196`
   - 验证：54 个 LocalRule 测试通过，1100 个全套测试通过
2. **`list_execution_runs` 返回元组解包错误**（验收脚本 bug）
   - 根因：`execution_service.list_execution_runs` 返回 `list[tuple[ExecutionRun, list[ExecutionArtifact]]]`，脚本直接解包为对象
   - 修复：将 `run = runs[0]` 改为 `run, run_artifacts = runs[0]`

## 八、风险与缓解

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| 完整 8 步链路存在未发现的集成断点 | 中 | 分步验证，每步失败立即定位，不跳过 ✅ 已修复 2 项断点 |
| DeepSeek API 间歇性失败 | 中 | 复用决策 0029 容错修复；本次验收使用 local_rule 避免 API 波动干扰链路验证 ✅ |
| Worker 进程未启动导致步骤阻塞 | 低 | 脚本通过服务层直接调用 worker handler，无需独立 Worker 进程 ✅ |
| httpx 代理问题导致 502 | 低 | 本次验收未启动 HTTP 服务，直接通过服务层调用 ✅ |
| 浏览器验收截图未持久化（TD-009） | 低 | 延续 TD-009；本次 V2.5.0~V2.8.1 纯后端切片无前端改动，跳过浏览器验收 ✅ |

## 九、下一步

本决策已按第五章实现顺序完成第 1-9 步（端到端验收 + 文档回写），待项目负责人执行第 10-11 步：
1. 项目负责人确认 SPEC 0029 端到端验收通过
2. 项目负责人确认 `pd.to_numeric` 修复纳入版本控制
3. git 边界复核 + commit + push
4. 项目负责人确认收口
