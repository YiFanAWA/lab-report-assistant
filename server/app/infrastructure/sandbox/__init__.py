"""受控执行环境基础设施。

提供受控 Python 代码执行能力：
- AST import 白名单校验
- subprocess + 临时脚本执行（禁止 shell=True）
- 限时、限内存（psutil 软监控）、限输出大小
- 产物收集（CSV 和 PNG）

执行环境由 SPEC 0005 定义，业务语义由 server/app/modules/execution/ 拥有。
本模块只做基础设施适配，不持有业务状态。
"""
