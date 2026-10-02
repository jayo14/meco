from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketPairObservation, Signal
from app.market.dexscreener import MarketPair


async def save_market_pair_observations(
    session: AsyncSession,
    *,
    signal: Signal,
    pairs: list[MarketPair],
    target_seconds: int,
) -> list[MarketPairObservation]:
    observed_at = datetime.now(timezone.utc)

    anchor = signal.received_at or signal.message_created_at

    seconds_since_signal = max(
        0,
        int((observed_at - anchor).total_seconds()),
    )

    saved: list[MarketPairObservation] = []

    for pair in pairs:
        observation = MarketPairObservation(
            signal_id=signal.id,
            token_address=signal.token_address,
            observed_at=observed_at,
            target_seconds=target_seconds,
            seconds_since_signal=seconds_since_signal,

            pair_address=pair.pair_address,
            dex_id=pair.dex_id,
            url=pair.url,

            base_token_address=pair.base_token_address,
            base_token_name=pair.base_token_name,
            base_token_symbol=pair.base_token_symbol,

            quote_token_address=pair.quote_token_address,
            quote_token_name=pair.quote_token_name,
            quote_token_symbol=pair.quote_token_symbol,

            price_native=pair.price_native,
            price_usd=pair.price_usd,
            liquidity_usd=pair.liquidity_usd,

            volume_5m=pair.volume_m5,
            volume_1h=pair.volume_h1,
            volume_6h=pair.volume_h6,
            volume_24h=pair.volume_h24,

            buys_5m=pair.buys_m5,
            sells_5m=pair.sells_m5,

            price_change_5m=pair.price_change_m5,
            price_change_1h=pair.price_change_h1,
            price_change_6h=pair.price_change_h6,
            price_change_24h=pair.price_change_h24,

            market_cap=pair.market_cap,
            fdv=pair.fdv,

            pair_created_at=pair.pair_created_at,
        )

        session.add(observation)
        saved.append(observation)

    await session.commit()

    for observation in saved:
        await session.refresh(observation)

    return saved
