from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SunLena API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://sunlena:local_only_change_me@database:5432/sunlena"
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = "/run/secrets/firebase-admin.json"
    apple_search_country: str = "IN"

    model_config = SettingsConfigDict(
        env_prefix="SUNLENA_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
