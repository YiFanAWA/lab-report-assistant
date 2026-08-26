# 决策 0039：启动 SPEC 0030 pptxforge 集成与图表美化增强

**日期：** 2026-07-31
**决策类型：** 启动新切片
**状态：** 实现中
**关联 SPEC：** [SPEC 0030](../specs/0030-pptxforge-and-chart-beautification.md)
**前序决策：** [决策 0038](0038-start-spec-0029-e2e-acceptance.md)（SPEC 0029 已由项目负责人确认收口）

## 一、背景

SPEC 0029 端到端集成验收已由项目负责人确认收口（2026-07-31，E2E_RESULT=PASS，1100 passed 零回归）。项目负责人查看实际 Word/PPT 产物后反馈"效果还是一般，再去互联网上或者 GitHub 中借鉴，可以大规模改动，但是对应接口要正确匹配"。

经调研 GitHub，确定两个借鉴方向：
1. **pptxforge**（GA16-24/pptxforge，MIT，265+ stars）：10 个生产级主题、视觉原语（CardGrid/Callout/StatRow）、电影级 Morph 转场。
2. **期刊级图表美化**（Nature 期刊风格）：NPG 期刊离散配色、a/b/c 面板标签、fill_between 误差带、多面板 subplot 布局。

SPEC 0030 草案已编写（包含 12 章节），项目负责人审阅后确认以下决策点：
- PptConfig 主题映射方案 B（新增 `theme_preset` 字段）
- PPT 视觉范围：pptxforge 完全接管，移除 SPEC 0025/0026 相关代码
- 图表配色：NPG 期刊配色
- 多面板布局：自适应
- pptxforge 版本：锁定 `>=0.1.2,<0.2`

## 二、决策

批准 SPEC 0030「pptxforge 集成与图表美化增强」进入实现阶段。

### 2.1 范围

- **owner 层**：
  - PPT 配置合同：`server/app/modules/outlines/contracts.py`（`PptConfig` 扩展为四字段）
  - PPT 渲染器：`server/app/infrastructure/renderers/ppt_renderer.py`（内部重构，`render()` 签名不变）
  - 图表生成层：`server/app/modules/llm/code_task_provider.py`、`server/app/modules/llm/deepseek_code_task_provider.py`
  - 依赖声明：`server/pyproject.toml`
- **依赖**：新增 `pptxforge>=0.1.2,<0.2`（MIT 协议）
- **API 合同**：`PptConfig` 扩展为四字段（新增 `theme_preset: str | None`），其余 API schema 不变
- **数据库 schema**：不新增 Alembic 迁移
- **API/Service/Worker 接线**：不改动

### 2.2 核心改动点

1. **PptConfig 合同扩展（方案 B）**：新增 `theme_preset: str | None` 字段，10 主题枚举校验
2. **PPT 渲染层重构**：`render()` 内部引入 pptxforge Deck + 主题系统 + 视觉原语；移除 SPEC 0025/0026 三角色彩派生与渐变/圆角/阴影代码
3. **图表配色升级**：`_HEADER` 中 `sns.set_theme(palette="bright")` 替换为 NPG 期刊配色
4. **图表布局升级**：a/b/c 面板标签、多面板 subplot 布局、fill_between 误差带
5. **dpi 缺陷修复**：移除 `plt.savefig(..., dpi=100)` 的 dpi 覆盖，统一由 rcParams `savefig.dpi=300` 控制
6. **DeepSeek prompt 同步**：`_SYSTEM_PROMPT` 追加 NPG 配色 + 面板标签设计规则

### 2.3 接口正确匹配保障

以下接口不变，确保大规模改动不破坏现有接线：
- `PptRenderer.render()` 签名不变
- Provider `generate()` / `stream_generate()` 签名不变
- API / Service / Worker 接线不变
- 数据库 schema 不变
- 沙箱白名单不加 pptxforge（仅渲染器进程使用）
- owner 边界不变

## 三、约束

- 不改变 `render()` 签名、Provider 接口、API/Service/Worker 接线
- 不修改数据库 schema
- 沙箱白名单不加 pptxforge
- 保留 SPEC 0024（16:9 画布/五级字号）、SPEC 0027（_GridHelper/_pct_to_emu）、SPEC 0028（nature-figure rcParams）核心成果
- 回归零容忍：现有所有测试必须全部通过（本切片修改的测试除外）
- 遵循 TDD：红阶段（编写失败测试）→ 绿阶段（实现代码）→ 重构阶段

## 四、实现顺序

遵循 AGENTS.md 阶段闸顺序：

```text
1. 项目负责人确认 SPEC 0030 草案 ✅（本次决策批准）
2. 创建决策 0039（启动 SPEC 0030）✅（本文件）
3. 安装 pptxforge 依赖，更新 pyproject.toml ⏳
4. 更新 PptConfig 合同：contracts.py 新增 theme_preset 字段 ⏳
5. 测试先行：编写新增测试（红阶段）⏳
6. 图表美化实现（code_task_provider.py + deepseek_code_task_provider.py）⏳
7. PPT 渲染层重构（ppt_renderer.py）⏳
8. 绿阶段：测试全部通过 ⏳
9. 真实文件视觉验收 ⏳
10. 端到端验收（复用 verify_spec0029_e2e.py）⏳
11. 文档回写（README、acceptance、implementation-plan、dependency-review）⏳
12. git 边界复核 + commit + push ⏳
13. 项目负责人确认收口 ⏳
```

## 五、验收入口

- 新增测试全部通过（test_theme_mapping / test_npg_palette / test_panel_labels / test_dpi_unified / test_pptxforge_deck_output）
- 现有测试零回归（1100 passed 基线）
- 真实 PPT 文件可在 PowerPoint / LibreOffice 打开，应用 pptxforge 主题
- 图表 PNG 分辨率为 300 dpi，配色为 NPG 期刊色板
- 多图场景有 a/b/c 面板标签
- 端到端验收 E2E_RESULT=PASS

## 六、风险与缓解

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| pptxforge v0.1.2 为 Beta 版本，API 可能不稳定 | 中 | 锁定版本 `pptxforge>=0.1.2,<0.2`；保留 python-pptx fallback 路径 |
| pptxforge 不支持中文字体 | 中 | 验证 Deck 主题字体可配置；必要时回退到 python-pptx 渲染 |
| pptxforge Deck.save() 校验严格 | 低 | 捕获 DeckValidationError，降级到 python-pptx 渲染 |
| NPG 配色与 theme_color 冲突 | 低 | 图表配色独立于 PPT 主题（NPG 为期刊通用色板） |
| dpi 提升到 300 增大文件体积 | 低 | 可接受（实验报告需高清图表） |
| 大规模改动引入隐藏回归 | 中 | TDD 红绿重构 + 全套回归测试 + 真实文件视觉验收 |

## 七、下一步

本决策批准后立即执行：
1. 安装 pptxforge 依赖
2. 更新 PptConfig 合同
3. 编写 TDD 红阶段测试
4. 实现图表美化 + PPT 渲染层重构
5. 绿阶段测试 + 验收
