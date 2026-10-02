import asyncio
import logging

from telethon import TelegramClient, events

from app.config.settings import get_settings
from app.database.repository import save_signal, update_signal_market
from app.database.session import SessionLocal
from app.market.observer import observe_signal
from app.market.dexscreener import get_token_pairs
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

    signal = extract_token_signal(
        message.text,
        chat_id=event.chat_id,
        message_id=message.id,
        detected_at=message.date,
    )
    if not signal:
        return

    logger.info(
        "🚨 TOKEN DETECTED | mint=%s | slippage=%s%%",
        signal.token_address,
        signal.slippage,
    )

    mint_info = await get_mint_info(signal.token_address)

    if mint_info is None:
        logger.warning(
            "❌ INVALID TOKEN MINT | mint=%s",
            signal.token_address,
        )
        return

    logger.info(
        "✅ VALID TOKEN MINT | mint=%s | decimals=%s | supply=%s",
        mint_info.address,
        mint_info.decimals,
        mint_info.supply,
    )


    logger.info(
        "📡 SIGNAL CONTEXT | chat_id=%s | message_id=%s | detected_at=%s",
        signal.chat_id,
        signal.message_id,
        signal.detected_at,
    )

    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=None,
            market_status="pending",
            source_name=source_name,
            source_username=source_username,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )

    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "⚠️ NO MARKET DATA | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )
        async with SessionLocal() as session:
            saved_signal.market_status = "no_market_data"
            session.add(saved_signal)
            await session.commit()
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "⚠️ NO LIQUID MARKET PAIR | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )
        async with SessionLocal() as session:
            saved_signal.market_status = "no_liquid_pair"
            session.add(saved_signal)
            await session.commit()
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
        "📊 MARKET SNAPSHOT | price=$%s | liquidity=$%s | "
        "5m_volume=$%s | buys=%s | sells=%s | dex=%s",
        snapshot.price_usd,
        snapshot.liquidity_usd,
        snapshot.volume_5m,
        snapshot.buys_5m,
        snapshot.sells_5m,
        snapshot.dex_id,
    )

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
