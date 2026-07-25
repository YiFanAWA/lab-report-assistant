# 决策 0022：启动 SPEC 0016 技术债务清理切片

> **日期：** 2026-07-25  
> **状态：** 已确认并完成收口  
> **决策人：** 项目负责人

## 背景

V1.2.0 发布后，`dev-docs/tech-debt-inventory.md` 登记 4 个可记录债务（TD-004/005/006/008），均为文档准确性、依赖声明或脚本输出问题，不影响主链路功能，但需在后续切片中清理：

- **TD-004**：科学计算包未声明在 `pyproject.toml`，Docker 化时通过 Dockerfile 硬编码弥补。
- **TD-005**：AGENTS.md "当前已知非阻断债务"章节仍记载"未暴露 Browser 工具"过时表述。
- **TD-006**：acceptance.md 各 SPEC 收口记录"可视化点击验收：未执行"与 V1.0 整体验收已补做浏览器验收的状态不一致。
- **TD-008**：`worker_e2e_verify.py` 硬编码日志标题为"V1.0"，每次回归测试需手动修正。

## 决策

1. 启动 SPEC 0016 技术债务清理切片，清理上述 4 个债务。
2. 切片范围限定为基础设施（pyproject.toml + Dockerfile）、文档（AGENTS.md + acceptance.md + dependency-review.md + README.md）、脚本（worker_e2e_verify.py），不触碰业务代码、API 合同、数据库。
3. 科学计算包作为 `[project.optional-dependencies] analysis` 声明，而非主 `dependencies`（应用代码不直接导入，是分析依赖）。
4. 不修改 AGENTS.md 规则条款，只更新"当前已知非阻断债务"事实清单。
5. 不回溯修改各 SPEC 收口记录，只在 acceptance.md 顶部新增浏览器验收状态说明。
6. `worker_e2e_verify.py` 默认值保持 "V1.0" 向后兼容，新增 `--version` 和 `--output` 参数。
7. 发布为 v1.3.0。

## 理由

- 4 个债务均为可记录债务，不影响主链路，但累积会让后续 agent 误判项目状态。
- TD-004 与 SPEC 0013 Docker 化紧密相关，Dockerfile 硬编码是临时弥补，应在债务清理切片中正式声明依赖。
- TD-005/006 涉及 AGENTS.md 和 acceptance.md 的文档准确性，保留过时表述会让后续 agent 误以为浏览器验收从未做。
- TD-008 是 TD-004/005/006 清理时的附带修复，避免后续回归测试继续手动修正日志标题。

## 影响范围

- `server/pyproject.toml`：新增 `[project.optional-dependencies] analysis` 段。
- `server/Dockerfile`：改用 `pip install -e ".[dev,analysis]"`。
- `server/worker_e2e_verify.py`：新增 `parse_args()` 函数，支持 `--version` 和 `--output` 参数。
- `server/tests/test_worker_e2e_verify.py`：新增 7 个单元测试。
- `AGENTS.md`：更新"当前已知非阻断债务"章节（仅事实清单，规则条款未变）。
- `dev-docs/acceptance.md`：顶部追加"浏览器验收状态说明"小节。
- `dev-docs/dependency-review.md`：§9.2/9.3 同步更新。
- `dev-docs/tech-debt-inventory.md`：TD-004/005/006/008 移入"已关闭债务"。
- `README.md`：快速启动章节同步 `pip install -e ".[dev,analysis]"`。

## 验收证据

- 后端测试：736 passed, 0 warnings（729 原有 + 7 新增 TD-008 测试）。
- 前端构建：tsc --noEmit 通过，Vite 构建通过（114 模块转换，dist/ 394.96 kB，gzip 107.49 kB）。
- Alembic 迁移：成功（无数据库变更）。
- Docker 镜像构建：成功（exit 0）。
- Docker 容器内科学计算包导入：`import pandas, numpy, scipy, sklearn, matplotlib, psutil` 全部成功。
- `pip install --dry-run -e ".[analysis]"`：analysis 段依赖解析正确，所有包版本已满足。
- AGENTS.md diff：只涉及"当前已知非阻断债务"章节（第 203-204 行），规则条款未变。
- acceptance.md diff：只涉及顶部"当前限制"段落，各 SPEC 收口记录未回溯修改。

## 后续方向

V1.3.0 SPEC 0016 技术债务清理完成后，项目当前无活跃可记录债务。下一阶段方向待项目负责人规划。
