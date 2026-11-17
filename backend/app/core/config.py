"""全局配置：pydantic-settings 读 .env（规格 §2.3 键表）。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    kb_env: str = "dev"
    kb_secret_key: str = ""  # 必填，启动时校验
    kb_admin_username: str = "admin"
    kb_admin_password: str = "admin123"
    kb_data_dir: Path = Path("./data")
    embedding_base_url: str = "http://localhost:11434/v1"
    embedding_model: str = "bge-m3"
    kb_max_upload_mb: int = 100
    kb_max_upload_files: int = 20
    kb_cors_origin: str = "http://localhost:5201"

    # 云端 GLM 预填（可选；推荐在设置页配置，key 加密落库）
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_api_key: str = ""
    glm_model: str = "glm-4.6"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "kb.sqlite3"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def data_dir(self) -> Path:
        return self.kb_data_dir

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "storage"

    @property
    def reports_dir(self) -> Path:
        # data/ 位于仓库根时，reports_output 与其同级（规格 §2.1）
        return self.data_dir.parent / "reports_output"

    @property
    def podcasts_dir(self) -> Path:
        # 音频属于用户数据，随 data/ 一起存放
        return self.data_dir / "podcasts"

    @property
    def is_dev(self) -> bool:
        return self.kb_env == "dev"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.kb_secret_key:
        raise RuntimeError(
            "KB_SECRET_KEY 未配置：请复制 backend/.env.example 为 .env 并填写 "
            '(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")'
        )
    return s
