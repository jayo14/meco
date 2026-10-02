from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.market.models import MarketSnapshot
from app.telegram.parser import TokenSignal
from app.solana.validator import MintInfo


async def save_signal(
    session: AsyncSession,
    signal: TokenSignal,
    mint_info: MintInfo,
    snapshot: MarketSnapshot,
) -> Signal:
    record = Signal(
        chat_id=signal.chat_id,
        message_id=signal.message_id,
        message_text=signal.message_text,
        detected_at=signal.detected_at,
        token_address=signal.token_address,
        slippage=signal.slippage,
        decimals=mint_info.decimals,
        supply=mint_info.supply,
        pair_address=snapshot.pair_address,
        dex_id=snapshot.dex_id,
        price_usd=snapshot.price_usd,
        liquidity_usd=snapshot.liquidity_usd,
        volume_5m=snapshot.volume_5m,
        buys_5m=snapshot.buys_5m,
        sells_5m=snapshot.sells_5m,
        observed_at=datetime.now(timezone.utc),
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record
