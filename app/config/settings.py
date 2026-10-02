from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "meco"
    app_env: str = "development"
    log_level: str = "INFO"

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_name: str = "meco"
    telegram_channels: str = ""

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/meco"
    )

    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def telegram_channel_ids(self) -> list[int]:
        if not self.telegram_channels.strip():
            return []

        return [
            int(channel.strip())
            for channel in self.telegram_channels.split(",")
            if channel.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
