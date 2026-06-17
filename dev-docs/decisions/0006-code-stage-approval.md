# 决策 0006：代码阶段批准与当前轮执行暂停

> 日期：2026-06-16  
> 状态：已接受  
> 关联文档：[project-charter.md](../project-charter.md)、[tech-stack.md](../tech-stack.md)、[dependency-review.md](../dependency-review.md)、[implementation-plan.md](../implementation-plan.md)

## 背景

项目已完成立项、技术栈、项目规范名、V1 登录边界和首个演示课题确认。项目负责人提供了“胃病数据分析”的教学实验版 Excel 数据，并暂定大模型供应商为 DeepSeek。

项目负责人要求创建代码阶段批准记录，并完成代码阶段开始前的依赖版本与官方目录规范复核。同时，项目负责人明确补充：**现在不写代码**。

## 决策

本项目进入“代码阶段已批准，但当前轮执行暂停”的状态。

含义：

- 代码阶段门禁已完成文档批准。
- 后续可以依据 `implementation-plan.md` 进入框架初始化、依赖安装和业务代码实现。
- 当前这一轮不得创建业务代码、安装依赖或初始化技术框架。
- 后续实际开始代码执行前，必须重新读取 `dev-docs/README.md`、`AGENTS.md`、`tech-stack.md`、`dependency-review.md` 和 `implementation-plan.md`。
- 若用户在后续明确要求“开始按实施计划执行代码阶段”，才允许开始创建代码和安装依赖。

## 已确认前置条件

- 项目规范目录名：`lab-report-assistant`。
- V1 产品形态：本地单用户 Web MVP。
- V1 登录边界：不做注册登录，不做在线多用户账号体系。
- V1 技术栈：见 `tech-stack.md`。
- 依赖版本与官方目录规范：见 `dependency-review.md`。
- V1 首个标准演示课题：胃病数据分析。
- 样例数据来源：`C:\Users\爹\Downloads\胃病数据集_教学实验版.xlsx`。
- 大模型供应商：DeepSeek。
- 默认模型：`deepseek-v4-pro`。
- 快速候选模型：`deepseek-v4-flash`。

## 执行边界

代码阶段开始后必须遵守：

- 不引入注册登录、用户账号、多人协作或云端项目功能。
- 不把 DeepSeek 模型名写死在业务模块中，必须通过 `LLMGateway` 和配置读取。
- 不提交真实 API 密钥。
- 不使用 `deepseek-chat` 或 `deepseek-reasoner` 作为默认模型名。
- 不把样例数据当成医学诊断数据，只能作为教学数据分析样例。
- 不绕过登录、验证码、付费墙或访问控制。
- 不让前端、提示词或临时脚本拥有业务状态机。
- 不把当前轮文档批准误解为已经完成代码实现。

## 影响

- `dev-docs/dependency-review.md` 成为代码阶段依赖版本和目录规范的依据。
- `dev-docs/implementation-plan.md` 的任务 0 可以标记为文档门禁已完成，但代码实现任务仍未执行。
- `dev-docs/acceptance.md` 应记录代码阶段已获批准但当前轮暂停执行。
- 下一次实际编码时，应先创建或切换到安全的项目目录与分支，再按实施计划执行。

## 重新评估条件

出现以下情况时，必须更新本决策或新增决策记录：

- 用户撤销代码阶段批准；
- 用户要求继续保持只做文档不写代码；
- DeepSeek 供应商或默认模型变化；
- 样例数据文件替换或字段变化；
- 依赖版本复核超过 7 天仍未初始化；
- 项目物理目录从 `VibeCoding` 迁移到 `lab-report-assistant`；
- 项目范围从本地单用户改为在线多用户。

