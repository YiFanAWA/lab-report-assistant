# SPEC 0035：大样本公开论文解读案例

## 目标

使用公开大样本数据和对应开放论文，生成一套“论文原文解读 + 数据复核 + 局限说明”的 Word/PDF 与答辩 PPT 成品。

本轮案例：Strack 等 2014 年论文《Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Patient Records》，配套 Diabetes 130-US Hospitals 数据集。

## 来源

- 论文：PMCID `PMC3996476`，DOI `10.1155/2014/781670`，开放获取 PDF 与 Europe PMC 全文 XML。
- 数据：UCI Diabetes 130-US Hospitals，原始 CSV 101,766 条记录、50 列；数据集 DOI `10.24432/C5230J`，CC BY 4.0。
- 论文原始分析样本：69,984 条；论文报告 HbA1c 检测率 18.4%。

来源文件、下载地址和本地复核摘要保存在 `server/dev-docs/e2e-screenshots/spec0035_paper_review/`。

## 口径边界

- “论文原文结论”与“本地公开数据复核结果”必须分开显示。
- 本地复核只做描述性分组比较，不冒充论文原始多变量 Logistic 回归，也不声称复现论文因果结论。
- 医学内容只用于教学数据分析，不提供诊断或治疗建议。
