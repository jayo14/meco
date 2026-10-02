from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.market.models import MarketSnapshot
from app.solana.validator import MintInfo
from app.telegram.parser import TokenSignal


async def create_signal(
    session: AsyncSession,
    *,
    signal: TokenSignal,
    source_name: str | None,
    source_username: str | None,
) -> Signal | None:
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

        market_status="pending",
    )

    session.add(saved_signal)

    try:
        await session.commit()

    except IntegrityError:
        await session.rollback()

        result = await session.execute(
            select(Signal).where(
                Signal.chat_id == signal.chat_id,
                Signal.message_id == signal.message_id,
            )
        )

        existing_signal = result.scalar_one_or_none()

        if existing_signal is not None:
            return None

        raise

    await session.refresh(saved_signal)

    return saved_signal


async def update_signal_validation(
    session: AsyncSession,
    *,
    signal_id: int,
    mint_info: MintInfo | None,
    validation_status: str,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.validation_status = validation_status

    if mint_info is not None:
        signal.decimals = mint_info.decimals
        signal.supply = mint_info.supply

    await session.commit()


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
    signal.volume_1h = snapshot.volume_1h
    signal.volume_24h = snapshot.volume_24h

    signal.buys_5m = snapshot.buys_5m
    signal.sells_5m = snapshot.sells_5m

    signal.price_change_5m = snapshot.price_change_5m
    signal.price_change_1h = snapshot.price_change_1h
    signal.price_change_24h = snapshot.price_change_24h

    signal.market_cap = snapshot.market_cap
    signal.fdv = snapshot.fdv

    signal.observed_at = datetime.now(timezone.utc)

    await session.commit()


async def update_signal_market_status(
    session: AsyncSession,
    *,
    signal_id: int,
    market_status: str,
) -> None:
    signal = await session.get(Signal, signal_id)

    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    signal.market_status = market_status

    await session.commit()
