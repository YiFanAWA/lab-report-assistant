# 开放许可科研图形资产库

本目录只保存经过逐项来源、许可证、哈希和 SVG 安全审计的科研图形资产。

- `manifest.json` 是资产真源清单；运行时只暴露通过注册表门禁的资产。
- `svg/` 保存可编辑真源；不得手工替换后跳过 SHA-256 更新和复核。
- `png/`（生成后）是 Word/PPT 兼容派生缓存，不是授权真源。
- `ATTRIBUTION.md` 由清单稳定生成，供论文图注、附录和仓库 NOTICE 使用。
- `LICENSES/` 保存资产许可证文本。

首批组件来自 Bioicons 仓库提交 `d29e766ea7580b8063c4f47b29e872db40a4d979` 中明确位于 `static/icons/cc-0/` 的文件，许可证为 CC0-1.0。BioRender、Mind the Graph 及其他带水印或需付费出版许可的素材不进入本目录。

新增资产时必须同步：原始 URL、固定上游版本、作者、规范许可证 id、许可证 URL、修改说明、尺寸、`viewBox`、哈希和验证日期，并运行 `tests/test_scientific_asset_registry.py`。
