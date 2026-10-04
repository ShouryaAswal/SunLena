from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SunLena API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://sunlena:local_only_change_me@database:5432/sunlena"
    firebase_project_id: str | None = None
    firebase_service_account_path: str | None = "/run/secrets/firebase-admin.json"
    apple_search_country: str = "IN"
    media_root: str = "/var/lib/sunlena/media"
    media_max_file_bytes: int = 157286400
    media_max_user_bytes: int = 524288000
    media_signing_secret: str = "local-only-change-me"
    ytdlp_pot_provider_url: str = "http://bgutil-provider:4416"
    # Containers run with a read-only root filesystem; /tmp is a tmpfs.
    ytdlp_cache_dir: str = "/tmp/yt-dlp-cache"
    media_extractor: Literal["yt-dlp", "cobalt"] = "yt-dlp"
    # YouTube (direct URLs and catalog searches) needs PO tokens that only the
    # yt-dlp + bgutil pipeline supplies; Cobalt returns empty tunnels for many
    # videos without a browser-based session server. Only applies when
    # media_extractor is "cobalt".
    youtube_extractor: Literal["yt-dlp", "cobalt"] = "yt-dlp"
    cobalt_api_base_url: str = "http://cobalt:9000/"
    cobalt_api_token: SecretStr | None = None
    cobalt_auth_scheme: Literal["Api-Key", "Bearer"] = "Api-Key"
    cobalt_request_timeout_seconds: float = 30
    cobalt_download_timeout_seconds: float = 180

    model_config = SettingsConfigDict(
        env_prefix="SUNLENA_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
