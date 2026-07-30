# 决策 0032：启动 SPEC 0024 PPT 渲染器布局与视觉层次改进

**日期：** 2026-07-30
**状态：** 已由项目负责人确认收口（2026-07-31，详见 [决策 0033](0033-confirm-spec-0024-acceptance.md)）
**版本：** V2.5.0
**关联 SPEC：** [SPEC 0024](../specs/0024-ppt-renderer-layout-and-visual-hierarchy.md)
**上游 SPEC：** [SPEC 0011](../specs/0011-ppt-config-options.md)（PPT 配置选项）、[SPEC 0006](../specs/0006-outline-and-deliverables.md)（大纲与交付物）

---

## 一、背景

SPEC 0011 已为 PPT 生成增加了配置能力（目标页数、主题色、图表开关），但端到端链路验证后发现 PPT 视觉效果不尽人意：

1. **布局粗糙**：直接使用内置 `slide_layouts[0/1/5]`，依赖 PowerPoint 默认母版，缺乏专业感
2. **图表布置僵硬**：固定 `Inches(1 + i*4)` 横向排列，最多 2 张，单图不居中放大、多图溢出
3. **图文分离**：图表页只有图、内容页只有文字，无法做"左文右图"双栏
4. **无视觉层次**：无色块/分隔线/装饰元素，纯文字堆砌
5. **主题色应用浅**：只涂标题文字颜色，无色块背景、无分隔线、无要点标记色
6. **4:3 默认比例**：不符合现代 16:9 投影/显示器标准

## 二、决策

启动 SPEC 0024 PPT 渲染器布局与视觉层次改进切片，重构 `PptRenderer` 的布局与视觉层次。

### 核心改动

| 功能点 | 实现内容 |
| --- | --- |
| F1 16:9 画布 | 幻灯片尺寸改为 13.333×7.5 英寸 |
| F2 空白版式 | 所有页面改用 `slide_layouts[6]`，精确定位每个元素 |
| F3 封面页重构 | 主题色顶部色块 + 白色 36pt 大标题 + 副标题 + 底部装饰线 |
| F4 双栏内容页 | 左栏 40% 文本要点（主题色圆点）+ 右栏 60% 图表 |
| F5 图表自适应 | 单图居中放大（width=8"）、双图并排（各 5.8"）、3-4 图 2×2 网格（各 3.8"） |
| F6 图文混排 | 内容页支持"左文右图"布局，图表自动关联到内容页右栏 |
| F7 总结页重构 | 居中排版 + 主题色分隔线 + 要点提炼 |
| F8 五级字号体系 | 主标题 36pt / 页面标题 28pt / 副标题 20pt / 正文 16pt / 注释 12pt |
| F9 主题色扩展应用 | 色块背景、分隔线、要点圆点标记、标题文字 |
| F10 页脚信息 | 每页底部显示项目名 + 页码（封面页除外） |

### 约束

- **不引入新依赖**（继续使用 `python-pptx>=1.0.2`）
- **不改变 PptConfig 合同**（`target_slide_count`/`theme_color`/`include_charts` 三字段不变）
- **不改变 API/service/Worker 接线**（`render()` 签名不变，调用方零改动）
- **不修改数据库 schema**（布局参数是渲染器内部常量）
- **不改变文件存储路径和版本管理**

## 三、实现摘要

### 修改文件

| 文件 | 改动 |
| --- | --- |
| `server/app/infrastructure/renderers/ppt_renderer.py` | 重构为空白版式驱动，新增布局常量、辅助方法、双栏内容页、图表自适应布局、五级字号体系、主题色扩展应用 |
| `server/tests/test_ppt_config.py` | 修复 4 个测试（3 个失败 + 1 个空跳），新增 `_slide_has_color()` 辅助函数适配空白版式主题色验证 |
| `server/tests/test_renderers.py` | 更新 2 个测试适配空白版式（遍历 shapes 找文本替代 placeholder） |
| `dev-docs/specs/0024-ppt-renderer-layout-and-visual-hierarchy.md` | SPEC 文档（新增） |

### 新增方法

- `_render_title_slide()`：封面页（色块+标题+副标题+装饰线）
- `_add_content_slide()`：双栏内容页（标题+左栏文本+右栏图表+页脚）
- `_add_content_left_column()`：左栏文本要点（主题色圆点+标题+说明）
- `_add_content_right_chart()`：右栏图表嵌入
- `_add_content_right_text()`：无图表时右栏补充文本
- `_add_chart_slide()`：图表自适应布局页
- `_place_chart_centered()`：单图居中放大
- `_place_chart_side_by_side()`：双图左右并排
- `_place_chart_grid()`：多图 2×2 网格
- `_render_summary_slide()`：总结页（居中排版+分隔线）
- `_set_run_font()`：统一字体设置（含东亚字体）
- `_add_color_block()`：纯色色块
- `_add_divider()`：分隔线
- `_add_footer()`：页脚（项目名+页码+分隔线）
- `_resolve_theme_color()`：主题色解析（None 时降级到默认深灰色 #333333）

## 四、验收结果

### 4.1 测试验收

| 测试范围 | 结果 |
| --- | --- |
| `test_ppt_config.py` + `test_renderers.py` | 41 passed（含修复的 4 个测试） |
| PPT/outline/word/renderer 相关全量 | 142 passed in 15.86s |
| 其他非流式测试 | 107 passed in 93.85s |
| **SPEC 0024 引入的回归** | **0** |

### 4.2 真实文件验收

生成 PPT 文件验证：
- **画布尺寸**：13.333×7.500 英寸（16:9，比例 1.778）✅
- **五级字号**：[12.0, 16.0, 20.0, 28.0, 36.0]pt 完整 ✅
- **主题色应用**：4/4 页面都应用了主题色（色块、标题、圆点、分隔线）✅
- **双栏布局**：内容页左栏文本要点 + 右栏图表 ✅
- **图表嵌入**：3 张图表分配到 3 个内容页右栏 ✅
- **页脚**：项目名 + 页码 ✅

### 4.3 预存非阻断债务

| 测试文件 | 失败测试 | 根因 | 与 SPEC 0024 关系 |
| --- | --- | --- | --- |
| `test_code_task_stream_api.py` | `test_完整流程多chunk加done事件` | `candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK | 无关（`.env` 中 API key 导致） |
| `test_requirement_api.py` | `test_requirement_api_happy_path_updates_and_confirms_plan` | 同上 | 无关 |

根因：`server/.env` 中设置了 `DEEPSEEK_API_KEY`，导致 LLM 网关使用 DeepSeek provider 而非测试期望的 LocalRule provider。这两个失败在 SPEC 0024 修改前已存在。

### 4.4 约束遵守

- ✅ 不引入新依赖
- ✅ 不改变 PptConfig 合同（三字段不变）
- ✅ 不改变 API/service/Worker 接线（`render()` 签名不变）
- ✅ 不修改数据库 schema
- ✅ 不改变文件存储路径和版本管理

## 五、风险与缓解

| 风险 | 缓解措施 |
| --- | --- |
| 空白版式 `slide_layouts[6]` 索引兼容性 | python-pptx 默认提供 11 个 layout，索引 6 为空白版式，已通过 142 个测试验证 |
| 微软雅黑跨平台 | Docker 镜像可安装 `fonts-wqy-microhei` 作为中文回退，本切片不做字体嵌入 |
| 图表宽高比失真 | 只指定 `width` 不指定 `height`，让 python-pptx 自动计算保持比例 |
| 向后兼容 | `render()` 签名不变，`config=None` 时使用新布局（行为合理不报错），现有测试全部通过 |

## 六、后续入口

- PPT 母版上传与自定义模板（推迟到后续）
- PPT 动画与过渡效果（推迟到 V3.0）
- 在线 PPT 预览（推迟到后续）
- Word 渲染器布局改进（独立切片）
- 预存失败修复：`test_code_task_stream_api.py` 和 `test_requirement_api.py` 的 `candidate_source` 断言问题（需调整测试 mock 策略或在测试中临时清除 `DEEPSEEK_API_KEY`）
