# SPEC 0032：PPT Master 与上海交大模板适配

## 1. 目标

在不破坏现有“统一大纲—真实执行结果—图表索引—PPT 交付物”链路的前提下，吸收 `hugohe3/ppt-master` 的路由式 PPT 工作流，以及 `xhh678876/openclaw-sjtu` 中可确认的交大 PPT 模板能力，改善实验汇报 PPT 的叙事一致性、模板复用和视觉验收质量。

## 2. 当前问题

当前项目已经具备 `PptRenderer`、`pptxforge` 主题和 `python-pptx` 降级路径，但外部工作流中的以下能力尚未形成项目内合同：

- PPT 生成模式无法明确表达“原生可编辑”“学术报告”“交大风格”三类视觉目标；
- PPT 模板能力没有独立的项目内注册表和来源记录；
- 外部 Skill 的路由式叙事和逐页视觉门禁没有被固化为当前项目的验收语义；
- 当前 PPT 配置虽能控制页数、主题色和图表开关，但无法选择经过审查的模板/风格配置。

## 3. 范围

### 3.1 本切片做什么

1. 在 `PptConfig` 增加可选的 `ppt_workflow` 字段，支持：
   - `native_editable`：默认原生可编辑模式；
   - `academic`：论文/实验汇报风格；
   - `sjtu_academic`：上海交大风格学术汇报模式。
2. 增加项目内 PPT 工作流注册表，维护模式名称、适用场景、版式约束和来源。
3. 将工作流模式映射到现有 `PptRenderer` 的主题、布局密度、图表标题和页脚策略。
4. 保留 `pptxforge` 主路径和 `python-pptx` fallback；不改变 `PptRenderer.render()` 签名。
5. 为交大风格提供本地模板资源入口和来源说明；本切片只接入仓库中可审查、可合法分发的模板资源，不自动下载校园图库或调用交大账号服务。
6. 增加结构化配置测试、模板注册表测试和真实 PPT 重新打开/逐页渲染验收。

### 3.2 本切片明确不做

- 不复制 `ppt-master` 的完整 AI IDE 编排、赞助服务、图像生成服务或语音/视频导出链路；
- 不接入上海交大 Canvas、邮箱、论坛、课程评价、校园登录或任何外部账号；
- 不从模型临时上下文直接生成 PPT；
- 不把整页截图或 PDF 页面粘贴成不可编辑 PPT；
- 不修改数据库 schema、交付物状态机、Worker 任务语义或现有 API 路由；
- 不新增论文 PDF 生成能力；
- 不在本切片中替换现有 `PptRenderer` 的 owner。

## 4. 外部来源与许可边界

### 4.1 PPT Master

- 仓库：<https://github.com/hugohe3/ppt-master>
- 许可证：MIT；若复制代码或实质性代码片段，必须保留版权与许可证文本。
- 本切片只吸收其公开工作流思想、路由原则和验收要求；默认不复制整套 Skill 源码。

### 4.2 上海交大 Skill

- 仓库：<https://github.com/xhh678876/openclaw-sjtu>
- 许可证：以仓库当前 `LICENSE` 为准；复制代码或资源前必须保留其许可声明。
- 本切片只接入经审查的 PPT 模板/配置资源，不接入校园业务脚本和凭证。
- 若模板文件的再分发权无法确认，则只保留模板来源和适配说明，不将文件复制进主仓库。

## 5. Owner 与数据流

### 5.1 唯一 owner

PPT 工作流模式、模板注册表和模式到渲染参数的映射，唯一 owner 为 `server/app/modules/outlines/ppt_workflows.py`；`PptRenderer` 只负责消费该合同并完成渲染。

`PptConfig` 只负责 API 合同校验；API、前端、Worker 和模型提示词不得各自维护模式语义。

### 5.2 数据流

```text
已确认大纲 + 已确认执行产物
        -> PptConfig.ppt_workflow
        -> PPT 工作流注册表
        -> PptRenderer 选择主题/布局/图注策略
        -> pptxforge 主路径
        -> python-pptx fallback
        -> 结构化 QA + 逐页真实渲染
```

## 6. 合同设计

`PptConfig` 新增：

```text
ppt_workflow: "native_editable" | "academic" | "sjtu_academic" | null
```

- `null` 等同于现有默认行为，保持向后兼容；
- 非法模式必须返回结构化校验错误；
- `ppt_workflow` 优先级低于显式 `theme_preset`，高于 `theme_color` 推导；
- `sjtu_academic` 不得隐式下载外部模板、图片、字体或凭证。

## 7. 实现要求

1. 新增 `ppt_workflows.py` 或等价静态模块，提供注册表和只读解析函数。
2. `PptRenderer` 只调用注册表解析结果，不在渲染方法中散落字符串判断。
3. `native_editable` 必须继续输出可被 `python-pptx` 打开的原生 PPTX。
4. `academic` 和 `sjtu_academic` 必须复用真实执行图表，图表只做等比缩放，不拉伸、不遮挡、不越界。
5. 每个图表页必须包含稳定的图表标签/图题；来源信息沿用现有证据/执行产物关系。
6. 模板和字体缺失时必须结构化降级到内置主题，不得静默伪装为模板已应用。

## 8. 验收标准

### 8.1 合同与单元测试

- `PptConfig` 默认值和三个合法模式通过；
- 非法模式返回 Pydantic 校验错误；
- 模式优先级与既有 `theme_preset`/`theme_color` 规则一致；
- 注册表条目不包含外部凭证、任意宿主路径或网络下载动作。

### 8.2 真实文件验收

至少生成三份真实 PPTX：

- 默认 `native_editable`；
- `academic`；
- `sjtu_academic`。

每份文件必须：

- 能被 `python-pptx` 重新打开；
- 16:9 页面尺寸正确；
- 图表、图题和正文没有裁切、重叠、乱码或越界；
- 逐页渲染 PNG 并完成人工/视觉检查；
- 与同一份执行产物的图表数量和文件来源一致。

### 8.3 回归验收

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py server/tests/test_ppt_workflows.py
server/.venv/Scripts/python.exe -m pytest
npm.cmd run lint
npm.cmd run build
```

## 9. 停止条件

当三个工作流均能生成并通过真实 PPTX 结构检查、逐页渲染检查和项目回归测试，且依赖/许可/来源文档已回写，停止本切片。若模板再分发权无法确认，则停止在“模板来源登记 + 无资源复制”的安全边界，不继续复制资源。

## 10. 未闭合风险

- `ppt-master` 推荐的长上下文模型不是当前项目模型合同的一部分，本切片不修改 LLM Provider；
- 上海交大仓库的模板文件与字体授权需要逐项确认，无法确认的资源不进入主仓库；
- 真实视觉验收依赖本机 Office/LibreOffice/渲染工具可用性，缺失时必须记录替代证据。
