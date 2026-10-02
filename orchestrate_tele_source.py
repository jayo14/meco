import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update .env.example
if os.path.exists(".env.example"):
    with open(".env.example", "a") as f:
        f.write("\nTELEGRAM_CHANNELS=\n")
    run_cmd("Add TELEGRAM_CHANNELS to env example")

# 2. Update app/config/settings.py
settings_content = """from functools import lru_cache

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
"""
with open("app/config/settings.py", "w") as f:
    f.write(settings_content)
run_cmd("Add telegram channels filtering configuration")

# 3. Update app/database/models.py
with open("app/database/models.py", "r") as f:
    models_content = f.read()

models_target = """    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )"""
models_replacement = models_target + """

    source_name: Mapped[str | None] = mapped_column(String(255))
    source_username: Mapped[str | None] = mapped_column(String(255))"""
models_content = models_content.replace(models_target, models_replacement)
with open("app/database/models.py", "w") as f:
    f.write(models_content)
run_cmd("Add source_name and source_username to signals table")

# 5. Update app/database/repository.py
repo_content = """from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.market.models import MarketSnapshot
from app.telegram.parser import TokenSignal
from app.solana.validator import MintInfo


async def save_signal(
    session: AsyncSession,
    signal: TokenSignal,
    mint_info: MintInfo,
    snapshot: MarketSnapshot,
    *,
    source_name: str | None,
    source_username: str | None,
) -> Signal:
    record = Signal(
        chat_id=signal.chat_id,
        message_id=signal.message_id,
        message_text=signal.message_text,
        detected_at=signal.detected_at,

        source_name=source_name,
        source_username=source_username,

        token_address=signal.token_address,
        slippage=signal.slippage,

        decimals=mint_info.decimals,
        supply=mint_info.supply,

        pair_address=snapshot.pair_address,
        dex_id=snapshot.dex_id,
        price_usd=snapshot.price_usd,
        liquidity_usd=snapshot.liquidity_usd,
        volume_5m=snapshot.volume_5m,
        buys_5m=snapshot.buys_5m,
        sells_5m=snapshot.sells_5m,

        observed_at=datetime.now(timezone.utc),
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record
"""
with open("app/database/repository.py", "w") as f:
    f.write(repo_content)
run_cmd("Support saving Telegram source data in signal repository")

# 6, 7, 8. Update app/telegram/client.py
with open("app/telegram/client.py", "r") as f:
    client_content = f.read()

# First replace handle_new_message start to add chat fetching and filtering
old_handle_start = """    message = event.message

    if not message.text:
        return

    logger.info(
        "New Telegram message | chat_id=%s | message_id=%s",
        event.chat_id,
        message.id,
    )"""

new_handle_start = """    message = event.message

    if not message.text:
        return

    if (
        settings.telegram_channel_ids
        and event.chat_id not in settings.telegram_channel_ids
    ):
        return

    chat = await event.get_chat()
    source_name = getattr(chat, "title", None)
    source_username = getattr(chat, "username", None)

    logger.info(
        "New Telegram message | source=%s | username=%s | "
        "chat_id=%s | message_id=%s",
        source_name,
        source_username,
        event.chat_id,
        message.id,
    )"""
client_content = client_content.replace(old_handle_start, new_handle_start)

# Next, update save_signal call
old_save = """    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=snapshot,
        )"""

new_save = """    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=snapshot,
            source_name=source_name,
            source_username=source_username,
        )"""
client_content = client_content.replace(old_save, new_save)
with open("app/telegram/client.py", "w") as f:
    f.write(client_content)
run_cmd("Extract and persist Telegram source metadata")

# 9. Create scripts/list_telegram_chats.py
script_content = """import asyncio
import logging

from telethon import TelegramClient

from app.config.settings import get_settings


logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)


async def main() -> None:
    settings = get_settings()

    client = TelegramClient(
        settings.telegram_session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.start()

    print("\\n=== TELEGRAM CHATS ===\\n")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        print(
            f"name={dialog.name!r} | "
            f"chat_id={dialog.id} | "
            f"username={getattr(entity, 'username', None)!r}"
        )

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
"""
with open("scripts/list_telegram_chats.py", "w") as f:
    f.write(script_content)
run_cmd("Create script to list telegram chat IDs")

