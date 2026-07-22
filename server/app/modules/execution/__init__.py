"""执行核心模块。

拥有 CodeTask、ExecutionRun、ExecutionArtifact 的业务语义：
- 代码任务候选生成、编辑、确认、拒绝
- 受控执行环境触发与结果保存
- STALE 传播（AnalysisPlan → CodeTask → ExecutionRun）
- 项目状态推进（ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED）

API、Worker、提示词只能调用本模块的 service 方法，不能直接修改执行状态。
"""
