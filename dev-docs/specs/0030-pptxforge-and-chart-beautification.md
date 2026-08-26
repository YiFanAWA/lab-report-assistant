# SPEC 0030：pptxforge 集成与图表美化增强

**状态：** 草案，待项目负责人批准进入实现
**起草日期：** 2026-07-31
**前序 SPEC：** [SPEC 0029](0029-e2e-integration-acceptance.md)（端到端集成验收，已由项目负责人确认收口）
**调研依据：** [pptxforge GitHub](https://github.com/GA16-24/pptxforge)（MIT 协议，v0.1.2，Python>=3.10）、[nature-skills](https://github.com/Yuan1z0825/nature-skills)（Apache-2.0，已用于 SPEC 0028）
**owner 层：**
- PPT 配置合同：`server/app/modules/outlines/contracts.py`（`PptConfig`，不改字段）
- PPT 渲染器：`server/app/infrastructure/renderers/ppt_renderer.py`（内部重构，`render()` 签名不变）
- 图表生成层：`server/app/modules/llm/code_task_provider.py`、`server/app/modules/llm/deepseek_code_task_provider.py`
- 执行沙箱：`server/app/infrastructure/sandbox/python_executor.py`（import 白名单）
- 依赖声明：`server/pyproject.toml`
- 不改变 owner 边界

## 一、背景与动机

### 1.1 用户反馈与需求

项目负责人在 SPEC 0029 端到端验收后查看实际 Word/PPT 产物，反馈"效果还是一般"，要求"再去互联网上或者 GitHub 中借鉴，可以大规模改动，但是对应接口要正确匹配"。

经调研 GitHub，确定两个借鉴方向：
1. **pptxforge**（GA16-24/pptxforge，MIT，265+ stars）：10 个生产级主题、视觉原语（CardGrid/Callout/StatRow）、电影级 Morph 转场、原生 3D 模型嵌入。专注于产出"beautiful decks"而非模板填充。
2. **期刊级图表美化**（Nature 期刊风格）：NPG（Nature Publishing Group）期刊离散配色、fill_between 误差带、a/b/c 面板标签、多面板 subplot 布局。

### 1.2 现有产物差距分析

| 维度 | 现状（SPEC 0024-0028） | 差距 | 借鉴方向 |
| --- | --- | --- | --- |
| PPT 主题 | 单一 `theme_color` 派生三角色彩 | 缺少预设主题系统，视觉风格单一 | pptxforge 10 主题 |
| PPT 版式 | 双栏 40/60 + 三明治结构 | 版式固定，缺少 CardGrid/Callout 等视觉原语 | pptxforge 视觉原语 |
| PPT 转场 | 无 | 静态幻灯片，缺少电影级转场 | pptxforge Morph 转场 |
| 图表配色 | `sns.set_theme(palette="bright")` | 配色固定，非色盲友好，非期刊级 | NPG 期刊配色 |
| 图表精度 | `savefig(dpi=100)` 覆盖 rcParams `savefig.dpi=300` | **dpi 不一致缺陷**，输出分辨率偏低 | 统一 dpi=300 |
| 图表布局 | 单图单 figure | 缺少多面板 subplot、a/b/c 面板标签 | Nature 多面板布局 |
| 图表统计 | 无误差带 | 缺少 fill_between 误差可视化 | 误差带 |

### 1.3 dpi 不一致缺陷（SPEC 0028 遗留）

`code_task_provider.py` 的 `_HEADER` 设 `matplotlib.rcParams['savefig.dpi'] = 300`，但 `_build_chart_code` 生成的 `plt.savefig(..., dpi=100)` 显式覆盖为 100。这是 SPEC 0028 引入的缺陷，本切片顺带修复。

## 二、目标与边界

### 2.1 目标

1. **引入 pptxforge 依赖**：在 `pyproject.toml` 新增 `pptxforge>=0.1.2`；沙箱白名单不需要改（pptxforge 仅用于渲染器，不在用户代码沙箱中执行）
2. **PPT 渲染层重构**：`PptRenderer.render()` 内部引入 pptxforge 的 `Deck` + 主题系统 + 视觉原语，替换现有直接操作 `python-pptx` 的命令式代码
3. **PptConfig 主题映射**：`theme_color` 字段语义保持（hex 值），作为 fallback 映射到 pptxforge 主题；新增 `theme_preset` 字段直接指定 pptxforge 主题名（见 2.3 已确认方案 B）
4. **图表配色升级**：`_HEADER` 中 `sns.set_theme(palette="bright")` 替换为 NPG 期刊配色
5. **图表布局升级**：`_build_chart_code` 支持 a/b/c 面板标签、多面板 subplot 布局、fill_between 误差带
6. **修复 dpi 不一致**：移除 `plt.savefig(..., dpi=100)` 的 dpi 覆盖，统一使用 rcParams 的 `savefig.dpi=300`
7. **DeepSeek prompt 同步**：`deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 追加 NPG 配色 + 面板标签设计规则

### 2.2 边界（必须遵守）

- **不改变 owner 边界**：PPT 渲染改动在 `ppt_renderer.py` 内；图表生成改动在 `code_task_provider.py` + `deepseek_code_task_provider.py` 内；沙箱校验改动在 `python_executor.py` 内
- **`PptConfig` 合同扩展（方案 B，已确认）**：`target_slide_count` / `theme_color` / `include_charts` 三字段语义与类型不变；**新增** `theme_preset: str | None` 可选字段（pptxforge 主题名，枚举校验）
- **不改变 `render()` 签名**：`(project_name, project_topic, outline_sections, execution_artifacts, output_path, config: dict | None) -> str` 不变
- **不改变 Provider 接口**：`generate()` / `stream_generate()` 签名不变
- **SPEC 0024-0028 成果处置**（pptxforge 完全接管，已确认）：
  - 16:9 画布、五级字号保持（SPEC 0024）
  - **移除**三角色彩派生 `_derive_color_palette` / `_darken_color`（SPEC 0025），由 pptxforge 主题原生提供
  - **移除**渐变填充/圆角矩形/外阴影/细边框代码 `_add_gradient_block` / `_add_rounded_color_block` / `_add_picture_shadow` / `_add_divider`（SPEC 0026），由 pptxforge 主题原生提供
  - **保留** `_GridHelper` / `_pct_to_emu`（SPEC 0027 布局辅助，补充 pptxforge Grid 场景）
  - nature-figure rcParams 保留（SPEC 0028）
- **不改变 API / Service / Worker 接线**：`PptConfig` Pydantic 合同不变，API schema 不变
- **不修改数据库 schema**：不新增 Alembic 迁移
- **沙箱白名单不加 pptxforge**：pptxforge 仅在渲染器进程内使用，用户代码沙箱不暴露
- **回归零容忍**：现有所有测试必须全部通过（本切片修改的测试除外）

### 2.3 PptConfig 主题映射方案（已确认采用方案 B）

**项目负责人已确认采用方案 B**：新增 `theme_preset: str | None` 字段，允许直接指定 pptxforge 主题名。

PptConfig 合同从三字段扩展为四字段：
- `target_slide_count: int | None`（保持不变）
- `theme_color: str | None`（保持不变，hex 值，用于三角色彩派生 fallback）
- `include_charts: bool`（保持不变）
- `theme_preset: str | None`（**新增**，pptxforge 主题名，如 "MIDNIGHT_EXECUTIVE"、"PACIFIC_DEEP"；None 时由 theme_color 映射）

主题优先级：`theme_preset` > `theme_color` 映射 > 默认 `SLATE_MINIMALIST`。

合法主题名枚举（10 个）：`MIDNIGHT_EXECUTIVE`、`PACIFIC_DEEP`、`FOREST_MOSS`、`ROYAL_PLUM`、`BERRY_BOLD`、`MONOCHROME_INK`、`SLATE_MINIMALIST`、`AMBER_EDITORIAL`、`CORAL_ENERGY`、`SUNRISE_CITRUS`。

## 三、技术方案

### 3.1 PPT 渲染层重构（pptxforge 集成）

#### 3.1.1 集成策略

`PptRenderer.render()` 内部改造：

```python
# 现状：直接操作 python-pptx
prs = Presentation()
self._set_slide_size(prs)
self._add_title_slide(prs, ...)
prs.save(output_path)

# 目标：包装 pptxforge Deck
from pptxforge import Deck, themes
deck = Deck(theme=self._map_theme(theme_color), title=project_name, author="实验报告助手")
deck.add_title_slide(title=project_name, eyebrow=project_topic, subtitle=...)
deck.add_content_slide(title=..., layout=self._build_layout(outline_sections, execution_artifacts))
written = deck.save(output_path)
```

#### 3.1.2 主题映射

`theme_color` hex → pptxforge 主题映射表（方案 B 的 fallback，当 `theme_preset` 为 None 时使用）：

| theme_color 区间 | pptxforge 主题 | 说明 |
| --- | --- | --- |
| 蓝色系（蓝/深蓝/靛） | `MIDNIGHT_EXECUTIVE` | 严肃/执行/商务 |
| 青色系（青/teal） | `PACIFIC_DEEP` | 科学/医学/解剖 |
| 绿色系（绿/翠） | `FOREST_MOSS` | 可持续/生物/农业 |
| 紫色系（紫/品红） | `ROYAL_PLUM` 或 `BERRY_BOLD` | 奢华/品牌 |
| 灰色系（灰/黑） | `MONOCHROME_INK` 或 `SLATE_MINIMALIST` | 编辑/工程 |
| 暖色系（橙/珊瑚） | `AMBER_EDITORIAL` 或 `CORAL_ENERGY` | 编辑/消费 |
| 黄色系（黄/金） | `SUNRISE_CITRUS` | 明亮/营销 |
| 其他 | `SLATE_MINIMALIST` | 默认中性 |

映射函数 `_map_theme(theme_color: str | None) -> themes.Constant`。

#### 3.1.3 视觉原语映射

现有 `_add_content_slide` / `_add_chart_slide` 内部布局改为 pptxforge layout 原语：

- 左栏文本要点 + 右栏图表 → `TwoColumn(left=Text(...), right=Image(...), split=0.4)`
- 多图表网格 → `Grid([Image(...), ...], cols=2)`
- 统计数字 → `StatCallout(number=..., label=...)`
- 章节分隔 → `add_section_slide(number=..., title=..., caption=...)`

#### 3.1.4 代码清理（pptxforge 完全接管）

- **移除** `_derive_color_palette` / `_darken_color`（SPEC 0025 三角色彩派生，由 pptxforge 主题原生替代）
- **移除** `_add_gradient_block` / `_add_rounded_color_block` / `_add_picture_shadow` / `_add_divider`（SPEC 0026 视觉效果，由 pptxforge 主题原生替代）
- **保留** `_GridHelper` / `_pct_to_emu`（SPEC 0027 布局辅助，pptxforge Grid 布局补充）
- **保留** `_set_run_font` / `_add_footer` / `_add_placeholder_textbox`（基础排版，pptxforge 不覆盖）

### 3.2 图表美化层

#### 3.2.1 NPG 期刊配色

`_HEADER` 中替换：

```python
# 现状
sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")

# 目标：NPG（Nature Publishing Group）期刊配色
NPG_PALETTE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488",
               "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"]
sns.set_theme(style="whitegrid", palette=sns.color_palette(NPG_PALETTE), font="Microsoft YaHei")
```

NPG 配色为 Nature Publishing Group 期刊风格，8 色覆盖红/天蓝/翠绿/深蓝/橙/灰蓝/浅绿/朱红，贴近 Nature 期刊视觉。

#### 3.2.2 a/b/c 面板标签

`_build_chart_code` 中多图场景升级为 subplot + 面板标签：

```python
# 目标：多面板布局 + a/b/c 标签
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, field, label in zip(axes, data_fields, ['a', 'b']):
    sns.histplot(data=df, x=field, kde=True, bins=30, ax=ax)
    ax.set_title(f'({label}) {field}')
    ax.text(-0.1, 1.05, label, transform=ax.transAxes, fontsize=16, fontweight='bold', va='top')
```

#### 3.2.3 fill_between 误差带

描述性统计与分组统计图表新增误差带可视化（当有标准差/置信区间时）：

```python
mean = df.groupby('group')['value'].mean()
std = df.groupby('group')['value'].std()
plt.fill_between(mean.index, mean - std, mean + std, alpha=0.2, color=NPG_PALETTE[2])
plt.plot(mean.index, mean, color=NPG_PALETTE[2])
```

#### 3.2.4 dpi 统一修复

移除所有 `plt.savefig(..., dpi=100)` 中的 `dpi=100` 参数，统一由 rcParams `savefig.dpi=300` 控制：

```python
# 现状（缺陷）
plt.savefig(OUTPUT_DIR + '/chart.png', dpi=100, bbox_inches='tight')

# 目标
plt.savefig(OUTPUT_DIR + '/chart.png', bbox_inches='tight')  # 使用 rcParams savefig.dpi=300
```

### 3.3 DeepSeek prompt 同步

`deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 追加：
- NPG 期刊配色规则（8 色，Nature Publishing Group 风格）
- a/b/c 面板标签规范（多图 subplot 场景）
- fill_between 误差带使用场景
- dpi 由 rcParams 统一控制，不在 savefig 中覆盖

## 四、测试策略

### 4.1 受影响测试清单

| 测试文件 | 受影响原因 | 预期改动 |
| --- | --- | --- |
| `test_renderers.py` | render() 内部重构 | 适配 pptxforge Deck 输出，验证主题映射 |
| `test_ppt_config.py` | PptConfig 主题映射 | 新增主题映射测试（theme_color → pptxforge 主题） |
| `test_local_rule_code_task_provider_format.py` | _HEADER 配色 + _build_chart_code 布局 | 适配 NPG 配色、面板标签、dpi 移除 |
| `test_deepseek_code_task_provider_stream.py` | _SYSTEM_PROMPT 更新 | 适配 prompt 内容断言 |

### 4.2 新增测试

- `test_theme_mapping`：theme_color hex → pptxforge 主题映射覆盖
- `test_npg_palette`：_HEADER 中 NPG 配色正确注入
- `test_panel_labels`：多图 subplot 场景 a/b/c 标签生成
- `test_dpi_unified`：savefig 不含 dpi 覆盖，使用 rcParams
- `test_pptxforge_deck_output`：render() 输出可被 python-pptx 重新打开

### 4.3 TDD 流程

1. 红阶段：编写新增测试，确认失败
2. 绿阶段：实现 pptxforge 集成 + 图表美化
3. 重构阶段：清理兼容代码，保留必要 fallback
4. 回归：全套测试通过

## 五、验收方法

### 5.1 单元测试

```text
server/.venv/Scripts/python.exe -m pytest server/tests -k "ppt or chart or code_task or renderer"
```

### 5.2 真实文件视觉验收

1. 用 SPEC 0029 端到端验收脚本生成 PPT + 图表
2. 验证 PPT 可在 PowerPoint / LibreOffice 打开
3. 验证图表 PNG 分辨率为 300 dpi
4. 验证图表配色为 NPG 期刊色板
5. 验证多图场景有 a/b/c 面板标签

### 5.3 回归验收

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

### 5.4 端到端验收

复用 `server/scripts/verify_spec0029_e2e.py`，验证完整工作流仍打通，PPT/Word 产物正常生成。

## 六、回滚方案

1. git revert 本切片 commit
2. `pyproject.toml` 移除 `pptxforge` 依赖
3. `ppt_renderer.py` 恢复到 SPEC 0026 状态（python-pptx 命令式）
4. `code_task_provider.py` 恢复到 SPEC 0028 状态（nature-figure rcParams + seaborn bright）
5. 沙箱白名单无需改（本切片不修改沙箱）

回滚风险：低。所有改动集中在 4 个文件 + 1 个依赖声明。

## 七、风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| pptxforge v0.1.2 为 Beta 版本 | API 可能不稳定 | 锁定版本 `pptxforge>=0.1.2,<0.2`；保留 python-pptx fallback 路径 |
| pptxforge 不支持中文字体 | PPT 中文乱码 | 验证 Deck 主题字体可配置；必要时回退到 python-pptx 渲染 |
| pptxforge Deck.save() 校验严格 | outline_sections 内容可能触发 overflow | 捕获 DeckValidationError，降级到 python-pptx 渲染 |
| NPG 配色与 theme_color 冲突 | 图表配色与 PPT 主题不协调 | 图表配色独立于 PPT 主题（NPG 为期刊通用色板） |
| dpi 提升到 300 增大文件体积 | PPT 文件变大 | 可接受（实验报告需高清图表）；必要时保留 100 dpi 选项 |

## 八、依赖审查

### 8.1 新增依赖

| 依赖 | 版本 | 协议 | 用途 | 必要性 |
| --- | --- | --- | --- | --- |
| pptxforge | >=0.1.2,<0.2 | MIT | PPT 主题系统 + 视觉原语 + Morph 转场 | 高（本切片核心） |

### 8.2 依赖更新清单

- `server/pyproject.toml`：新增 `pptxforge>=0.1.2,<0.2`
- `dev-docs/dependency-review.md`：新增 pptxforge 条目，记录协议、版本、用途、决策依据
- 沙箱白名单 `DEFAULT_ALLOWED_IMPORTS`：**不新增** pptxforge（仅渲染器进程使用）

## 九、与前序 SPEC 关系

| SPEC | 关系 | 说明 |
| --- | --- | --- |
| SPEC 0024 | 保留基础 | 16:9 画布、双栏布局、五级字号保持 |
| SPEC 0025 | 保留 fallback | 三角色彩派生保留为 fallback（pptxforge 主题不匹配时） |
| SPEC 0026 | 部分替代 | 渐变/圆角/阴影由 pptxforge 主题原生提供 |
| SPEC 0027 | 保留 | _GridHelper / _pct_to_emu 保留 |
| SPEC 0028 | 保留 + 修复 | nature-figure rcParams 保留；修复 dpi=100 覆盖 300 的缺陷 |
| SPEC 0029 | 复用验收 | 端到端验收脚本复用 |

## 十、实现顺序

```text
1. 项目负责人确认 SPEC 0030 草案 + 创建决策 0039
2. 安装 pptxforge 依赖，更新 pyproject.toml
3. 更新 PptConfig 合同：contracts.py 新增 `theme_preset: str | None` 字段（枚举校验）+ 前端 PPT 配置表单新增 theme_preset 下拉输入
4. 测试先行：编写新增测试（红阶段）
5. 图表美化实现（code_task_provider.py + deepseek_code_task_provider.py）
   - NPG 配色
   - a/b/c 面板标签
   - fill_between 误差带
   - dpi 统一修复
6. PPT 渲染层重构（ppt_renderer.py）
   - _map_theme 主题映射
   - render() 内部改用 pptxforge Deck
   - 视觉原语映射
   - 保留 fallback 路径
7. 绿阶段：测试全部通过
8. 真实文件视觉验收
9. 端到端验收（复用 verify_spec0029_e2e.py）
10. 文档回写（README、acceptance、implementation-plan、dependency-review）
11. git 边界复核 + commit + push
12. 项目负责人确认收口
```

## 十一、文档回写

- `dev-docs/README.md`：真源索引新增 SPEC 0030
- `dev-docs/acceptance.md`：新增 SPEC 0030 验收记录
- `dev-docs/implementation-plan.md`：新增 V2.10.0 阶段描述
- `dev-docs/dependency-review.md`：新增 pptxforge 依赖条目
- `dev-docs/decisions/0039-start-spec-0030-pptxforge-chart-beautification.md`：启动决策

## 十二、约束声明

1. ✅ `PptConfig` 合同扩展为四字段（方案 B，新增 `theme_preset` 可选字段，原三字段语义不变）
2. ✅ 不改变 `render()` 签名
3. ✅ 不改变 Provider `generate()` / `stream_generate()` 签名
4. ✅ 不改变 owner 边界
5. ✅ 不改变 API / Service / Worker 接线
6. ✅ 不修改数据库 schema
7. ✅ 沙箱白名单不加 pptxforge
8. ✅ 保留 SPEC 0024-0028 核心成果（画布/字号/Grid/rcParams）
9. ✅ 引入 1 个新依赖 pptxforge（MIT，需更新 dependency-review）
10. ✅ 修复 SPEC 0028 遗留的 dpi 不一致缺陷
