# 决策 0033：确认 SPEC 0024 PPT 渲染器布局与视觉层次改进收口

> **日期：** 2026-07-31
> **状态：** 已确认收口
> **决策人：** 项目负责人
> **类型：** 开发切片收口确认
> **关联 SPEC：** [SPEC 0024](../specs/0024-ppt-renderer-layout-and-visual-hierarchy.md)
> **启动决策：** [决策 0032](0032-start-spec-0024-ppt-renderer-layout.md)

## 背景

SPEC 0024（PPT 渲染器布局与视觉层次改进，V2.5.0）已于 2026-07-30 完成核心实现与测试验收（启动决策见 [决策 0032](0032-start-spec-0024-ppt-renderer-layout.md)），包括 16:9 画布、空白版式精确定位、双栏内容页、图表自适应布局、五级字号体系和主题色扩展应用。

2026-07-30 至 2026-07-31 期间，项目负责人用真实胃病数据分析课题完成端到端视觉测评，发现并修复了若干视觉阻断问题：

1. **图表中文乱码**：matplotlib 未配置中文字体，图表标题和坐标轴显示为空心方框。修复：在 `code_task_provider.py` 和 `deepseek_code_task_provider.py` 中添加 `matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']` 配置。
2. **PPT 页数限制为 6 页**：`_build_content_groups` 方法将章节合并为 3 组内容页，导致内容不齐全。修复：改为每个章节单独一页，解除 6 页限制。
3. **第 5 页图片超出模板**：`_place_chart_grid` 方法只设置图片宽度未限制高度，导致图片与页脚重叠。修复：新增 `_fit_image_size` 方法按宽高比缩放并限制最大高度，调整下排 top 从 4.2" 改为 4.0"，max_height 从 2.5" 改为 2.3"。
4. **3 张图表布局不协调**：原 2×2 网格布局在 3 张图时右下角空白。修复：新增 `_place_chart_three` 方法，实现上排 2 张并排 + 下排 1 张居中布局。
5. **文本截断过严**：`content[:200]` 截断导致内容不完整。修复：放宽为 `content[:500]`。

基于上述补充验证和修复，项目负责人于 2026-07-31 正式确认 SPEC 0024 收口。

## 收口确认依据

### 核心实现（2026-07-30，引用决策 0032）

- **ppt_renderer.py 重构**：空白版式（`slide_layouts[6]`）+ 精确定位驱动，新增 16:9 画布常量、双栏布局参数、五级字号体系、主题色默认深灰色
- **页面类型**：封面页（色块+白色大标题+副标题+装饰线）、双栏内容页（左栏文本要点带主题色圆点 + 右栏图表）、图表自适应布局页、总结页（居中排版+分隔线）
- **辅助方法**：`_set_run_font`（含东亚字体）、`_add_color_block`、`_add_divider`、`_add_footer`、`_resolve_theme_color`（None 降级到 #333333）

### 端到端视觉测评与修复（2026-07-30 至 2026-07-31）

| 问题 | 根因 | 修复 | 验证 |
| --- | --- | --- | --- |
| 图表中文乱码 | matplotlib 未配置中文字体 | `code_task_provider.py` 和 `deepseek_code_task_provider.py` 添加字体配置 | 重新生成图表，中文正常显示 ✅ |
| PPT 限制 6 页 | `_build_content_groups` 合并章节为 3 组 | 改为每个章节单独一页 | PPT 从 6 页扩展为 8 页 ✅ |
| 图片超出模板 | `_place_chart_grid` 未限制图片高度 | 新增 `_fit_image_size` 方法，调整 max_height=2.3" 和下排 top=4.0" | 第 5 页底部=6.7" < 页脚线 7.0" ✅ |
| 3 图布局不协调 | 2×2 网格在 3 图时右下角空白 | 新增 `_place_chart_three`（上排 2 张并排 + 下排 1 张居中） | 3 图布局协调 ✅ |
| 文本截断过严 | `content[:200]` 截断 | 放宽为 `content[:500]` | 内容更完整 ✅ |

### 测试验收（2026-07-31 本轮重新验证）

| 测试范围 | 结果 | 说明 |
| --- | --- | --- |
| `test_ppt_config.py` + `test_renderers.py` | **41 passed** in 5.40s | PPT 核心测试零回归 |
| PPT/outline 相关全量（6 文件） | **142 passed** in 12.78s | 覆盖 PPT 生成 API、outline service、Worker handler、Word 模板、PPT 配置、渲染器全链路 |
| 完整后端测试 | **106 passed, 1 failed** in 52.12s | 唯一失败 `test_analysis_stream_api.py::test_完整流程多chunk加done事件`（`candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK）是预存环境问题（`.env` 中 `DEEPSEEK_API_KEY` 已设置），与 SPEC 0024 无关 |
| 前端 lint | **通过** | `tsc --noEmit` 无错误 |
| 前端 build | **通过** | `vite build` 成功，116 模块转换，dist/index.html + dist/assets/index-*.js 生成 |

### 约束遵守

- ✅ 不引入新依赖（继续使用 `python-pptx>=1.0.2`）
- ✅ 不改变 PptConfig 合同（`target_slide_count`/`theme_color`/`include_charts` 三字段不变）
- ✅ 不改变 API/service/Worker 接线（`render()` 签名不变，调用方零改动）
- ✅ 不修改数据库 schema
- ✅ 不改变文件存储路径和版本管理

### 配套修复（纳入本次收口）

- `server/app/modules/llm/code_task_provider.py`：添加 matplotlib 中文字体配置（+2 行）
- `server/app/modules/llm/deepseek_code_task_provider.py`：在 `_SYSTEM_PROMPT` 中添加中文字体配置指令（+6 行）

这两处修复是 PPT 视觉效果的配套改进：matplotlib 生成的图表嵌入 PPT 时中文必须正常显示，否则 PPT 视觉层次改进失效。修复不改变 LLM 模块的业务语义和合同。

## 版本收口状态

- **本地 commit**：待创建（本次收口将创建 commit + tag v2.5.0）
- **本地 tag**：`v2.5.0` 待创建
- **远程 push 状态**：待项目负责人确认后执行

## 文档回写（本次收口同步更新）

- `dev-docs/README.md`：顶部状态行新增 V2.5.0 SPEC 0024 收口记录；真源索引新增决策 0033
- `dev-docs/acceptance.md`：补充端到端视觉测评与修复记录、收口确认记录
- `dev-docs/implementation-plan.md`：V2.5.0 阶段表述新增 SPEC 0024 收口记录
- `dev-docs/decisions/0032-start-spec-0024-ppt-renderer-layout.md`：状态行从"已完成实现与验收"更新为"已由项目负责人确认收口（2026-07-31）"
- `dev-docs/changelog-v2.5.0.md`（新增）：V2.5.0 详细发布说明
- `dev-docs/decisions/0033-confirm-spec-0024-acceptance.md`（本文件）：新增收口确认决策记录

## 已知预存债务（不在本次范围）

| 测试文件 | 失败测试 | 根因 | 后续入口 |
| --- | --- | --- | --- |
| `test_analysis_stream_api.py` | `test_完整流程多chunk加done事件` | `candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK | 调整测试 mock 策略或在测试中临时清除 `DEEPSEEK_API_KEY` 环境变量 |
| `test_code_task_stream_api.py` | `test_完整流程多chunk加done事件` | 同上 | 同上 |
| `test_requirement_api.py` | `test_requirement_api_happy_path_updates_and_confirms_plan` | 同上 | 同上 |

这三个预存失败根因相同：`server/.env` 中设置了 `DEEPSEEK_API_KEY`，导致 LLM 网关使用 DeepSeek provider 而非测试期望的 LocalRule provider。与 SPEC 0024 无关，留作后续测试 mock 策略调整入口。

## 后续方向

- SPEC 0024 收口后，下一阶段方向待项目负责人规划
- 已完成 PPT 优秀格式调研（McKinsey PPT Design / Anthropic pptx skill / 数据可视化最佳实践），识别出 6 个可借鉴方向：三角色彩系统、深浅对比三明治结构、数据可视化专用色板、图表洞察性标题、生产防护规则、布局模式扩展
- 上述方向均需先编写并确认对应 SPEC，不得直接进入实现
