# SPEC 0020 证据卡片流式化浏览器端到端验收报告

**验收日期：** 2026-07-26
**验收范围：** SPEC 0020 证据卡片生成流式化（AC-39 浏览器验收）
**验收环境：** Windows 11 Pro，Python 3.13.5，Node.js，SQLite，本地单用户
**验收人：** AI Agent（项目负责人授权）
**结论：** **通过**，AC-39 浏览器验收满足要求

---

## 一、验收总览

| 序号 | 验收项 | 类型 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | 后端 SSE 端点 | API 验证 | ✅ 通过 | POST /sources/{source_id}/evidence/stream-generate 返回 200 + text/event-stream |
| 2 | 前端服务启动 | 运行时验证 | ✅ 通过 | Vite dev 在 5173 端口启动 |
| 3 | 后端服务启动 | 运行时验证 | ✅ 通过 | uvicorn 在 8001 端口启动，/health 返回 ok |
| 4 | 浏览器页面加载 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-01-home.png |
| 5 | 项目详情页 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-02-project-detail.png |
| 6 | 证据卡片工作区 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-03-evidence-workspace.png |
| 7 | 流式生成按钮与原按钮共存 | UI 验收 | ✅ 通过 | "生成候选"与"流式生成"按钮并列可见 |
| 8 | 流式生成过程展示 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-04-streaming-start.png |
| 9 | 流式完成提示 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-05-streaming-done.png |
| 10 | 证据卡片列表刷新 | UI 验收 | ✅ 通过 | 截图 e2e-spec0020-07-evidence-cards.png |
| 11 | 证据卡片持久化 | API 验证 | ✅ 通过 | GET /evidence 返回 3 张 CANDIDATE 卡片（LOCAL_RULE） |
| 12 | 浏览器控制台 | UI 验收 | ✅ 通过 | 无 SPEC 0020 相关 error |

---

## 二、验收环境

- 前端地址：`http://localhost:5173/`
- 后端地址：`http://127.0.0.1:8001`
- 数据库：SQLite（已迁移到最新 head）
- 浏览器：Chromium（browser_use agent 驱动）
- LLM 配置：DEEPSEEK_API_KEY 未设置，后端降级到 LocalRule 规则生成器
- 测试数据：
  - 项目 ID：`proj_spec0020_e2e`（状态 REQUIREMENT_CONFIRMED）
  - 来源 ID：`src_spec0020_e2e_001`（状态 PARSED，含多段落文本，每段 ≥ 30 字符）

---

## 三、浏览器端到端验收详情

### 3.1 首页加载

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 页面 URL | ✅ | `http://localhost:5173/` 正常加载 |
| 页面标题 | ✅ | "实验报告助手" |
| 项目列表 | ✅ | 显示"SPEC0020 流式证据卡片验收项目" |
| 白屏检查 | ✅ | 无白屏，页面正常渲染 |

截图：`e2e-screenshots/e2e-spec0020-01-home.png`

### 3.2 进入项目详情页

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| URL 跳转 | ✅ | 跳转至 `/projects/proj_spec0020_e2e` |
| 项目信息 | ✅ | 显示项目名称、课题、状态 |
| 功能区域 | ✅ | 显示各功能入口 |

截图：`e2e-screenshots/e2e-spec0020-02-project-detail.png`

### 3.3 证据卡片工作区

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 来源列表 | ✅ | 显示"胃病数据分析参考文档（验收用）" |
| 来源状态 | ✅ | 显示"已解析" |
| 生成候选按钮 | ✅ | 蓝色"生成候选"按钮可见 |
| 流式生成按钮 | ✅ | 紫色"流式生成"按钮可见（与原按钮并列） |

截图：`e2e-screenshots/e2e-spec0020-03-evidence-workspace.png`

### 3.4 流式生成过程（核心验收项）

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 按钮状态切换 | ✅ | 点击后按钮文字变为"流式生成中…" |
| chunk 展示区 | ✅ | 出现带边框灰色背景展示区，显示累积 JSON |
| JSON 内容 | ✅ | 展示区包含 cards/summary/evidence_type 等字段 |
| 取消按钮 | ✅ | 出现红色边框"取消"按钮 |
| 正在生成提示 | ✅ | 显示"正在逐 chunk 生成…"提示 |

截图：`e2e-screenshots/e2e-spec0020-04-streaming-start.png`

### 3.5 流式完成状态

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 展示区消失 | ✅ | 流式展示区和取消按钮在完成后消失 |
| 完成提示 | ✅ | 显示绿色"流式生成完成 ✓ [LOCAL_RULE（降级）] · 共 3 张卡片" |
| 卡片列表刷新 | ✅ | 证据卡片列表自动刷新，显示 3 张新生成的卡片 |
| 卡片内容 | ✅ | 每张卡片显示 summary、evidence_type、locator 等信息 |

截图：`e2e-screenshots/e2e-spec0020-05-streaming-done.png`、`e2e-spec0020-07-evidence-cards.png`

### 3.6 证据卡片持久化验证

通过 API 验证证据卡片已持久化到数据库：

```
GET /api/projects/proj_spec0020_e2e/evidence
```

返回 3 张 CANDIDATE 状态的证据卡片：

| 卡片 | evidence_type | locator | candidate_source | status |
| --- | --- | --- | --- | --- |
| 1 | BACKGROUND | 第1段 | LOCAL_RULE | CANDIDATE |
| 2 | METHOD | 第2段 | LOCAL_RULE | CANDIDATE |
| 3 | RESULT | 第3段 | LOCAL_RULE | CANDIDATE |

### 3.7 控制台消息

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| SPEC 0020 相关 error | ✅ 无 | 流式生成流程未产生任何 error |
| 历史遗留 error | ✅ 无关 | 其他项目/功能残留请求，与 SPEC 0020 无关 |

---

## 四、验收结论

### 4.1 AC-39 验收结果

| AC | 描述 | 结果 |
| --- | --- | --- |
| AC-39 | 浏览器验收：流式生成按钮可见、点击后流式展示区显示 chunk 累积、完成后显示候选来源提示、证据卡片列表刷新 | ✅ 通过 |

### 4.2 功能验证矩阵

| 功能点 | 设计要求 | 实际结果 | 结论 |
| --- | --- | --- | --- |
| 流式按钮与原按钮共存 | "生成候选"和"流式生成"并列 | 两个按钮并列显示 | ✅ |
| 点击触发流式 | 调用 streamGenerateEvidence | 按钮变为"流式生成中…" | ✅ |
| chunk 累积展示 | 带边框展示区 + pre 标签 | 展示区显示累积 JSON | ✅ |
| 取消按钮 | 流式期间显示 | 红色边框取消按钮可见 | ✅ |
| 完成提示 | 含 candidate_source + 降级标记 | "LOCAL_RULE（降级）· 共 3 张卡片" | ✅ |
| 卡片列表刷新 | done 事件触发 invalidate | 列表自动显示 3 张新卡片 | ✅ |
| 降级路径 | DEEPSEEK_API_KEY 未设置时降级 | LocalRule 降级，fallback_used=true | ✅ |
| 数据持久化 | 完成后卡片写入数据库 | API 查询返回 3 张 CANDIDATE 卡片 | ✅ |

### 4.3 截图清单

| 截图文件 | 说明 |
| --- | --- |
| e2e-spec0020-01-home.png | 首页加载 |
| e2e-spec0020-02-project-detail.png | 项目详情页 |
| e2e-spec0020-03-evidence-workspace.png | 证据卡片工作区（流式前） |
| e2e-spec0020-04-streaming-start.png | 流式生成中（chunk 累积 + 取消按钮） |
| e2e-spec0020-05-streaming-done.png | 流式完成（绿色提示） |
| e2e-spec0020-07-evidence-cards.png | 证据卡片列表刷新 |

截图保存路径：`dev-docs/e2e-screenshots/`

---

## 五、非阻断说明

1. **DEEPSEEK_API_KEY 未设置**：本次验收在 LocalRule 降级路径下完成，未覆盖 DeepSeek 真实流式调用路径。DeepSeek 真实流式调用路径已在后端单元测试（test_deepseek_evidence_provider_stream.py，mock DeepSeekClient）中覆盖，待后续配置真实 API_KEY 后补充真实 LLM 流式验收。

2. **历史遗留控制台 error**：控制台存在其他项目/功能的历史请求残留 error，与 SPEC 0020 流式证据卡片功能无关，不影响本次验收结论。
