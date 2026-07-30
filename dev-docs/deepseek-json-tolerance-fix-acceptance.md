# DeepSeek 任务单 JSON 解析失败容错修复｜验收报告

> 日期：2026-07-30
> 范围：后端 DeepSeek 流式生成任务单时高频抛 `DEEPSEEK_JSON_PARSE_ERROR` 的根因排查、修复与验证
> 状态：修复已实施并验证；真实 DeepSeek 5 次复测失败率 60%→0%
> 关联文档：[决策 0029](decisions/0029-deepseek-json-tolerance-fix.md)、[Vite 代理 SSE 缓冲修复验收报告](vite-proxy-sse-fix-acceptance.md)（其 TODO-1 由本次修复关闭）

## 1. 问题现象

前次 Vite 代理 SSE 缓冲修复完成后（详见 `vite-proxy-sse-fix-acceptance.md`），SSE 传输层已确认完整（1471 chunk 全部到达），但流式最终收到 `event: error`（`error_code: DEEPSEEK_JSON_PARSE_ERROR`）而非 `event: done`。

具体表现：
- 前端流式生成任务单时，chunk 内容能正常增量显示
- 流式末尾收到 error 事件，`message` 为"流式生成的 JSON 校验失败: ..."
- 前端展示错误提示，任务单未保存
- 浏览器侧表现为 `net::ERR_ABORTED`（实为对后端 error 事件的处理副作用，非传输问题）

## 2. 排查步骤

### 2.1 定位错误抛出点

通过代码审查定位到错误抛出位置：[`deepseek_requirement_provider.py`](../server/app/modules/llm/deepseek_requirement_provider.py) 的 `stream_draft` 方法。

```python
# stream_draft 末尾，流式完成后校验完整 JSON
raw = "".join(chunks)
try:
    self._parse_and_validate(raw)
except DeepSeekError:
    raise
except Exception as e:
    raise DeepSeekError(
        code="DEEPSEEK_JSON_PARSE_ERROR",
        message=f"流式生成的 JSON 校验失败: {e}",
    ) from e
```

`_parse_and_validate` 内部两步校验：
1. `json.loads(raw)` —— JSON 语法校验
2. `DeepSeekRequirementResponse.model_validate(data)` —— Pydantic 结构校验

**问题：错误消息只含 `{e}`，不记录 raw 内容，无法判断是 JSON 语法错误还是结构不符。**

### 2.2 确认缓存不参与

检查 `LLM_CACHE_ENABLED` 配置（`config.py` 默认 `false`，`.env` 未设置），**LLM 缓存禁用**，排除"缓存污染导致持续失败"的推测。

### 2.3 编写独立诊断脚本

为不污染生产代码，编写独立诊断脚本 `.tmp/diagnose_deepseek_json.py`，逻辑：
1. 从数据库读取项目 `proj_2759dc9c98d7` 的 `RequirementSource.original_text`（232 字符的胃病实验要求）
2. 用相同的 `_SYSTEM_PROMPT` + `_build_user_prompt` 调用 `DeepSeekClient.stream_chat_completion` 获取完整 raw
3. 输出 raw 长度、前 2000 字符、末尾 500 字符
4. 依次尝试 `json.loads(raw)` 和 `DeepSeekRequirementResponse.model_validate(data)`
5. 失败时输出精确的 `ValidationError.errors()`（含 loc、type、msg、input）

### 2.4 首次单次调用

首次单次调用 DeepSeek API：**校验通过**（837 chunks，2153 字符，合法 JSON 且符合 schema）。

这说明问题是**间歇性**的，非必然失败。根因在 LLM 输出的随机性（`temperature=0.3`）。

### 2.5 循环 5 次复现失败

将诊断脚本改为循环调用 5 次，成功复现：**5 次调用，3 次失败（60% 失败率）**。

## 3. 根因分析

### 3.1 失败模式 A：`suggested_scope` 返回 `null`（第 2 次）

`DeepSeekReplicationLevel.suggested_scope` 字段定义为 `str`（非 Optional），但 LLM 返回了 `null`：

```json
"replication_level": {
    "level": "L1",
    "label": "方法复述",
    "supported_in_v1": true,
    "reason": "...",
    "suggested_scope": null
}
```

Pydantic 报错：`loc=('replication_level', 'suggested_scope')`, `type=string_type`, `input_value=None`

### 3.2 失败模式 B：`*_requirements` 返回对象数组（第 4、5 次）

`data_requirements` / `method_requirements` / `chart_requirements` / `report_requirements` 字段定义为 `list[str]`，但 LLM 返回了 `list[dict]`：

```json
// schema 要求：list[str]
"chart_requirements": [
    {"description": "年龄分布直方图"},
    {"description": "不同性别患者的病情分布图"},
    {"description": "各指标相关性矩阵热力图"}
]
```

Pydantic 报错：`loc=('chart_requirements', 0)`, `type=string_type`, `input_value={'description': '年龄分布直方图'}`

**关键观察**：同一份输出内 `acceptance_criteria` 却返回了正确的字符串数组——**LLM 行为在同一份输出内都不一致**，无法通过单一 prompt 措辞完全规避。

### 3.3 根本原因

| 层次 | 原因 |
|------|------|
| Prompt | 原 `_SYSTEM_PROMPT` 只列字段名，没有明确元素类型约束（"字符串数组"vs"对象数组"），也没给出正/反例 |
| LLM | `temperature=0.3` 下 LLM 对 `*_requirements` 字段的返回格式在 `list[str]` 和 `list[dict]` 之间摇摆；对 `suggested_scope` 在 `str` 和 `null` 之间摇摆 |
| 容错 | provider `_parse_and_validate` 严格 `model_validate`，一旦不符直接抛异常，流式场景下已 yield 的 chunk 无法撤回 |

### 3.4 排除项

- **LLM 缓存污染**：`LLM_CACHE_ENABLED` 默认 `false`，`.env` 未启用，缓存不参与。
- **SSE 传输层**：前期已确认 1471 chunk 完整到达（见 Vite 修复报告 §4.4）。
- **JSON 语法错误**：5 次失败均为 Pydantic 结构校验失败，非 `json.loads` 语法错误。

### 3.5 证据文件

| 文件 | 内容 |
|------|------|
| `.tmp/deepseek_raw_run2.json` | `suggested_scope: null` 失败样本 |
| `.tmp/deepseek_raw_run4.json` | 多个 `*_requirements` 返回对象数组失败样本 |
| `.tmp/deepseek_raw_run5.json` | `chart_requirements` 返回对象数组失败样本 |

> 注：`.tmp/` 为 gitignored 本地排查目录，证据文件不进版本控制，仅作本地复现参考。

## 4. 修复方案与决策依据

### 4.1 候选方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A. 仅 Prompt 强化 | 只改 system prompt，明确字段类型和示例 | 最小改动 | LLM 仍有概率不遵守（temperature 随机性），无法 100% 根除 |
| B. 仅模型容错 | 只加 Pydantic validator 容错 | 校验层吸收不稳定 | prompt 不约束导致 LLM 持续返回非预期格式，容错逻辑越堆越多，补丁式开发风险 |
| C. Prompt 强化 + 轻量容错（采纳） | 两者结合 | prompt 减少错误概率，容错兜底吸收残余 | 需同时改两处 |

### 4.2 决策依据

项目负责人于 2026-07-30 确认采用 **方案 C（Prompt 强化 + 轻量容错）**，依据：

1. **符合宪法"抽象只在减少真实复杂度时引入"**：LLM 输出的不稳定性是真实存在的复杂度（5 次 60% 失败率已证），统一的 `field_validator` 是结构化容错，非散落 `if`。
2. **符合宪法"禁止补丁式开发"**：用 Pydantic v2 `field_validator(mode="before")` + 模块级函数，是声明式容错，可测试可审查。
3. **兼顾稳定性与架构干净**：prompt 强化是根治主路径，容错是兜底，两者职责清晰。
4. **不引入新依赖**：`field_validator` 是 Pydantic v2 内置。
5. **范围可控**：仅改任务单 provider，其他 provider 同类问题留观察，不预先扩大。

### 4.3 不采纳方案的理由

- **方案 A（仅 Prompt）**：LLM 输出天然不稳定，即使 prompt 明确约束，temperature=0.3 下仍可能不遵守。用户体验"流了半天最后报错"不可接受。
- **方案 B（仅容错）**：违反宪法"大模型网关只返回可校验候选结果"的精神——若 prompt 不约束，LLM 会持续返回非预期格式，容错逻辑会针对每种新偏差不断堆叠，演变为补丁式。
- **不用散落 if 容错**：宪法明确禁止。

## 5. 实施步骤

严格遵循宪法阶段闸"测试先行或至少先补风险测试"。

### 5.1 步骤 1：测试先行——补容错场景风险测试

在 `server/tests/test_deepseek_requirement_provider_stream.py` 末尾新增 `TestDeepSeekResponseTolerance` 测试类，9 个测试定义期望行为：

| 测试 | 期望 |
|------|------|
| `test_data_requirements返回对象数组时容错为字符串数组` | `[{"description":"..."}]` → `["..."]` |
| `test_method_requirements返回对象数组时容错` | 同上 |
| `test_chart_requirements返回对象数组时容错` | 同上 |
| `test_report_requirements返回对象数组时容错` | 同上 |
| `test_suggested_scope为null时容错为空串` | `null` → `""` |
| `test_混合元素数组容错_字符串与对象共存` | `["str", {"description":"x"}]` → `["str", "x"]` |
| `test_对象无description字段取首个字符串值` | `[{"reason":"x"}]` → `["x"]` |
| `test_正常字符串数组不受容错影响` | `["a","b"]` 保持不变 |
| `test_整份LLM不稳定输出容错后通过校验` | 多字段同时偏差时容错后通过 |

运行确认测试如预期失败（**8 failed, 1 passed**），证明测试能准确捕获问题：

```
FAILED test_suggested_scope为null时容错为空串
  Input should be a valid string [type=string_type, input_value=None]
FAILED test_整份LLM不稳定输出容错后通过校验
  6 validation errors: data/method/chart/report_requirements + suggested_scope
```

### 5.2 步骤 2：实现 Pydantic 容错 validator

在 `deepseek_requirement_provider.py` 新增：

**模块级容错函数**：
```python
def _coerce_str_list(v: object) -> object:
    """容错：将字符串数组中的非 str 元素统一为 str。

    转换规则：
    - str 元素：保留
    - dict 元素：优先取 description；否则取首个 str 值；都没有则跳过
    - 其他类型：str() 转换
    """
    if not isinstance(v, list):
        return v
    result: list[str] = []
    for item in v:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            desc = item.get("description")
            if isinstance(desc, str):
                result.append(desc)
            else:
                str_vals = [val for val in item.values() if isinstance(val, str)]
                if str_vals:
                    result.append(str_vals[0])
        else:
            result.append(str(item))
    return result


def _coerce_none_to_empty(v: object) -> object:
    """容错：将 None 转为空串。"""
    return "" if v is None else v
```

**在模型上加 validator**：
- `DeepSeekReplicationLevel.suggested_scope`：`@field_validator("suggested_scope", mode="before")`
- `DeepSeekRequirementResponse` 的 6 个 `list[str]` 字段（`data/method/chart/report/presentation_requirements` + `acceptance_criteria`）：统一 `@field_validator(..., mode="before")`

使用 `mode="before"` 确保在校验前转换，不污染业务 payload。

### 5.3 步骤 3：强化 `_SYSTEM_PROMPT`

在 `_SYSTEM_PROMPT` 中新增【字段类型约束——严格遵守，否则校验失败】章节：

- 明确 `*_requirements` / `chart_requirements` / `acceptance_criteria` 每个元素必须是「字符串」，不得是对象
- 给出 ✅ 正确示例：`["年龄分布直方图", "相关性矩阵热力图"]`
- 给出 ❌ 错误示例：`[{"description": "年龄分布直方图"}]`
- 明确 `replication_level.suggested_scope` 必须是「非空字符串」，不得为 null
- 给出正/反例

### 5.4 步骤 4：运行测试确认通过

```
pytest tests/test_deepseek_requirement_provider_stream.py -v
→ 16 passed in 0.36s（含 9 个新增容错测试 + 7 个原有测试，无回归）
```

## 6. 验证证据

### 6.1 后端单元测试

**目标测试文件**（含容错测试）：
```
pytest tests/test_deepseek_requirement_provider_stream.py -v
→ 16 passed in 0.36s
```

**相关目录测试**（llm + requirements，用 `local_rule` provider 正确环境）：
```
pytest tests/test_requirement_api.py tests/test_requirements_stream_api.py -q
→ 17 passed in 2.85s
```

**全量后端测试说明**：
全量 pytest 中 4 个失败为 `.env` 配置 `REQUIREMENT_DRAFT_PROVIDER=deepseek` 导致测试真实调用 DeepSeek API（日志可见 `DeepSeek 超时，attempt=1`，耗时 363s），**非本次改动回归**。用 `local_rule` provider 重跑这 4 项全部通过。

> 这是前次端到端验收留下的 `.env` 污染单元测试环境问题，已记录为环境配置债务，不在本次修复范围。

### 6.2 alembic 迁移

```
DATABASE_URL=sqlite:///临时库 python -m alembic upgrade head
→ Running upgrade -> 0001, create projects table
→ Running upgrade 0001 -> 0002, ...
→ Running upgrade 0006 -> 0007, create word_templates table
```

全量迁移 0001→0007 成功（本修复不改 schema）。

### 6.3 前端验收

```
npm.cmd run lint    → tsc --noEmit 通过，无类型错误
npm.cmd run build   → vite build 成功（116 modules transformed，3.52s）
```

（本次修复不改前端，前端验收为回归确认。）

### 6.4 真实 DeepSeek 复测（核心证据）

用修复后的诊断脚本（强化 prompt + 容错 validator）对项目 `proj_2759dc9c98d7` 相同输入连续调用 5 次：

| 调用 | 结果 | 备注 |
|------|------|------|
| 第 1 次 | ✅ 通过 | |
| 第 2 次 | ✅ 通过 | 修复前第 2 次是 `suggested_scope: null` 失败 |
| 第 3 次 | ✅ 通过 | |
| 第 4 次 | ✅ 通过 | 修复前第 4 次是 `*_requirements` 对象数组失败 |
| 第 5 次 | ✅ 通过 | 修复前第 5 次是 `chart_requirements` 对象数组失败 |

**汇总：5 次调用，成功 5 次，失败 0 次。**

### 6.5 修复前后对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 失败率 | 60%（3/5） | **0%（0/5）** |
| 失败模式 A（suggested_scope null） | 出现 | 消除 |
| 失败模式 B（requirements 对象数组） | 出现 | 消除 |
| 流式用户体验 | 流了半天后报错 | 正常完成 |

### 6.6 端到端验收（完整流式生成链路）

修复 commit 后，重启后端 uvicorn，用真实 DeepSeek API 对项目 `proj_2759dc9c98d7` 触发完整流式生成请求，验证 SSE 链路以 `done` 而非 `error` 结束、任务单正确落库。

**请求**：`POST /api/projects/proj_2759dc9c98d7/requirements/plans/stream-generate`，body `{"source_id": "6fd42ff5c0e7"}`

**结果**：

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| HTTP 状态 | 200 | 200 |
| chunk 事件数 | ~1471（全部到达） | **1391**（全部到达） |
| 最终事件 | `error`（DEEPSEEK_JSON_PARSE_ERROR） | **`done`** ✅ |
| error 事件 | 1 | **0** |
| 任务单落库 | ❌ 未保存 | ✅ `plan_id=8f3379669144` |
| candidate_source | — | DEEPSEEK（真实 LLM，非降级） |
| fallback_used | — | False |
| topic | — | 胃病数据分析实验 |
| required_tasks | — | 7 个 |
| replication_level | — | L0，`suggested_scope` 有值（非 null） |

**结论**：端到端链路完整跑通，流式生成以 `done` 事件结束，任务单正确保存到数据库，`replication_level.suggested_scope` 字段有值（容错/prompt 强化生效）。**Vite 修复报告的 TODO-1 由本次端到端验收正式关闭。**

### 6.7 完整业务流程链路验证（确认任务单 → ANALYSIS_CONFIRMED）

为验证 DeepSeek 容错修复在真实业务全链路中持续有效，本次在端到端任务单生成（§6.6）之后，继续推进完整业务流程，覆盖从确认任务单到 `ANALYSIS_CONFIRMED` 的全部状态流转，验证每一环节的 LLM 流式生成、Worker 后台任务与状态推进均正常。

**验证环境**：后端 uvicorn（8001）+ 独立 Worker 进程（`python -m worker.main`）+ 真实 DeepSeek API（`.env` 含 `DEEPSEEK_API_KEY`）。项目 `proj_2759dc9c98d7`（胃病数据分析）。

**状态流转与证据**：

| 步骤 | 操作 | 状态流转 | 证据 |
|------|------|----------|------|
| 1. 确认任务单 | `POST /requirements/plans/8f3379669144/confirm` | REQUIREMENT_PARSED → **REQUIREMENT_CONFIRMED** | plan.status CANDIDATE→CONFIRMED；project.status REQUIREMENT_CONFIRMED |
| 2. 上传 PDF 来源 | `POST /sources/pdf`（手工构造最小 PDF，pypdf 可提取 585 字符胃病医学资料） | 来源 PENDING → Worker 领取 PARSE_DOCUMENT → 成功 → **PARSED** | Worker 日志：`领取 56aaeba393a5 (PARSE_DOCUMENT) 成功`；source.status=PARSED |
| 3. 完成来源收集 | `POST /sources/complete` | REQUIREMENT_CONFIRMED → **SOURCES_COLLECTED** | 至少 1 个 PARSED 来源；project.status=SOURCES_COLLECTED |
| 4. 流式生成证据卡片 | `POST /sources/142ef7ce9e49/evidence/stream-generate` | —— | SSE 14.8s，424 chunk，`done` 事件，card_count=6，candidate_source=DEEPSEEK，fallback_used=false |
| 5. 确认证据卡片 | 逐个 `POST /evidence/{card_id}/confirm`（6 张） | 6 张 CANDIDATE → 全部 CONFIRMED | 6 张卡片 status=CONFIRMED |
| 6. 完成证据确认 | `POST /evidence/complete` | SOURCES_COLLECTED → **EVIDENCE_CONFIRMED** | project.status=EVIDENCE_CONFIRMED |
| 7. 上传数据集 | `POST /datasets/upload`（100 行胃病 CSV：年龄/性别/病理结果/检查指标） | 数据集 PENDING → Worker 领取 PARSE_DATASET → 成功 → **READY** | Worker 日志：`领取 617ddf6ed5b1 (PARSE_DATASET) 成功`；dataset.status=READY |
| 8. 完成数据集收集 | `POST /datasets/complete` | EVIDENCE_CONFIRMED → **DATASET_READY** | project.status=DATASET_READY |
| 9. 确认分析方案 | `POST /analysis/883277c246f4/confirm` | plan CANDIDATE → CONFIRMED | plan.status=CONFIRMED |
| 10. 完成分析确认 | `POST /analysis/complete` | DATASET_READY → **ANALYSIS_CONFIRMED** | project.status=ANALYSIS_CONFIRMED |

**关键发现**：

1. **Worker 自动触发分析方案生成**：数据集 `PARSE_DATASET` 成功后，`handle_parse_dataset` 调用 `datasets.service.trigger_analysis_plan_generation` 自动创建 `GENERATE_ANALYSIS_PLAN` job；Worker 随后领取该 job，用真实 DeepSeek 生成分析方案候选（`883277c246f4`，CANDIDATE，cleaning_plan 338 字符 / analysis_plan 735 字符 / chart_plan 937 字符），无需手动触发流式生成即得到候选。
2. **沙箱网络限制**：`FETCH_URL`（en.wikipedia.org）因沙箱网络限制 3 次超时后 FAILED（`FETCH_TIMEOUT`，retry=2 耗尽）。DeepSeek API 可通但通用 URL 抓取不通。改用 PDF 上传方案（本地解析，不触网）完成来源采集，链路不受影响。
3. **DeepSeek 容错修复持续有效**：全链路中任务单流式生成（§6.6）、证据卡片流式生成（步骤 4）、分析方案生成（Worker 自动触发）均以 DeepSeek 真实调用完成，0 次 `DEEPSEEK_JSON_PARSE_ERROR`，容错 validator 与 prompt 强化稳定生效。

**最终状态汇总**：

| 实体 | ID | 最终状态 |
|------|----|----------|
| 项目 | proj_2759dc9c98d7 | **ANALYSIS_CONFIRMED** |
| 任务单 | 8f3379669144 | CONFIRMED |
| 来源(PDF) | 142ef7ce9e49 | PARSED |
| 来源(URL) | ffcddfb7374b | FAILED（沙箱网络，非链路缺陷） |
| 证据卡片 | 6 张 | 全部 CONFIRMED |
| 数据集 | 8e4ce0f346bc | READY |
| 分析方案 | 883277c246f4 | CONFIRMED（DEEPSEEK） |
| Jobs | 3 SUCCEEDED / 1 FAILED(FETCH_URL) | —— |

**结论**：从确认任务单到 `ANALYSIS_CONFIRMED` 的完整业务流程链路全部打通，覆盖任务单确认、来源采集与解析、证据卡片流式生成与确认、数据集上传与解析、分析方案生成与确认共 6 个状态节点。DeepSeek 容错修复在全链路中持续有效，无 JSON 解析失败。

## 7. 验收结论

| 验收项 | 结果 | 证据 |
|--------|------|------|
| 根因已定位 | ✅ PASS | 3 类失败模式 + 证据文件 |
| 容错 validator 生效 | ✅ PASS | 9 个容错测试全过 |
| Prompt 强化已加 | ✅ PASS | `_SYSTEM_PROMPT` 含字段类型约束章节 |
| 原有测试无回归 | ✅ PASS | 16 passed（7 原有 + 9 新增） |
| alembic 迁移 | ✅ PASS | 0001→0007 成功 |
| 前端 lint + build | ✅ PASS | tsc 通过，vite build 成功 |
| 真实 DeepSeek 复测 | ✅ PASS | 5 次 0 失败（60%→0%） |
| 端到端完整链路验收 | ✅ PASS | 流式生成收到 `done`，任务单落库 `plan_id=8f3379669144`，真实 LLM 非降级 |
| 完整业务流程链路验证 | ✅ PASS | 确认任务单→ANALYSIS_CONFIRMED 全链路 10 步打通，6 状态节点，0 次 JSON 解析失败 |
| 文档回写 | ✅ PASS | 决策 0029 + acceptance + README 索引 |
| Vite 报告 TODO-1 关闭 | ✅ PASS | 端到端验收正式关闭：流式以 `done` 结束，任务单保存 |

**总体结论：DeepSeek 任务单 JSON 解析失败问题已根治，真实 LLM 调用失败率从 60% 降至 0%，且不引入新依赖、不破坏现有架构。**

## 8. 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `server/app/modules/llm/deepseek_requirement_provider.py` | 修改 | 新增 `_coerce_str_list` / `_coerce_none_to_empty` 容错函数；`DeepSeekReplicationLevel` + `DeepSeekRequirementResponse` 加 `field_validator(mode="before")`；强化 `_SYSTEM_PROMPT` |
| `server/tests/test_deepseek_requirement_provider_stream.py` | 修改 | 新增 `TestDeepSeekResponseTolerance` 测试类，9 个容错场景测试 |
| `dev-docs/decisions/0029-deepseek-json-tolerance-fix.md` | 新建 | 决策记录（根因、方案对比、决策依据、影响范围） |
| `dev-docs/acceptance.md` | 修改 | 新增本次修复记录 |
| `dev-docs/README.md` | 修改 | 真源索引新增决策 0029 |
| `dev-docs/deepseek-json-tolerance-fix-acceptance.md` | 新建 | 本验收报告 |

## 9. 范围界定与后续方向

### 9.1 本次修复范围

- **仅任务单 provider**：`deepseek_requirement_provider.py` 的 `DeepSeekRequirementResponse` 模型。
- **仅两类失败模式**：`*_requirements` 对象数组 + `suggested_scope` null。

### 9.2 范围外（不改动）

- 其他 provider（证据卡片、分析方案、代码任务、大纲）：不动，留作后续观察。
- `deepseek_client.py`：不动（client 不负责 schema 校验）。
- 数据库 schema / Alembic 迁移：不动。
- 前端：不动。

### 9.3 后续方向

| 编号 | 描述 | 触发条件 |
|------|------|----------|
| FOLLOWUP-1 | 其他 provider 若出现同类 schema 不匹配，复用本容错模式（`_coerce_str_list` / `_coerce_none_to_empty`） | 证据卡片/分析方案/代码任务/大纲流式生成出现 `DEEPSEEK_JSON_PARSE_ERROR` 时 |
| FOLLOWUP-2 | 考虑将容错函数提取到共享模块（如 `app/modules/llm/tolerance.py`）供所有 provider 复用 | 至少 2 个 provider 出现同类问题（避免过度抽象） |
| ENV-DEBT-1 | `.env` 配置 `REQUIREMENT_DRAFT_PROVIDER=deepseek` 污染单元测试环境，导致全量 pytest 真实调用 DeepSeek | 下次版本收口前处理（测试应显式注入 provider 或 conftest 隔离环境变量） |

## 10. 运行环境说明

- 排查期间后端 uvicorn 运行于 `http://localhost:8001`（排查时为释放 SQLite 锁已停止）
- 真实 DeepSeek API：`deepseek-v4-pro`，`base_url=https://api.deepseek.com`，`temperature=0.3`
- `.env` 含真实 `DEEPSEEK_API_KEY`（前次端到端验收配置，不进版本控制）
- 诊断脚本：`.tmp/diagnose_deepseek_json.py`（gitignored，本地复现用）
- Pydantic 版本：2.13.4（支持 `field_validator` v2 语法）
