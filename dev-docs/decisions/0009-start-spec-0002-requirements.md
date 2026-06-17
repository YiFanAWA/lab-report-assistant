# 决策 0009：启动 SPEC 0002 实验要求输入与结构化任务单切片

> 日期：2026-06-16  
> 状态：已创建，待项目负责人确认  
> 提出人：Codex  
> 确认人：待项目负责人确认  
> 关联文档：[specs/0002-requirement-input-and-task-plan.md](../specs/0002-requirement-input-and-task-plan.md)、[implementation-plan.md](../implementation-plan.md)、[acceptance.md](../acceptance.md)

## 背景

SPEC 0001 项目工作区与脚手架已由项目负责人确认验收。项目负责人要求“进行下一个切片”。

根据 `dev-docs/README.md` 和 `implementation-plan.md`，下一切片必须先编写或确认“实验要求输入与结构化任务单 SPEC”，再进入实现。

## 决策

启动 SPEC 0002：实验要求输入与结构化任务单。

当前动作只创建和索引 SPEC，不进入代码实现。待项目负责人审阅并确认 SPEC 0002 后，才能开始本切片的代码实现、依赖调整、数据库迁移和前端页面开发。

## 推荐主线

本切片采用以下主线：

```text
实验项目
  -> 保存原始实验要求
  -> 生成结构化任务单候选
  -> 给出 L0-L3 判断
  -> 用户编辑
  -> 用户确认
  -> 项目状态推进到 REQUIREMENT_CONFIRMED
```

## 边界

- 本切片不做公开 URL 采集。
- 本切片不做论文、网页或 PDF 证据解析。
- 本切片不做数据集上传、清洗、分析或 Python 执行。
- 本切片不生成 Word 或 PPT。
- 本切片不要求真实 DeepSeek API Key。
- 本切片不把本地测试适配器输出伪装成真实模型输出。

## 影响

- 新增 `dev-docs/specs/0002-requirement-input-and-task-plan.md`。
- `dev-docs/README.md` 将当前阶段指向 SPEC 0002 待确认。
- `dev-docs/acceptance.md` 记录 SPEC 0002 已启动但尚未实现。
- `dev-docs/implementation-plan.md` 标记下一切片进入任务 4 的 SPEC 阶段。

## 重新评估条件

出现以下情况时，必须更新 SPEC 或新增决策记录：

- 项目负责人要求本切片直接接入真实 DeepSeek；
- 项目负责人要求先做资料采集而不是实验要求拆解；
- `.docx` 解析依赖需要新增但未完成依赖复核；
- L0-L3 判断规则需要改动；
- 本切片范围被扩大到数据分析、Python 执行或交付物生成。
