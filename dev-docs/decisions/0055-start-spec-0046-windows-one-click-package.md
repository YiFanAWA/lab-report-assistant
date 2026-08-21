# 决策 0055：启动 SPEC 0046 Windows 一键运行封装

## 状态

已确认进入实现；本轮实现与验收材料已形成，待项目负责人确认版本收口。

## 背景

项目负责人希望把本地 Web MVP 封装成用户可直接下载、解压并双击运行的 Windows EXE。用户运行端不应要求 Docker、Python、Node.js、虚拟环境、命令行或手工 .env 配置；开发机仍可以保留现有前端构建、Python 测试和 Docker 开发入口。

## 决策

1. 采用 Windows x64 portable bundle，不在本切片引入安装器、代码签名、自动更新、macOS/Linux 包或原生重写前端。
2. 根目录唯一用户入口为 实验报告助手.exe。它只拥有进程编排、路径映射、健康检查、浏览器打开和退出清理语义，不拥有项目、实验、分析、LLM 或交付物业务语义。
3. 使用 PyInstaller 生成 one-file 启动器和 one-directory 服务运行时。服务目录同时承载后端、Worker、Alembic 迁移资源、科学计算依赖和 sandbox_runner.exe；生产前端由 web/ 静态目录提供。
4. 启动器把 SQLite、项目文件、日志和交付物放到 %LOCALAPPDATA%\\LabReportAssistant，服务只绑定 127.0.0.1，默认端口从 8787 开始自动选择。
5. 运行包默认使用本地规则提供者，不在发布物内放入 DeepSeek 或其他外部模型密钥。外部模型设置作为后续用户设置切片处理。
6. PyInstaller 仅作为构建期依赖，版本约束放在 packaging/windows/requirements-build.txt，不把 PyInstaller 混入应用运行时依赖合同。

## 实现 owner

- 构建与发布编排：packaging/windows/build_windows_bundle.py
- 用户可见启动与退出：packaging/windows/launcher_entry.py
- 打包服务入口、迁移、Worker 和沙箱转接：packaging/windows/service_entry.py
- 前端 SPA 静态回退：server/app/infrastructure/packaging/static_files.py
- 启动器源合同测试：server/tests/test_spec0046_windows_packaging.py

## 已完成的证据

- 前端 tsc -b && vite build 通过。
- PyInstaller 6.22.2 服务包与根目录启动器构建通过；服务和启动器均携带当前 Conda 基座所需 DLL。
- 便携服务黑盒验证通过：Alembic 0001~0007 迁移完成，/health、根首页和 SPA 路由均返回 200，Worker 可启动并由测试回收。
- 根目录 EXE 黑盒验证通过：one-file 外层/内层进程启动，健康端点返回 200，实际运行窗口可发现，发送关闭消息后内外层进程退出，服务进程残留数为 0。
- 新增启动器合同测试 4 passed。

## 未闭合风险

- 当前环境不是一台全新 Windows x64 机器，无法在本轮提供“宿主机完全没有 Python、Node.js、Docker”的独立实机证据；现有证据是发布目录直接运行和打包日志。
- 根目录 one-file 外层进程退出码 1 已定位并修复：浏览器打开失败不再阻断服务，生命周期窗口改用系统 STATIC 类和显式消息循环；正式 EXE 验收退出码为 0。
- 未签名 EXE 可能触发 Windows Defender 或 SmartScreen 提示；不作为本切片技术阻断，但发布说明必须保留提示。

## 收口条件

当前仍需项目负责人确认是否接受“未在独立无开发运行时 Windows x64 主机实测”的环境边界；确认后再执行精确 stage、中文 commit 和远程 push。构建输出位于 server/.tmp/windows-package/，必须留在 Git 之外。
