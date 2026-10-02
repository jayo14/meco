import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update app/telegram/parser.py
with open("app/telegram/parser.py", "r") as f:
    content = f.read()

content = content.replace(
    "    detected_at: datetime",
    "    message_created_at: datetime\n    received_at: datetime"
)
content = content.replace(
    "    detected_at: datetime,",
    "    message_created_at: datetime,\n    received_at: datetime,"
)
content = content.replace(
    "        detected_at=detected_at,",
    "        message_created_at=message_created_at,\n        received_at=received_at,"
)
with open("app/telegram/parser.py", "w") as f:
    f.write(content)

# Update tests/test_parser.py
with open("tests/test_parser.py", "r") as f:
    content = f.read()

content = content.replace(
    "detected_at=datetime.now(timezone.utc)",
    "message_created_at=datetime.now(timezone.utc),\n        received_at=datetime.now(timezone.utc)"
)
with open("tests/test_parser.py", "w") as f:
    f.write(content)


# 3. Update app/database/models.py
with open("app/database/models.py", "r") as f:
    content = f.read()

content = content.replace(
    """    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )""",
    """    message_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    market_status: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
    )"""
)
with open("app/database/models.py", "w") as f:
    f.write(content)


# 4. Update app/database/repository.py
content = """from datetime import datetime

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
"""
with open("app/database/repository.py", "w") as f:
    f.write(content)


# 5. Update app/telegram/client.py
with open("app/telegram/client.py", "r") as f:
    content = f.read()

import_target = "from app.database.repository import save_signal"
import_replace = "from app.database.repository import save_signal, update_signal_market"
content = content.replace(import_target, import_replace)

old_signal_extract = """    signal = extract_token_signal(
        message.text,
        chat_id=event.chat_id,
        message_id=message.id,
        detected_at=datetime.now(timezone.utc),
    )"""
new_signal_extract = """    received_at = datetime.now(timezone.utc)

    signal = extract_token_signal(
        message.text,
        chat_id=event.chat_id,
        message_id=message.id,
        message_created_at=message.date,
        received_at=received_at,
    )"""
content = content.replace(old_signal_extract, new_signal_extract)

old_mint_validation = """    logger.info(
        "✅ VALID TOKEN MINT | mint=%s | decimals=%s | supply=%s",
        signal.token_address,
        mint_info.decimals,
        mint_info.supply,
    )"""
new_mint_validation = """    logger.info(
        "✅ VALID TOKEN MINT | mint=%s | decimals=%s | supply=%s",
        signal.token_address,
        mint_info.decimals,
        mint_info.supply,
    )

    logger.info(
        "📡 SIGNAL TIMING | message_created_at=%s | received_at=%s | "
        "telegram_latency=%.2fs",
        signal.message_created_at,
        signal.received_at,
        (
            signal.received_at - signal.message_created_at
        ).total_seconds(),
    )"""
content = content.replace(old_mint_validation, new_mint_validation)

old_market_flow = """    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "⚠️ NO MARKET DATA | mint=%s",
            signal.token_address,
        )
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "⚠️ NO LIQUID MARKET PAIR | mint=%s",
            signal.token_address,
        )
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=snapshot,
            source_name=source_name,
            source_username=source_username,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )

    asyncio.create_task(
        observe_signal(saved_signal)
    )

    logger.info(
        "📊 MARKET SNAPSHOT | price=$%s | liquidity=$%s | "
        "5m_volume=$%s | buys=%s | sells=%s | dex=%s",
        snapshot.price_usd,
        snapshot.liquidity_usd,
        snapshot.volume_5m,
        snapshot.buys_5m,
        snapshot.sells_5m,
        snapshot.dex_id,
    )"""
new_market_flow = """    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=None,
            market_status="pending",
            source_name=source_name,
            source_username=source_username,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )

    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "⚠️ NO MARKET DATA | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )
        async with SessionLocal() as session:
            saved_signal.market_status = "no_market_data"
            session.add(saved_signal)
            await session.commit()
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "⚠️ NO LIQUID MARKET PAIR | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )
        async with SessionLocal() as session:
            saved_signal.market_status = "no_liquid_pair"
            session.add(saved_signal)
            await session.commit()
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        await update_signal_market(
            session,
            signal_id=saved_signal.id,
            snapshot=snapshot,
        )

    logger.info(
        "📊 MARKET SNAPSHOT | price=$%s | liquidity=$%s | "
        "5m_volume=$%s | buys=%s | sells=%s | dex=%s",
        snapshot.price_usd,
        snapshot.liquidity_usd,
        snapshot.volume_5m,
        snapshot.buys_5m,
        snapshot.sells_5m,
        snapshot.dex_id,
    )

    asyncio.create_task(
        observe_signal(saved_signal)
    )"""
content = content.replace(old_market_flow, new_market_flow)
with open("app/telegram/client.py", "w") as f:
    f.write(content)


# 7. Update observer
with open("app/market/observer.py", "r") as f:
    content = f.read()

content = content.replace(
    "async def wait_and_capture(",
    "def get_signal_anchor(signal: Signal) -> datetime:\n    return signal.received_at or signal.message_created_at\n\n\nasync def wait_and_capture("
)
old_elapsed = """    now = datetime.now(timezone.utc)

    elapsed = max(
        0,
        (now - signal.detected_at).total_seconds(),
    )"""
new_elapsed = """    anchor = get_signal_anchor(signal)

    now = datetime.now(timezone.utc)

    elapsed = max(
        0,
        (now - anchor).total_seconds(),
    )"""
content = content.replace(old_elapsed, new_elapsed)
with open("app/market/observer.py", "w") as f:
    f.write(content)

with open("app/database/observation_repository.py", "r") as f:
    content = f.read()

old_repo_elapsed = """    seconds_since_signal = max(
        0,
        int((observed_at - signal.detected_at).total_seconds()),
    )"""
new_repo_elapsed = """    anchor = signal.received_at or signal.message_created_at

    seconds_since_signal = max(
        0,
        int((observed_at - anchor).total_seconds()),
    )"""
content = content.replace(old_repo_elapsed, new_repo_elapsed)
with open("app/database/observation_repository.py", "w") as f:
    f.write(content)

run_cmd("Record precision receive time and explicitly log market status")
