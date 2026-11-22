import asyncio
import logging
import time
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
from app.identity.registry import TokenRegistry
from app.market.dexscreener import get_token_pairs
from app.market.observer import observe_signal, recover_pending_observations
from app.market.snapshot import create_market_snapshot, select_primary_pair
from app.social.ingestion import SocialIngestionService
from app.social.matcher import TokenSocialMatcher
from app.social.narratives import NarrativeEngine
from app.social.telegram_adapter import TelegramSocialAdapter
from app.solana.validator import (
    MintValidationStatus,
    get_mint_info,
)
from app.security.redaction import setup_secure_logging
from app.telegram.parser import extract_token_signal

logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)
setup_secure_logging()

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

    # perf_counter is for measuring elapsed durations.
    # It is intentionally separate from wall-clock timestamps.
    pipeline_started = time.perf_counter()

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

    if settings.enable_telegram_social and message.text:
        try:
            tg_adapter = TelegramSocialAdapter()
            raw_post = tg_adapter.transform_telegram_message(
                message_id=message.id,
                channel_id=event.chat_id,
                channel_title=source_name or source_username,
                text=message.text,
                date=message.date,
                views=getattr(message, "views", 0) or 0,
                forwards=getattr(message, "forwards", 0) or 0,
            )
            ingestion_service = SocialIngestionService(SessionLocal)
            matcher = TokenSocialMatcher(SessionLocal)
            narrative_engine = NarrativeEngine(SessionLocal)
            async with SessionLocal() as session, session.begin():
                db_post = await ingestion_service.ingest_post(session, raw_post)
                if db_post:
                    await matcher.associate_post(session, db_post)
                    await narrative_engine.associate_post_narratives(session, db_post)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed ingesting telegram message into social pipeline: %s", exc)

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

    telegram_latency = (
        signal.received_at - signal.message_created_at
    ).total_seconds()

    logger.info(
        "📡 SIGNAL TIMING | chat_id=%s | message_id=%s | "
        "message_created_at=%s | received_at=%s | "
        "telegram_latency=%.3fs",
        signal.chat_id,
        signal.message_id,
        signal.message_created_at,
        signal.received_at,
        telegram_latency,
    )

    # ---------------------------------------------------------
    # STEP 1: DURABLE INGESTION
    # ---------------------------------------------------------

    db_started = time.perf_counter()

    async with SessionLocal() as session:
        saved_signal = await create_signal(
            session=session,
            signal=signal,
            source_name=source_name,
            source_username=source_username,
        )

    db_duration = time.perf_counter() - db_started

    if saved_signal is None:
        logger.info(
            "⏭️ DUPLICATE SIGNAL | chat_id=%s | message_id=%s | "
            "db_persistence=%.3fs",
            signal.chat_id,
            signal.message_id,
            db_duration,
        )
        return

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s | "
        "db_persistence=%.3fs",
        saved_signal.id,
        saved_signal.token_address,
        db_duration,
    )

    try:
        async with SessionLocal() as session, session.begin():
            await TokenRegistry.record_telegram_signal_discovery(
                session,
                chat_id=signal.chat_id,
                message_id=signal.message_id,
                message_text=signal.message_text,
                token_address=signal.token_address,
                message_created_at=signal.message_created_at,
                received_at=signal.received_at,
                source_name=source_name,
                source_username=source_username,
            )
    except Exception as reg_exc:  # noqa: BLE001
        logger.warning(
            "Canonical token resolution skipped for Telegram signal: %s",
            reg_exc,
        )

    # ---------------------------------------------------------
    # STEP 2: SOLANA VALIDATION
    # ---------------------------------------------------------

    validation_started = time.perf_counter()

    validation = await get_mint_info(
        signal.token_address,
    )

    validation_duration = (
        time.perf_counter() - validation_started
    )

    logger.info(
        "⛓️ SOLANA VALIDATION | signal_id=%s | "
        "status=%s | duration=%.3fs",
        saved_signal.id,
        validation.status.value,
        validation_duration,
    )

    if validation.status == MintValidationStatus.INVALID:
        logger.warning(
            "❌ INVALID TOKEN MINT | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        update_started = time.perf_counter()

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="invalid",
            )

        update_duration = time.perf_counter() - update_started

        logger.info(
            "⏱️ VALIDATION STATUS PERSISTED | "
            "signal_id=%s | duration=%.3fs",
            saved_signal.id,
            update_duration,
        )

        return

    if validation.status == MintValidationStatus.RPC_FAILED:
        logger.error(
            "⚠️ SOLANA RPC FAILED | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        update_started = time.perf_counter()

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="rpc_failed",
            )

        update_duration = time.perf_counter() - update_started

        logger.info(
            "⏱️ VALIDATION STATUS PERSISTED | "
            "signal_id=%s | duration=%.3fs",
            saved_signal.id,
            update_duration,
        )

        return

    mint_info = validation.mint_info

    if mint_info is None:
        raise RuntimeError(
            "VALID validation result has no mint info"
        )

    logger.info(
        "✅ VALID TOKEN MINT | signal_id=%s | mint=%s | "
        "decimals=%s | supply=%s",
        saved_signal.id,
        mint_info.address,
        mint_info.decimals,
        mint_info.supply,
    )

    validation_db_started = time.perf_counter()

    async with SessionLocal() as session:
        await update_signal_validation(
            session,
            signal_id=saved_signal.id,
            mint_info=mint_info,
            validation_status="valid",
        )

    validation_db_duration = (
        time.perf_counter() - validation_db_started
    )

    logger.info(
        "💾 VALIDATION SAVED | signal_id=%s | "
        "duration=%.3fs",
        saved_signal.id,
        validation_db_duration,
    )

    # ---------------------------------------------------------
    # STEP 3: MARKET DATA
    # ---------------------------------------------------------

    market_started = time.perf_counter()

    try:
        pairs = await get_token_pairs(
            signal.token_address,
        )
    except Exception:
        market_duration = time.perf_counter() - market_started

        logger.exception(
            "MARKET FETCH FAILED | signal_id=%s | mint=%s | "
            "duration=%.3fs",
            saved_signal.id,
            signal.token_address,
            market_duration,
        )

        async with SessionLocal() as session:
            await update_signal_market_status(
                session,
                signal_id=saved_signal.id,
                market_status="fetch_failed",
            )

        return

    market_duration = time.perf_counter() - market_started

    logger.info(
        "🌐 MARKET FETCH | signal_id=%s | "
        "pairs=%s | duration=%.3fs",
        saved_signal.id,
        len(pairs),
        market_duration,
    )

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

    market_db_started = time.perf_counter()

    async with SessionLocal() as session:
        await update_signal_market(
            session,
            signal_id=saved_signal.id,
            snapshot=snapshot,
        )

    market_db_duration = (
        time.perf_counter() - market_db_started
    )

    logger.info(
        "💾 MARKET SNAPSHOT SAVED | signal_id=%s | "
        "duration=%.3fs",
        saved_signal.id,
        market_db_duration,
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
    # STEP 4: PIPELINE TIMING
    # ---------------------------------------------------------

    total_duration = time.perf_counter() - pipeline_started

    logger.info(
        "⏱️ PIPELINE TIMING | signal_id=%s | "
        "telegram_latency=%.3fs | "
        "db_persistence=%.3fs | "
        "solana_validation=%.3fs | "
        "validation_db=%.3fs | "
        "market_fetch=%.3fs | "
        "market_db=%.3fs | "
        "total_meco_processing=%.3fs",
        saved_signal.id,
        telegram_latency,
        db_duration,
        validation_duration,
        validation_db_duration,
        market_duration,
        market_db_duration,
        total_duration,
    )

    # ---------------------------------------------------------
    # STEP 5: SCHEDULE OBSERVATIONS
    # ---------------------------------------------------------

    asyncio.create_task(
        observe_signal(saved_signal)
    )


async def main() -> None:
    logger.info("Starting Meco Telegram listener...")

    backoff = 2
    while True:
        try:
            if not client.is_connected():
                await client.start()

            me = await client.get_me()
            backoff = 2  # reset backoff on successful connect

            logger.info(
                "Authenticated as: %s",
                getattr(me, "username", None) or getattr(me, "first_name", "Unknown"),
            )
            try:
                recovered = await recover_pending_observations()
                if recovered > 0:
                    logger.info("Durable checkpoint recovery: %s pending observations queued", recovered)
            except Exception as e:
                logger.warning("Observation checkpoint recovery failed: %s", e)

            logger.info("Listening for Telegram messages...")

            await client.run_until_disconnected()
            logger.warning("Telegram client disconnected. Attempting reconnect...")

        except asyncio.CancelledError:
            logger.info("Shutdown signal received. Stopping Meco listener cleanly...")
            break
        except Exception:
            logger.exception(
                "Connection error occurred. Retrying in %ss...", backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    asyncio.run(main())
