# SPEC 0031：论文级 Word/PPT 视觉质量与真实渲染验收

## 一、背景

SPEC 0030 已改善 PPT 主题和图表配色，但真实渲染检查仍发现：Word 默认渲染缺少论文版式系统，PPT 内容页留白和证据层次不足，图表缺少稳定的图题/来源信息，部分真实图表在 Office 渲染器中出现标题乱码或不可读。

本切片只改善交付物的视觉表达和验收质量，不改变项目、数据、执行、交付物状态机、数据库 schema、API 路由或现有渲染入口合同。

## 二、目标

1. Word 默认渲染具备统一的论文级页面、字体、标题、正文、图题、表题、页眉、页脚和页码样式。
2. Word 图表按原始宽高比自适应页面可用宽度，不再固定使用单一图片宽度。
3. Word 表格采用轻量学术表格样式，突出表头、减少满屏网格线，并限制表格尺寸。
4. PPT 图表页和内容页显示稳定的图表标签/图题，不把不可读的图内标题作为唯一语义来源。
5. 图表代码统一使用可用字体回退、300 DPI、受控标题长度、`constrained_layout` 或等价布局保护，避免中文乱码和裁切。
6. 生成真实 `.docx`、`.pptx` 后执行结构化 QA、PPT 逐页真实渲染和 Word 逐页真实渲染。

## 三、边界与 owner

- Word 版式 owner：`server/app/infrastructure/renderers/word_renderer.py`。
- PPT 版式 owner：`server/app/infrastructure/renderers/ppt_renderer.py`。
- 图表生成 owner：`server/app/modules/llm/code_task_provider.py` 与 `deepseek_code_task_provider.py`。
- API、Worker、前端只负责调用、展示和下载，不拥有视觉语义。
- 不新增数据库字段，不修改 `WordRenderer.render()`、`PptRenderer.render()` 或 Provider 接口签名。
- 不把论文排版逻辑放入 API、Worker 或提示词。
- 不自动安装外部 Skill，不引入与本切片无关的依赖。

## 四、视觉合同

### 4.1 Word

- 页面：A4，正文区域采用稳定页边距。
- 字体：中文和西文显式设置，避免依赖宿主机默认字体；图表图片仍保持原始像素和宽高比。
- 层次：封面、一级标题、二级标题、正文、图题、表题、来源说明、附录索引分别有稳定样式。
- 图表：图题与图片保持相邻，图片居中，最大宽度不超过正文区域。
- 表格：首行表头突出，正文单元格使用小字号和合理内边距，表格超出列数时截断并留下说明。
- 追溯：图表和表格保留执行产物名称，无法读取文件时返回结构化可见占位文本。

### 4.2 PPT

- 保留 16:9、主题 preset、图表自适应布局和 python-pptx fallback。
- 页面标题不承担全部语义；图表旁增加简短图题/产物名，正文优先呈现结论而非原始长段落。
- 图表在 PPT 中只做等比缩放，不拉伸、不遮挡、不溢出页边界。
- 真实渲染检查每页的文字、图片、字体、溢出和图表可见性。

### 4.3 图表

- 采用期刊式低噪声风格：减少无意义装饰，保留必要坐标、单位、图例和统计信息。
- 默认 `savefig.dpi=300`，显式保存时不得降级覆盖。
- 中文字体按宿主环境可用字体回退，不能只写死单一字体。
- 标题过长时优先缩短或移至文档图题，不能用极小字号硬塞进图内。

## 五、验收

### 5.1 自动验收

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_renderers.py server/tests/test_spec0030_pptxforge_chart_beautification.py
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

### 5.2 真实文件验收

- 生成至少一个带 PNG 图表和 CSV 表格的真实 Word/PPT 示例。
- Word 使用 `render_docx.py` 输出全部页面 PNG，检查无裁切、重叠、缺字、图题漂移和表格断裂。
- PPT 使用 `render_slides.py` 输出全部页面 PNG，检查无裁切、重叠、乱码、图片失真和过度留白。
- 重新打开 `.docx`、`.pptx`，检查文档结构、图片数量、表格数量、页数和页面尺寸。

## 六、停止条件

当 Word/PPT 真实示例、结构化 QA、定向测试和基础回归全部通过，并且预览结果已向项目负责人展示后，本切片停止；不在本切片顺手改业务状态、前端流程或数据库 schema。
