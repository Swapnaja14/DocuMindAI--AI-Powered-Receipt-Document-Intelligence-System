import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is loaded into environment variables
load_dotenv()


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "documind"

    jwt_secret_key: str = "default_secret_key_change_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    upload_dir: str = "storage/uploads"
    max_file_size_mb: int = 10
    max_user_storage_mb: int = 50
    max_user_documents: int = 100

    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_seconds: int = 600
    redis_enabled: bool = True
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    faiss_index_path: str = "storage/faiss/index.faiss"

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.5-flash-lite"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")

    def model_post_init(self, __context) -> None:
        if self.is_production:
            if self.debug:
                # Force debug mode off in production
                self.debug = False
            if self.jwt_secret_key == "default_secret_key_change_in_production":
                import warnings
                warnings.warn(
                    "SECURITY WARNING: Production environment detected with default JWT_SECRET_KEY! "
                    "Configure a strong secret via JWT_SECRET_KEY environment variable.",
                    UserWarning,
                    stacklevel=2,
                )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
