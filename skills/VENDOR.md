# vendor 外部资料说明

`skills/` 目录下包含以下已下载的第三方 skill/plugin 仓库：

- `skills/superpowers/` — Superpowers: 一套 AI 编程智能体行为塑形系统（MIT License）
- `skills/sliver-code-skill/` — Sliver Engineering Workflow（MIT License）

这些是项目外部 vendored 资料，不属于本项目业务代码。它们作为开发辅助工具被下载到项目目录下供 agent 使用。

提交规则：

- 这些目录是外部 Git 仓库，当前作为本地开发辅助资料使用，不纳入本项目主仓提交。
- 本项目只提交本说明文件，`skills/superpowers/` 与 `skills/sliver-code-skill/` 由 `.gitignore` 保持在 git 外。
- 若后续需要让新机器自动取得这些 skill，应另行决策采用子模块、安装脚本或文档化下载流程。
- 本项目不维护或修改这些外部仓库的内容。若需要修改，应 fork 或单独插件。
