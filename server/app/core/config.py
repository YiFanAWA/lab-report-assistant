"""应用配置。

从环境变量或 .env 文件读取，提供默认值。不写入真实密钥。
数据库路径基于稳定根目录，不依赖工作目录。
"""

import os
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # server/

logger = logging.getLogger(__name__)


class Settings:
    @property
    def app_env(self) -> str:
        return os.getenv("APP_ENV", "local")

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", _default_database_url())

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
    def evidence_draft_provider(self) -> str:
        return os.getenv("EVIDENCE_DRAFT_PROVIDER", "local_rule")

    @property
    def source_fetch_timeout_seconds(self) -> int:
        return int(os.getenv("SOURCE_FETCH_TIMEOUT_SECONDS", "15"))

    @property
    def source_fetch_max_bytes(self) -> int:
        return int(os.getenv("SOURCE_FETCH_MAX_BYTES", "20971520"))

    @property
    def source_upload_max_bytes(self) -> int:
        return int(os.getenv("SOURCE_UPLOAD_MAX_BYTES", "20971520"))

    @property
    def deepseek_api_key(self) -> str:
        return os.getenv("DEEPSEEK_API_KEY", "")


def _default_database_url() -> str:
    """生成基于稳定根目录的默认 SQLite URL，自动创建父目录。"""
    default_path = PROJECT_ROOT / "data" / "db" / "app.db"
    parent = default_path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    logger.info("默认数据库路径: %s", default_path)
    return f"sqlite:///{default_path}"


settings = Settings()
