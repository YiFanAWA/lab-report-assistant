# 决策 0019：接入真实 DeepSeek LLM

## 状态

已接受。

## 日期

2026-07-23

## 决策人

项目负责人。

## 背景

V1.0.0 使用 LocalRule 本地规则提供者生成所有候选（实验要求拆解、证据卡片、分析方案、代码任务、实验大纲）。LocalRule 基于关键词匹配，候选质量受限于规则覆盖面，无法处理复杂或非标准的实验要求。

V1.0 的最大功能缺口是真实 LLM 未接入（V1.0 已知限制 L1、架构待决事项 A1）。V1.1.0 的核心目标是接入真实 DeepSeek LLM，提升候选质量。

## 决策

接入 **DeepSeek LLM**（通过统一 LLM Gateway），保留 LocalRule 作为降级后备。

### 技术选择

1. **直接 HTTP 调用而非 openai SDK**：减少依赖，DeepSeek API 兼容 OpenAI 格式，直接用 httpx 调用即可。
2. **Pydantic 结构化输出校验**：每个 provider 用 Pydantic 模型校验 LLM 返回的 JSON，防止幻觉导致字段缺失。
3. **降级策略**：LLM 调用失败时自动降级到 LocalRule，不阻断流程。
4. **环境变量切换**：通过 `REQUIREMENT_DRAFT_PROVIDER=deepseek` 等环境变量切换，无需修改代码。
5. **monkeypatch 而非 patch settings**：单元测试使用 monkeypatch 设置环境变量，避免 mock 对象状态泄露。

### 新增依赖

- `httpx>=0.24.0`（从 dev 依赖提升为生产依赖）

### 新增文件

- 基础设施：`server/app/infrastructure/llm/deepseek_client.py`
- 5 个 provider：`server/app/modules/llm/deepseek_*.py`
- 2 个测试文件：`server/tests/test_deepseek_client.py` + `test_deepseek_providers.py`

## 范围边界

本决策引入：

- DeepSeekClient 基础设施（HTTP 调用/超时/重试/错误映射）
- 5 个 DeepSeek provider 实现（继承现有 ABC 接口）
- Gateway 工厂函数扩展（新增 deepseek 分支）
- 5 个环境变量配置
- 36 个单元测试（mock HTTP，不调用真实 API）

本决策明确不做：

- 不接入其他 LLM 供应商（只接 DeepSeek）
- 不做流式输出（保持异步任务模式）
- 不做 LLM 调用缓存
- 不做 LLM 成本统计和计费
- 不修改现有 API 路由合同（前端无感切换）
- 不删除 LocalRule（作为降级后备保留）

## 验收证据

- `python -m pytest`：605 passed, 0 warnings（原 569 + 新增 36）
- 新增测试覆盖成功/降级/校验失败/错误码映射场景
- 现有 569 个测试无回归

## 约束

- 不为通过测试而简化降级逻辑
- 不删除 LocalRule（降级后备）
- 不修改现有 API 合同
- 真实 DeepSeek 调用需要 `DEEPSEEK_API_KEY` 环境变量
- LLM 调用失败不得向前端返回裸异常
