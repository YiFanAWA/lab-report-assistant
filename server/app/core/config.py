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


settings = Settings()
