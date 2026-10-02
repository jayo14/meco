from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.market.models import MarketSnapshot
from app.solana.validator import MintInfo
from app.telegram.parser import TokenSignal


async def save_signal(
    session: AsyncSession,
    *,
    signal: TokenSignal,
    mint_info: MintInfo,
    snapshot: MarketSnapshot | None,
    market_status: str,
    source_name: str | None,
    source_username: str | None,
) -> Signal:

    saved_signal = Signal(
        chat_id=signal.chat_id,
        message_id=signal.message_id,
        message_text=signal.message_text,

        message_created_at=signal.message_created_at,
        received_at=signal.received_at,

        source_name=source_name,
        source_username=source_username,

        token_address=signal.token_address,
        slippage=signal.slippage,

        decimals=mint_info.decimals,
        supply=mint_info.supply,

        market_status=market_status,

        pair_address=snapshot.pair_address if snapshot else None,
        dex_id=snapshot.dex_id if snapshot else None,
        price_usd=snapshot.price_usd if snapshot else None,
        liquidity_usd=snapshot.liquidity_usd if snapshot else None,
        volume_5m=snapshot.volume_5m if snapshot else None,
        buys_5m=snapshot.buys_5m if snapshot else None,
        sells_5m=snapshot.sells_5m if snapshot else None,
        observed_at=(
            datetime.now(signal.received_at.tzinfo)
            if snapshot
            else None
        ),
    )

    session.add(saved_signal)

    await session.commit()
    await session.refresh(saved_signal)

    return saved_signal


async def update_signal_market(
    session: AsyncSession,
    *,
    signal_id: int,
    snapshot: MarketSnapshot,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.market_status = "available"

    signal.pair_address = snapshot.pair_address
    signal.dex_id = snapshot.dex_id
    signal.price_usd = snapshot.price_usd
    signal.liquidity_usd = snapshot.liquidity_usd
    signal.volume_5m = snapshot.volume_5m
    signal.buys_5m = snapshot.buys_5m
    signal.sells_5m = snapshot.sells_5m
    signal.observed_at = datetime.now(
        signal.received_at.tzinfo
        if signal.received_at
        else None
    )

    await session.commit()
