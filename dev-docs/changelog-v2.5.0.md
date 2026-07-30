# V2.5.0 变更日志

> **发布日期：** 2026-07-31
> **版本：** V2.5.0
> **关联 SPEC：** [SPEC 0024 PPT 渲染器布局与视觉层次改进](specs/0024-ppt-renderer-layout-and-visual-hierarchy.md)
> **启动决策：** [决策 0032](decisions/0032-start-spec-0024-ppt-renderer-layout.md)
> **收口决策：** [决策 0033](decisions/0033-confirm-spec-0024-acceptance.md)

---

## 一、概述

V2.5.0 是 PPT 渲染器的布局与视觉层次改进版本。SPEC 0011 已为 PPT 生成增加了配置能力（目标页数、主题色、图表开关），但端到端链路验证后发现 PPT 视觉效果不尽人意：布局粗糙、图表布置僵硬、图文分离、无视觉层次、主题色应用浅、字体单一、4:3 默认比例。

本版本重构 `PptRenderer` 的布局与视觉层次，采用 16:9 宽屏画布 + 空白版式精确定位 + 双栏内容页 + 图表自适应布局 + 五级字号体系 + 主题色扩展应用，显著提升 PPT 视觉专业度。

## 二、新增功能

### 2.1 PPT 渲染器布局重构（SPEC 0024）

| 功能点 | 说明 |
| --- | --- |
| F1 16:9 画布 | 幻灯片尺寸改为 13.333×7.5 英寸（16:9 宽屏） |
| F2 空白版式驱动 | 所有页面改用 `slide_layouts[6]`（空白版式），精确定位每个元素 |
| F3 封面页重构 | 主题色顶部色块 + 白色 36pt 大标题 + 副标题 + 底部装饰线 |
| F4 双栏内容页 | 左栏 40% 文本要点（主题色圆点）+ 右栏 60% 图表 |
| F5 图表自适应布局 | 单图居中放大（8"）/ 双图并排（5.8"）/ 3 图上 2 下 1 居中 / 4 图 2×2 网格（3.8"）/ 5+ 图截断到 4 张 |
| F6 图文混排 | 内容页支持"左文右图"布局，图表自动关联到内容页右栏 |
| F7 总结页重构 | 居中排版 + 主题色分隔线 + 要点提炼 |
| F8 五级字号体系 | 主标题 36pt / 页面标题 28pt / 副标题 20pt / 正文 16pt / 注释 12pt |
| F9 主题色扩展应用 | 色块背景、分隔线、要点圆点标记、标题文字 |
| F10 页脚信息 | 每页底部显示项目名 + 页码（封面页除外） |

### 2.2 端到端视觉测评修复

| 问题 | 修复 |
| --- | --- |
| 图表中文乱码 | `code_task_provider.py` 和 `deepseek_code_task_provider.py` 添加 matplotlib 中文字体配置（Microsoft YaHei / SimHei / DejaVu Sans） |
| PPT 限制 6 页 | `_build_content_groups` 改为每个章节单独一页，解除页数限制 |
| 图片超出模板 | 新增 `_fit_image_size` 方法按宽高比缩放并限制最大高度；调整 `_place_chart_grid` 参数 |
| 3 图布局不协调 | 新增 `_place_chart_three` 方法（上排 2 张并排 + 下排 1 张居中） |
| 文本截断过严 | `content[:200]` 放宽为 `content[:500]` |

## 三、修改文件

| 文件 | 改动 |
| --- | --- |
| `server/app/infrastructure/renderers/ppt_renderer.py` | 重构为空白版式驱动，新增布局常量、辅助方法、双栏内容页、图表自适应布局、五级字号体系、主题色扩展应用、`_fit_image_size`、`_place_chart_three` |
| `server/app/modules/llm/code_task_provider.py` | 添加 matplotlib 中文字体配置（+2 行） |
| `server/app/modules/llm/deepseek_code_task_provider.py` | 在 `_SYSTEM_PROMPT` 中添加中文字体配置指令（+6 行） |
| `server/tests/test_ppt_config.py` | 修复 4 个测试适配空白版式，新增 `_slide_has_color()` 辅助函数 |
| `server/tests/test_renderers.py` | 更新 2 个测试适配空白版式 |

## 四、约束遵守

- ✅ 不引入新依赖（继续使用 `python-pptx>=1.0.2`）
- ✅ 不改变 PptConfig 合同（`target_slide_count`/`theme_color`/`include_charts` 三字段不变）
- ✅ 不改变 API/service/Worker 接线（`render()` 签名不变，调用方零改动）
- ✅ 不修改数据库 schema
- ✅ 不改变文件存储路径和版本管理

## 五、测试验收

| 测试范围 | 结果 |
| --- | --- |
| PPT 核心测试（`test_ppt_config.py` + `test_renderers.py`） | 41 passed |
| PPT/outline 相关全量测试（6 文件） | 142 passed |
| 完整后端测试 | 106 passed, 1 failed（预存环境问题，与 SPEC 0024 无关） |
| 前端 lint | 通过 |
| 前端 build | 通过 |

## 六、已知预存债务

| 测试文件 | 失败测试 | 根因 |
| --- | --- | --- |
| `test_analysis_stream_api.py` | `test_完整流程多chunk加done事件` | `candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK（`.env` 中 `DEEPSEEK_API_KEY` 已设置） |
| `test_code_task_stream_api.py` | `test_完整流程多chunk加done事件` | 同上 |
| `test_requirement_api.py` | `test_requirement_api_happy_path_updates_and_confirms_plan` | 同上 |

这三个预存失败与 SPEC 0024 无关，后续修复入口：调整测试 mock 策略或在测试中临时清除 `DEEPSEEK_API_KEY` 环境变量。

## 七、后续方向

- 下一阶段方向待项目负责人规划
- 已完成 PPT 优秀格式调研，识别 6 个可借鉴方向：
  1. 三角色彩系统（60-70% 主色 + 1-2 辅助色 + 1 强调色）
  2. 深浅对比"三明治"结构（深色封面 + 浅色内容 + 深色结论）
  3. 数据可视化专用色板（色盲友好 4 色序列）
  4. 图表洞察性标题（陈述结论而非主题）
  5. 生产防护规则（图例色一致 / 标题统一 / 轴标签居中）
  6. 布局模式扩展（对比页 / KPI 卡片页 / 时间线页）
- 上述方向均需先编写并确认对应 SPEC，不得直接进入实现
