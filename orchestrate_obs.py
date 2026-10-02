import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# Task 1: Replace observation_repository.py
obs_repo_content = """from datetime import datetime, timezone

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
"""
with open("app/database/observation_repository.py", "w") as f:
    f.write(obs_repo_content)
run_cmd("Update observation repository to accept Signal model")

# Task 2 & 5: Create observer.py with short intervals
observer_content = """import asyncio
import logging
from datetime import datetime, timezone

from app.database.models import Signal
from app.database.observation_repository import save_market_observation
from app.database.session import SessionLocal
from app.market.dexscreener import get_token_pairs
from app.market.snapshot import (
    create_market_snapshot,
    select_primary_pair,
)

logger = logging.getLogger("meco.observer")


OBSERVATION_INTERVALS = (
    5,
    10,
    20,
)


async def capture_observation(signal: Signal) -> None:
    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "NO MARKET DATA | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "NO LIQUID PAIR | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        observation = await save_market_observation(
            session,
            signal=signal,
            snapshot=snapshot,
        )

    logger.info(
        "📈 OBSERVATION | signal_id=%s | elapsed=%ss | "
        "price=$%s | liquidity=$%s",
        signal.id,
        observation.seconds_since_signal,
        observation.price_usd,
        observation.liquidity_usd,
    )


async def observe_signal(signal: Signal) -> None:
    now = datetime.now(timezone.utc)

    signal_age = max(
        0,
        int((now - signal.detected_at).total_seconds()),
    )

    for target_seconds in OBSERVATION_INTERVALS:
        delay = target_seconds - signal_age

        if delay > 0:
            await asyncio.sleep(delay)

        try:
            await capture_observation(signal)
        except Exception:
            logger.exception(
                "OBSERVATION FAILED | signal_id=%s | target=%ss",
                signal.id,
                target_seconds,
            )
"""
os.makedirs("app/market", exist_ok=True)
with open("app/market/observer.py", "w") as f:
    f.write(observer_content)
run_cmd("Create observation worker with temporary intervals")

# Task 3: Add unique constraint to MarketObservation
with open("app/database/models.py", "r") as f:
    models_content = f.read()

models_content = models_content.replace(
    "from sqlalchemy import (",
    "from sqlalchemy import (\n    UniqueConstraint,"
)

models_content = models_content.replace(
    '__tablename__ = "market_observations"\n',
    '__tablename__ = "market_observations"\n\n    __table_args__ = (\n        UniqueConstraint(\n            "signal_id",\n            "seconds_since_signal",\n            name="uq_market_observation_signal_time",\n        ),\n    )\n'
)

with open("app/database/models.py", "w") as f:
    f.write(models_content)

run_cmd("Add unique constraint to market observation intervals")

