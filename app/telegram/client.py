import asyncio
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
