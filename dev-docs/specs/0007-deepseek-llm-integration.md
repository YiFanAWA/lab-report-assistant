# SPEC 0007：真实 DeepSeek LLM 接入

> **状态：** 已由项目负责人批准进入实现  
> **日期：** 2026-07-23  
> **前置：** V1.0.0 已发布（v1.0.0 标签）  
> **目标版本：** v1.1.0

---

## 一、目标与边界

### 1.1 目标

将 V1.0 的 5 个 LocalRule 提供者替换为真实 DeepSeek LLM 提供者，保留 LocalRule 作为降级后备：

| # | 提供者 | 配置项 | LocalRule 文件 | LLM 替换文件 |
| --- | --- | --- | --- | --- |
| 1 | 实验要求拆解 | `REQUIREMENT_DRAFT_PROVIDER` | `local_rule_provider.py` | `deepseek_requirement_provider.py` |
| 2 | 证据卡片提取 | `EVIDENCE_CARD_PROVIDER` | `evidence_card_provider.py` | `deepseek_evidence_provider.py` |
| 3 | 分析方案生成 | `ANALYSIS_PLAN_PROVIDER` | `analysis_plan_provider.py` | `deepseek_analysis_plan_provider.py` |
| 4 | 代码任务生成 | `CODE_TASK_PROVIDER` | `code_task_provider.py` | `deepseek_code_task_provider.py` |
| 5 | 实验大纲生成 | `OUTLINE_PROVIDER` | `outline_provider.py` | `deepseek_outline_provider.py` |

### 1.2 范围内

- 新增 `DeepSeekClient` 基础设施（统一 HTTP 调用 + 超时 + 重试 + 日志）
- 新增 5 个 DeepSeek provider 实现（继承现有 ABC）
- 扩展 Gateway 工厂函数，新增 `deepseek` 选项
- Pydantic 结构化输出校验（防止 LLM 幻觉导致字段缺失）
- LLM 不可用时降级到 LocalRule
- 新增 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_TIMEOUT_SECONDS`、`DEEPSEEK_MAX_RETRIES` 环境变量
- 单元测试（mock HTTP 调用 + 结构化输出校验）

### 1.3 范围外

- 不接入其他 LLM 供应商（只接 DeepSeek）
- 不做流式输出（保持异步任务模式）
- 不做 LLM 调用缓存
- 不做 LLM 成本统计和计费
- 不做在线 LLM 配置切换（通过环境变量配置）
- 不修改现有 LocalRule 实现（作为降级后备保留）
- 不修改现有 API 路由合同（Gateway 透明切换）

---

## 二、架构设计

### 2.1 分层架构

```
API 路由（不改动）
  ↓ 调用
Gateway 工厂函数（扩展：新增 deepseek 分支）
  ↓ 返回
DeepSeekXxxProvider（新增，继承现有 ABC）
  ↓ 调用
DeepSeekClient（新增，基础设施层）
  ↓ HTTP POST
DeepSeek API（https://api.deepseek.com/chat/completions）
```

### 2.2 唯一 Owner 边界

| 层 | Owner | 职责 |
| --- | --- | --- |
| 基础设施 | `server/app/infrastructure/llm/deepseek_client.py` | HTTP 调用、超时、重试、错误映射 |
| LLM 模块 | `server/app/modules/llm/deepseek_*.py` | Prompt 构造、结构化输出校验、降级逻辑 |
| Gateway | `server/app/modules/llm/gateway.py` | 工厂选择（local_rule/deepseek/fake） |
| 配置 | `server/app/core/config.py` | 环境变量读取 |
| API 路由 | 不改动 | 只通过 Gateway 获取 provider |

### 2.3 降级策略

```
LLM 调用失败（网络/超时/HTTP错误/JSON解析失败/Pydantic校验失败）
  ↓
记录错误日志（LLM_FALLBACK 触发）
  ↓
降级到 LocalRule 提供者
  ↓
source_label 标记为 "LOCAL_RULE_FALLBACK"
  ↓
返回候选（质量降级但不阻断流程）
```

### 2.4 结构化输出校验

每个 DeepSeek provider 使用 Pydantic 模型校验 LLM 返回的 JSON：

```python
class DeepSeekRequirementResponse(BaseModel):
    topic: str
    experiment_type: str
    research_subject: str
    required_tasks: list[DeepSeekTask]
    # ... 与 RequirementPlanPayload 对齐
```

校验失败时触发降级。

---

## 三、DeepSeekClient 设计

### 3.1 基础设施层

**文件：** `server/app/infrastructure/llm/deepseek_client.py`

```python
class DeepSeekClient:
    """DeepSeek API 统一客户端。

    职责：HTTP 调用、超时、重试、错误映射。
    不负责 Prompt 构造和结构化输出校验（由 provider 负责）。
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int, max_retries: int): ...

    def chat_completion(self, messages: list[dict],
                        response_format: dict | None = None,
                        temperature: float = 0.3) -> str:
        """调用 DeepSeek chat/completions 接口，返回 content 字符串。

        参数：
        - messages: OpenAI 兼容的 messages 格式
        - response_format: 可选，{"type": "json_object"} 要求 JSON 输出
        - temperature: 采样温度，默认 0.3（偏稳定）

        异常：
        - DeepSeekError（code, message）—— 所有错误统一为结构化错误
        """
```

### 3.2 错误码映射

| HTTP 状态 / 错误类型 | 错误码 | 处理 |
| --- | --- | --- |
| 网络超时 | `DEEPSEEK_TIMEOUT` | 降级 |
| 连接失败 | `DEEPSEEK_CONNECTION_ERROR` | 降级 |
| 401 鉴权失败 | `DEEPSEEK_AUTH_ERROR` | 降级 + 日志警告 |
| 429 限流 | `DEEPSEEK_RATE_LIMITED` | 降级 |
| 5xx 服务端错误 | `DEEPSEEK_SERVER_ERROR` | 降级 |
| JSON 解析失败 | `DEEPSEEK_JSON_PARSE_ERROR` | 降级 |
| Pydantic 校验失败 | `DEEPSEEK_SCHEMA_VALIDATION_ERROR` | 降级 |

所有错误均降级到 LocalRule，不向前端返回裸异常。

### 3.3 重试策略

- 只对 5xx 和网络超时重试
- 不对 401/429/400 重试（不可恢复）
- 重试次数：`DEEPSEEK_MAX_RETRIES`（默认 2）
- 重试间隔：指数退避（1s, 2s, 4s）

---

## 四、Provider 设计

### 4.1 统一模式

所有 5 个 DeepSeek provider 遵循相同模式：

```python
class DeepSeekXxxProvider(XxxDraftProvider):
    """DeepSeek LLM 驱动的 xxx 候选提供者。"""

    def __init__(self, client: DeepSeekClient,
                 fallback: LocalRuleXxxProvider): ...

    def source_label(self) -> str:
        return "DEEPSEEK"

    def generate(self, ...) -> XxxDraft:
        try:
            prompt = self._build_prompt(...)
            raw = self._client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            parsed = self._parse_and_validate(raw)
            return self._to_draft(parsed)
        except (DeepSeekError, ValidationError) as e:
            logger.warning(f"DeepSeek 调用失败，降级到 LocalRule: {e}")
            return self._fallback.generate(...)
```

### 4.2 Prompt 设计原则

- **System prompt** 明确角色和输出格式要求
- **User prompt** 包含结构化上下文（已确认的任务单/证据/字段概览/分析方案/执行结果）
- **要求 JSON 输出**：`response_format={"type": "json_object"}`
- **字段对齐**：Prompt 中说明的 JSON schema 与 Pydantic 模型一致
- **不泄露原始数据**：只传概览和摘要，不传完整数据集

---

## 五、配置项

### 5.1 新增环境变量

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | `""` | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 基础 URL |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | HTTP 超时秒数 |
| `DEEPSEEK_MAX_RETRIES` | `2` | 最大重试次数 |
| `DEEPSEEK_TEMPERATURE` | `0.3` | 采样温度 |

### 5.2 现有配置项复用

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `deepseek` | LLM 供应商 |
| `LLM_MODEL` | `deepseek-v4-pro` | 模型名 |
| `REQUIREMENT_DRAFT_PROVIDER` | `local_rule` | 切换为 `deepseek` 启用 |
| `EVIDENCE_CARD_PROVIDER` | `local_rule` | 切换为 `deepseek` 启用 |
| `ANALYSIS_PLAN_PROVIDER` | `local_rule` | 切换为 `deepseek` 启用 |
| `CODE_TASK_PROVIDER` | `local_rule` | 切换为 `deepseek` 启用 |
| `OUTLINE_PROVIDER` | `local_rule` | 切换为 `deepseek` 启用 |

### 5.3 启用方式

方式 A（全局启用）：
```bash
set REQUIREMENT_DRAFT_PROVIDER=deepseek
set EVIDENCE_CARD_PROVIDER=deepseek
set ANALYSIS_PLAN_PROVIDER=deepseek
set CODE_TASK_PROVIDER=deepseek
set OUTLINE_PROVIDER=deepseek
set DEEPSEEK_API_KEY=sk-xxx
```

方式 B（单模块启用）：
```bash
set OUTLINE_PROVIDER=deepseek
set DEEPSEEK_API_KEY=sk-xxx
```

---

## 六、API 合同

### 6.1 不修改现有 API

V1.1.0 **不修改任何现有 API 路由合同**。LLM 接入对前端透明：
- Gateway 根据环境变量自动选择 provider
- `candidate_source` 字段值从 `LOCAL_RULE` 变为 `DEEPSEEK`（或 `LOCAL_RULE_FALLBACK`）
- 响应结构不变

### 6.2 新增 API（可选，运维用途）

```
GET /api/llm/status
```

返回当前 LLM 配置状态（不暴露密钥）：

```json
{
  "llm_provider": "deepseek",
  "llm_model": "deepseek-v4-pro",
  "providers": {
    "requirement_draft": "deepseek",
    "evidence_card": "deepseek",
    "analysis_plan": "deepseek",
    "code_task": "deepseek",
    "outline": "deepseek"
  },
  "api_key_configured": true
}
```

---

## 七、测试策略

### 7.1 单元测试（mock HTTP）

- `test_deepseek_client.py`：mock HTTP 响应，测试成功/超时/401/429/5xx/JSON 解析失败
- `test_deepseek_providers.py`：mock DeepSeekClient，测试 5 个 provider 的成功/降级/校验失败场景

### 7.2 测试原则

- 不调用真实 DeepSeek API（CI 和本地测试均 mock）
- 测试结构化输出校验（LLM 返回缺失字段时降级）
- 测试降级路径（LLM 失败后 LocalRule 返回正确候选）
- 测试 source_label 正确标记（`DEEPSEEK` / `LOCAL_RULE_FALLBACK`）

### 7.3 验收命令

```text
server/.venv/Scripts/python.exe -m pytest
npm.cmd run lint
npm.cmd run build
```

---

## 八、依赖

### 8.1 新增依赖

- **`httpx>=0.24.0`**（已在 dev 依赖中，提升为生产依赖）

### 8.2 不新增依赖

- 不使用 `openai` SDK（直接 HTTP 调用，减少依赖）
- 不使用 `tenacity`（重试逻辑自己实现，简单场景）

---

## 九、验收标准

1. `DEEPSEEK_API_KEY` 配置后，5 个 provider 可调用真实 DeepSeek
2. LLM 调用失败时自动降级到 LocalRule，不向前端返回裸异常
3. `candidate_source` 正确标记为 `DEEPSEEK` 或 `LOCAL_RULE_FALLBACK`
4. Pydantic 结构化输出校验生效（LLM 幻觉字段缺失时降级）
5. 单元测试全部通过（mock HTTP），0 warnings
6. 现有 API 路由合同不变（前端无感切换）
7. LocalRule 仍可作为独立 provider 使用（不删除、不破坏）

---

## 十、实施顺序

按 AGENTS.md 阶段闸：

1. **SPEC 0007 文档确认**（本文件）
2. **DeepSeekClient 基础设施**（`server/app/infrastructure/llm/deepseek_client.py`）
3. **5 个 DeepSeek provider 实现**（`server/app/modules/llm/deepseek_*.py`）
4. **Gateway 扩展**（`server/app/modules/llm/gateway.py` 新增 `deepseek` 分支）
5. **config 配置项**（`server/app/core/config.py` 新增 5 个环境变量）
6. **单元测试**（mock HTTP + 结构化输出校验 + 降级路径）
7. **验收命令**（pytest + lint + build）
8. **文档回写**（changelog、acceptance、dependency-review、decisions/0019）
9. **git 提交推送**
