"""受控 Python 执行环境测试。

覆盖 python_executor 的核心风险面：
- validate_code：import 白名单、动态调用拦截、别名、from import、语法错误
- execute_code：成功执行、产物收集（CSV/PNG）、超时、内存超限、输出过大、
  DATA_PATH/OUTPUT_DIR 注入、脚本失败、禁止 import 在执行时也生效
"""

import time

import pytest

from app.infrastructure.sandbox.python_executor import (
    ArtifactInfo,
    DEFAULT_ALLOWED_IMPORTS,
    ExecutionResult,
    SandboxError,
    execute_code,
    execute_code_safe,
    validate_code,
)


# --- validate_code 测试 ---


class TestValidateCode:
    """AST import 白名单校验测试。"""

    def test_allows_pandas_alias(self):
        """import pandas as pd 别名允许。"""
        validate_code("import pandas as pd\n")

    def test_allows_numpy(self):
        """import numpy 允许。"""
        validate_code("import numpy\n")

    def test_allows_from_scipy_stats(self):
        """from scipy.stats import ttest_ind 允许。"""
        validate_code("from scipy.stats import ttest_ind\n")

    def test_allows_from_sklearn_ensemble(self):
        """from sklearn.ensemble import RandomForestClassifier 允许。"""
        validate_code("from sklearn.ensemble import RandomForestClassifier\n")

    def test_allows_matplotlib_pyplot(self):
        """from matplotlib import pyplot 允许。"""
        validate_code("from matplotlib import pyplot as plt\n")

    def test_allows_multiple_imports(self):
        """多行 import 全部在白名单内允许。"""
        code = (
            "import pandas as pd\n"
            "import numpy as np\n"
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "import matplotlib.pyplot as plt\n"
            "from scipy import stats\n"
            "from sklearn.linear_model import LinearRegression\n"
        )
        validate_code(code)

    def test_rejects_os(self):
        """import os 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import os\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"
        assert "os" in exc_info.value.message

    def test_rejects_subprocess(self):
        """import subprocess 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import subprocess\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_socket(self):
        """import socket 被拒绝（网络禁用核心）。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import socket\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_ssl(self):
        """import ssl 被拒绝（防止绕过 socket 拉黑）。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import ssl\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_http_client(self):
        """from http.client import HTTPConnection 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("from http.client import HTTPConnection\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_urllib(self):
        """import urllib 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import urllib\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_urllib_request(self):
        """from urllib.request import urlopen 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("from urllib.request import urlopen\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_requests(self):
        """import requests 被拒绝。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import requests\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_shutil(self):
        """import shutil 被拒绝。"""
        with pytest.raises(SandboxError):
            validate_code("import shutil\n")

    def test_rejects_ctypes(self):
        """import ctypes 被拒绝。"""
        with pytest.raises(SandboxError):
            validate_code("import ctypes\n")

    def test_rejects_pickle(self):
        """import pickle 被拒绝。"""
        with pytest.raises(SandboxError):
            validate_code("import pickle\n")

    def test_rejects_multiprocessing(self):
        """import multiprocessing 被拒绝。"""
        with pytest.raises(SandboxError):
            validate_code("import multiprocessing\n")

    def test_rejects_dynamic_import_call(self):
        """__import__('os') 动态调用被拦截。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("m = __import__('os')\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"
        assert "__import__" in exc_info.value.message

    def test_rejects_importlib_import_module(self):
        """importlib.import_module('os') 被拦截。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code(
                "import importlib\n"
                "m = importlib.import_module('os')\n"
            )
        # import 本身就会被拒绝（importlib 不在白名单）
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_rejects_syntax_error(self):
        """语法错误归为 EXECUTION_IMPORT_FORBIDDEN。"""
        with pytest.raises(SandboxError) as exc_info:
            validate_code("import pandas as pd\nfor x in\n")
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_allows_empty_code(self):
        """空代码允许通过校验。"""
        validate_code("")

    def test_allows_comment_only(self):
        """纯注释代码允许通过校验。"""
        validate_code("# 这只是注释\n")

    def test_custom_allowed_imports(self):
        """自定义白名单：默认禁止的模块在自定义白名单内时允许。"""
        # 自定义白名单包含 json
        validate_code("import json\n", allowed_imports=["json", "pandas"])

    def test_default_allowed_imports_content(self):
        """默认白名单包含 SPEC 0005 决策确认的 6 个模块。"""
        assert set(DEFAULT_ALLOWED_IMPORTS) == {
            "pandas", "numpy", "matplotlib", "scipy", "sklearn", "openpyxl"
        }


# --- execute_code 成功路径测试 ---


class TestExecuteCodeSuccess:
    """execute_code 成功执行路径测试。"""

    def test_executes_simple_print(self, tmp_path):
        """简单 print 代码成功执行，stdout 被捕获。"""
        work_dir = tmp_path / "run1"
        result = execute_code(
            code="print('hello sandbox')\n",
            work_dir=str(work_dir),
            data_path="/nonexistent/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert "hello sandbox" in result.stdout
        assert result.duration_seconds > 0
        assert result.sandbox_error_code is None

    def test_data_path_variable_injected(self, tmp_path):
        """DATA_PATH 变量被正确注入为字符串字面量。"""
        work_dir = tmp_path / "run2"
        result = execute_code(
            code="print('DATA_PATH=' + DATA_PATH)\n",
            work_dir=str(work_dir),
            data_path="/test/path/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert "DATA_PATH=/test/path/data.csv" in result.stdout

    def test_output_dir_variable_injected(self, tmp_path):
        """OUTPUT_DIR 变量被正确注入为受控工作目录绝对路径。"""
        work_dir = tmp_path / "run3"
        result = execute_code(
            code="print('OUTPUT_DIR=' + OUTPUT_DIR)\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert "OUTPUT_DIR=" in result.stdout
        assert str(work_dir) in result.stdout

    def test_work_dir_auto_created(self, tmp_path):
        """work_dir 不存在时自动创建。"""
        work_dir = tmp_path / "nested" / "deep" / "run4"
        assert not work_dir.exists()
        result = execute_code(
            code="print('ok')\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert work_dir.exists()

    def test_collects_csv_artifact(self, tmp_path):
        """执行生成 CSV 文件后被收集为 TABLE_CSV 产物。"""
        work_dir = tmp_path / "run5"
        code = (
            "import pandas as pd\n"
            "df = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})\n"
            "df.to_csv(OUTPUT_DIR + '/result.csv', index=False)\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=30,
        )
        assert result.exit_code == 0
        csv_artifacts = [a for a in result.artifacts if a.artifact_type == "TABLE_CSV"]
        assert len(csv_artifacts) == 1
        assert csv_artifacts[0].name == "result.csv"
        assert csv_artifacts[0].file_path == "result.csv"
        assert csv_artifacts[0].file_size_bytes > 0

    def test_collects_png_artifact(self, tmp_path):
        """执行生成 PNG 文件后被收集为 CHART_PNG 产物。"""
        work_dir = tmp_path / "run6"
        code = (
            "import matplotlib\n"
            "import matplotlib.pyplot as plt\n"
            "plt.figure()\n"
            "plt.plot([1, 2, 3], [1, 4, 9])\n"
            "plt.title('test')\n"
            "plt.savefig(OUTPUT_DIR + '/chart.png', dpi=80)\n"
            "plt.close()\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=30,
        )
        assert result.exit_code == 0
        png_artifacts = [a for a in result.artifacts if a.artifact_type == "CHART_PNG"]
        assert len(png_artifacts) == 1
        assert png_artifacts[0].name == "chart.png"
        assert png_artifacts[0].file_size_bytes > 0

    def test_artifacts_sorted_by_name(self, tmp_path):
        """多个产物按名称排序返回。"""
        work_dir = tmp_path / "run7"
        code = (
            "import pandas as pd\n"
            "pd.DataFrame({'a': [1]}).to_csv(OUTPUT_DIR + '/zzz.csv', index=False)\n"
            "pd.DataFrame({'b': [2]}).to_csv(OUTPUT_DIR + '/aaa.csv', index=False)\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=30,
        )
        assert result.exit_code == 0
        names = [a.name for a in result.artifacts]
        assert names == ["aaa.csv", "zzz.csv"]

    def test_script_file_cleaned_up(self, tmp_path):
        """执行完成后临时脚本 _run.py 被清理。"""
        work_dir = tmp_path / "run8"
        execute_code(
            code="print('done')\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        # _run.py 应该被清理（用户产物保留）
        assert not (work_dir / "_run.py").exists()

    def test_reads_csv_data_path(self, tmp_path):
        """DATA_PATH 指向真实 CSV 文件时用户代码可读取。"""
        import csv
        data_file = tmp_path / "sample.csv"
        with open(data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "age"])
            writer.writerow(["alice", "30"])
            writer.writerow(["bob", "25"])

        work_dir = tmp_path / "run9"
        code = (
            "import pandas as pd\n"
            "df = pd.read_csv(DATA_PATH)\n"
            "print('rows=' + str(len(df)))\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path=str(data_file),
            timeout_seconds=30,
        )
        assert result.exit_code == 0
        assert "rows=2" in result.stdout


# --- execute_code 失败路径测试 ---


class TestExecuteCodeFailures:
    """execute_code 失败路径测试。"""

    def test_script_exception_captured(self, tmp_path):
        """脚本抛异常时 exit_code != 0，stderr 包含堆栈。"""
        work_dir = tmp_path / "fail1"
        result = execute_code(
            code="raise ValueError('boom')\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code != 0
        assert "ValueError" in result.stderr or "boom" in result.stderr
        assert result.sandbox_error_code is None  # 非沙箱限制错误

    def test_import_forbidden_raises_before_execution(self, tmp_path):
        """禁止 import 在执行前抛 SandboxError，不创建 ExecutionRun。"""
        work_dir = tmp_path / "fail2"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                code="import os\nprint(os.getcwd())\n",
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=10,
            )
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_socket_import_rejected(self, tmp_path):
        """import socket 被拒绝，无法创建网络连接。"""
        work_dir = tmp_path / "fail3"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                code="import socket\ns = socket.socket()\n",
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=10,
            )
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_requests_import_rejected(self, tmp_path):
        """import requests 被拒绝。"""
        work_dir = tmp_path / "fail4"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                code="import requests\nrequests.get('http://example.com')\n",
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=10,
            )
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_dynamic_import_rejected(self, tmp_path):
        """__import__('os') 动态调用被拦截。"""
        work_dir = tmp_path / "fail5"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                code="m = __import__('os')\nprint(m.getcwd())\n",
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=10,
            )
        assert exc_info.value.code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_timeout_raises(self, tmp_path):
        """死循环代码超过 timeout_seconds 抛 EXECUTION_TIMEOUT。"""
        work_dir = tmp_path / "fail6"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                code="while True:\n    pass\n",
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=2,  # 短超时加速测试
            )
        assert exc_info.value.code == "EXECUTION_TIMEOUT"

    def test_memory_limit_raises(self, tmp_path):
        """持续分配内存超过限制抛 EXECUTION_MEMORY_LIMIT。

        用持续分配而非一次性分配（[0]*100M 分配太快可能错过 0.5s 轮询窗口）。
        """
        work_dir = tmp_path / "fail7"
        with pytest.raises(SandboxError) as exc_info:
            execute_code(
                # 持续分配 ~8MB chunks 直到超限
                code=(
                    "chunks = []\n"
                    "while True:\n"
                    "    chunks.append([0] * 1000000)\n"
                ),
                work_dir=str(work_dir),
                data_path="/test/data.csv",
                timeout_seconds=15,
                memory_limit_mb=80,  # 80MB，让 Python 启动后分配超限
            )
        assert exc_info.value.code == "EXECUTION_MEMORY_LIMIT"

    def test_output_too_large_marked(self, tmp_path):
        """输出超过 output_max_bytes 时标记 EXECUTION_OUTPUT_TOO_LARGE。"""
        work_dir = tmp_path / "fail8"
        result = execute_code(
            code="print('x' * 5000)\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
            output_max_bytes=1024,  # 1KB 限制
        )
        # 不抛异常，返回带标记的结果
        assert result.sandbox_error_code == "EXECUTION_OUTPUT_TOO_LARGE"
        assert len(result.stdout.encode("utf-8")) <= 1024

    def test_failed_script_still_collects_artifacts(self, tmp_path):
        """脚本执行失败但已生成的产物仍被收集。"""
        work_dir = tmp_path / "fail9"
        code = (
            "import pandas as pd\n"
            "pd.DataFrame({'a': [1, 2]}).to_csv(OUTPUT_DIR + '/partial.csv', index=False)\n"
            "raise RuntimeError('after artifact')\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=30,
        )
        assert result.exit_code != 0
        assert "RuntimeError" in result.stderr or "after artifact" in result.stderr
        # 产物仍被收集
        csv_artifacts = [a for a in result.artifacts if a.artifact_type == "TABLE_CSV"]
        assert len(csv_artifacts) == 1
        assert csv_artifacts[0].name == "partial.csv"


# --- execute_code_safe 测试 ---


class TestExecuteCodeSafe:
    """execute_code_safe 将 SandboxError 转换为 ExecutionResult 测试。"""

    def test_success_returns_result(self, tmp_path):
        """成功执行返回正常 ExecutionResult。"""
        work_dir = tmp_path / "safe1"
        result = execute_code_safe(
            code="print('ok')\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert "ok" in result.stdout
        assert result.sandbox_error_code is None

    def test_import_forbidden_returns_error_result(self, tmp_path):
        """禁止 import 时返回带错误码的 ExecutionResult，不抛异常。"""
        work_dir = tmp_path / "safe2"
        result = execute_code_safe(
            code="import os\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=10,
        )
        assert result.exit_code == -1
        assert result.sandbox_error_code == "EXECUTION_IMPORT_FORBIDDEN"
        assert "EXECUTION_IMPORT_FORBIDDEN" in result.stderr

    def test_timeout_returns_error_result(self, tmp_path):
        """超时返回带错误码的 ExecutionResult。"""
        work_dir = tmp_path / "safe3"
        result = execute_code_safe(
            code="while True:\n    pass\n",
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=2,
        )
        assert result.exit_code == -1
        assert result.sandbox_error_code == "EXECUTION_TIMEOUT"

    def test_memory_limit_returns_error_result(self, tmp_path):
        """内存超限返回带错误码的 ExecutionResult。"""
        work_dir = tmp_path / "safe4"
        result = execute_code_safe(
            code=(
                "chunks = []\n"
                "while True:\n"
                "    chunks.append([0] * 1000000)\n"
            ),
            work_dir=str(work_dir),
            data_path="/test/data.csv",
            timeout_seconds=15,
            memory_limit_mb=80,
        )
        assert result.exit_code == -1
        assert result.sandbox_error_code == "EXECUTION_MEMORY_LIMIT"


# --- 集成测试 ---


class TestExecuteCodeIntegration:
    """execute_code 集成测试：覆盖完整数据分析流程。"""

    def test_full_pandas_analysis_flow(self, tmp_path):
        """完整 pandas 数据分析流程：读取、清洗、统计、保存产物。"""
        import csv
        data_file = tmp_path / "gastric.csv"
        with open(data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["age", "sex", "diagnosis"])
            writer.writerow(["45", "M", "gastritis"])
            writer.writerow(["60", "F", "ulcer"])
            writer.writerow(["55", "M", "gastritis"])
            writer.writerow(["70", "F", "normal"])

        work_dir = tmp_path / "integration1"
        code = (
            "import pandas as pd\n"
            "df = pd.read_csv(DATA_PATH)\n"
            "df['age'] = df['age'].astype(int)\n"
            "stats = df.groupby('diagnosis')['age'].agg(['mean', 'count'])\n"
            "stats.to_csv(OUTPUT_DIR + '/group_stats.csv')\n"
            "print('groups=' + str(len(stats)))\n"
        )
        result = execute_code(
            code=code,
            work_dir=str(work_dir),
            data_path=str(data_file),
            timeout_seconds=60,
        )
        assert result.exit_code == 0
        assert "groups=3" in result.stdout
        csv_artifacts = [a for a in result.artifacts if a.artifact_type == "TABLE_CSV"]
        assert len(csv_artifacts) == 1
        assert csv_artifacts[0].name == "group_stats.csv"
