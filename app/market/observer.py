import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from app.database.models import MarketObservation, Signal
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

    max_tolerance = 60 if target_seconds < 3600 else 300
    if elapsed > (target_seconds + max_tolerance):
        logger.warning(
            "⚠️ MISSED OBSERVATION (OFFLINE) | signal_id=%s | target=%ss | elapsed=%.1fs",
            signal.id,
            target_seconds,
            elapsed,
        )
        async with SessionLocal() as session:
            await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="missed_offline",
            )
        return

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


async def recover_pending_observations(
    session_factory=SessionLocal,
    lookback_hours: int = 25,
) -> int:
    """
    Durable Task Recovery (Phase 9):
    Inspects database for signals created in the last 24h+ and recovers any
    unrecorded observation checkpoints, scheduling upcoming ones and
    marking severely expired ones as 'missed_offline'.
    Returns count of recovered/re-enqueued checkpoints.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    recovered_count = 0

    async with session_factory() as session:
        stmt = (
            select(Signal)
            .where(
                or_(
                    Signal.received_at >= cutoff,
                    Signal.message_created_at >= cutoff,
                )
            )
            .order_by(Signal.id.desc())
        )
        res = await session.execute(stmt)
        signals = res.scalars().all()

        for sig in signals:
            obs_stmt = select(MarketObservation.target_seconds).where(
                MarketObservation.signal_id == sig.id
            )
            obs_res = await session.execute(obs_stmt)
            existing_targets = set(obs_res.scalars().all())

            missing_targets = [t for t in OBSERVATION_INTERVALS if t not in existing_targets]
            for target_sec in missing_targets:
                asyncio.create_task(wait_and_capture(sig, target_sec))
                recovered_count += 1

    logger.info("Durable observation recovery completed: %d tasks resumed/handled.", recovered_count)
    return recovered_count
