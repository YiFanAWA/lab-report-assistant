# 决策 0018：引入 Vitest + React Testing Library 前端测试框架

## 状态

已接受。

## 日期

2026-07-23

## 决策人

项目负责人。

## 背景

SPEC 0005 前端接线完成后，前端项目新增了 `ExecutionWorkspaceView` 及其 11 个 API 端点（7 code_tasks + 4 execution_runs），代码量约 1150 行。但前端项目此前没有任何测试框架配置：

- `package.json` 无 `test` 脚本
- `devDependencies` 无 jest、vitest、@testing-library 等测试依赖
- 无测试配置文件（jest.config / vitest.config）
- 无测试文件（无 `.test.ts` / `.test.tsx`）
- 无 setupTests 文件

根据 `AGENTS.md` 验收规则"声明完成前必须有本轮实际运行过的证据"，以及"后端业务合同变化必须有服务层或 API 层测试"的延伸要求，前端新增大量 API 接线和交互逻辑后，缺少自动化测试会导致回归风险不可控，只能依赖手动浏览器验收，效率低且覆盖不全。

为建立前端测试基线，需要引入前端测试框架，为 11 个 API 端点和 ExecutionWorkspaceView 组件补充单元测试。

## 决策

引入 **Vitest + React Testing Library** 作为前端测试框架，而非 Jest + RTL。

### 选择 Vitest 的理由

1. **Vite 原生集成**：项目已使用 Vite 6.4.3 作为构建工具，Vitest 是 Vite 官方测试框架，零额外配置即可复用 `vite.config.ts` 的模块解析和 TypeScript 支持。
2. **API 兼容 Jest**：`describe`/`it`/`expect`/`vi.mock` 等 API 与 Jest 一致，降低学习成本，后续如需迁移到 Jest 改动极小。
3. **ESM 原生支持**：项目 `package.json` 声明 `"type": "module"`，Vitest 原生支持 ESM，而 Jest 需要额外配置 babel-jest 或 ts-jest 处理 ESM。
4. **依赖体积小**：Vitest 不需要 jest-environment-jsdom + babel-jest + ts-jest 等中间层，传递依赖更少。

### 新增 devDependencies

| 依赖 | 安装版本 | 用途 |
| --- | --- | --- |
| `vitest` | 4.1.10 | 测试框架核心 |
| `@testing-library/react` | ^16.0.0 | React 组件 DOM 测试 |
| `@testing-library/jest-dom` | ^6.0.0 | jest-dom matchers（toBeInTheDocument 等） |
| `@testing-library/user-event` | ^14.0.0 | 用户交互模拟 |
| `jsdom` | ^25.0.0 | 浏览器环境模拟 |

### 新增配置文件

- `apps/web/vitest.config.ts`：jsdom 环境 + globals + setupFiles
- `apps/web/src/setupTests.ts`：jest-dom matchers + afterEach cleanup
- `apps/web/package.json`：新增 `test`（vitest run）和 `test:watch`（vitest）脚本

## 范围边界

本决策引入：

- 5 个 devDependencies（vitest + RTL 三件套 + jsdom）
- 2 个配置文件（vitest.config.ts + setupTests.ts）
- 2 个测试文件（api.test.ts 20 个测试 + ExecutionWorkspaceView.test.tsx 17 个测试）
- 37 个单元测试，覆盖 11 个 API 函数和 ExecutionWorkspaceView 组件核心渲染路径

本决策明确不做：

- 不引入 E2E 测试框架（Playwright/Cypress），V1.0 端到端验收继续依赖手动浏览器验收和后端 Worker E2E 脚本。
- 不要求 100% 覆盖率，V1.0 聚焦 API 函数正确性和核心组件渲染路径。
- 不为所有历史组件补充测试（requirements/sources/evidence/datasets/analysis/outlines），后续按需补充。
- 不引入 CI 集成，V1.0 为本地单用户 MVP，测试在本地运行。

## 关键技术决策

1. **Vitest 而非 Jest**：与 Vite 项目原生集成，ESM 原生支持，配置量最小。详见上文"选择 Vitest 的理由"。

2. **jsdom 而非 happy-dom**：jsdom 生态更成熟，@testing-library/react 官方文档以 jsdom 为主，兼容性更可靠。happy-dom 性能更好但偶有边界 case 不兼容。

3. **`vi.mock` 模块路径与组件 import 路径一致**：测试文件在 `src/routes/__tests__/` 下，mock 路径使用 `../../features/xxx/hooks`，与 `ExecutionWorkspaceView.tsx` 中的实际 import 路径一致，确保 mock 生效。

4. **`getAllByText` 处理重复文本**：项目状态中文映射（如"失败"出现在项目状态和执行记录状态中）会导致 `getByText` 抛出"Found multiple elements"错误，使用 `getAllByText` 或改用更精确的按钮查询。

5. **`cleanup` 在 `afterEach` 自动执行**：避免测试间 DOM 残留，通过 setupTests.ts 全局配置。

## 验收证据

完成本决策后已满足：

- `npm.cmd run test`：37 个测试全部通过（api 20 + 组件 17）
- `npm.cmd run lint`：tsc --noEmit 类型检查通过
- `npm.cmd run build`：Vite 构建通过，113 模块，389.56 kB
- 测试覆盖：11 个 API 函数的 URL/method/body/响应解析/错误处理 + 组件渲染/状态门控/按钮启用禁用

## 依赖影响

本决策新增 5 个 devDependencies，均为开发依赖，不影响生产构建产物体积。传递依赖共 85 个包，已记录在 `dependency-review.md` §4 前端依赖复核表。

真实 DeepSeek 调用继续推迟到后续切片，本决策不涉及后端依赖变化。

## 约束

- 不把测试框架引入误解为 V1 完成的前置条件；V1.0 的核心验收标准仍是端到端流程跑通。
- 不为通过测试而简化组件逻辑或删除边界 case 处理。
- 不引入快照测试（snapshot testing），V1.0 聚焦行为测试而非 UI 快照。
- 不把测试覆盖率作为唯一质量指标，手动浏览器验收仍不可替代。
- 后续新增前端组件时，应同步补充对应 API 和组件测试，避免测试债务积累。
