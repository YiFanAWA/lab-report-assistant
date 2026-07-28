# 实验报告助手 V2.4.0 发布通知

**版本：** v2.4.0
**发布日期：** 2026-07-28
**上一版本：** v2.3.0
**提交：** `c4b5fdf`（tag `v2.4.0`）
**变更范围：** 1 个开发切片（SPEC 0022 代码任务生成流式化）

---

## 🎯 核心亮点

**V2.4.0 完成实验报告工作流第五个、也是最后一个 LLM 生成环节的流式化改造。**

用户在「分析方案已确认」状态下点击「流式生成」按钮后，能实时看到 LLM 逐 chunk 生成的代码任务 JSON（含 `code` 字段的 Python 代码），并随时可取消。这标志着流式化改造**全面完成**，五个 LLM 生成场景（任务单 / 大纲 / 证据卡片 / 分析方案 / 代码任务）全部具备流式能力。

## 📋 主要变更点

### 1. 新增功能：SPEC 0022 代码任务生成流式化

| 维度 | V2.3.0（Worker 异步） | V2.4.0（SSE 流式） |
|---|---|---|
| 用户等待感知 | 任务状态轮询 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持 | 支持（取消按钮 + 服务端断开检测） |
| 错误反馈 | 任务失败后提示 | 中途失败保留已生成内容（partial_text） |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /analysis/{plan_id}/code/generate`（**保留兼容**） | `POST /analysis/{plan_id}/code/stream-generate`（新增 SSE） |

**新增端点：** `POST /api/projects/{project_id}/analysis/{plan_id}/code/stream-generate`

**架构选择（复用 SPEC 0018/0019/0020/0021 成熟模式）：**

- SSE 端点绕过 Worker，请求内直接调用 Provider（解决 Worker 异步与 SSE 同步推送语义不兼容）
- 分段持有 db session：Phase 1 校验 → Phase 2 流式生成（释放 db）→ Phase 3 JSON 校验 → Phase 4 保存（重新打开 db）
- 降级策略：首 chunk 前失败降级 `LocalRuleCodeTaskProvider`（拆分多 chunk 模拟流式）
- 错误分层：流前错误用 HTTP 状态码（404/409），流后错误用 SSE `error` 事件
- **并发保护**：服务端 `active_streams` 字典，同一 AnalysisPlan 同一时刻仅允许一个活动流式请求
- **服务端取消语义**：`Request.is_disconnected()` 检测客户端断开，取消后不保存、不推送 done/error
- **Phase 3 状态复核**：保存前重新校验项目、AnalysisPlan 状态与 `updated_at` 版本一致性
- 保留原 Worker 异步端点与 handler 零改动（完全向后兼容）

### 2. 收口复核修复（1 项阻断问题）

**问题：** 浏览器验收期间发现 `LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 分析类型调用 `target_fields.split()`，假设字符串，但 SPEC 0021 修复后 `target_fields` 可能为 list（如 `["diagnosis","gender"]`），导致 `'list' object has no attribute 'split'` 异常。

**修复：** 新增 `_first_field_name()` 辅助函数兼容 list/str/None 三种类型，新增 2 个回归测试覆盖。

## 📊 测试统计

| 测试面 | 数量 | 说明 |
|---|---|---|
| 后端 | **975 passed**（0 warnings） | 895 原有 + 80 新增（SPEC 0022 流式 78 + 回归 2） |
| 前端 | **570 passed** | 551 原有 + 19 新增 |
| **合计** | **1545 个测试** | 新增 99 个 |
| 浏览器验收 | ✅ PASS | 6 个关键验证点全部通过（流式按钮 / JSON 累积 / 取消 / 完成提示 / 列表刷新 / CANDIDATE 状态） |

**新增测试文件：**

- `test_deepseek_code_task_provider_stream.py`（14）
- `test_code_task_service_stream.py`（9）
- `test_code_task_stream_api.py`（17）
- `test_local_rule_code_task_provider_format.py`（21 + 2 回归）
- `api-stream.test.ts`（7）
- `hooks-stream.test.tsx`（12）

## 🔒 约束遵守

| 约束 | 结果 |
|---|---|
| 不引入新依赖（Python / npm） | ✅ |
| 不修改数据库 schema（无 Alembic 迁移） | ✅ |
| 复用 `stream-sse.ts`（零修改） | ✅ |
| 保留原 Worker 异步端点兼容 | ✅ |
| Worker handler 零改动 | ✅ |
| 不引入 WebSocket / 长轮询 | ✅ |
| owner 边界保持（API 只做协议映射） | ✅ |

## ⚠️ 已知限制

1. **TD-009 延续**：浏览器验收截图已通过 browser_use agent 持久化（5 张截图保存成功），TD-009 作为历史债务延续，非阻断。
2. **DEEPSEEK_API_KEY 未设置**：本次浏览器验收在 LocalRule 降级路径下完成；真实 DeepSeek 流式调用路径已在后端单元测试（mock DeepSeekClient）中覆盖，待后续配置真实 API_KEY 后补充真实 LLM 流式验收。
3. **流式阶段展示原始 JSON**：采用方案 A（流式展示原始 JSON 文本，完成后切换为格式化代码），未引入增量 JSON 解析器或代码语法高亮库，留待后续优化切片。

## 📦 升级说明

- **本地部署用户**：`git pull origin master` 即可，无需数据库迁移、无需安装新依赖。
- **Docker 部署用户**：重新构建镜像即可（`docker-compose build && docker-compose up -d`）。
- **配置项**：无新增环境变量。

## 📁 详细变更

完整变更说明请见 [changelog-v2.4.0.md](changelog-v2.4.0.md)。

## 🔮 下一阶段

实验报告工作流五个 LLM 生成环节已全部完成流式化。后续可选方向（待项目负责人规划）：

- **SPEC 0023**：多来源证据批量流式生成（扩展 SPEC 0020 支持跨来源批量）
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收
- **前端流式状态持久化**：流式中刷新页面时恢复流式状态

后续新切片开始前仍需先编写并确认新 SPEC。
