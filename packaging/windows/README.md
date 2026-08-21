# Windows 便携包说明

## 用户运行

1. 下载并解压 Windows x64 发布目录。
2. 双击根目录的 实验报告助手.exe。
3. 程序会自动启动本地后端和 Worker，并打开默认浏览器。
4. 运行窗口提供“退出应用”按钮；退出后，本次启动的后台服务会被回收。

用户数据默认保存在 %LOCALAPPDATA%\\LabReportAssistant，日志位于该目录的 logs\\backend.log、logs\\worker.log。发布包不要求用户安装 Python、Node.js、Docker 或执行命令。

当前版本默认使用本地规则提供者；如果要使用 DeepSeek 等外部模型，需要在后续设置功能中配置自己的凭证，发布包不会内置密钥。

## 开发机构建

在已配置项目开发环境的 Windows 机器上执行：

    server\\.venv\\Scripts\\python.exe -m pip install -r packaging\\windows\\requirements-build.txt
    server\\.venv\\Scripts\\python.exe packaging\\windows\\build_windows_bundle.py

构建结果位于 server\\.tmp\\windows-package\\release\\实验报告助手-win-x64。server\\.tmp\\windows-package\\、前端 dist 和本地用户数据都不应提交到 Git。

## 当前边界

- 运行目标：Windows x64。
- 界面：本机默认浏览器中的 React 工作台。
- 发布形式：portable bundle，不是安装器。
- 未签名 EXE 可能触发 Windows Defender 或 SmartScreen 提示。
- 必须在真实干净 Windows x64 机器上继续完成无 Python、Node.js、Docker 前置条件的验收。
