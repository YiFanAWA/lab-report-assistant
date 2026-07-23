# SPEC 0011｜PPT 配置选项

> 状态：SPEC 文档已编写，待项目负责人确认后进入实现
> 所属版本：V1.1.0
> 上游 SPEC：[SPEC 0006 大纲与交付物](0006-outline-and-deliverables.md)（已确认收口，定义 PptRenderer 基础渲染）
> 关联规划：[v1.1.0-planning.md](../v1.1.0-planning.md) 增强目标 5

## 1. 目标

在 SPEC 0006 已建立的 PPT 渲染基础之上，为 PPT 生成增加三项用户可配置选项：

1. **目标页数**：用户指定期望的 PPT 页数，渲染器据此动态决定实际生成页数。
2. **主题色**：用户从预设色板中选择一个主题色，应用到 PPT 标题文字和标题背景。
3. **图表开关**：用户可选择是否在 PPT 中包含图表页（引用执行产物中的 PNG）。

本切片不改变 PPT 渲染的核心架构（仍是 PptRenderer 从同一份已确认大纲提炼生成 .pptx），只在渲染参数层增加配置能力。

## 2. 范围

### 2.1 本切片实现

| # | 功能点 | 说明 |
| --- | --- | --- |
| F1 | PPT 配置合同 | 新增 `PptConfig` Pydantic 模型，包含 `target_slide_count: int \| None`、`theme_color: str \| None`、`include_charts: bool` 三个可选字段 |
| F2 | 渲染器参数扩展 | `PptRenderer.render()` 新增可选 `config` 参数，接收 `PptConfig` 或 dict |
| F3 | 页数控制逻辑 | 渲染器根据 `target_slide_count` 动态决定生成页数：内容多时合并/截断到目标页数，内容少时保持实际页数不强行凑数 |
| F4 | 主题色应用逻辑 | 渲染器根据 `theme_color` 设置标题文字颜色和标题背景颜色；未配置时保持现有默认黑色文字 |
| F5 | 图表开关逻辑 | `include_charts=True` 时生成图表页（现有行为），`include_charts=False` 时跳过图表页 |
| F6 | API 请求体 | `POST /outline/{id}/ppt/generate` 新增可选请求体 `GeneratePptRequest`（含 `config` 字段） |
| F7 | service 层扩展 | `generate_ppt()` 接收可选 `config` 参数，写入 job `input_data` |
| F8 | Worker 接线 | `handle_generate_ppt` 从 `input_data` 读 `config` 传给渲染器 |
| F9 | 前端类型 | 新增 `PptConfig` 接口和 `GeneratePptRequest` 类型 |
| F10 | 前端 API | `generatePpt()` 新增可选 `config` 参数 |
| F11 | 前端 hooks | `useGeneratePpt` mutation 传递 config |
| F12 | 前端 UI | `OutlineWorkspaceView` 新增 PPT 配置表单（页数输入+色板选择+图表开关） |

### 2.2 本切片不做

- 不做 PPT 母版上传（全局模板路径 `PPT_TEMPLATE_PATH` 推迟到 V2.0）
- 不做 PPT 动画、复杂排版、母版编辑
- 不做在线 PPT 预览（推迟到 V2.0）
- 不做每张图表单独配置（使用全局开关）
- 不做任意 hex 色值输入（使用预设色板）
- 不做配置持久化到数据库（每次生成时传参，不落库）
- 不做页数范围 `[min, max]`（使用单一目标页数）
- 不改变 Word 生成流程（Word 无配置选项）
- 不改变 PPT 文件存储路径和版本管理机制（仍是 `ppt_v{version}.pptx`，版本递增，旧版本保留）

## 3. 设计决策（已由项目负责人确认）

### 决策 1：页数配置采用"目标页数"

**选择**：用户指定一个目标页数（如 10 页），渲染器动态决定实际页数。

**理由**：
- 实现简单、行为可预测
- "页数范围"需要判断何时达到上下限，"不足下限要凑页"语义不明确
- 内容多时合并/截断到目标页数，内容少时保持实际页数不强行凑数，符合"不为了凑数生成空页"原则

**约束**：
- 目标页数范围：5-20 页（小于 5 无意义，大于 20 演示过长）
- 默认值：不指定时保持现有行为（标题页 + 内容页 + 图表页 + 总结页，约 5-8 页）
- 目标页数只影响内容页数量，标题页和总结页始终生成

### 决策 2：主题色采用"预设色板"

**选择**：提供 6 个预设主题色，用户从中选择。

**预设色板**：

| 色值 | 名称 | 说明 |
| --- | --- | --- |
| `#2563eb` | 蓝色 | 默认色，与现有 UI 主色一致 |
| `#7c3aed` | 紫色 | 与现有 PPT 按钮色一致 |
| `#16a34a` | 绿色 | 学术清新 |
| `#dc2626` | 红色 | 醒目强调 |
| `#ea580c` | 橙色 | 活泼明快 |
| `#475569` | 灰色 | 商务沉稳 |

**应用范围**：
- 标题页：主标题文字颜色
- 内容页：标题文字颜色
- 图表页：标题文字颜色
- 总结页：标题文字颜色
- 不应用到正文文字（保持黑色确保可读性）
- 不应用到幻灯片背景（保持白色确保对比度）

**理由**：
- 避免无效色值（预设色板全部合法）
- 避免用户输入与白色背景对比度不足的色值
- 与现有前端 UI 配色一致
- 实现简单，无需 hex 校验逻辑

### 决策 3：图表开关采用"全局开关"

**选择**：一个布尔值 `include_charts`，控制是否生成图表页。

**行为**：
- `include_charts=True`（默认）：生成图表页，引用执行产物中的 PNG（现有行为，最多 2 张）
- `include_charts=False`：完全不生成图表页

**理由**：
- 实现简单、语义清晰
- 每张图表单独配置导致 UI 动态化且图表数量不固定
- 全局开关足以满足"不要图表"的需求

### 决策 4：配置不持久化到数据库

**选择**：PPT 配置只作为生成参数传入，不落库。

**理由**：
- PPT 配置是渲染参数，不是业务真相，不需要独立 owner 表
- 每次 PPT 生成时传当前表单值，简单且无迁移
- 生成失败的版本不保留配置，符合"失败不被覆盖"语义
- DeliverableVersion 表已记录 `file_size_bytes` 和 `duration_seconds`，足以追溯生成结果

**后果**：
- 用户每次重新生成 PPT 时需要重新选择配置（前端表单可记住上次值作为 UX 优化，但不作为后端合同）
- 无法追溯"某个历史版本用了什么配置"，但可通过 ChangeRecord 的 summary 间接推断

## 4. 架构设计

### 4.1 Owner 边界

PPT 配置的 owner 链与现有 PPT 渲染链一致，不新增 owner 层：

| 层 | 文件 | 职责 |
| --- | --- | --- |
| 合同层 | `server/app/modules/outlines/contracts.py` | 新增 `PptConfig`、`GeneratePptRequest` Pydantic 模型 |
| Service 层 | `server/app/modules/outlines/service.py` | `generate_ppt()` 接收 config，写入 job `input_data` |
| 渲染器 | `server/app/infrastructure/renderers/ppt_renderer.py` | `render()` 接收 config，应用页数/主题色/图表开关 |
| API 适配层 | `server/app/api/routers/outlines.py` | `generate_ppt` 端点接收 `GeneratePptRequest` body |
| Worker | `server/worker/handlers.py` | `handle_generate_ppt` 从 `input_data` 读 config 传给渲染器 |
| 前端 types | `apps/web/src/features/outlines/types.ts` | 新增 `PptConfig`、`GeneratePptRequest` 接口 |
| 前端 API | `apps/web/src/features/outlines/api.ts` | `generatePpt()` 新增 config 参数 |
| 前端 hooks | `apps/web/src/features/outlines/hooks.ts` | `useGeneratePpt` 传递 config |
| 前端 UI | `apps/web/src/routes/OutlineWorkspaceView.tsx` | 新增 PPT 配置表单组件 |

### 4.2 PptConfig 合同

```python
class PptConfig(BaseModel):
    """PPT 生成配置（SPEC 0011）。

    所有字段可选，未提供时使用默认值。
    配置不持久化，每次生成时传入。
    """

    target_slide_count: int | None = Field(
        default=None,
        description="目标页数（5-20），None 表示使用默认行为",
        ge=5,
        le=20,
    )
    theme_color: str | None = Field(
        default=None,
        description="主题色 hex 值，None 表示使用默认黑色",
    )
    include_charts: bool = Field(
        default=True,
        description="是否包含图表页",
    )
```

**主题色校验**：`theme_color` 必须在预设色板内，否则返回 `PPT_CONFIG_INVALID_THEME_COLOR` 错误。校验逻辑在 service 层，不在 Pydantic 层（保持合同层无业务逻辑）。

**预设色板常量**：在 `contracts.py` 或 `ppt_renderer.py` 中定义 `PPT_THEME_COLORS` 常量集合。

### 4.3 GeneratePptRequest 合同

```python
class GeneratePptRequest(BaseModel):
    """触发 PPT 生成请求（SPEC 0011）。

    所有字段可选，不传时使用默认配置。
    """

    config: PptConfig = Field(default_factory=PptConfig)
```

### 4.4 渲染器扩展

`PptRenderer.render()` 新增 `config` 参数：

```python
def render(
    self,
    project_name: str,
    project_topic: str,
    outline_sections: list[dict],
    execution_artifacts: list[dict],
    output_path: str,
    config: dict | None = None,  # SPEC 0011 新增
) -> str:
```

**config 解析**：
- `config=None` 或空 dict：保持现有行为（向后兼容）
- `config` 非空：解析 `target_slide_count`、`theme_color`、`include_charts`

**页数控制逻辑**（`target_slide_count`）：

1. 计算内容页候选列表（按 source_type 分组，与现有逻辑一致）
2. 如果 `target_slide_count` 未指定：保持现有行为（生成所有内容页）
3. 如果 `target_slide_count` 已指定：
   - `available_slots = target_slide_count - 2`（减去标题页和总结页，最小为 0）
   - 如果内容页候选数 > `available_slots`：合并章节到 `available_slots` 个页面（每页最多 5 个要点，超出截断）
   - 如果内容页候选数 <= `available_slots`：保持实际内容页数（不强行凑数，不生成空页）
   - 图表页不计入 `target_slide_count`（图表是附加页，由 `include_charts` 独立控制）

**主题色应用逻辑**（`theme_color`）：

1. 解析 hex 色值为 RGBColor（python-pptx 的 `RGBColor.from_string(hex_str)`）
2. 标题页：`title.text_frame.paragraphs[0].font.color.rgb = theme_color`
3. 内容页/图表页/总结页：`title_shape.text_frame.paragraphs[0].font.color.rgb = theme_color`
4. 不修改正文文字颜色（保持黑色）
5. 不修改幻灯片背景

**图表开关逻辑**（`include_charts`）：

1. `include_charts=True`：保持现有 `_add_chart_slide` 行为
2. `include_charts=False`：跳过 `_add_chart_slide` 调用

### 4.5 Service 层扩展

`generate_ppt()` 新增可选 `config` 参数：

```python
def generate_ppt(
    db: Session,
    project_id: str,
    outline_id: str,
    config: dict | None = None,  # SPEC 0011 新增
) -> tuple[str, str]:
```

**config 校验**（在 service 层，不在 Pydantic 层）：
- `theme_color` 非空时，必须在 `PPT_THEME_COLORS` 集合内，否则抛出 `AppError(code="PPT_CONFIG_INVALID_THEME_COLOR")`
- `target_slide_count` 的范围校验由 Pydantic `ge=5, le=20` 完成

**写入 job input_data**：

```python
job = job_service.create_job(
    db,
    project_id=project_id,
    job_type=JobType.GENERATE_PPT.value,
    input_data={
        "outline_id": outline_id,
        "deliverable_id": deliverable.id,
        "config": config or {},  # SPEC 0011 新增
    },
)
```

### 4.6 API 适配层

`generate_ppt` 端点新增请求体：

```python
@router.post("/outline/{outline_id}/ppt/generate",
             response_model=GenerateDeliverableResponse,
             status_code=201)
def generate_ppt(project_id: str, outline_id: str,
                  body: GeneratePptRequest | None = None,  # SPEC 0011 新增，可选
                  db: Session = Depends(_db)):
    config = body.config.model_dump() if body else None
    job_id, deliverable_id = outline_service.generate_ppt(
        db, project_id, outline_id, config=config)
    return GenerateDeliverableResponse(
        job_id=job_id, deliverable_id=deliverable_id, template_used=False)
```

**向后兼容**：`body` 参数可选，不传时使用默认配置（`config=None`）。

### 4.7 Worker 接线

`handle_generate_ppt` 从 `input_data` 读 config 传给渲染器：

```python
def handle_generate_ppt(db: Session, job) -> dict:
    data = _parse_input(job)
    outline_id = data.get("outline_id")
    deliverable_id = data.get("deliverable_id")
    config = data.get("config")  # SPEC 0011 新增
    # ... 校验 outline_id 和 deliverable_id ...
    renderer = PptRenderer()
    renderer.render(
        project_name=project.name,
        project_topic=project.topic,
        outline_sections=sections,
        execution_artifacts=artifacts,
        output_path=str(output_path),
        config=config,  # SPEC 0011 新增
    )
```

**降级策略**：
- `config=None` 或空 dict：保持现有行为
- `config` 中字段缺失：使用字段默认值（`target_slide_count=None`、`theme_color=None`、`include_charts=True`）
- 渲染器应用 config 失败（如 hex 色值解析异常）：捕获异常，记录 warning 日志，降级到无 config 渲染

### 4.8 前端接线

**types.ts 新增**：

```typescript
/** PPT 生成配置（SPEC 0011）。 */
export interface PptConfig {
  target_slide_count?: number | null;
  theme_color?: string | null;
  include_charts?: boolean;
}

/** 触发 PPT 生成请求（SPEC 0011）。 */
export interface GeneratePptRequest {
  config?: PptConfig;
}
```

**api.ts 扩展**：

```typescript
export async function generatePpt(
  projectId: string,
  outlineId: string,
  config?: PptConfig  // SPEC 0011 新增
): Promise<GenerateDeliverableResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}/ppt/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: config ?? {} }),
    }
  );
  return handle<GenerateDeliverableResponse>(r);
}
```

**hooks.ts 扩展**：`useGeneratePpt` mutation 调用 `generatePpt` 时传递 config 参数。

**OutlineWorkspaceView.tsx 新增**：
- PPT 配置表单组件（页数输入框 + 色板选择器 + 图表开关 checkbox）
- 表单状态管理（`useState` 管理三个配置值）
- 生成 PPT 按钮点击时将 config 传入 `pptMutation.mutate`

## 5. 实现计划

### 步骤 1：合同层

- `contracts.py` 新增 `PptConfig`、`GeneratePptRequest`
- 新增 `PPT_THEME_COLORS` 常量（预设色板集合）

### 步骤 2：渲染器扩展

- `ppt_renderer.py` 的 `render()` 新增 `config` 参数
- 新增 `_apply_theme_color` 辅助方法
- 新增 `_control_slide_count` 辅助方法
- 扩展 `_render_content_slides` 支持 `include_charts` 开关

### 步骤 3：Service 层

- `service.py` 的 `generate_ppt()` 新增 `config` 参数
- 新增 config 校验逻辑（theme_color 必须在预设色板内）
- job `input_data` 写入 config

### 步骤 4：API 适配层

- `outlines.py` 的 `generate_ppt` 端点新增 `body` 参数
- `main.py` 新增错误码映射（`PPT_CONFIG_INVALID_THEME_COLOR` → 400）

### 步骤 5：Worker 接线

- `handlers.py` 的 `handle_generate_ppt` 读 config 传给渲染器
- 渲染器异常降级到无 config 渲染 + warning 日志

### 步骤 6：前端类型和 API

- `types.ts` 新增 `PptConfig`、`GeneratePptRequest`
- `api.ts` 的 `generatePpt()` 新增 config 参数
- `hooks.ts` 的 `useGeneratePpt` 传递 config

### 步骤 7：前端 UI

- `OutlineWorkspaceView.tsx` 新增 PPT 配置表单（页数输入 + 色板选择 + 图表开关）
- 表单值传入 `pptMutation.mutate`

### 步骤 8：测试

- 后端：渲染器测试（config 各字段的应用逻辑 + 降级）+ API 测试（请求体解析 + 错误码）
- 前端：API 测试（generatePpt 传 config）+ 组件测试（配置表单渲染和交互）

### 步骤 9：验收 + 文档回写 + git 收口

- 运行完整验收命令
- 更新 `acceptance.md`、`implementation-plan.md`、`v1.1.0-planning.md`
- git commit + push

## 6. 验收标准

### 6.1 渲染器验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| R1 | `config=None` 时渲染 | 保持现有行为，生成默认页数的 PPT |
| R2 | `target_slide_count=6` 时渲染 | 内容页数不超过 4 页（6 - 标题页 - 总结页），内容少时保持实际页数 |
| R3 | `target_slide_count=20` 时渲染 | 内容页数不超过 18 页，内容少时保持实际页数 |
| R4 | `theme_color="#7c3aed"` 时渲染 | 标题页和内容页标题文字颜色为紫色 |
| R5 | `include_charts=False` 时渲染 | 不生成图表页 |
| R6 | `include_charts=True`（默认）时渲染 | 生成图表页（有图表产物时） |
| R7 | config 中 hex 色值解析异常时降级 | 记录 warning 日志，降级到无 config 渲染 |

### 6.2 API 验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| A1 | `POST /ppt/generate` 无 body | 成功，使用默认配置生成 |
| A2 | `POST /ppt/generate` body=`{config:{target_slide_count:10}}` | 成功，返回 job_id 和 deliverable_id |
| A3 | `POST /ppt/generate` body=`{config:{theme_color:"#invalid"}}` | 返回 400 + `PPT_CONFIG_INVALID_THEME_COLOR` |
| A4 | `POST /ppt/generate` body=`{config:{target_slide_count:3}}` | 返回 400 + `REQUEST_VALIDATION_ERROR`（小于 5） |
| A5 | `POST /ppt/generate` body=`{config:{target_slide_count:25}}` | 返回 400 + `REQUEST_VALIDATION_ERROR`（大于 20） |
| A6 | `POST /ppt/generate` body=`{config:{include_charts:false}}` | 成功，Worker 跳过图表页 |

### 6.3 前端验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| F1 | OutlineWorkspaceView 显示 PPT 配置表单 | 包含页数输入框、色板选择器、图表开关 |
| F2 | 选择主题色后点击生成 PPT | 请求体包含 `config.theme_color` |
| F3 | 不填写页数时点击生成 PPT | 请求体 `config.target_slide_count` 为 null |
| F4 | 关闭图表开关后点击生成 PPT | 请求体 `config.include_charts` 为 false |
| F5 | `generatePpt` API 测试 | 正确传递 config 参数到请求体 |

### 6.4 整体验收命令

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
npm.cmd run test -- --run
```

## 7. 风险与降级

### 7.1 页数控制与内容截断

**风险**：目标页数过小（如 5 页）时，大纲章节内容可能被过度截断，导致 PPT 信息丢失。

**缓解**：
- 页数下限设为 5（Pydantic `ge=5`）
- 每页最多 5 个要点（现有行为），超出截断并加省略号
- 渲染器不为了凑数生成空页

### 7.2 主题色对比度

**风险**：虽然使用预设色板，但某些色值在特定投影环境下可能对比度不足。

**缓解**：
- 预设色板全部为中等亮度色值，在白色背景上有足够对比度
- 主题色只应用到标题文字，不应用到正文（正文保持黑色）
- 不修改幻灯片背景（保持白色）

### 7.3 向后兼容

**风险**：现有调用方（如 Worker handler 的旧 input_data）不包含 config 字段。

**缓解**：
- `config` 参数可选，`None` 时保持现有行为
- Worker handler 使用 `data.get("config")` 读取，缺失时返回 `None`
- API 端点 `body` 参数可选，不传时使用默认配置
- 渲染器 `config=None` 时完全保持现有渲染逻辑

### 7.4 配置不持久化的追溯性

**风险**：用户无法追溯某个历史 PPT 版本使用了什么配置。

**缓解**：
- ChangeRecord 的 summary 可记录"触发 PPT 生成"事件，但不记录具体 config（避免变更记录膨胀）
- 用户每次重新生成时重新选择配置，前端表单可记住上次值作为 UX 优化
- DeliverableVersion 的 `file_size_bytes` 和 `duration_seconds` 可间接反映配置影响

## 8. 依赖与配置

### 8.1 依赖

- 无新增依赖（`python-pptx>=1.0.2` 已安装）
- 无新增 Python 包

### 8.2 配置

- 无新增环境变量
- 无新增数据库迁移（配置不持久化）
- 预设色板 `PPT_THEME_COLORS` 作为代码常量，不作为环境变量

## 9. 不属于本切片的事项

- PPT 母版上传（推迟到 V2.0）
- PPT 动画和复杂排版（不在 V1.1.0 范围）
- 在线 PPT 预览（推迟到 V2.0）
- PPT 模板渲染（类似 Word 模板，推迟到 V2.0）
- 配置持久化和历史配置追溯（本切片不做，每次生成时传参）
- Word 生成配置选项（Word 无配置选项，只有模板支持）
