from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketObservation
from app.market.models import MarketSnapshot


async def save_market_observation(
    session: AsyncSession,
    *,
    signal_id: int,
    token_address: str,
    seconds_since_signal: int,
    snapshot: MarketSnapshot,
) -> MarketObservation:
    observation = MarketObservation(
        signal_id=signal_id,
        token_address=token_address,
        observed_at=datetime.now(timezone.utc),
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
