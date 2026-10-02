from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
    message_created_at: Mapped[datetime] = mapped_column(
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
    )

    validation_status: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
    )

    source_name: Mapped[str | None] = mapped_column(String(255))
    source_username: Mapped[str | None] = mapped_column(String(255))

    # Token
    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    slippage: Mapped[float | None] = mapped_column(Float)

    # Solana
    decimals: Mapped[int | None] = mapped_column(Integer)
    supply: Mapped[int | None] = mapped_column(BigInteger)

    # Initial market observation
    pair_address: Mapped[str | None] = mapped_column(String(128))
    dex_id: Mapped[str | None] = mapped_column(String(64))

    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)

    volume_5m: Mapped[float | None] = mapped_column(Float)
    volume_1h: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)

    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)

    price_change_5m: Mapped[float | None] = mapped_column(Float)
    price_change_1h: Mapped[float | None] = mapped_column(Float)
    price_change_24h: Mapped[float | None] = mapped_column(Float)

    market_cap: Mapped[float | None] = mapped_column(Float)
    fdv: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

class MarketObservation(Base):
    __tablename__ = "market_observations"

    __table_args__ = (
        UniqueConstraint(
            "signal_id",
            "target_seconds",
            name="uq_market_observation_signal_target",
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

    pair_address: Mapped[str | None] = mapped_column(
        String(128),
    )

    dex_id: Mapped[str | None] = mapped_column(
        String(64),
    )

    observation_status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        default="success",
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    target_seconds: Mapped[int] = mapped_column(Integer)

    seconds_since_signal: Mapped[int] = mapped_column(Integer)

    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)

    volume_5m: Mapped[float | None] = mapped_column(Float)

    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)

    price_change_5m: Mapped[float | None] = mapped_column(Float)

class MarketPairObservation(Base):
    __tablename__ = "market_pair_observations"

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

    target_seconds: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    seconds_since_signal: Mapped[int] = mapped_column(Integer)

    pair_address: Mapped[str] = mapped_column(
        String(128),
        index=True,
    )

    dex_id: Mapped[str] = mapped_column(String(64))

    url: Mapped[str | None] = mapped_column(Text)

    base_token_address: Mapped[str | None] = mapped_column(
        String(64),
    )

    base_token_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    base_token_symbol: Mapped[str | None] = mapped_column(
        String(64),
    )

    quote_token_address: Mapped[str | None] = mapped_column(
        String(64),
    )

    quote_token_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    quote_token_symbol: Mapped[str | None] = mapped_column(
        String(64),
    )

    price_native: Mapped[float | None] = mapped_column(Float)
    price_usd: Mapped[float | None] = mapped_column(Float)

    liquidity_usd: Mapped[float | None] = mapped_column(Float)

    volume_5m: Mapped[float | None] = mapped_column(Float)
    volume_1h: Mapped[float | None] = mapped_column(Float)
    volume_6h: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)

    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)

    price_change_5m: Mapped[float | None] = mapped_column(Float)
    price_change_1h: Mapped[float | None] = mapped_column(Float)
    price_change_6h: Mapped[float | None] = mapped_column(Float)
    price_change_24h: Mapped[float | None] = mapped_column(Float)

    market_cap: Mapped[float | None] = mapped_column(Float)
    fdv: Mapped[float | None] = mapped_column(Float)

    pair_created_at: Mapped[int | None] = mapped_column(BigInteger)
