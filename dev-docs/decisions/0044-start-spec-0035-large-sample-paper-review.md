# 决策 0044：启动 SPEC 0035 大样本公开论文解读案例

## 决策

项目负责人要求将演示改为“数据量大、存在对应论文、能够爬取论文并制作论文解读”的案例。采用 Diabetes 130-US Hospitals 数据集与 Strack 等 2014 年开放论文作为首个案例，使用已有 Word/PPT 交付物链生成成品。

## 约束

- 论文、数据集、镜像和全文 XML 必须保存来源清单；
- 论文原始样本/结果与本地复核样本/结果分开标注；
- 不把本地描述性统计包装成论文原始回归复现；
- 不改变业务数据、证据、执行和大纲 owner；
- 不引入新运行时依赖。

## 验收

以 SPEC 0035 的大样本口径、来源追溯、Word/PPT 结构和逐页视觉检查为准。

## 实现证据

- 原始 CSV、论文 PDF、全文 XML、来源清单和图表已固化到 `server/dev-docs/e2e-screenshots/spec0035_paper_review/`。
- 生成脚本为 `server/scripts/generate_spec0035_paper_review.py`；DOCX 可重新打开，包含 77 段落和 4 张真实图表；两套 PPT 各 7 页、16:9。
- 视觉验收使用工作区渲染依赖输出两套 PPT 的逐页 PNG 和拼图；`slides_test.py` 仍受 Windows 临时路径 JSON 反斜杠问题影响，未将其结果冒充通过。
- 全量后端测试为 1150 passed；Alembic、前端 lint、前端 build 均通过。DOCX/PDF 转换因当前机器缺少 LibreOffice/Word 留有环境缺口。
