# 决策 0013：确认 SPEC 0002 第二开发切片验收

## 状态

已接受。

## 日期

2026-06-17

## 决策人

项目负责人。

## 背景

SPEC 0002“实验要求输入与结构化任务单”已完成实现，覆盖粘贴实验要求、简单 `.docx` 上传、结构化任务单候选、L0-L3 判断、用户编辑、用户确认、项目状态推进和最小变更记录。

项目负责人要求：“当前项目SPEC2做好了吗，审查一下，然后进行git”。本轮复核按 SPEC 0002、根目录 `AGENTS.md` 和 `dev-docs/acceptance.md` 进行。

## 复核结果

- 未发现进入公开 URL 采集、PDF 解析、证据卡片、数据集工作区、Python 执行、Word/PPT 生成或真实 DeepSeek 调用的范围漂移。
- 后端 owner 仍集中在 `server/app/modules/requirements/`、`server/app/modules/projects/`、`server/app/modules/llm/` 和 `server/app/infrastructure/documents/`。
- API 路由保持薄接线，未拥有核心业务判断。
- 前端只展示后端结构化状态、任务单和错误，不自行判断 L0-L3。
- 本轮补充了前端 `REQUIREMENT_PARSED` 中文展示、`.docx` 文件名清洗和空 Word 文本 API 测试。

## 验收证据

- `server/.venv/Scripts/python.exe -m pytest`：`26 passed, 1 warning`。
- `server/.venv/Scripts/python.exe -m alembic upgrade head`：迁移已在 head，无错误。
- `apps/web` 下 `npm.cmd run lint`：通过。
- `apps/web` 下 `npm.cmd run build`：通过。

已知 warning 为第三方 `fastapi.testclient` 对 `httpx` 的弃用提示，继续作为非阻断债务记录。

## 决策

确认 SPEC 0002 第二开发切片验收通过并收口。

后续可以进行本切片的 git 版本控制收口。进入下一开发切片前，必须先编写并确认“公开资料与证据工作流”SPEC。

## 约束

- 不把 SPEC 0002 的通过误解为 V1 完成。
- 不把当前代理/API/构建验收误写为真实浏览器点击截图验收。
- 不得跳过下一切片 SPEC 直接实现 URL、PDF、证据卡片、数据集、Python 执行或 Word/PPT 生成。
- 两个外部 skill 仓库仍作为本地辅助资料保留在 `skills/` 下，不纳入本项目主仓提交。
