from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class SourceCapabilities:
    source_name: str
    can_stream_realtime: bool = True
    provides_transaction_signature: bool = True
    provides_slot: bool = False
    provides_metadata: bool = False
    supports_catchup_replay: bool = False
    supported_event_types: list[str] = field(default_factory=lambda: ["token_created"])


@dataclass(frozen=True)
class NormalizedDiscoveryEvent:
    mint_address: str
    source: str
    event_type: str = "token_created"
    source_event_id: str | None = None
    signature: str | None = None
    slot: int | None = None
    commitment: str | None = None
    source_timestamp: datetime | None = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any] = field(default_factory=dict)

    # Optional initial metadata extracted from source
    name: str | None = None
    symbol: str | None = None
    decimals: int | None = None
    total_supply: int | None = None
    metadata_uri: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceHealthSnapshot:
    source: str
    status: ConnectionState
    last_connected_at: datetime | None = None
    last_disconnected_at: datetime | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    reconnect_count: int = 0
    events_received: int = 0
    valid_events: int = 0
    invalid_events: int = 0
    duplicate_events: int = 0
    new_tokens_count: int = 0
    processing_failures: int = 0
    last_processing_latency_ms: float | None = None
    last_source_latency_ms: float | None = None
