from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "memescout"
    app_env: str = "development"
    log_level: str = "INFO"

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_name: str = "memescout"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/memescout"
    )

    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
