from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketObservation, Signal
from app.market.models import MarketSnapshot


async def save_market_observation(
    session: AsyncSession,
    *,
    signal: Signal,
    snapshot: MarketSnapshot | None,
    target_seconds: int,
    observation_status: str,
) -> MarketObservation:
    observed_at = datetime.now(timezone.utc)

    anchor = signal.received_at or signal.message_created_at

    seconds_since_signal = max(
        0,
        int((observed_at - anchor).total_seconds()),
    )

    observation = MarketObservation(
        signal_id=signal.id,
        token_address=signal.token_address,

        pair_address=(
            snapshot.pair_address
            if snapshot is not None
            else None
        ),
        dex_id=(
            snapshot.dex_id
            if snapshot is not None
            else None
        ),

        observed_at=observed_at,

        target_seconds=target_seconds,
        seconds_since_signal=seconds_since_signal,

        observation_status=observation_status,

        price_usd=(
            snapshot.price_usd
            if snapshot is not None
            else None
        ),
        liquidity_usd=(
            snapshot.liquidity_usd
            if snapshot is not None
            else None
        ),
        volume_5m=(
            snapshot.volume_5m
            if snapshot is not None
            else None
        ),
        buys_5m=(
            snapshot.buys_5m
            if snapshot is not None
            else None
        ),
        sells_5m=(
            snapshot.sells_5m
            if snapshot is not None
            else None
        ),
        price_change_5m=(
            snapshot.price_change_5m
            if snapshot is not None
            else None
        ),
    )

    session.add(observation)

    try:
        await session.commit()
        await session.refresh(observation)
        return observation

    except IntegrityError:
        await session.rollback()

        result = await session.execute(
            select(MarketObservation).where(
                MarketObservation.signal_id == signal.id,
                MarketObservation.target_seconds == target_seconds,
            )
        )

        existing = result.scalar_one_or_none()

        if existing is None:
            raise

        return existing
