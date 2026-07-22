# 技术债务清理计划

**创建日期：** 2026-07-22  
**当前阶段：** SPEC 0006 已收口，准备进入 V1.0 完整端到端验收  
**适用范围：** 实验报告助手项目  
**目标：** 在 V1.0 验收阶段清理已知非阻断技术债务，确保 V1.0 发布前无遗留警告

---

## 一、债务总览

| 债务编号 | 名称 | 引入切片 | 严重程度 | 清理优先级 | 计划清理时机 |
| --- | --- | --- | --- | --- | --- |
| TD-001 | fastapi.testclient httpx 弃用提示 | SPEC 0002 | 低（不影响功能） | 中 | V1.0 验收阶段 |
| TD-002 | pandas datetime 推断 UserWarning | SPEC 0004 | 低（不影响数据正确性） | 中 | V1.0 验收阶段 |

---

## 二、TD-001：fastapi.testclient httpx 弃用提示

### 2.1 问题描述

**现象：** 运行 `python -m pytest` 时出现 1 条 StarletteDeprecationWarning：

```
.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning:
  Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa
```

**根因：** FastAPI/Starlette 的 TestClient 依赖 `httpx` 库进行 HTTP 请求，但 Starlette 新版本已弃用 `httpx`，推荐使用 `httpx2`（httpx 的后继版本）。

**影响范围：** 仅影响测试环境，不影响生产运行。所有 API 测试均正常通过（569 passed）。

**自：** SPEC 0002 阶段引入，持续保留至今。

### 2.2 清理方案

#### 方案 A：安装 httpx2（推荐）

**操作：**
1. 在 `server/pyproject.toml` 的测试依赖中添加 `httpx2`。
2. 运行 `pip install httpx2`。
3. 验证 `python -m pytest` 不再出现弃用警告。
4. 验证全部 569 个测试仍通过。

**风险评估：**
- httpx2 是 httpx 的后继版本，API 基本兼容。
- TestClient 会自动检测并使用 httpx2。
- 回退方案：如果 httpx2 引入兼容性问题，可卸载并回到 httpx。

**验证命令：**
```bash
server/.venv/Scripts/python.exe -m pytest -W error::DeprecationWarning
```
（将弃用警告提升为错误，确保无警告）

#### 方案 B：抑制警告（不推荐，仅作后备）

**操作：** 在 `server/pyproject.toml` 的 `[tool.pytest.ini_options]` 中添加：

```toml
filterwarnings = [
    "ignore::DeprecationWarning:starlette.testclient",
]
```

**风险：** 掩盖真实问题，不推荐作为长期方案。

### 2.3 清理步骤

| 步骤 | 操作 | 验证 | 预计耗时 |
| --- | --- | --- | --- |
| 1 | `pip install httpx2` | 安装成功 | 2 分钟 |
| 2 | 运行 `python -m pytest` | 569 passed, 0 warnings（或减少 1 条） | 1 分钟 |
| 3 | 更新 `pyproject.toml` 添加 httpx2 依赖 | 文件已更新 | 1 分钟 |
| 4 | 更新 `dev-docs/dependency-review.md` 记录 httpx2 版本 | 文档已更新 | 2 分钟 |
| 5 | 更新 `dev-docs/acceptance.md` 记录债务已清理 | 文档已更新 | 1 分钟 |

### 2.4 回退方案

如果 httpx2 导致测试失败：
1. `pip uninstall httpx2`
2. 恢复 `pyproject.toml`
3. 采用方案 B（抑制警告）作为临时方案
4. 在 `dev-docs/acceptance.md` 记录回退原因

---

## 三、TD-002：pandas datetime 推断 UserWarning

### 3.1 问题描述

**现象：** 运行 `python -m pytest` 时出现 20 条 UserWarning：

```
server/app/infrastructure/parsers/dataset_parser.py:96: UserWarning:
  Could not infer format, so each element will be parsed individually,
  falling back to `dateutil`. To ensure parsing is consistent and as-expected,
  please specify a format.
    converted = __import__("pandas").to_datetime(series, errors="coerce")
```

**根因：** `dataset_parser.py:96` 调用 `pandas.to_datetime(series, errors="coerce")` 时未指定 `format` 参数。pandas 无法推断日期格式时，回退到 `dateutil` 逐元素解析，并发出 UserWarning。

**影响范围：** 仅影响数据集解析的日期字段处理。不影响其他模块。数据解析结果正确（`errors="coerce"` 保证无效日期变为 NaT 而非抛错）。

**自：** SPEC 0004 阶段引入，持续保留至今。

### 3.2 清理方案

#### 方案 A：显式指定日期格式推断策略（推荐）

**操作：** 修改 `server/app/infrastructure/parsers/dataset_parser.py:96`，在调用 `to_datetime` 前先尝试推断格式，或使用 `format="mixed"` 显式声明混合格式：

```python
# 修改前
converted = __import__("pandas").to_datetime(series, errors="coerce")

# 修改后（pandas 2.0+ 支持 format="mixed"）
converted = __import__("pandas").to_datetime(series, errors="coerce", format="mixed")
```

**风险评估：**
- `format="mixed"` 是 pandas 2.0+ 引入的参数，当前环境 pandas 3.0.3 支持。
- 该参数显式声明允许混合日期格式，pandas 不再发 UserWarning。
- 解析行为与当前一致（逐元素解析，无效日期变 NaT）。

**验证命令：**
```bash
server/.venv/Scripts/python.exe -m pytest tests/test_dataset_parser.py -v
server/.venv/Scripts/python.exe -m pytest -W error::UserWarning
```

#### 方案 B：抑制特定警告（后备）

**操作：** 在 `dataset_parser.py` 中使用 `warnings.catch_warnings()` 上下文管理器局部抑制：

```python
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    converted = __import__("pandas").to_datetime(series, errors="coerce")
```

**风险：** 掩盖真实问题，不推荐作为长期方案。

### 3.3 清理步骤

| 步骤 | 操作 | 验证 | 预计耗时 |
| --- | --- | --- | --- |
| 1 | 读取 `dataset_parser.py:96` 上下文 | 确认修改位置 | 1 分钟 |
| 2 | 添加 `format="mixed"` 参数 | 代码已修改 | 1 分钟 |
| 3 | 运行 `python -m pytest tests/test_dataset_parser.py -v` | 29 passed, 0 warnings | 1 分钟 |
| 4 | 运行 `python -m pytest` 全套 | 569 passed, 0 warnings（或减少 20 条） | 1 分钟 |
| 5 | 更新 `dev-docs/acceptance.md` 记录债务已清理 | 文档已更新 | 1 分钟 |

### 3.4 回退方案

如果 `format="mixed"` 导致测试失败或解析行为变化：
1. 恢复原代码 `to_datetime(series, errors="coerce")`
2. 采用方案 B（局部抑制警告）
3. 在 `dev-docs/acceptance.md` 记录回退原因

---

## 四、清理后的验收标准

清理 TD-001 和 TD-002 后，运行验收命令应满足：

| 验收命令 | 当前结果 | 目标结果 |
| --- | --- | --- |
| `python -m pytest` | 569 passed, **21 warnings** | 569 passed, **0 warnings** |
| `python -m alembic upgrade head` | 成功 | 成功（不变） |
| `npm run lint` | 通过 | 通过（不变） |
| `npm run build` | 通过 | 通过（不变） |

**目标：** 将 warnings 从 21 条降至 0 条（1 条来自 TD-001 + 20 条来自 TD-002）。

---

## 五、执行计划

### 5.1 执行时机

**建议时机：** V1.0 完整端到端验收阶段开始时，作为第一个清理任务。

**理由：**
- 两个债务都是低风险修改，不影响业务逻辑。
- 在 V1.0 验收前清理，可以确保 V1.0 发布时无任何警告。
- 清理后需要重新运行全套验收命令验证。

### 5.2 执行顺序

```
1. 清理 TD-001（安装 httpx2）→ 验证测试
2. 清理 TD-002（添加 format="mixed"）→ 验证测试
3. 运行全套验收命令（pytest + alembic + lint + build）
4. 确认 0 warnings
5. 文档回写（acceptance.md、dependency-review.md、changelog.md）
6. git 提交并推送
```

### 5.3 预计耗时

| 任务 | 预计耗时 |
| --- | --- |
| TD-001 清理 + 验证 | 10 分钟 |
| TD-002 清理 + 验证 | 10 分钟 |
| 全套验收命令 | 5 分钟 |
| 文档回写 | 10 分钟 |
| git 提交推送 | 5 分钟 |
| **合计** | **40 分钟** |

### 5.4 风险控制

| 风项 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| httpx2 兼容性问题 | 低 | 测试失败 | 回退到 httpx，采用抑制警告方案 |
| format="mixed" 解析行为变化 | 低 | 日期解析结果不同 | 回退到原代码，采用局部抑制方案 |
| 清理后引入新 warning | 极低 | 验收不通过 | 逐步清理，每步验证 |

---

## 六、已关闭债务

| 债务编号 | 名称 | 引入切片 | 关闭时间 | 关闭证据 |
| --- | --- | --- | --- | --- |
| TD-003 | 浏览器点击截图验收未执行 | SPEC 0002 | 2026-07-22 | 本会话已完成浏览器端到端验收，截图保存至 `dev-docs/e2e-screenshots/`，详见 `dev-docs/e2e-acceptance-report-v1.0.md` |

---

## 七、后续监控

清理完成后，在后续每次切片收口验收时，检查 `python -m pytest` 的 warnings 数量是否为 0。如果出现新的 warning，应立即评估是否为阻断问题，并更新本计划。
