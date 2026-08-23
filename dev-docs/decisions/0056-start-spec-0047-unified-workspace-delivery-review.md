# 决策 0056：启动 SPEC 0047 统一工作台与交付审阅

## 决策

确认启动 SPEC 0047，范围包括：

- 统一 WorkspaceShell 与项目阶段只读投影；
- 交付物审阅台与后端质量门禁投影；
- Word、PDF、PPT 三类正式交付物；
- PDF 从最终 DOCX 派生，并优先随 Windows portable bundle 提供 LibreOffice headless 转换运行时；
- 保留现有路由、Word/PPT API 和业务 owner，新增接口采用兼容式扩展；
- 允许整理本切片触达的内联样式和共享 token，但不进行无关全站重构。

## 用户确认

- SPEC 0045 已收口，案例定位为教学性论文复核报告。
- SPEC 0046 已收口，Windows 一键运行方向继续有效。
- 允许新增本切片的 API/投影合同。
- PDF 是正式交付物。
- 先接受较大的 portable 包体，后续再进行压缩优化。

## 技术取舍

当前 `DocxPdfExporter` 依赖 Microsoft Word COM，不能满足干净 Windows 环境的免配置目标。采用随发布包提供的 LibreOffice headless 适配器，仍以 DOCX 为唯一正文源，避免维护第二套 PDF 排版系统。

LibreOffice 官方下载页和许可证页已于 2026-08-22 核对。Windows x86-64 26.2.5 MSI 响应大小为 372,948,992 bytes；发布时必须记录精确版本、SHA-256、许可证和归属信息。

## 不在本决策中

- 不改变数据分析、统计方法、LLM Gateway 或实验要求合同。
- 不把 PDF 生成失败伪装为 Word 成功或项目完成。
- 不直接改写根 `AGENTS.md` 的宪法内容；其中旧阶段文字作为治理漂移单独处理。

## 验收入口

详见 [SPEC 0047](../specs/0047-unified-workspace-shell-delivery-review.md)。

必须完成后端/API、前端构建、PDF 真实生成、portable bundle、1280px 浏览器和干净 Windows 验收后，才能进行本切片 Git 版本收口。
