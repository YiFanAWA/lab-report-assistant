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
    def deepseek_base_url(self) -> str:
        """DeepSeek API 基础 URL。"""
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @property
    def deepseek_timeout_seconds(self) -> int:
        """DeepSeek HTTP 超时秒数。"""
        raw = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 30

    @property
    def deepseek_max_retries(self) -> int:
        """DeepSeek 最大重试次数（仅对 5xx 和网络超时重试）。"""
        raw = os.getenv("DEEPSEEK_MAX_RETRIES", "2")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 2

    @property
    def deepseek_temperature(self) -> float:
        """DeepSeek 采样温度（默认 0.3，偏稳定）。"""
        raw = os.getenv("DEEPSEEK_TEMPERATURE", "0.3")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.3

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
        """Word 模板路径（可选，留空使用默认模板）。

        注意：全局模板功能推迟到 V2.0。V1.1.0 使用项目级模板上传。
        此环境变量保留但不使用。
        """
        return os.getenv("WORD_TEMPLATE_PATH", "")

    @property
    def word_template_max_size_bytes(self) -> int:
        """Word 模板文件大小上限（默认 5MB）。"""
        raw = os.getenv("WORD_TEMPLATE_MAX_SIZE_BYTES", str(5 * 1024 * 1024))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 5 * 1024 * 1024

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

    @property
    def data_retention_days(self) -> int:
        """数据保留天数（SPEC 0012）。

        - 0（默认）：永久保留，不清理
        - >0：保留 N 天，超过 N 天的项目进入清理列表
        - 负值或非数字：降级到 0（永久保留）
        - 浮点数：截断为整数（与现有 int(raw) 配置模式一致）
        """
        raw = os.getenv("DATA_RETENTION_DAYS", "0")
        try:
            value = int(raw)
            if value < 0:
                return 0
            return value
        except (TypeError, ValueError):
            return 0

    @property
    def llm_cache_enabled(self) -> bool:
        """是否启用 LLM 调用缓存（SPEC 0014）。

        - true：启用（cache 注入 DeepSeekClient）
        - false/空/其他：禁用（默认，行为与 SPEC 0007 一致）
        """
        raw = os.getenv("LLM_CACHE_ENABLED", "false")
        if raw.lower() == "true":
            return True
        if raw.lower() in ("false", ""):
            return False
        # 非法值降级到禁用
        import logging
        logging.getLogger(__name__).warning(
            f"LLM_CACHE_ENABLED 非法值 '{raw}'，降级到 false（禁用）"
        )
        return False

    @property
    def llm_cache_ttl_seconds(self) -> int:
        """缓存有效期秒数（SPEC 0014）。

        - 默认 86400（1 天）
        - 非数字降级到 86400
        - <=0 表示禁用（create_client_from_settings 不创建 cache）
        - 浮点数截断为整数
        """
        raw = os.getenv("LLM_CACHE_TTL_SECONDS", "86400")
        try:
            return int(raw)
        except (TypeError, ValueError):
            import logging
            logging.getLogger(__name__).warning(
                f"LLM_CACHE_TTL_SECONDS 非法值 '{raw}'，降级到 86400"
            )
            return 86400

    @property
    def llm_cache_db_path(self) -> str:
        """缓存 SQLite 文件路径（SPEC 0014）。

        默认 server/data/llm_cache/llm_cache.db，独立于业务数据库。
        空值使用默认路径。
        """
        raw = os.getenv("LLM_CACHE_DB_PATH", "")
        if raw:
            return raw
        return str(PROJECT_ROOT / "data" / "llm_cache" / "llm_cache.db")


settings = Settings()
