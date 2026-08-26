# 决策 0041：启动 SPEC 0032 PPT Master 与上海交大模板适配

## 决策

批准进入 SPEC 0032 实现阶段。

本切片采用“能力适配”而非“整仓库嵌入”：保留当前项目的 PPT 渲染 owner、证据链和真实图表，将外部项目的工作流原则与经许可审查的模板能力映射到 `PptConfig`、`server/app/modules/outlines/ppt_workflows.py` 和 `PptRenderer`。

## 依据

- `ppt-master` 的核心价值是路由式工作流、原生可编辑 PPTX、模板填充和逐页质量检查；这些能力与当前项目交付物目标一致。
- `openclaw-sjtu` 同时包含校园业务脚本和 PPT/模板资源，整仓库接入会扩大产品边界并引入无关凭证与外部系统风险。
- 当前项目已经有 `pptxforge` 主路径、`python-pptx` fallback、真实图表和 `PptConfig`，最小改动是增加模式注册表与映射，而不是引入第二套渲染器。

## 边界

- 不接入 Canvas、邮箱、论坛、校园登录、外部图片下载或语音/视频能力。
- 不改变数据库 schema、Worker、API 路由和 `PptRenderer.render()` 签名。
- 模板版权无法确认时不复制资源，仅记录来源。

## 验收

以 SPEC 0032 的合同测试、三种模式真实 PPTX、逐页渲染和全量回归为准。
