import asyncio
import logging

from telethon import TelegramClient, events

from app.config.settings import get_settings
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

    logger.info(
        "New Telegram message | chat_id=%s | message_id=%s",
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
