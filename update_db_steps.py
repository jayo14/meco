import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# Step 1. Update app/database/models.py
with open("app/database/models.py", "r") as f:
    content = f.read()

imports_target = "from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text"
imports_replacement = """from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)"""
content = content.replace(imports_target, imports_replacement)

observation_model = """
class MarketObservation(Base):
    __tablename__ = "market_observations"

    id: Mapped[int] = mapped_column(primary_key=True)

    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id"),
        index=True,
    )

    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    seconds_since_signal: Mapped[int] = mapped_column(Integer)

    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)

    volume_5m: Mapped[float | None] = mapped_column(Float)

    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)

    price_change_5m: Mapped[float | None] = mapped_column(Float)
"""
content += observation_model

with open("app/database/models.py", "w") as f:
    f.write(content)

run_cmd("Add MarketObservation to database models")

# Step 3. Create observation_repository.py
obs_repo = """from datetime import datetime, timezone

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
"""
with open("app/database/observation_repository.py", "w") as f:
    f.write(obs_repo)

run_cmd("Create observation repository")
