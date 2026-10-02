import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update app/database/repository.py
content_repo = """from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.market.models import MarketSnapshot
from app.solana.validator import MintInfo
from app.telegram.parser import TokenSignal


async def create_signal(
    session: AsyncSession,
    *,
    signal: TokenSignal,
    source_name: str | None,
    source_username: str | None,
) -> Signal:
    saved_signal = Signal(
        chat_id=signal.chat_id,
        message_id=signal.message_id,
        message_text=signal.message_text,

        message_created_at=signal.message_created_at,
        received_at=signal.received_at,

        source_name=source_name,
        source_username=source_username,

        token_address=signal.token_address,
        slippage=signal.slippage,

        market_status="pending",
    )

    session.add(saved_signal)

    await session.commit()
    await session.refresh(saved_signal)

    return saved_signal


async def update_signal_validation(
    session: AsyncSession,
    *,
    signal_id: int,
    mint_info: MintInfo | None,
    validation_status: str,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.validation_status = validation_status

    if mint_info is not None:
        signal.decimals = mint_info.decimals
        signal.supply = mint_info.supply

    await session.commit()


async def update_signal_market(
    session: AsyncSession,
    *,
    signal_id: int,
    snapshot: MarketSnapshot,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.market_status = "available"

    signal.pair_address = snapshot.pair_address
    signal.dex_id = snapshot.dex_id
    signal.price_usd = snapshot.price_usd
    signal.liquidity_usd = snapshot.liquidity_usd
    signal.volume_5m = snapshot.volume_5m
    signal.buys_5m = snapshot.buys_5m
    signal.sells_5m = snapshot.sells_5m

    signal.observed_at = datetime.now(timezone.utc)

    await session.commit()


async def update_signal_market_status(
    session: AsyncSession,
    *,
    signal_id: int,
    market_status: str,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.market_status = market_status

    await session.commit()
"""
with open("app/database/repository.py", "w") as f:
    f.write(content_repo)


# 2. Update app/database/models.py
with open("app/database/models.py", "r") as f:
    content = f.read()

content = content.replace(
    "    market_status: Mapped[str | None] = mapped_column(\n        String(32),\n        index=True,\n    )",
    "    market_status: Mapped[str | None] = mapped_column(\n        String(32),\n        index=True,\n    )\n\n    validation_status: Mapped[str | None] = mapped_column(\n        String(32),\n        index=True,\n    )"
)
with open("app/database/models.py", "w") as f:
    f.write(content)


# 4. Update app/solana/validator.py
content_validator = """import asyncio
import logging
from dataclasses import dataclass

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from app.config.settings import get_settings


logger = logging.getLogger("meco.solana")


@dataclass(frozen=True)
class MintInfo:
    address: str
    decimals: int
    supply: int


async def get_mint_info(
    token_address: str,
    *,
    retries: int = 2,
) -> MintInfo | None:
    \"\"\"
    Check whether a Solana address is a valid SPL token mint.

    Returns:
        MintInfo if the address is a valid token mint.
        None if the address is invalid or the RPC cannot validate it
        after all retries.
    \"\"\"

    settings = get_settings()

    try:
        pubkey = Pubkey.from_string(token_address)
    except ValueError:
        return None

    for attempt in range(retries + 1):
        try:
            async with AsyncClient(settings.solana_rpc_url) as client:
                response = await client.get_token_supply(pubkey)

            if response.value is None:
                return None

            return MintInfo(
                address=token_address,
                decimals=response.value.decimals,
                supply=int(response.value.amount),
            )

        except Exception as exc:
            if attempt >= retries:
                logger.exception(
                    "SOLANA RPC FAILED | mint=%s | attempts=%s",
                    token_address,
                    attempt + 1,
                )
                return None

            delay = 1.0 * (2 ** attempt)

            logger.warning(
                "SOLANA RPC RETRY | mint=%s | attempt=%s/%s | "
                "error=%s | retry_in=%.1fs",
                token_address,
                attempt + 1,
                retries,
                type(exc).__name__,
                delay,
            )

            await asyncio.sleep(delay)

    return None
"""
with open("app/solana/validator.py", "w") as f:
    f.write(content_validator)


# 5. Update app/telegram/client.py
content_client = """import asyncio
import logging
from datetime import datetime, timezone

from telethon import TelegramClient, events

from app.config.settings import get_settings
from app.database.repository import (
    create_signal,
    update_signal_market,
    update_signal_market_status,
    update_signal_validation,
)
from app.database.session import SessionLocal
from app.market.dexscreener import get_token_pairs
from app.market.observer import observe_signal
from app.market.snapshot import create_market_snapshot, select_primary_pair
from app.solana.validator import get_mint_info
from app.telegram.parser import extract_token_signal


logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("meco.telegram")

settings = get_settings()

client = TelegramClient(
    settings.telegram_session_name,
    settings.telegram_api_id,
    settings.telegram_api_hash,
)


@client.on(events.NewMessage)
async def handle_new_message(event: events.NewMessage.Event) -> None:
    try:
        await process_new_message(event)

    except Exception:
        logger.exception(
            "UNHANDLED MESSAGE PROCESSING ERROR | chat_id=%s | message_id=%s",
            event.chat_id,
            getattr(event.message, "id", None),
        )


async def process_new_message(
    event: events.NewMessage.Event,
) -> None:
    message = event.message

    if not message.text:
        return

    if event.chat_id not in settings.telegram_channel_ids:
        logger.info(
            "IGNORED MESSAGE | chat_id=%s | message_id=%s",
            event.chat_id,
            message.id,
        )
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
    )

    logger.info("Message: %s", message.text)

    received_at = datetime.now(timezone.utc)

    signal = extract_token_signal(
        message.text,
        chat_id=event.chat_id,
        message_id=message.id,
        message_created_at=message.date,
        received_at=received_at,
    )

    if not signal:
        return

    logger.info(
        "🚨 TOKEN DETECTED | mint=%s | slippage=%s%%",
        signal.token_address,
        signal.slippage,
    )

    logger.info(
        "📡 SIGNAL TIMING | chat_id=%s | message_id=%s | "
        "message_created_at=%s | received_at=%s | "
        "telegram_latency=%.3fs",
        signal.chat_id,
        signal.message_id,
        signal.message_created_at,
        signal.received_at,
        (
            signal.received_at - signal.message_created_at
        ).total_seconds(),
    )

    # ---------------------------------------------------------
    # STEP 1: DURABLE INGESTION
    # ---------------------------------------------------------

    async with SessionLocal() as session:
        saved_signal = await create_signal(
            session=session,
            signal=signal,
            source_name=source_name,
            source_username=source_username,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )

    # ---------------------------------------------------------
    # STEP 2: SOLANA VALIDATION
    # ---------------------------------------------------------

    mint_info = await get_mint_info(
        signal.token_address,
    )

    if mint_info is None:
        logger.warning(
            "❌ TOKEN VALIDATION FAILED | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="failed",
            )

        return

    logger.info(
        "✅ VALID TOKEN MINT | signal_id=%s | mint=%s | "
        "decimals=%s | supply=%s",
        saved_signal.id,
        mint_info.address,
        mint_info.decimals,
        mint_info.supply,
    )

    async with SessionLocal() as session:
        await update_signal_validation(
            session,
            signal_id=saved_signal.id,
            mint_info=mint_info,
            validation_status="valid",
        )

    # ---------------------------------------------------------
    # STEP 3: MARKET DATA
    # ---------------------------------------------------------

    try:
        pairs = await get_token_pairs(
            signal.token_address,
        )
    except Exception:
        logger.exception(
            "MARKET FETCH FAILED | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_market_status(
                session,
                signal_id=saved_signal.id,
                market_status="fetch_failed",
            )

        return

    if not pairs:
        logger.warning(
            "⚠️ NO MARKET DATA | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_market_status(
                session,
                signal_id=saved_signal.id,
                market_status="no_market_data",
            )

        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "⚠️ NO LIQUID MARKET PAIR | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_market_status(
                session,
                signal_id=saved_signal.id,
                market_status="no_liquid_pair",
            )

        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        await update_signal_market(
            session,
            signal_id=saved_signal.id,
            snapshot=snapshot,
        )

    logger.info(
        "📊 MARKET SNAPSHOT | signal_id=%s | "
        "price=$%s | liquidity=$%s | "
        "5m_volume=$%s | buys=%s | sells=%s | "
        "dex=%s | pair=%s",
        saved_signal.id,
        snapshot.price_usd,
        snapshot.liquidity_usd,
        snapshot.volume_5m,
        snapshot.buys_5m,
        snapshot.sells_5m,
        snapshot.dex_id,
        snapshot.pair_address,
    )

    # ---------------------------------------------------------
    # STEP 4: SCHEDULE OBSERVATIONS
    # ---------------------------------------------------------

    asyncio.create_task(
        observe_signal(saved_signal)
    )


async def main() -> None:
    logger.info("Starting Meco Telegram listener...")

    await client.start()

    me = await client.get_me()

    logger.info(
        "Authenticated as: %s",
        getattr(me, "username", None) or me.first_name,
    )

    logger.info("Listening for Telegram messages...")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
"""
with open("app/telegram/client.py", "w") as f:
    f.write(content_client)


run_cmd("Implement durable pipeline ingestion and Solana validation retries")

