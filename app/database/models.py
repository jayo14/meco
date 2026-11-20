from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    mint_address: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    symbol: Mapped[str | None] = mapped_column(String(64))
    decimals: Mapped[int | None] = mapped_column(Integer)
    total_supply: Mapped[int | None] = mapped_column(BigInteger)

    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    first_discovery_source: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(32),
        default="unverified",
        index=True,
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(32),
        default="discovered",
        index=True,
    )
    risk_score: Mapped[float | None] = mapped_column(Float)
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    metadata_uri: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    discovery_events: Mapped[list["DiscoveryEvent"]] = relationship(
        "DiscoveryEvent",
        back_populates="token",
        cascade="all, delete-orphan",
    )
    sources: Mapped[list["TokenSource"]] = relationship(
        "TokenSource",
        back_populates="token",
        cascade="all, delete-orphan",
    )
    security_profile: Mapped["TokenSecurityProfile | None"] = relationship(
        "TokenSecurityProfile",
        back_populates="token",
        uselist=False,
        cascade="all, delete-orphan",
    )
    metadata_record: Mapped["TokenMetadataRecord | None"] = relationship(
        "TokenMetadataRecord",
        back_populates="token",
        uselist=False,
        cascade="all, delete-orphan",
    )
    holder_snapshots: Mapped[list["TokenHolderSnapshot"]] = relationship(
        "TokenHolderSnapshot",
        back_populates="token",
        cascade="all, delete-orphan",
    )
    market_snapshots: Mapped[list["TokenMarketSnapshot"]] = relationship(
        "TokenMarketSnapshot",
        back_populates="token",
        cascade="all, delete-orphan",
    )
    lifecycle_events: Mapped[list["TokenLifecycleEvent"]] = relationship(
        "TokenLifecycleEvent",
        back_populates="token",
        cascade="all, delete-orphan",
    )
    enrichment_tasks: Mapped[list["EnrichmentTask"]] = relationship(
        "EnrichmentTask",
        back_populates="token",
        cascade="all, delete-orphan",
    )


class DiscoveryEvent(Base):
    __tablename__ = "discovery_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    token_id: Mapped[int | None] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
        default="token_created",
    )
    source_event_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    signature: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
    )
    slot: Mapped[int | None] = mapped_column(BigInteger)
    commitment: Mapped[str | None] = mapped_column(String(32))

    source_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token | None] = relationship(
        "Token",
        back_populates="discovery_events",
    )


class TokenSource(Base):
    __tablename__ = "token_sources"

    __table_args__ = (
        UniqueConstraint("token_id", "source", name="uq_token_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    event_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )
    source_metadata: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="sources",
    )


class DiscoveryCheckpoint(Base):
    __tablename__ = "discovery_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    last_signature: Mapped[str | None] = mapped_column(String(128))
    last_slot: Mapped[int | None] = mapped_column(BigInteger)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StreamHealth(Base):
    __tablename__ = "stream_health"

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="disconnected",
        index=True,
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    reconnect_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    events_received: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    valid_events: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    invalid_events: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    duplicate_events: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    new_tokens_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    processing_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    last_processing_latency_ms: Mapped[float | None] = mapped_column(Float)
    last_source_latency_ms: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class EnrichmentTask(Base):
    __tablename__ = "enrichment_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=10,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    lock_token: Mapped[str | None] = mapped_column(String(64))
    lock_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="enrichment_tasks",
    )


class TokenSecurityProfile(Base):
    __tablename__ = "token_security_profiles"

    __table_args__ = (
        UniqueConstraint("token_id", name="uq_security_token_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        unique=True,
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    token_program: Mapped[str] = mapped_column(String(64))
    mint_authority: Mapped[str | None] = mapped_column(String(64))
    is_mintable: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_authority: Mapped[str | None] = mapped_column(String(64))
    is_freezable: Mapped[bool] = mapped_column(Boolean, default=False)
    permanent_delegate: Mapped[str | None] = mapped_column(String(64))
    metadata_update_authority: Mapped[str | None] = mapped_column(String(64))
    is_mutable: Mapped[bool | None] = mapped_column(Boolean)
    has_transfer_fee: Mapped[bool] = mapped_column(Boolean, default=False)
    transfer_fee_basis_points: Mapped[int | None] = mapped_column(Integer)
    is_lp_burned_or_locked: Mapped[bool | None] = mapped_column(Boolean)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_factors: Mapped[list | None] = mapped_column(JSON)
    verified_facts: Mapped[list | None] = mapped_column(JSON)
    raw_onchain_data: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="security_profile",
    )


class TokenMetadataRecord(Base):
    __tablename__ = "token_metadata_records"

    __table_args__ = (
        UniqueConstraint("token_id", name="uq_metadata_token_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        unique=True,
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    symbol: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    image_uri: Mapped[str | None] = mapped_column(Text)
    metadata_uri: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    telegram: Mapped[str | None] = mapped_column(String(255))
    twitter: Mapped[str | None] = mapped_column(String(255))
    discord: Mapped[str | None] = mapped_column(String(255))
    launchpad: Mapped[str | None] = mapped_column(String(64))
    is_uri_fetched: Mapped[bool] = mapped_column(Boolean, default=False)
    uri_fetch_error: Mapped[str | None] = mapped_column(Text)
    raw_offchain_metadata: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="metadata_record",
    )


class TokenHolderSnapshot(Base):
    __tablename__ = "token_holder_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    total_holders_count: Mapped[int | None] = mapped_column(Integer)
    top10_concentration_pct: Mapped[float | None] = mapped_column(Float)
    top20_concentration_pct: Mapped[float | None] = mapped_column(Float)
    deployer_address: Mapped[str | None] = mapped_column(String(64))
    deployer_holding_pct: Mapped[float | None] = mapped_column(Float)
    top_holders: Mapped[list | None] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="holder_snapshots",
    )


class TokenMarketSnapshot(Base):
    __tablename__ = "token_market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    primary_pair_address: Mapped[str | None] = mapped_column(String(128))
    primary_dex_id: Mapped[str | None] = mapped_column(String(64))
    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    fdv: Mapped[float | None] = mapped_column(Float)
    volume_5m: Mapped[float | None] = mapped_column(Float)
    volume_1h: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)
    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)
    price_change_5m: Mapped[float | None] = mapped_column(Float)
    price_change_1h: Mapped[float | None] = mapped_column(Float)
    price_change_24h: Mapped[float | None] = mapped_column(Float)
    pairs_count: Mapped[int] = mapped_column(Integer, default=1)
    earliest_pair_created_at: Mapped[int | None] = mapped_column(BigInteger)
    pool_age_seconds: Mapped[int | None] = mapped_column(Integer)
    pairs_data: Mapped[list | None] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="market_snapshots",
    )


class TokenLifecycleEvent(Base):
    __tablename__ = "token_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("tokens.id"),
        index=True,
    )
    mint_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )

    token: Mapped[Token] = relationship(
        "Token",
        back_populates="lifecycle_events",
    )
