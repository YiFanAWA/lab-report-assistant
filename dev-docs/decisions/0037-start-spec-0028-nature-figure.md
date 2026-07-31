# 决策 0037：启动 SPEC 0028 Nature 风格图表集成

**日期：** 2026-07-31
**决策类型：** 启动新切片
**状态：** 已由项目负责人确认收口（2026-07-31）
**关联 SPEC：** [SPEC 0028](../specs/0028-nature-figure-integration.md)
**前序决策：** [决策 0036](0036-start-spec-0027-chart-beautification.md)（SPEC 0027 已由项目负责人确认收口）

## 一、背景

SPEC 0027（图表美化与布局增强）已由项目负责人确认收口（2026-07-31），引入了 `scienceplots` + `seaborn` + `easypptx` 三个依赖。项目负责人随后要求调研 GitHub 上的 nature-skills 项目并评估技术栈替换。

调研发现 nature-figure skill（来自 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)，Apache-2.0 协议）通过手动 `rcParams` 配置实现 Nature 期刊风格，无需外部样式库依赖。影响面分析确认移除 SciencePlots 仅影响 5 个测试用例和 6 处生产代码，Seaborn API 和 PPT 布局层完全不受影响。

## 二、决策

批准 SPEC 0028 进入实现阶段，采用**方案 A**：

1. **移除** `scienceplots` 依赖（pyproject.toml + 沙箱白名单）
2. **替换** `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` 为 nature-figure rcParams
3. **保留** `seaborn` 和 `easypptx` 依赖
4. **修改** 5 个受影响测试用例（C1/C2/C3/S1/S4）
5. **不引入** 任何新依赖

## 三、约束

- 不改变 owner 边界
- 不改变 `PptConfig` 合同
- 不破坏 SPEC 0024/0025/0026/0027 成果（除 SciencePlots 外）
- 保留中文字体支持（Microsoft YaHei）
- 保留 Seaborn 图表 API
- 保留 `_GridHelper` 网格布局
- 回归零容忍

## 四、实现顺序

```text
1. TDD 红色阶段：修改 5 个测试用例
2. TDD 绿色阶段：修改生产代码（code_task_provider/deepseek_code_task_provider/python_executor/pyproject.toml）
3. 运行回归测试套件
4. 卸载 scienceplots 包
5. 真实图表 + PPT 视觉验证
6. 文档回写 + git 收口
```

## 五、验收标准

- 5 个修改测试通过
- 所有回归测试通过（零回归）
- `scienceplots` 从 pyproject.toml 和沙箱白名单中移除
- nature-figure rcParams 生效（去右框/顶框、粗轴线、中文字体）
- 6 种预设色 PPT 渲染成功

## 六、风险

| 风险 | 缓解措施 |
| --- | --- |
| rcParams 与 Seaborn 主题冲突 | `sns.set_theme` 在 rcParams 之后调用，需验证最终效果 |
| 中文字体显示异常 | `font.sans-serif` 首选 `Microsoft YaHei`，与 SPEC 0027 一致 |
| 图表质量下降 | 回滚策略：`git revert` 恢复 SciencePlots |

## 七、验收证据（2026-07-31 实现收口回写）

### 7.1 测试验收

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| SPEC 0027+0028 专项测试 | `pytest test_local_rule_code_task_provider_format.py test_python_executor.py -k "Spec0027"` | 26 passed |
| 受影响测试全套 | `pytest test_local_rule_code_task_provider_format.py test_ppt_config.py test_renderers.py test_python_executor.py` | 204 passed 零回归 |

### 7.2 真实文件验收

- _HEADER 内容验证：10/10 检查通过（不含 scienceplots、含 nature-figure rcParams）
- 沙箱执行验证：成功生成 3 张图表 PNG + 1 张相关性 CSV（scienceplots 已卸载）
- 6 种预设色 PPT 渲染：blue/purple/green/red/orange/gray 全部成功

### 7.3 额外修复

- `test_python_executor.py` 的 `test_default_allowed_imports_content` 测试同步更新（影响面分析中遗漏，回归测试中发现并修复）

### 7.4 约束遵守验证

- ✅ 未改变 owner 边界
- ✅ 未改变 PptConfig 合同
- ✅ 未破坏 SPEC 0024/0025/0026/0027 成果（除 SciencePlots 外）
- ✅ 未引入新依赖
- ✅ 保留了中文字体支持、Seaborn 图表 API、_GridHelper 网格布局
- ✅ API/Service/Worker 接线不变
