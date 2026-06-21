# 决策 0015：确认 SPEC 0003 公开资料与证据工作流验收

## 状态

已接受。

## 日期

2026-06-22

## 决策人

项目负责人。

## 背景

SPEC 0003“公开资料与证据工作流”已完成公开 URL 安全登记、本地辅助资料登记、文本解析、证据候选、人工编辑确认、项目状态推进、API 和前端工作台实现。早期候选分支混入未验收的 Skill、Orchestrator、feasibility、Alembic 0004 和浅层 Skill 测试，因此最终收口改为从 `master` 建立独立干净分支，只提取 SPEC 0003 范围。

Browser 自动化接口不提供本地文件选择注入能力。本轮采用“真实 API 文件上传合同 + Browser 下游真实交互”的分段证据；项目负责人明确回复“确认 SPEC 0003 收口”，接受该证据边界。

## 验收证据

- 后端业务回归：`54 passed, 1 warning`；warning 为已登记的第三方 TestClient 弃用提示。
- 全新 SQLite：依次迁移到 `0003 (head)`。
- 前端：`npm.cmd run lint` 与 `npm.cmd run build` 均通过，Vite 转换 95 modules。
- 代理主链路：需求确认、TXT 上传、解析、候选生成、证据确认、刷新读取均通过，项目状态推进到 `EVIDENCE_CONFIRMED`。
- 安全错误：私网 URL 返回 HTTP 400 与 `SOURCE_URL_BLOCKED_PRIVATE_NETWORK`。
- Browser：私网 URL 错误展示、解析、候选生成、证据编辑保存、刷新保持、证据确认、状态推进和导航通过，控制台无 error/warn。
- Git 边界：Skill、Orchestrator、feasibility、Alembic 0004 和相关测试未进入干净收口分支。

## 决策

确认 SPEC 0003 公开资料与证据工作流验收通过并收口，可以进入本切片的精确 git 提交与远程上传。

## 约束

- 本决策不代表 V1 已完成。
- 本决策不批准 Skill、Orchestrator、feasibility、数据集、Python 执行、Word/PPT 或其他下一切片实现。
- 下一切片必须先编写并由项目负责人确认对应 SPEC。
- 不得把候选分支中的迁移 0004、Skill 代码或浅层测试包装为 SPEC 0003 已验收内容。
