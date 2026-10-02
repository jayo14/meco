import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update app/database/repository.py
content_repo = """from datetime import datetime, timezone

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
    signal.buys_5m = snapshot.buys_5m
    signal.sells_5m = snapshot.sells_5m

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
"""
with open("app/database/repository.py", "w") as f:
    f.write(content_repo)


# 2. Update app/telegram/client.py
with open("app/telegram/client.py", "r") as f:
    content = f.read()

client_old = """    async with SessionLocal() as session:
        saved_signal = await create_signal(
            session=session,
            signal=signal,
            source_name=source_name,
            source_username=source_username,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )"""

client_new = """    async with SessionLocal() as session:
        saved_signal = await create_signal(
            session=session,
            signal=signal,
            source_name=source_name,
            source_username=source_username,
        )

    if saved_signal is None:
        logger.info(
            "⏭️ DUPLICATE SIGNAL | chat_id=%s | message_id=%s",
            signal.chat_id,
            signal.message_id,
        )
        return

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )"""

content = content.replace(client_old, client_new)
with open("app/telegram/client.py", "w") as f:
    f.write(content)

run_cmd("Ignore duplicate signals on unique constraint collision")

