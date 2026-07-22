"""大纲与交付物核心模块。

拥有 Outline、Deliverable、DeliverableVersion 的业务语义：
- 统一实验大纲生成、用户确认、编辑、失效传播
- Word/PPT 生成请求、生成状态、交付物版本
- 交付物与证据/执行记录之间的追溯关系

API、Worker、提示词只能调用本模块的 service 方法，不能直接修改大纲状态。
"""
