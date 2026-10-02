from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketObservation, Signal
from app.market.models import MarketSnapshot


async def save_market_observation(
    session: AsyncSession,
    *,
    signal: Signal,
    snapshot: MarketSnapshot,
) -> MarketObservation:
    observed_at = datetime.now(timezone.utc)

    seconds_since_signal = max(
        0,
        int((observed_at - signal.detected_at).total_seconds()),
    )

    observation = MarketObservation(
        signal_id=signal.id,
        token_address=signal.token_address,
        observed_at=observed_at,
        seconds_since_signal=seconds_since_signal,
        price_usd=snapshot.price_usd,
        liquidity_usd=snapshot.liquidity_usd,
        volume_5m=snapshot.volume_5m,
        buys_5m=snapshot.buys_5m,
        sells_5m=snapshot.sells_5m,
        price_change_5m=snapshot.price_change_5m,
    )

    session.add(observation)

    await session.commit()
    await session.refresh(observation)

    return observation
