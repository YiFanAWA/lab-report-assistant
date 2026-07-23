# SPEC 0011 测试计划｜PPT 配置选项

> 状态：测试计划已编写，待实现后执行验证
> 所属 SPEC：[SPEC 0011 PPT 配置选项](0011-ppt-config-options.md)

## 1. 测试范围

覆盖 SPEC 0011 的三个核心配置项及其组合：

| 配置项 | 取值范围 | 默认值 |
| --- | --- | --- |
| `target_slide_count` | 5-20 或 None | None（保持现有行为） |
| `theme_color` | 6 个预设色或 None | None（默认黑色） |
| `include_charts` | true / false | true |

## 2. 渲染器测试（后端单元测试）

文件：`server/tests/test_ppt_config.py`

### 2.1 页数控制（target_slide_count）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| R-PAGE-01 | config=None 保持默认行为 | `config=None`，大纲 6 个章节 | 生成标题页+内容页+总结页，页数与现有行为一致 |
| R-PAGE-02 | 目标页数 6，内容多于可用槽位 | `target_slide_count=6`，大纲 10 个章节 | 内容页数不超过 4（6-标题页-总结页），章节被合并 |
| R-PAGE-03 | 目标页数 20，内容少于可用槽位 | `target_slide_count=20`，大纲 4 个章节 | 内容页数保持 4（不强行凑空页） |
| R-PAGE-04 | 目标页数 5（最小值），内容多 | `target_slide_count=5`，大纲 8 个章节 | 内容页数不超过 3（5-2），章节被合并截断 |
| R-PAGE-05 | 图表页不计入目标页数 | `target_slide_count=8`，含图表产物 | 内容页+标题页+总结页<=8，图表页额外生成 |

### 2.2 主题色（theme_color）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| R-COLOR-01 | config=None 保持默认黑色 | `config=None` | 标题文字颜色为默认（不修改） |
| R-COLOR-02 | 主题色为紫色 | `theme_color="#7c3aed"` | 标题页和内容页标题文字颜色为紫色 RGBColor(0x7c,0x3a,0xed) |
| R-COLOR-03 | 主题色为蓝色（默认推荐色） | `theme_color="#2563eb"` | 标题文字颜色为蓝色 RGBColor(0x25,0x63,0xeb) |
| R-COLOR-04 | 主题色应用到所有页面类型 | `theme_color="#16a34a"`，含图表产物和总结章节 | 标题页、内容页、图表页、总结页标题均为绿色 |
| R-COLOR-05 | 主题色不修改正文和背景 | `theme_color="#dc2626"` | 正文文字保持黑色，背景保持白色 |

### 2.3 图表开关（include_charts）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| R-CHART-01 | include_charts=True 有图表产物 | `include_charts=True`，含 2 个 CHART_PNG | 生成图表页，嵌入 2 张 PNG |
| R-CHART-02 | include_charts=False 有图表产物 | `include_charts=False`，含 2 个 CHART_PNG | 不生成图表页 |
| R-CHART-03 | include_charts=False 无图表产物 | `include_charts=False`，无 CHART_PNG | 不生成图表页（现有行为一致） |

### 2.4 降级策略

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| R-FALL-01 | config 为空 dict | `config={}` | 保持默认行为 |
| R-FALL-02 | config 部分字段缺失 | `config={"theme_color":"#2563eb"}`（无 target_slide_count 和 include_charts） | 只应用主题色，其他使用默认值 |
| R-FALL-03 | hex 色值解析异常 | `config={"theme_color":"#invalid"}`（已过 service 校验但渲染器内部异常） | 捕获异常，降级到无 config 渲染，记录 warning |

## 3. Service 层测试（后端单元测试）

文件：`server/tests/test_outline_service.py`（扩展）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| S-01 | generate_ppt 无 config | `config=None` | 成功创建 job，input_data 无 config 字段 |
| S-02 | generate_ppt 有 config | `config={"target_slide_count":10,"theme_color":"#2563eb"}` | 成功创建 job，input_data 含 config |
| S-03 | theme_color 不在预设色板内 | `config={"theme_color":"#ff0000"}` | 抛出 AppError(code="PPT_CONFIG_INVALID_THEME_COLOR") |
| S-04 | theme_color 为预设色板内值 | `config={"theme_color":"#475569"}` | 成功通过校验 |

## 4. API 测试（后端集成测试）

文件：`server/tests/test_outline_api.py`（扩展）

| 测试 ID | 场景 | 请求 | 期望响应 |
| --- | --- | --- | --- |
| A-01 | 无 body 生成 PPT | `POST /ppt/generate`（无 body） | 201，返回 job_id 和 deliverable_id，template_used=false |
| A-02 | 有 config 生成 PPT | `body={"config":{"target_slide_count":10}}` | 201，返回 job_id 和 deliverable_id |
| A-03 | 完整 config 生成 PPT | `body={"config":{"target_slide_count":8,"theme_color":"#7c3aed","include_charts":false}}` | 201，返回 job_id |
| A-04 | 无效 theme_color | `body={"config":{"theme_color":"#ff0000"}}` | 400，error.code=PPT_CONFIG_INVALID_THEME_COLOR |
| A-05 | target_slide_count 小于 5 | `body={"config":{"target_slide_count":3}}` | 422，请求校验失败 |
| A-06 | target_slide_count 大于 20 | `body={"config":{"target_slide_count":25}}` | 422，请求校验失败 |
| A-07 | include_charts=false | `body={"config":{"include_charts":false}}` | 201，成功创建 |
| A-08 | 空 config 对象 | `body={"config":{}}` | 201，使用默认值 |

## 5. Worker 接线测试（后端集成测试）

文件：`server/tests/test_ppt_config.py`（扩展）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| W-01 | input_data 含 config | job.input_data={"outline_id","deliverable_id","config":{"theme_color":"#2563eb"}} | 渲染器被调用时传入 config |
| W-02 | input_data 不含 config | job.input_data={"outline_id","deliverable_id"}（旧格式） | 渲染器被调用时 config=None，保持现有行为 |
| W-03 | 渲染器异常降级 | config 含异常 theme_color（模拟渲染器内部异常） | 降级到无 config 渲染，version 状态 SUCCEEDED，记录 warning |

## 6. 前端 API 测试

文件：`apps/web/src/features/outlines/__tests__/api.test.ts`（扩展）

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| F-API-01 | generatePpt 无 config | `generatePpt(projectId, outlineId)` | POST 请求无 body 或 body 为 `{config:{}}` |
| F-API-02 | generatePpt 有 config | `generatePpt(projectId, outlineId, {target_slide_count:10})` | POST body 含 `config.target_slide_count=10` |
| F-API-03 | generatePpt 完整 config | `generatePpt(projectId, outlineId, {target_slide_count:8,theme_color:"#7c3aed",include_charts:false})` | POST body 含完整 config |
| F-API-04 | generatePpt 请求失败 | 后端返回 400 | reject 错误对象 |

## 7. 前端组件测试

文件：`apps/web/src/routes/__tests__/OutlineWorkspaceView.test.tsx`（扩展）

| 测试 ID | 场景 | 期望结果 |
| --- | --- | --- |
| F-UI-01 | CONFIRMED 状态显示 PPT 配置表单 | 包含页数输入框、色板选择器、图表开关 |
| F-UI-02 | 色板显示 6 个预设色 | 渲染 6 个色块选项 |
| F-UI-03 | 选择主题色后点击生成 PPT | pptMutation.mutate 被调用时含 theme_color |
| F-UI-04 | 不填写页数时点击生成 PPT | config.target_slide_count 为 null |
| F-UI-05 | 关闭图表开关后点击生成 PPT | config.include_charts 为 false |
| F-UI-06 | 输入页数后点击生成 PPT | config.target_slide_count 为输入值 |

## 8. 测试执行命令

```text
# 后端测试
cd server
.venv\Scripts\python.exe -m pytest tests/test_ppt_config.py -v
.venv\Scripts\python.exe -m pytest -v

# 前端测试
cd apps\web
npm.cmd test -- --run
```

## 9. 验收通过标准

| 维度 | 标准 |
| --- | --- |
| 渲染器测试 | R-PAGE-01~05 + R-COLOR-01~05 + R-CHART-01~03 + R-FALL-01~03 全部通过 |
| Service 测试 | S-01~04 全部通过 |
| API 测试 | A-01~08 全部通过 |
| Worker 测试 | W-01~03 全部通过 |
| 前端 API 测试 | F-API-01~04 全部通过 |
| 前端组件测试 | F-UI-01~06 全部通过 |
| 全量回归 | 后端 pytest 全量通过（无新增 warning），前端 vitest 全量通过 |
| 类型检查 | npm run lint 通过 |
| 构建 | npm run build 通过 |
| 迁移 | alembic upgrade head 通过（无新增迁移） |
