# 实验报告助手｜开发真源索引

本文档是项目内部真源入口。后续产品设计、任务拆解、技术选型、代码实现和验收工作，必须先读取本索引和当前有效文档。

## 当前阶段

- 阶段：代码阶段
- 状态：SPEC 0002 实验要求输入与结构化任务单已完成实现、复核验收并由项目负责人确认收口
- 下一阶段入口：编写并确认“公开资料与证据工作流”切片 SPEC；确认前不得进入下一切片实现

## 工程入口

- [../server/](../server/)：后端 FastAPI 服务
- [../apps/web/](../apps/web/)：前端 React 工作台
- [commands.md](commands.md)：实际运行命令索引
- [../skills/VENDOR.md](../skills/VENDOR.md)：外部 vendored skill/plugin 说明

## 当前真源

- [project-charter.md](project-charter.md)：已确认锁定的项目立项文档，是当前最高优先级产品真源。
- [project-initiation.md](project-initiation.md)：Sliver 启动门禁兼容入口，只指向 `project-charter.md`，不维护第二份产品真相。
- [architecture.md](architecture.md)：当前架构主线、唯一归属层、核心合同、禁止路径和技术主线建议。
- [tech-stack.md](tech-stack.md)：已确认锁定的 V1 技术栈、框架边界、Worker、Python 受控执行环境和重新评估条件。
- [dependency-review.md](dependency-review.md)：代码阶段开始前的依赖版本、DeepSeek 模型、样例数据和官方目录规范复核。
- [commands.md](commands.md)：实际运行命令索引，由代码阶段脚手架创建后维护。
- [acceptance.md](acceptance.md)：阶段门禁、证据要求、停止条件和漂移锁。
- [implementation-plan.md](implementation-plan.md)：进入代码阶段后的任务拆解计划，已用于执行 SPEC 0001；后续切片仍需先确认范围。
- [specs/0001-project-workspace-and-scaffold.md](specs/0001-project-workspace-and-scaffold.md)：第一开发切片 SPEC，限定脚手架与项目工作区最小闭环。
- [specs/0002-requirement-input-and-task-plan.md](specs/0002-requirement-input-and-task-plan.md)：第二开发切片 SPEC，限定实验要求输入、结构化任务单和 L0-L3 判断。
- [decisions/0001-lock-project-charter.md](decisions/0001-lock-project-charter.md)：锁定立项文档为后续工作依据的决策记录。
- [decisions/0002-enter-architecture-planning.md](decisions/0002-enter-architecture-planning.md)：进入架构与开发计划阶段的决策记录。
- [decisions/0003-document-language.md](decisions/0003-document-language.md)：项目自有文档必须使用中文的决策记录。
- [decisions/0004-lock-technology-stack.md](decisions/0004-lock-technology-stack.md)：锁定 V1 技术栈和本地单用户部署主线的决策记录。
- [decisions/0005-lock-v1-project-identity-and-demo.md](decisions/0005-lock-v1-project-identity-and-demo.md)：锁定项目规范目录名、V1 不做注册登录和首个演示课题的决策记录。
- [decisions/0006-code-stage-approval.md](decisions/0006-code-stage-approval.md)：记录代码阶段曾获批准但当轮暂停执行的历史决策，已由决策 0007 承接为正式执行。
- [decisions/0007-code-stage-execution-started.md](decisions/0007-code-stage-execution-started.md)：记录代码阶段正式启动执行的决策记录。
- [decisions/0008-confirm-spec-0001-acceptance.md](decisions/0008-confirm-spec-0001-acceptance.md)：确认 SPEC 0001 第一开发切片验收通过的决策记录。
- [decisions/0009-start-spec-0002-requirements.md](decisions/0009-start-spec-0002-requirements.md)：启动 SPEC 0002 实验要求输入与结构化任务单切片的决策记录。
- [decisions/0010-project-specific-agent-constitution.md](decisions/0010-project-specific-agent-constitution.md)：将根目录 `AGENTS.md` 从通用模板收敛为项目级宪法的决策记录。
- [decisions/0011-version-control-after-version-completion.md](decisions/0011-version-control-after-version-completion.md)：规定每完成一版或一个已确认开发切片后，必须进行一次 git 提交与远程上传收口。
- [decisions/0012-lock-git-remote.md](decisions/0012-lock-git-remote.md)：锁定当前项目远程仓库为 GitHub 上的 `YiFanAWA/lab-report-assistant`。
- [decisions/0013-confirm-spec-0002-acceptance.md](decisions/0013-confirm-spec-0002-acceptance.md)：确认 SPEC 0002 第二开发切片复核验收通过并进入版本控制收口。

## 变更规则

- 项目方向、功能边界、技术路线或验收标准发生变化时，必须先更新 `project-charter.md`。
- 每次影响范围、边界或验收标准的变更，必须新增或更新 `dev-docs/decisions/` 下的决策记录。
- 不允许只在对话中口头修改项目真源。
- 后续每个新切片开始前，必须先确认对应 SPEC 或任务范围。
- 每完成一版或一个已确认开发切片，必须按根目录 `AGENTS.md` 的“版本收口上传规则”完成验收、文档回写、精确提交和远程上传；未配置远程仓库或上传失败时，必须记录原因。

## 真源优先级

事实冲突时按以下顺序处理：

1. 当前代码、测试、脚本、运行证据和 git 状态。
2. 根目录 `AGENTS.md`。
3. 本索引和 active 真源文档。
4. 决策记录。
5. 历史对话、旧草稿和未索引文档。
