"""应用配置。

从环境变量或 .env 文件读取，提供默认值。不写入真实密钥。
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # server/


class Settings:
    @property
    def app_env(self) -> str:
        return os.getenv("APP_ENV", "local")

    @property
    def database_url(self) -> str:
        # 默认使用项目本地路径；沙箱文件系统若不支持 SQLite（Windows 挂载限制），
        # 可通过环境变量 DATABASE_URL 指向 /tmp 或其它可写位置。
        default_path = PROJECT_ROOT / "data" / "db" / "app.db"
        return os.getenv("DATABASE_URL", f"sqlite:///{default_path}")

    @property
    def project_data_root(self) -> Path:
        raw = os.getenv("PROJECT_DATA_ROOT", str(PROJECT_ROOT / "data" / "projects"))
        return Path(raw)

    @property
    def llm_provider(self) -> str:
        return os.getenv("LLM_PROVIDER", "deepseek")

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL", "deepseek-v4-pro")

    @property
    def requirement_draft_provider(self) -> str:
        return os.getenv("REQUIREMENT_DRAFT_PROVIDER", "local_rule")

    @property
    def deepseek_api_key(self) -> str:
        return os.getenv("DEEPSEEK_API_KEY", "")

    @property
    def source_fetch_timeout_seconds(self) -> int:
        raw = os.getenv("SOURCE_FETCH_TIMEOUT_SECONDS", "30")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 30

    @property
    def source_fetch_max_size_bytes(self) -> int:
        raw = os.getenv("SOURCE_FETCH_MAX_SIZE_BYTES", str(10 * 1024 * 1024))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 10 * 1024 * 1024

    @property
    def job_max_retries(self) -> int:
        raw = os.getenv("JOB_MAX_RETRIES", "2")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 2

    @property
    def job_retry_backoff_seconds(self) -> int:
        raw = os.getenv("JOB_RETRY_BACKOFF_SECONDS", "5")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 5

    @property
    def worker_poll_interval_seconds(self) -> float:
        raw = os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 1.0

    @property
    def evidence_card_provider(self) -> str:
        return os.getenv("EVIDENCE_CARD_PROVIDER", "local_rule")

    @property
    def dataset_max_size_bytes(self) -> int:
        raw = os.getenv("DATASET_MAX_SIZE_BYTES", str(50 * 1024 * 1024))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 50 * 1024 * 1024

    @property
    def analysis_plan_provider(self) -> str:
        return os.getenv("ANALYSIS_PLAN_PROVIDER", "local_rule")

    @property
    def code_task_provider(self) -> str:
        return os.getenv("CODE_TASK_PROVIDER", "local_rule")

    @property
    def execution_timeout_seconds(self) -> int:
        raw = os.getenv("EXECUTION_TIMEOUT_SECONDS", "30")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 30

    @property
    def execution_memory_limit_mb(self) -> int:
        raw = os.getenv("EXECUTION_MEMORY_LIMIT_MB", "1024")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 1024

    @property
    def execution_output_max_bytes(self) -> int:
        raw = os.getenv("EXECUTION_OUTPUT_MAX_BYTES", str(10 * 1024 * 1024))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 10 * 1024 * 1024

    @property
    def outline_provider(self) -> str:
        return os.getenv("OUTLINE_PROVIDER", "local_rule")

    @property
    def word_template_path(self) -> str:
        """Word 模板路径（可选，留空使用默认模板）。"""
        return os.getenv("WORD_TEMPLATE_PATH", "")

    @property
    def ppt_template_path(self) -> str:
        """PPT 母版路径（可选，留空使用默认母版）。"""
        return os.getenv("PPT_TEMPLATE_PATH", "")

    @property
    def deliverable_max_size_bytes(self) -> int:
        """交付物文件大小上限（默认 50MB）。"""
        raw = os.getenv("DELIVERABLE_MAX_SIZE_BYTES", str(50 * 1024 * 1024))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 50 * 1024 * 1024


settings = Settings()
