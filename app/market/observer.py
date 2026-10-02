import asyncio
import logging
from datetime import datetime, timezone

from app.database.models import Signal
from app.database.observation_repository import save_market_observation
from app.database.session import SessionLocal
from app.market.dexscreener import get_token_pairs
from app.market.snapshot import (
    create_market_snapshot,
    select_primary_pair,
)

logger = logging.getLogger("meco.observer")


OBSERVATION_INTERVALS = (
    30,
    60,
    300,
    900,
    1800,
    3600,
    21600,
    86400,
)


async def capture_observation(signal: Signal) -> None:
    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "NO MARKET DATA | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "NO LIQUID PAIR | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        observation = await save_market_observation(
            session,
            signal=signal,
            snapshot=snapshot,
        )

    logger.info(
        "📈 OBSERVATION | signal_id=%s | elapsed=%ss | "
        "price=$%s | liquidity=$%s",
        signal.id,
        observation.seconds_since_signal,
        observation.price_usd,
        observation.liquidity_usd,
    )


async def wait_and_capture(
    signal: Signal,
    target_seconds: int,
) -> None:
    now = datetime.now(timezone.utc)

    elapsed = max(
        0,
        (now - signal.detected_at).total_seconds(),
    )

    delay = target_seconds - elapsed

    if delay > 0:
        await asyncio.sleep(delay)

    try:
        await capture_observation(signal)
    except Exception:
        logger.exception(
            "OBSERVATION FAILED | signal_id=%s | target=%ss",
            signal.id,
            target_seconds,
        )


async def observe_signal(signal: Signal) -> None:
    tasks = [
        asyncio.create_task(
            wait_and_capture(
                signal,
                target_seconds,
            )
        )
        for target_seconds in OBSERVATION_INTERVALS
    ]

    await asyncio.gather(*tasks)
