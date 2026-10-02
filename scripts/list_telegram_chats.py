import asyncio
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

    print("\n=== TELEGRAM CHATS ===\n")

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
