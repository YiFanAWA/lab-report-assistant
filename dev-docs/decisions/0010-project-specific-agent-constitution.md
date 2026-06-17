# 决策 0010：项目级 Agent 宪法收敛

> 日期：2026-06-17  
> 状态：已记录  
> 相关文件：`AGENTS.md`、`CLAUDE.md`、[README.md](../README.md)、[project-charter.md](../project-charter.md)、[architecture.md](../architecture.md)、[acceptance.md](../acceptance.md)、[implementation-plan.md](../implementation-plan.md)

## 背景

根目录 `AGENTS.md` 原本是通用 Agent 宪法模板，仍包含 `@@PROJECT@@`、`@@TRUTH@@`、`@@STACK@@` 等占位符。本决策创建时，项目已经完成立项、技术栈锁定、架构设计、SPEC 0001 实现确认，并完成 SPEC 0002 的当前实现与验收；继续保留通用模板会让后续 agent 误判项目仍处于未适配状态。

## 决策

将根目录 `AGENTS.md` 收敛为“实验报告助手”项目专用宪法。

本次收敛写入以下项目专用规则：

- 当前项目真相、当前阶段和下一切片入口；
- `dev-docs/README.md` 作为内部真源索引；
- 本地单用户 Web MVP、第一版不做注册登录、不做在线多用户、不支持 L3 完整复现等产品边界；
- 前端、后端、数据库、文件、Python 执行和大模型网关的 owner 边界；
- 本决策创建时要求：SPEC 0002 当时仍未收口，因此不得进入下一切片实现；当前该要求已由决策 0013 承接为“SPEC 0002 已确认收口，下一切片必须先确认 SPEC”；
- 当前实际验收命令、已知非阻断债务和浏览器点击验收缺口；
- git 忽略边界和禁止吸入本地 Obsidian 文件、构建产物、虚拟环境、egg-info 元数据。

`CLAUDE.md` 保持为轻量入口，只指向 `AGENTS.md`，不维护第二套规则。

## 影响

- 后续 agent 不再需要解释通用模板中的占位符，必须直接按本项目真源工作。
- 后续任何新切片实现都必须先确认对应 SPEC。
- 后续涉及产品边界、技术路线、验收标准或宪法规则的变更，必须同步更新 `dev-docs/` 真源与决策记录。

## 压力测试

如果后续 agent 想直接开始公开 URL 采集、证据卡片、Python 执行或 Word/PPT 生成，新的 `AGENTS.md` 应当阻止该行为，并要求先完成以下步骤：

```text
SPEC 0002 已确认收口
  -> 编写下一切片 SPEC
  -> 项目负责人确认下一切片 SPEC
  -> 再进入对应实现
```

如果后续 agent 想让前端直接判断 L0-L3、实验结果真实性或项目阶段推进，新的 `AGENTS.md` 应当阻止该行为，并要求业务语义回到后端核心 owner 层。

## 验收方式

- 读取 `AGENTS.md`，确认不再包含 `@@...@@` 占位符。
- 读取 `AGENTS.md`，确认包含当前阶段、产品边界、owner 边界、验收命令和停止条件。
- 搜索 `AGENTS.md` 和本决策记录，确认项目自有文档保持中文语境。
