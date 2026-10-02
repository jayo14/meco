from datetime import datetime

from sqlalchemy import (
    UniqueConstraint,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Telegram
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    # Token
    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    slippage: Mapped[float | None] = mapped_column(Float)

    # Solana
    decimals: Mapped[int | None] = mapped_column(Integer)
    supply: Mapped[int | None] = mapped_column()

    # Initial market observation
    pair_address: Mapped[str | None] = mapped_column(String(128))
    dex_id: Mapped[str | None] = mapped_column(String(64))
    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)
    volume_5m: Mapped[float | None] = mapped_column(Float)
    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)

    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

class MarketObservation(Base):
    __tablename__ = "market_observations"

    __table_args__ = (
        UniqueConstraint(
            "signal_id",
            "seconds_since_signal",
            name="uq_market_observation_signal_time",
        ),
    )

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
