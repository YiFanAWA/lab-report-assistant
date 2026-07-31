# 决策 0035：启动 SPEC 0026 PPT 视觉效果增强

**日期：** 2026-07-31
**决策类型：** 启动新切片
**状态：** 已由项目负责人确认收口（2026-07-31）
**关联 SPEC：** [SPEC 0026](../specs/0026-ppt-visual-effects-enhancement.md)
**前序决策：** [决策 0034](0034-start-spec-0025-ppt-color-system.md)（SPEC 0025 已收口）

## 一、背景

SPEC 0025（三角色彩系统 + 深浅对比三明治结构）已于 2026-07-31 收口。项目负责人反馈"生成的还是有些不尽人意"，要求去 GitHub 搜集 Python 构建 PPT 相关方法并尝试。

调研结果记录于 [调研报告](../research/2026-07-31-python-pptx-visual-effects-research.md)。核心发现：

1. python-pptx 原生支持渐变填充（`fill.gradient()` API）
2. python-pptx 原生支持圆角矩形（`MSO_SHAPE.ROUNDED_RECTANGLE`）
3. 外阴影效果需 oxml 操作 `<a:effectLst>`，但实现成熟
4. 形状边框原生支持（`shape.line` API）

基于调研结果，起草 SPEC 0026，聚焦四项视觉增强：渐变填充、圆角矩形、外阴影、形状细边框。

## 二、决策

启动 SPEC 0026「PPT 视觉效果增强（渐变 + 圆角 + 阴影 + 边框）」。

### 2.1 范围

- **owner 层**：`server/app/infrastructure/renderers/ppt_renderer.py`（不改变）
- **依赖**：不引入新依赖（python-pptx + 标准库 colorsys/lxml）
- **合同**：不改变 `PptConfig` 三字段，不改变 `render()` 签名
- **API/Service/Worker 接线**：不改动

### 2.2 四项视觉增强

1. **渐变填充**：封面顶部色块、标题栏、页脚栏改为线性渐变（主色 → 主色暗化）
2. **圆角矩形**：左栏背景衬托改为圆角矩形（半径 0.05）
3. **外阴影效果**：右栏图表添加柔和外阴影（oxml 操作，blur=8pt, alpha=30%）
4. **形状细边框**：右栏图表添加辅助色 1pt 边框

### 2.3 不纳入

- 径向渐变、发光、3D 斜面、反射（视觉过重）
- 文本溢出精确检测（需引入 fork，留作技术债）
- 要点数量上限约束（属内容策略）
- 幻灯片母版重构（改动面过大）

## 三、风险与缓解

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| oxml 操作导致文件损坏 | 中 | 每次生成后重新打开验证；配套 XML 节点测试 |
| 渐变显示不一致 | 低 | python-pptx 原生 API 符合 OOXML 标准 |
| 阴影过重影响阅读 | 低 | 参数保守，可在后续 SPEC 调整 |

## 四、验收入口

- 新增 `TestSpec0026VisualEffects` 测试类（渐变 6 + 圆角 3 + 阴影 4 + 边框 2 + 暗化 2 = 17 个测试）
- 回归测试：362 个测试全部通过（1 预存 DEEPSEEK 失败除外）
- 真实文件验证：6 种预设色 PPT 程序化验证
- HTML 预览视觉验收

## 五、下一步

待项目负责人批准后，按以下顺序推进：

1. 测试先行：编写 `TestSpec0026VisualEffects`
2. 核心实现：`_darken_color` / `_add_gradient_block` / `_add_rounded_color_block` / `_add_picture_shadow`
3. 接线：修改 6 个调用点
4. 运行测试 + 真实文件验证
5. 文档回写 + git 收口
