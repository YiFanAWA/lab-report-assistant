# SPEC 0042：开放许可科研图形资产库与科研示意图组件系统

**状态：** 实现与本地验收完成，待项目负责人确认视觉效果后收口  
**日期：** 2026-08-13  
**前序 SPEC：** SPEC 0041 论文级异构图形编排与语义选图系统  
**owner：** `server/app/modules/scientific_assets/` 拥有资产清单、许可证策略、完整性校验、检索和署名合同；`server/app/modules/outlines/figure_planner.py` 继续拥有论文图形语义；`server/app/infrastructure/renderers/scientific_schematic_renderer.py` 只负责确定性绘制；Word/PDF/PPT renderer 只消费生成产物。

## 1. 背景与问题

SPEC 0039—0041 已建立图形语义、论证合同和异构编排，但当前逻辑图的视觉元素仍以矩形、文字和箭头为主。正式论文常见的实验流程、仪器路径和科研机制示意图还需要样本、容器、实验设备、数据处理、结果输出等具象组件，以及分支、汇合、多面板、图例和步骤编号。

网络上已有 BioRender、Mind the Graph 等高质量模板平台，但绕过水印、付费导出或许可证限制会引入侵权和论文发表风险。项目需要的是一套可审计、可离线、可再生成、可交接的开放许可本地资产库，而不是抓取受限平台素材。

## 2. 目标

1. 建立本地科研图形资产注册表，只接收许可证明确且允许当前用途的开放资源。
2. 保存 SVG 可编辑真源，并为 Word/PPT 生成经校验的 PNG 派生物；二者通过 SHA-256 和派生记录绑定。
3. 支持 Public Domain、CC0、MIT、Apache-2.0、BSD 和 CC BY 3.0/4.0；CC BY 素材自动进入署名清单。
4. 默认首批优先收录 Public Domain/CC0 组件，降低论文图注的署名负担。
5. 建立可复用科研示意图组件角色：样本、容器、处理、仪器、数据、分析和输出。
6. 使用确定性布局与绘制生成实验流程图、分析工作流和多面板科研示意图；DeepSeek 只产生可校验语义候选，不直接拥有 SVG/XML、坐标、许可证或科研事实。
7. Word/PDF/PPT 继续消费同一份 `FigurePlan` 和同一生成产物，保留来源、许可证、署名和研究证据追溯。

## 3. 非目标与禁止路径

- 不绕过 BioRender、Mind the Graph 或其他平台的水印、登录、付费导出和技术限制。
- 不抓取、反编译或再分发授权不明、仅限个人使用、禁止衍生或禁止再分发的素材。
- 不从已发表论文中抠取组件，也不把“网上可见”视为“可打包分发”。
- 不把整套第三方仓库直接嵌入应用；只按清单收录经过逐项许可证和安全审计的资产。
- 不建立自由拖拽编辑器，不新增数据库表、公开 API 或前端资产市场。
- 不允许 renderer、LLM prompt 或案例脚本成为资产许可证、图形语义或科研事实的第二 owner。
- 不生成缺少来源支持的医学机制，不把观察性关联绘制为确定性因果。

## 4. 许可证策略

### 4.1 自动允许

| 许可证 | 入库策略 | 成品要求 |
|---|---|---|
| Public Domain / CC0-1.0 | 自动允许 | 建议记录来源；无需强制署名 |
| MIT / Apache-2.0 / BSD-2-Clause / BSD-3-Clause | 自动允许 | 保留许可证与版权文本；按许可证生成 NOTICE |
| CC BY 3.0 / CC BY 4.0 | 自动允许 | 必须记录作者、来源、许可证链接、修改说明并生成署名 |

### 4.2 人工审核或拒绝

- CC BY-SA：首期不自动入库；其衍生与再分发条件可能影响整套图形或交付物，必须逐项人工评估。
- GPL/LGPL/AGPL：代码许可证不得自动映射为单个图形资产许可；没有明确资产许可时拒绝。
- NC、ND、Editorial Use Only、Personal Use Only、No Redistribution：拒绝进入运行时资产库。
- 自定义许可证、无许可证、来源页面与文件元数据冲突：拒绝并返回结构化原因。
- 带平台水印或必须通过付费计划取得出版许可的资产：拒绝。

许可证白名单和拒绝原因由 `scientific_assets` owner 维护，下载脚本、renderer 和 UI 不得自行放宽。

## 5. 资产清单合同

每项资产必须包含：

```text
ScientificAsset
  asset_id: str
  title: str
  semantic_roles: tuple[str, ...]
  category: str
  source_name: str
  source_url: str
  upstream_file_url: str
  author: str
  license_id: str
  license_url: str
  attribution_text: str
  modification_note: str
  source_format: "svg"
  source_path: str
  source_sha256: str
  preview_path: str | None
  preview_sha256: str | None
  width: float
  height: float
  view_box: str
  publication_allowed: bool
  redistribution_allowed: bool
  verified_at: str
```

注册表加载时必须校验：稳定 id 唯一、路径位于受控资产根目录、文件存在、哈希一致、许可证在白名单、署名字段满足许可证要求、SVG 通过安全检查。

## 6. 目录和 owner

```text
server/app/modules/scientific_assets/
  models.py              # 资产、许可证、署名和错误合同
  registry.py            # manifest 加载、检索和完整性校验
  license_policy.py      # 白名单、人工审核和拒绝策略
  attribution.py         # ATTRIBUTION/NOTICE 生成

server/app/assets/scientific/
  manifest.json
  ATTRIBUTION.md
  LICENSES/
  svg/
    apparatus/
    biological/
    data_analysis/
    instruments/
    outputs/
  png/                   # 可重建派生缓存，不是授权真源

server/app/infrastructure/renderers/
  scientific_schematic_renderer.py
```

`figure_planner.py` 只通过 `asset_id`/`semantic_role` 引用资产，不复制许可证判断。资产注册表不决定研究节点、边、因果关系或统计结论。

## 7. SVG 安全和资源上界

入库前必须拒绝：

- `script`、事件处理属性、动画和可执行内容；
- 外部 URL、远程字体、远程图片、`foreignObject`、`iframe`、对象嵌入；
- 越过受控根目录的文件引用和不受控 data URI；
- DTD、实体扩展和可能触发 XML 外部实体的内容；
- 超过 2 MiB 的单文件、超过 5,000 个 XML 元素、异常嵌套或无有效 `viewBox` 的 SVG；
- 不透明版权/水印标识与清单不一致的文件。

SVG 安全校验和许可证校验都通过后才允许生成派生 PNG。运行时不访问网络。

## 8. 科研示意图合同

在现有 `FigurePlan` 下增加可选的科研组件元数据，不新建图形语义 owner：

```text
ScientificSchematicSpec
  panels: tuple[SchematicPanel, ...]
  placements: tuple[SchematicPlacement, ...]
  connectors: tuple[SchematicConnector, ...]
  legend_items: tuple[str, ...]
  style_profile: str

SchematicPlacement
  placement_id: str
  node_id: str
  asset_id: str
  label: str
  role: str
  panel_id: str
  step_number: int | None
```

节点与边仍来自 `FigurePlan`；`asset_id` 只决定视觉组件。缺失组件时按以下顺序降级：同角色开放组件 → 项目自有抽象矢量原语 → 正式文本节点。禁止联网找图或偷偷替换为受限资产。

## 9. 渲染路线

1. 规划器确定图形语义、节点、边、证据状态和目标表面。
2. 组件映射器根据节点角色从注册表选择资产；相同输入必须得到相同结果。
3. 布局器按 `linear_flow`、`branch_merge`、`layered_mechanism`、`multi_panel` 等 profile 生成坐标。
4. renderer 组合开放 SVG/PNG 组件、项目自有箭头、面板、编号、标签、图例和边界说明。
5. 输出高分辨率 PNG 供现有 Word/PPT 路径消费，同时保存结构化 spec、原始资产 id、哈希和署名列表。
6. 若新增 SVG→PNG 依赖，必须单独完成依赖审查、锁定版本、Windows/Docker 验证和安全清洗前置；不得调用浏览器截图作为生产转换器。

## 10. 首批资产和样例范围

首批以 CC0/Public Domain 为主，覆盖：

- 数据源、CSV/表格、缺失检查、筛选、分组、统计模型、图表输出；
- 培养皿、孔板、试管、移液器、凝胶、电泳等实验器材；
- 显微镜、测序/检测设备等仪器；
- 细胞、DNA、蛋白等基础生物对象；
- 结果谱图、森林图、热图、表格等输出角色。

最小可验证样例为当前 Diabetes 论文解读的“公开数据 → 质量检查 → HbA1c 分组 → 30 天再入院 → Logistic 复核 → 论文图表”科研分析流程。它表达数据分析流程，不推断医学机制。

## 11. 实施顺序

1. 增加许可证、资产、署名和错误合同及负向测试。
2. 实现 manifest 注册表、哈希校验、受控路径和 SVG 安全校验。
3. 建立首批开放许可资产及完整许可证副本/署名清单。
4. 实现科研示意图 spec、角色映射、确定性布局和 renderer。
5. 生成当前论文案例样图并接入 Word/PDF/PPT 的同源产物。
6. 运行定向测试、全量回归、依赖/迁移/前端门禁和逐页视觉 QA。
7. 回写 `dev-docs/README.md`、`dependency-review.md`、`implementation-plan.md`、`acceptance.md` 和本 SPEC，等待项目负责人确认收口。

## 12. 验收标准

- 注册表能加载并检索首批资产，所有文件哈希、许可证和受控路径校验通过。
- 白名单许可证有正向测试；无许可证、NC、ND、未知许可证、缺失署名、哈希漂移和路径逃逸均有负向测试。
- SVG 中脚本、事件、外部引用、DTD、`foreignObject` 和资源上界违规均被拒绝。
- `ATTRIBUTION.md`/NOTICE 可稳定再生成，CC BY 素材的作者、来源、许可证和修改说明齐全。
- 至少生成一张包含具象科研组件、分支/汇合、步骤编号、图例和解释边界的高分辨率示意图，不再只由矩形框组成。
- Word/PDF/PPT 使用同一示意图产物；真实文件无裁切、重叠、线条穿字、模糊和错误署名。
- 不使用、下载或打包 BioRender/Mind the Graph 的受限与带水印素材。
- 全量后端测试、Alembic、前端 lint/build 通过；若新增转换依赖，Windows 与 Docker 两个目标环境均验证。

## 13. 风险与停止条件

- 许可证无法确认：不入库，记录结构化拒绝原因。
- SVG 无法安全清洗：不转换、不渲染，降级到项目自有原语。
- 转换器不能跨 Windows/Docker 稳定运行：不把该依赖接入主线，保留 SVG 真源和预生成派生物，重新评估适配器。
- 组件图让观察性分析看起来像因果或机制：阻断成品并回到 `FigurePlan` 证据状态修正。
- 视觉样例仍主要由矩形卡片构成，或没有显示组件库相对 SPEC 0041 的实质提升：不得收口。

当资产库、许可证/安全门禁、署名生成、科研示意图样例、Word/PDF/PPT 同源消费和全量回归均通过，并由项目负责人确认视觉效果与授权边界后，SPEC 0042 才可收口。


## 14. 实施与验收记录（2026-08-13）

- 新增 `scientific_assets` owner：许可证 allow/review/deny 策略、不可变资产合同、manifest 注册表、受控路径、SHA-256 对账、稳定署名生成和 SVG 安全门禁。
- 首批收录 7 个 Bioicons CC0 SVG，固定到上游 commit `d29e766ea7580b8063c4f47b29e872db40a4d979`；本地保存来源、作者、许可证、上游 URL、哈希与核验日期，不收录受限平台或带水印素材。
- `FigurePlan` 增加 `ScientificSchematicSpec`、面板、placement 和 connector 合同；placement 标签必须与 FigureNode 真源一致，connector 必须对应 FigureEdge。
- `ScientificSchematicRenderer` 生成 2400×1350、300 DPI PNG 与 JSON 追溯文件，支持分支/汇合、步骤编号、图例和曲线箭头；交付物携带资产 id、源文件哈希和逐项来源。
- 三路 Luna 只读审查推动收口：图形语义侧补齐 DAG 环路拒绝、连接标签与 FigureEdge 对账、观察性非因果措辞和按 source_ids/artifact_group 选图；许可安全侧补齐任意属性外部 `url()`、布尔字段严格类型和 NaN/Infinity viewBox 拒绝；交付物侧补齐 Word/PPT 同源 PNG 二进制哈希集成测试。
- 两张同源示意图已嵌入正式论文 DOCX、8 页 A4 PDF 与 7 页学术 PPTX。PDF 使用开放许可 Noto Sans SC 嵌入字体并附带原始 PNG/JSON，经 PDFium 生成 8 张 1191×1684 QA PNG；PPTX 由 `pptxforge` 学术主路径生成，并经 PowerPoint 原生导出 7 张 1920×1080 PNG。
- 修复正式 PPT 长中文封面标题在 `pptxforge` hero 区域溢出后降级的问题：主路径按稳定断点插入两行标题；科研资产页写入标准 `[Sources]` speaker notes。
- `resvg_py==0.3.3` 已在 Windows 项目 venv 和一次性 `python:3.13-slim` 容器验证；容器输出有效 PNG 签名 `89504e470d0a1a0a`，测试容器与临时镜像已删除。
- 定向测试 81 passed；最终全量后端 1215 passed；Alembic upgrade head、前端 lint、前端 build 全部通过。
- 工具限制：`slides_test.py` 在中文用户名路径下仍触发工具自身 JSON 反斜杠解析错误；Windows ACL helper 间歇故障也阻断了应用内截图查看。替代门禁为 PowerPoint 原生逐页导出、PDFium 逐页渲染、PPTX/DOCX 重开、页数/尺寸/媒体/notes/附件和 SHA-256 结构检查。

本 SPEC 已达到“实现与本地验收完成”，但按项目阶段闸，仍需项目负责人查看样例并确认视觉效果后才能标记正式收口。