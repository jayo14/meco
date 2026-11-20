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
    solana_ws_url: str | None = None
    pumpportal_ws_url: str = "wss://pumpportal.fun/api/data"

    enable_pumpportal_discovery: bool = True
    enable_solana_rpc_discovery: bool = True

    discovery_ws_heartbeat_interval: float = 30.0
    discovery_reconnect_min_delay: float = 1.0
    discovery_reconnect_max_delay: float = 60.0

    # Social Intelligence settings
    x_api_bearer_token: str | None = None
    enable_x_social: bool = False
    enable_rss_social: bool = True
    enable_telegram_social: bool = True
    rss_feeds: str = (
        "https://cointelegraph.com/rss,"
        "https://www.coindesk.com/arc/outboundfeeds/rss/,"
        "https://decrypt.co/feed"
    )
    social_poll_interval: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def resolved_solana_ws_url(self) -> str:
        if self.solana_ws_url and self.solana_ws_url.strip():
            return self.solana_ws_url.strip()
        rpc = self.solana_rpc_url.strip()
        if rpc.startswith("https://"):
            return "wss://" + rpc[8:]
        if rpc.startswith("http://"):
            return "ws://" + rpc[7:]
        return "wss://api.mainnet-beta.solana.com"

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
