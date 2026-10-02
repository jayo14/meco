import asyncio
import logging
from datetime import datetime, timezone

from app.database.models import Signal
from app.database.observation_repository import save_market_observation
from app.database.pair_observation_repository import (
    save_market_pair_observations,
)
from app.database.session import SessionLocal
from app.market.dexscreener import get_token_pairs
from app.market.snapshot import (
    create_market_snapshot,
    select_primary_pair,
)

logger = logging.getLogger("meco.observer")


OBSERVATION_INTERVALS = (
    10,
    30,
    60,
    120,
    180,
    300,
    600,
    900,
    1800,
    3600,
    21600,
    86400,
)


async def capture_observation(
    signal: Signal,
    target_seconds: int,
) -> None:
    try:
        pairs = await get_token_pairs(signal.token_address)
    except Exception:
        logger.exception(
            "MARKET FETCH FAILED | signal_id=%s | target=%ss",
            signal.id,
            target_seconds,
        )

        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="fetch_failed",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=fetch_failed | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
        )

        return

    if not pairs:
        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="no_market_data",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=no_market_data | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
        )

        return

    async with SessionLocal() as session:
        pair_observations = await save_market_pair_observations(
            session,
            signal=signal,
            pairs=pairs,
            target_seconds=target_seconds,
        )

    logger.info(
        "🔎 PAIRS CAPTURED | signal_id=%s | target=%ss | pairs=%s",
        signal.id,
        target_seconds,
        len(pair_observations),
    )

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="no_liquid_pair",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=no_liquid_pair | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
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
            target_seconds=target_seconds,
            observation_status="success",
        )

    logger.info(
        "📈 OBSERVATION | signal_id=%s | target=%ss | actual=%ss | "
        "status=%s | price=$%s | liquidity=$%s | dex=%s | pair=%s",
        observation.signal_id,
        observation.target_seconds,
        observation.seconds_since_signal,
        observation.observation_status,
        observation.price_usd,
        observation.liquidity_usd,
        observation.dex_id,
        observation.pair_address,
    )


def get_signal_anchor(signal: Signal) -> datetime:
    return signal.received_at or signal.message_created_at


async def wait_and_capture(
    signal: Signal,
    target_seconds: int,
) -> None:
    anchor = get_signal_anchor(signal)

    now = datetime.now(timezone.utc)

    elapsed = max(
        0,
        (now - anchor).total_seconds(),
    )

    delay = target_seconds - elapsed

    if delay > 0:
        await asyncio.sleep(delay)

    try:
        await capture_observation(signal, target_seconds)
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
