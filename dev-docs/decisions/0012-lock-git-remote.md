# 决策 0012：锁定项目远程仓库

## 状态

已记录。

## 日期

2026-06-17

## 背景

项目负责人在建立“每完成一版进行 git 上传”的版本控制规则后，指定远程仓库为 GitHub 仓库 `YiFanAWA/lab-report-assistant`。

## 决策

当前项目的默认远程仓库配置为：

```bash
origin  https://github.com/YiFanAWA/lab-report-assistant.git
```

后续每完成一版或一个已确认开发切片，必须按 `AGENTS.md` 的“版本收口上传规则”提交并 push 到该远程仓库。

## 影响范围

- 本地 git 配置已新增 `origin`。
- `dev-docs/commands.md` 记录当前远程仓库地址。
- 后续版本收口时，如果远程仓库鉴权、网络或权限失败，必须记录失败原因，不得宣称已上传。

## 禁止事项

- 不得因为配置了远程仓库就自动提交当前全部未跟踪文件。
- 不得使用 `git add .`。
- 不得把 `.obsidian/`、`.claude/`、`.codex/`、`memory/`、`.venv/`、`dist/`、`.tmp/`、本地数据库、密钥或 agent 运行记忆上传到远程仓库。
