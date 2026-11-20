import asyncio
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.discovery.engine import DiscoveryEngine
from app.discovery.models import (
    ConnectionState,
    NormalizedDiscoveryEvent,
    SourceCapabilities,
    SourceHealthSnapshot,
)
from app.discovery.pumpportal import (
    PumpPortalDiscoveryAdapter,
    parse_pumpportal_message,
)
from app.discovery.solana_rpc import (
    SolanaRpcDiscoveryAdapter,
    extract_mint_from_logs,
    parse_solana_logs_notification,
)
from app.identity.registry import TokenRegistry, is_valid_solana_address
from app.research.onchain import PUMP_PROGRAM_ID
from app.telegram.parser import extract_token_signal


# ==============================================================================
# In-Memory Fake Async Session for Persistence Testing
# ==============================================================================

class FakeAsyncSession:
    """
    Lightweight in-memory async session simulating SQLAlchemy AsyncSession
    for unit testing TokenRegistry and DiscoveryEngine without external PostgreSQL.
    """

    def __init__(self, db_state: dict | None = None) -> None:
        if db_state is None:
            self.db_state = {
                "tokens": {},           # mint -> Token
                "events": [],           # list[DiscoveryEvent]
                "token_sources": {},    # (token_id, source) -> TokenSource
                "checkpoints": {},      # source -> DiscoveryCheckpoint
                "health": {},           # source -> StreamHealth
                "signals": {},          # id -> Signal
            }
        else:
            self.db_state = db_state
        self._next_id = len(self.db_state["tokens"]) + 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def begin(self):
        return self

    def add(self, obj):
        from app.database.models import (
            DiscoveryCheckpoint,
            DiscoveryEvent,
            StreamHealth,
            Token,
            TokenSource,
        )
        if isinstance(obj, Token):
            if not getattr(obj, "id", None):
                obj.id = self._next_id
                self._next_id += 1
            self.db_state["tokens"][obj.mint_address] = obj
        elif isinstance(obj, DiscoveryEvent):
            if not getattr(obj, "id", None):
                obj.id = len(self.db_state["events"]) + 1
            self.db_state["events"].append(obj)
        elif isinstance(obj, TokenSource):
            if not getattr(obj, "id", None):
                obj.id = len(self.db_state["token_sources"]) + 1
            self.db_state["token_sources"][(obj.token_id, obj.source)] = obj
        elif isinstance(obj, DiscoveryCheckpoint):
            if not getattr(obj, "id", None):
                obj.id = len(self.db_state["checkpoints"]) + 1
            self.db_state["checkpoints"][obj.source] = obj
        elif isinstance(obj, StreamHealth):
            if not getattr(obj, "id", None):
                obj.id = len(self.db_state["health"]) + 1
            self.db_state["health"][obj.source] = obj

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        from app.database.models import (
            DiscoveryCheckpoint,
            StreamHealth,
            Token,
            TokenSource,
        )
        # Inspect query entity
        text_str = str(stmt)
        result_mock = MagicMock()

        if "FROM tokens" in text_str or "tokens.mint_address" in text_str:
            # Extract queried mint if present in where clause
            # Look up in in-memory tokens
            items = list(self.db_state["tokens"].values())
            # Simple parameter inspection
            params = stmt.compile().params
            target_mint = None
            for k, v in params.items():
                if "mint_address" in k:
                    target_mint = v
                    break

            if target_mint:
                matched = self.db_state["tokens"].get(target_mint)
                result_mock.scalar_one_or_none.return_value = matched
                result_mock.scalars.return_value.all.return_value = [matched] if matched else []
            else:
                result_mock.scalar_one_or_none.return_value = items[0] if items else None
                result_mock.scalars.return_value.all.return_value = items

        elif "FROM token_sources" in text_str:
            params = stmt.compile().params
            t_id = None
            src = None
            for k, v in params.items():
                if "token_id" in k:
                    t_id = v
                elif "source" in k:
                    src = v
            matched = self.db_state["token_sources"].get((t_id, src))
            result_mock.scalar_one_or_none.return_value = matched
            result_mock.scalars.return_value.all.return_value = [matched] if matched else []

        elif "FROM stream_health" in text_str:
            params = stmt.compile().params
            src = None
            for k, v in params.items():
                if "source" in k:
                    src = v
            matched = self.db_state["health"].get(src)
            result_mock.scalar_one_or_none.return_value = matched
            result_mock.scalars.return_value.all.return_value = list(self.db_state["health"].values())

        elif "FROM discovery_checkpoints" in text_str:
            params = stmt.compile().params
            src = None
            for k, v in params.items():
                if "source" in k:
                    src = v
            matched = self.db_state["checkpoints"].get(src)
            result_mock.scalar_one_or_none.return_value = matched
            result_mock.scalars.return_value.all.return_value = list(self.db_state["checkpoints"].values())
        else:
            result_mock.scalar_one_or_none.return_value = None
            result_mock.scalars.return_value.all.return_value = []

        return result_mock


def create_fake_session_factory(shared_state: dict | None = None):
    state = shared_state if shared_state is not None else {
        "tokens": {},
        "events": [],
        "token_sources": {},
        "checkpoints": {},
        "health": {},
        "signals": {},
    }
    def factory():
        return FakeAsyncSession(state)
    return factory, state


# ==============================================================================
# Unit Tests: Solana Address Validation
# ==============================================================================

def test_is_valid_solana_address():
    valid_pump = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    assert is_valid_solana_address(valid_pump) is True

    valid_sol = "So11111111111111111111111111111111111111112"
    assert is_valid_solana_address(valid_sol) is True

    # Invalid characters (0, O, I, l are forbidden in Base58)
    assert is_valid_solana_address("00000000000000000000000000000000000000000000") is False
    assert is_valid_solana_address("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII") is False

    # Too short / too long
    assert is_valid_solana_address("short") is False
    assert is_valid_solana_address("A" * 50) is False

    # None and empty
    assert is_valid_solana_address(None) is False
    assert is_valid_solana_address("") is False
    assert is_valid_solana_address("   ") is False


# ==============================================================================
# Unit Tests: PumpPortal Parser
# ==============================================================================

def test_parse_pumpportal_valid_event():
    raw = {
        "signature": "3u8dF...txsig",
        "mint": "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        "traderPublicKey": "4wG...wallet",
        "bondingCurveKey": "7bc...curve",
        "vTokensInBondingCurve": 1073000000000000,
        "vSolInBondingCurve": 30000000000,
        "marketCapSol": 30.5,
        "name": "Meco Meme",
        "symbol": "MECO",
        "uri": "https://ipfs.io/ipfs/QmTest",
        "initialBuy": 1000000,
        "timestamp": 1728100000000,  # ms timestamp
    }
    rec_time = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    event = parse_pumpportal_message(raw, received_at=rec_time)

    assert event is not None
    assert event.mint_address == "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    assert event.source == "pumpportal"
    assert event.event_type == "token_created"
    assert event.signature == "3u8dF...txsig"
    assert event.name == "Meco Meme"
    assert event.symbol == "MECO"
    assert event.metadata_uri == "https://ipfs.io/ipfs/QmTest"
    assert event.received_at == rec_time
    assert event.source_timestamp is not None
    assert event.source_metadata["market_cap_sol"] == 30.5
    assert event.source_metadata["bonding_curve_key"] == "7bc...curve"


def test_parse_pumpportal_invalid_payloads():
    # String JSON parsing
    valid_json = json.dumps({"mint": "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"})
    assert parse_pumpportal_message(valid_json) is not None

    # Malformed JSON
    assert parse_pumpportal_message("invalid json {") is None

    # Subscription confirmation message without mint
    assert parse_pumpportal_message({"message": "Successfully subscribed to token creations"}) is None

    # Missing mint
    assert parse_pumpportal_message({"name": "Test", "symbol": "TEST"}) is None

    # Non-dictionary payload
    assert parse_pumpportal_message([1, 2, 3]) is None
    assert parse_pumpportal_message(123) is None


# ==============================================================================
# Unit Tests: Solana RPC Logs Parser
# ==============================================================================

def test_extract_mint_from_logs():
    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"

    # Explicit label
    logs_explicit = [
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
        "Program log: Instruction: Create",
        f"Program log: mint: {valid_mint}",
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
    ]
    assert extract_mint_from_logs(logs_explicit) == valid_mint

    # Vanity mint without explicit prefix
    logs_vanity = [
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
        "Program log: Instruction: Create",
        f"Program log: creating bonding curve for {valid_mint} with cap",
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
    ]
    assert extract_mint_from_logs(logs_vanity) == valid_mint

    # Logs without any valid mint
    logs_none = [
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
        "Program log: Instruction: Create",
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success",
    ]
    assert extract_mint_from_logs(logs_none) is None


def test_parse_solana_logs_notification_valid():
    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    pump_id_str = str(PUMP_PROGRAM_ID)
    msg = {
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "result": {
                "context": {"slot": 298112233},
                "value": {
                    "signature": "5XyZ...txsig",
                    "err": None,
                    "logs": [
                        f"Program {pump_id_str} invoke [1]",
                        "Program log: Instruction: Create",
                        f"Program log: mint: {valid_mint}",
                        f"Program {pump_id_str} success",
                    ],
                },
            },
            "subscription": 42,
        },
    }

    event = parse_solana_logs_notification(msg, commitment="confirmed")
    assert event is not None
    assert event.mint_address == valid_mint
    assert event.source == "solana_rpc"
    assert event.signature == "5XyZ...txsig"
    assert event.slot == 298112233
    assert event.commitment == "confirmed"
    assert event.source_metadata["is_pump_program"] is True


def test_parse_solana_logs_notification_non_create_or_error():
    pump_id_str = str(PUMP_PROGRAM_ID)

    # 1. Non-create (Buy instruction)
    msg_buy = {
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "result": {
                "context": {"slot": 298112233},
                "value": {
                    "signature": "5XyZ...txsig",
                    "err": None,
                    "logs": [
                        f"Program {pump_id_str} invoke [1]",
                        "Program log: Instruction: Buy",
                    ],
                },
            },
        },
    }
    assert parse_solana_logs_notification(msg_buy) is None

    # 2. Transaction with error
    msg_err = {
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "result": {
                "context": {"slot": 298112233},
                "value": {
                    "signature": "5XyZ...txsig",
                    "err": {"InstructionError": [0, "Custom"]},
                    "logs": [
                        f"Program {pump_id_str} invoke [1]",
                        "Program log: Instruction: Create",
                    ],
                },
            },
        },
    }
    assert parse_solana_logs_notification(msg_err) is None

    # 3. Non-notification RPC message (e.g. response to logsSubscribe)
    msg_resp = {"jsonrpc": "2.0", "result": 12345, "id": 1}
    assert parse_solana_logs_notification(msg_resp) is None


# ==============================================================================
# Unit & Integration Tests: Discovery Engine Pipeline & Deduplication
# ==============================================================================

@pytest.mark.asyncio
async def test_discovery_engine_pipeline_new_token():
    session_factory, state = create_fake_session_factory()
    engine = DiscoveryEngine(session_factory=session_factory)

    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    discovered_tokens = []

    async def subscriber(token, event, is_new):
        discovered_tokens.append((token.mint_address, event.source, is_new))

    engine.subscribe_token_discovered(subscriber)

    # Simulate incoming PumpPortal event
    event = NormalizedDiscoveryEvent(
        mint_address=valid_mint,
        source="pumpportal",
        signature="tx_sig_1",
        name="Pump Token",
        symbol="PUMP",
        raw_payload={"test": 123},
    )

    await engine.handle_source_event(event)

    # Verify canonical token was created
    assert valid_mint in state["tokens"]
    token = state["tokens"][valid_mint]
    assert token.name == "Pump Token"
    assert token.first_discovery_source == "pumpportal"

    # Verify discovery event was recorded
    assert len(state["events"]) == 1
    assert state["events"][0].mint_address == valid_mint
    assert state["events"][0].signature == "tx_sig_1"
    assert state["events"][0].is_duplicate is False

    # Verify token source was associated
    assert (token.id, "pumpportal") in state["token_sources"]
    ts = state["token_sources"][(token.id, "pumpportal")]
    assert ts.event_count == 1

    # Verify subscriber was notified
    assert len(discovered_tokens) == 1
    assert discovered_tokens[0] == (valid_mint, "pumpportal", True)


@pytest.mark.asyncio
async def test_multiple_sources_resolve_to_single_canonical_token():
    """
    Test requirement: If PumpPortal and Solana RPC both discover the same mint,
    Meco records two source events and two source associations, but creates only ONE canonical token.
    """
    session_factory, state = create_fake_session_factory()
    engine = DiscoveryEngine(session_factory=session_factory)

    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    discovered_tokens = []

    async def subscriber(token, event, is_new):
        discovered_tokens.append((token.id, event.source, is_new))

    engine.subscribe_token_discovered(subscriber)

    # 1. Event from PumpPortal arrives first
    event_pumpportal = NormalizedDiscoveryEvent(
        mint_address=valid_mint,
        source="pumpportal",
        signature="pumpportal_sig",
        name="Shared Token",
        symbol="SHARED",
    )
    await engine.handle_source_event(event_pumpportal)

    # 2. Event from Solana RPC arrives second for the exact same mint
    event_solana_rpc = NormalizedDiscoveryEvent(
        mint_address=valid_mint,
        source="solana_rpc",
        signature="rpc_sig",
        slot=298000111,
        commitment="confirmed",
    )
    await engine.handle_source_event(event_solana_rpc)

    # Verify only 1 canonical token was created in the registry
    assert len(state["tokens"]) == 1
    token = state["tokens"][valid_mint]
    token_id = token.id

    # Verify 2 distinct discovery events were recorded
    assert len(state["events"]) == 2
    assert state["events"][0].source == "pumpportal"
    assert state["events"][0].is_duplicate is False
    assert state["events"][1].source == "solana_rpc"
    assert state["events"][1].is_duplicate is True  # Second event is flagged as duplicate discovery

    # Verify 2 token source associations exist for this single token
    assert (token_id, "pumpportal") in state["token_sources"]
    assert (token_id, "solana_rpc") in state["token_sources"]
    assert state["token_sources"][(token_id, "pumpportal")].event_count == 1
    assert state["token_sources"][(token_id, "solana_rpc")].event_count == 1

    # Verify subscriber was notified twice: first is_new=True, second is_new=False
    assert len(discovered_tokens) == 2
    assert discovered_tokens[0] == (token_id, "pumpportal", True)
    assert discovered_tokens[1] == (token_id, "solana_rpc", False)


@pytest.mark.asyncio
async def test_discovery_engine_rejects_invalid_mint():
    session_factory, state = create_fake_session_factory()
    engine = DiscoveryEngine(session_factory=session_factory)

    adapter = PumpPortalDiscoveryAdapter()
    engine.register_adapter(adapter)

    # Event with corrupted / non-Base58 mint address
    invalid_event = NormalizedDiscoveryEvent(
        mint_address="000_NOT_A_VALID_SOLANA_MINT_000",
        source="pumpportal",
    )
    await engine.handle_source_event(invalid_event)

    # Verify no tokens or events were created
    assert len(state["tokens"]) == 0
    assert len(state["events"]) == 0
    assert adapter.health.invalid_events == 1


@pytest.mark.asyncio
async def test_discovery_engine_fault_isolation_and_db_error():
    """Verify database exceptions do not crash the engine or halt processing."""
    session_factory, state = create_fake_session_factory()

    # Session that raises database error
    failing_session = MagicMock()
    failing_session.__aenter__.side_effect = RuntimeError("PostgreSQL connection drop")
    failing_factory = MagicMock(return_value=failing_session)

    engine = DiscoveryEngine(session_factory=failing_factory)
    adapter = PumpPortalDiscoveryAdapter()
    engine.register_adapter(adapter)

    event = NormalizedDiscoveryEvent(
        mint_address="6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        source="pumpportal",
    )

    # Should not raise exception
    await engine.handle_source_event(event)
    assert adapter.health.processing_failures == 1


# ==============================================================================
# Unit Tests: Adapter Reconnection & Lifecycle
# ==============================================================================

@pytest.mark.asyncio
async def test_pumpportal_adapter_reconnection_lifecycle(monkeypatch):
    """Verify PumpPortal adapter marks states, connects, and sends subscription once."""
    adapter = PumpPortalDiscoveryAdapter(
        ws_url="wss://pumpportal.fun/api/data",
        reconnect_min_delay=0.01,
        reconnect_max_delay=0.05,
    )
    adapter._running = True

    mock_ws = AsyncMock()
    # First message: valid token; then raise EOF to simulate disconnect
    mock_ws.__aiter__.return_value = [
        json.dumps({"mint": "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump", "txType": "create"}),
    ]
    mock_connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_ws)))
    monkeypatch.setattr("websockets.connect", mock_connect)

    dispatched = []
    adapter.on_event(lambda e: dispatched.append(e.mint_address))

    # Run connect and listen once
    await adapter._connect_and_listen()

    # Check that subscription payload was sent
    mock_ws.send.assert_called_once_with(json.dumps({"method": "subscribeNewToken"}))
    assert len(dispatched) == 1
    assert dispatched[0] == "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    assert adapter.health.status == ConnectionState.DISCONNECTED


@pytest.mark.asyncio
async def test_solana_rpc_adapter_reconnection_lifecycle(monkeypatch):
    """Verify Solana RPC adapter subscribes to logs and detects slot gaps."""
    adapter = SolanaRpcDiscoveryAdapter(
        ws_url="wss://api.mainnet-beta.solana.com",
        commitment="confirmed",
        reconnect_min_delay=0.01,
        reconnect_max_delay=0.05,
    )
    adapter._running = True

    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    pump_id_str = str(PUMP_PROGRAM_ID)

    # Two messages: slot 100 and slot 300 (gap > 100)
    msg1 = json.dumps({
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "result": {
                "context": {"slot": 100},
                "value": {
                    "signature": "sig1",
                    "err": None,
                    "logs": [
                        f"Program {pump_id_str} invoke [1]",
                        "Program log: Instruction: Create",
                        f"Program log: mint: {valid_mint}",
                    ],
                },
            },
        },
    })
    msg2 = json.dumps({
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "result": {
                "context": {"slot": 300},  # gap of 200 slots
                "value": {
                    "signature": "sig2",
                    "err": None,
                    "logs": [],
                },
            },
        },
    })

    mock_ws = AsyncMock()
    mock_ws.__aiter__.return_value = [msg1, msg2]
    mock_connect = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_ws)))
    monkeypatch.setattr("websockets.connect", mock_connect)

    dispatched = []
    adapter.on_event(lambda e: dispatched.append(e.signature))

    await adapter._connect_and_listen()

    # Verify subscription payload was sent
    sub_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [{"mentions": [pump_id_str]}, {"commitment": "confirmed"}],
    }
    mock_ws.send.assert_called_once_with(json.dumps(sub_payload))

    # Verify event was received
    assert len(dispatched) == 1
    assert dispatched[0] == "sig1"

    # Verify slot gap was detected
    assert adapter.slot_gap_count == 1
    assert adapter.last_observed_slot == 300


# ==============================================================================
# Regression Tests: Existing Telegram Pipeline Integration
# ==============================================================================

@pytest.mark.asyncio
async def test_telegram_signal_resolves_to_canonical_token():
    """
    Verify that incoming Telegram signals can be resolved into the canonical
    token registry while preserving full backward compatibility.
    """
    session_factory, state = create_fake_session_factory()

    valid_mint = "B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM"
    text = f"Buy now: CA: {valid_mint}\nSlippage: 15%"
    t_msg = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    t_rec = datetime(2026, 10, 5, 12, 0, 1, tzinfo=timezone.utc)

    # 1. Existing parser extracts signal cleanly
    signal = extract_token_signal(
        text,
        chat_id=-100123,
        message_id=456,
        message_created_at=t_msg,
        received_at=t_rec,
    )
    assert signal is not None
    assert signal.token_address == valid_mint
    assert signal.slippage == 15.0

    # 2. Record through TokenRegistry.record_telegram_signal_discovery
    async with session_factory() as session:
        token = await TokenRegistry.record_telegram_signal_discovery(
            session,
            chat_id=signal.chat_id,
            message_id=signal.message_id,
            message_text=signal.message_text,
            token_address=signal.token_address,
            message_created_at=signal.message_created_at,
            received_at=signal.received_at,
            source_name="Bullish Calls - Solana",
            source_username="bullishcalls",
            decimals=6,
            supply=1000000000,
            validation_status="valid_mint",
        )

    # Verify token exists in registry
    assert token is not None
    assert token.mint_address == valid_mint
    assert token.first_discovery_source == "telegram"
    assert token.verification_status == "valid_mint"
    assert token.decimals == 6

    # Verify discovery event was recorded with source=telegram
    assert len(state["events"]) == 1
    event = state["events"][0]
    assert event.source == "telegram"
    assert event.event_type == "signal_call"
    assert event.source_event_id == "-100123:456"

    # Verify token source association
    assert (token.id, "telegram") in state["token_sources"]
    ts = state["token_sources"][(token.id, "telegram")]
    assert ts.event_count == 1
    assert ts.source_metadata["source_name"] == "Bullish Calls - Solana"


# ==============================================================================
# Additional Tests: Timestamps, Concurrency, Health & Lifecycle
# ==============================================================================

@pytest.mark.asyncio
async def test_timestamp_preservation_and_latency():
    """Verify source_timestamp and received_at are preserved and source latency is recorded."""
    adapter = PumpPortalDiscoveryAdapter()
    dispatched = []
    adapter.on_event(lambda e: dispatched.append(e))

    t_source = datetime(2026, 10, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
    t_meco = datetime(2026, 10, 5, 12, 0, 0, 250000, tzinfo=timezone.utc)  # 250ms latency

    event = NormalizedDiscoveryEvent(
        mint_address="6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        source="pumpportal",
        source_timestamp=t_source,
        received_at=t_meco,
    )

    await adapter.emit_event(event)

    assert len(dispatched) == 1
    assert dispatched[0].source_timestamp == t_source
    assert dispatched[0].received_at == t_meco
    assert adapter.health.last_source_latency_ms == pytest.approx(250.0, rel=1e-2)


@pytest.mark.asyncio
async def test_concurrent_discovery_events():
    """Verify DiscoveryEngine safely handles concurrent bursts of incoming events."""
    session_factory, state = create_fake_session_factory()
    engine = DiscoveryEngine(session_factory=session_factory)

    from solders.keypair import Keypair

    mints = [str(Keypair().pubkey()) for _ in range(10)]

    events = [
        NormalizedDiscoveryEvent(
            mint_address=m,
            source="pumpportal",
            signature=f"sig_{m[:8]}",
            name=f"Token {m[:6]}",
        )
        for m in mints
    ]

    # Process all 10 concurrently
    await asyncio.gather(*(engine.handle_source_event(ev) for ev in events))

    assert len(state["tokens"]) == 10
    assert len(state["events"]) == 10
    assert len(state["token_sources"]) == 10


@pytest.mark.asyncio
async def test_stream_health_and_checkpoint_tracking():
    """Verify TokenRegistry correctly updates stream health metrics and checkpoints."""
    session_factory, state = create_fake_session_factory()

    async with session_factory() as session:
        # 1. Update stream health
        t_conn = datetime.now(timezone.utc)
        h = await TokenRegistry.upsert_stream_health(
            session,
            source="pumpportal",
            status="connected",
            last_connected_at=t_conn,
            events_received_increment=5,
            valid_events_increment=4,
            invalid_events_increment=1,
            new_tokens_increment=3,
            duplicate_events_increment=1,
            last_processing_latency_ms=12.5,
        )
        assert h.status == "connected"
        assert h.events_received == 5
        assert h.valid_events == 4
        assert h.invalid_events == 1
        assert h.new_tokens_count == 3
        assert h.duplicate_events == 1
        assert h.last_processing_latency_ms == 12.5

        # 2. Update checkpoint
        cp = await TokenRegistry.update_checkpoint(
            session,
            source="solana_rpc",
            last_signature="signature_checkpoint_123",
            last_slot=298500100,
        )
        assert cp.source == "solana_rpc"
        assert cp.last_signature == "signature_checkpoint_123"
        assert cp.last_slot == 298500100


@pytest.mark.asyncio
async def test_adapter_start_stop_clean_lifecycle():
    """Verify adapter start and stop background task lifecycle."""
    adapter = PumpPortalDiscoveryAdapter(
        ws_url="wss://pumpportal.fun/api/data",
        reconnect_min_delay=0.01,
        reconnect_max_delay=0.02,
    )

    # Mock _connect_and_listen to sleep
    async def mock_listen():
        while adapter.is_running:
            await asyncio.sleep(0.01)

    adapter._connect_and_listen = mock_listen

    await adapter.start()
    assert adapter.is_running is True
    assert adapter._task is not None

    await asyncio.sleep(0.03)

    await adapter.stop()
    assert adapter.is_running is False
    assert adapter.health.status == ConnectionState.STOPPED

