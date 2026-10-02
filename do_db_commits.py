import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Create repository.py
repo_content = """from sqlalchemy.ext.asyncio import AsyncSession

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
        observed_at=signal.detected_at,
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record
"""
with open("app/database/repository.py", "w") as f:
    f.write(repo_content)

run_cmd("Create signal repository")

# 2. Update client.py imports
with open("app/telegram/client.py", "r") as f:
    client_content = f.read()

imports_target = "from app.config.settings import get_settings"
imports_replacement = """from app.config.settings import get_settings
from app.database.repository import save_signal
from app.database.session import SessionLocal"""
client_content = client_content.replace(imports_target, imports_replacement)
with open("app/telegram/client.py", "w") as f:
    f.write(client_content)

run_cmd("Import database dependencies in telegram client")

# 3. Update client.py logic
with open("app/telegram/client.py", "r") as f:
    client_content = f.read()

target_logic = """    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )
"""
replacement_logic = target_logic + """
    async with SessionLocal() as session:
        saved_signal = await save_signal(
            session=session,
            signal=signal,
            mint_info=mint_info,
            snapshot=snapshot,
        )

    logger.info(
        "💾 SIGNAL SAVED | id=%s | mint=%s",
        saved_signal.id,
        saved_signal.token_address,
    )
"""
client_content = client_content.replace(target_logic, replacement_logic)
with open("app/telegram/client.py", "w") as f:
    f.write(client_content)

run_cmd("Save signal and log confirmation")
