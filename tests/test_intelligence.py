import struct
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import (
    EnrichmentTask,
    Token,
    TokenHolderSnapshot,
    TokenLifecycleEvent,
    TokenMarketSnapshot,
    TokenMetadataRecord,
    TokenSecurityProfile,
)
from app.intelligence.holders import (
    HolderEntry,
    capture_token_holder_snapshot,
)
from app.intelligence.lifecycle import (
    TokenLifecycleState,
    transition_lifecycle,
)
from app.intelligence.liquidity import (
    capture_token_liquidity_snapshot,
)
from app.intelligence.metadata import (
    extract_social_links,
    fetch_offchain_metadata,
    normalize_metadata_uri,
    sanitize_text,
)
from app.intelligence.orchestrator import (
    EnrichmentTaskQueue,
)
from app.intelligence.profile import (
    build_token_intelligence_profile,
)
from app.intelligence.security import (
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    calculate_security_score,
    decode_mint_account_data,
)
from app.market.dexscreener import MarketPair
from tests.test_discovery import create_fake_session_factory

# ==============================================================================
# Helper to build mock binary mint account data
# ==============================================================================

def pack_mock_mint_account(
    mint_auth: str | None = None,
    supply: int = 1_000_000_000,
    decimals: int = 6,
    is_init: bool = True,
    freeze_auth: str | None = None,
    permanent_delegate: str | None = None,
    transfer_fee_bp: int | None = None,
) -> bytes:
    from solders.pubkey import Pubkey

    # 1. Base SPL Mint (82 bytes)
    mint_auth_opt = 1 if mint_auth else 0
    mint_auth_bytes = bytes(Pubkey.from_string(mint_auth)) if mint_auth else (b"\x00" * 32)

    freeze_auth_opt = 1 if freeze_auth else 0
    freeze_auth_bytes = bytes(Pubkey.from_string(freeze_auth)) if freeze_auth else (b"\x00" * 32)

    base = struct.pack(
        "<I32sQBB I32s",
        mint_auth_opt,
        mint_auth_bytes,
        supply,
        decimals,
        1 if is_init else 0,
        freeze_auth_opt,
        freeze_auth_bytes,
    )

    # 2. Token-2022 TLV Extensions (if requested)
    ext = b""
    if transfer_fee_bp is not None:
        # Type 1 = TransferFeeConfig, len = 12
        # offset 8 has u16 transfer_fee_basis_points
        fee_data = b"\x00" * 8 + struct.pack("<H", transfer_fee_bp) + b"\x00" * 2
        ext += struct.pack("<HH", 1, len(fee_data)) + fee_data

    if permanent_delegate is not None:
        # Type 13 = PermanentDelegate, len = 32
        del_bytes = bytes(Pubkey.from_string(permanent_delegate))
        ext += struct.pack("<HH", 13, len(del_bytes)) + del_bytes

    return base + ext


# ==============================================================================
# Unit Tests: Metadata Sanitization, URI Normalization & Off-Chain Fetch
# ==============================================================================

def test_metadata_uri_normalization():
    assert normalize_metadata_uri("ipfs://QmHash123") == "https://ipfs.io/ipfs/QmHash123"
    assert normalize_metadata_uri("ar://TxId456") == "https://arweave.net/TxId456"
    assert normalize_metadata_uri("https://example.com/meta.json") == "https://example.com/meta.json"
    assert normalize_metadata_uri(None) is None
    assert normalize_metadata_uri("") is None


def test_sanitize_text():
    assert sanitize_text("  Valid Name  ", 10) == "Valid Name"
    assert sanitize_text("Long text exceeding maximum allowed length", 10) == "Long text "
    assert sanitize_text(None) is None
    assert sanitize_text("   ") is None


def test_extract_social_links():
    # 1. Metaplex extensions
    data1 = {
        "name": "Token",
        "extensions": {
            "website": "https://token.io",
            "twitter": "https://x.com/token",
            "telegram": "https://t.me/token",
            "discord": "https://discord.gg/token",
        },
    }
    s1 = extract_social_links(data1)
    assert s1["website"] == "https://token.io"
    assert s1["twitter"] == "https://x.com/token"
    assert s1["telegram"] == "https://t.me/token"
    assert s1["discord"] == "https://discord.gg/token"

    # 2. Root fields
    data2 = {
        "external_url": "https://mytoken.xyz",
        "twitter_url": "https://twitter.com/mytoken",
        "tg": "https://t.me/mytoken",
    }
    s2 = extract_social_links(data2)
    assert s2["website"] == "https://mytoken.xyz"
    assert s2["twitter"] == "https://twitter.com/mytoken"
    assert s2["telegram"] == "https://t.me/mytoken"
    assert s2["discord"] is None


@pytest.mark.asyncio
async def test_fetch_offchain_metadata_handling(monkeypatch):
    # 1. Unsupported URI scheme
    data, err = await fetch_offchain_metadata("ftp://evil.com/meta.json")
    assert data is None
    assert "unsupported_scheme" in err

    # 2. Mock HTTP 200 with valid JSON
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"name": "Meco Meme", "symbol": "MECO", "image": "https://test.io/img.png"}'
    mock_resp.json.return_value = {"name": "Meco Meme", "symbol": "MECO", "image": "https://test.io/img.png"}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client))

    data, err = await fetch_offchain_metadata("https://example.com/meta.json")
    assert err is None
    assert data["name"] == "Meco Meme"
    assert data["symbol"] == "MECO"

    # 3. Payload exceeding max bytes
    mock_resp.content = b"x" * (300 * 1024)  # 300 KB > 256 KB
    data, err = await fetch_offchain_metadata("https://example.com/huge.json")
    assert data is None
    assert err == "payload_exceeded_max_bytes"


# ==============================================================================
# Unit Tests: Authority & Security Audit
# ==============================================================================

def test_decode_mint_account_revoked_authorities():
    """Mint with revoked mint and freeze authority (clean safe token)."""
    raw_data = pack_mock_mint_account(mint_auth=None, freeze_auth=None, supply=1_000_000_000, decimals=6)
    sec = decode_mint_account_data(raw_data, owner_program=TOKEN_PROGRAM_ID)

    assert sec is not None
    assert sec.is_mintable is False
    assert sec.mint_authority is None
    assert sec.is_freezable is False
    assert sec.freeze_authority is None
    assert sec.supply == 1_000_000_000
    assert sec.decimals == 6
    assert sec.permanent_delegate is None
    assert sec.has_transfer_fee is False

    score, risk_factors, facts = calculate_security_score(sec)
    assert score == 0.0
    assert len(risk_factors) == 0
    assert "Freeze authority is REVOKED" in facts[2]
    assert "Mint authority is REVOKED" in facts[3]


def test_decode_mint_account_active_freeze_and_mint():
    """Mint with active freeze and mint authority (high risk honeypot candidate)."""
    fake_auth = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    raw_data = pack_mock_mint_account(mint_auth=fake_auth, freeze_auth=fake_auth)
    sec = decode_mint_account_data(raw_data, owner_program=TOKEN_PROGRAM_ID)

    assert sec is not None
    assert sec.is_mintable is True
    assert sec.mint_authority == fake_auth
    assert sec.is_freezable is True
    assert sec.freeze_authority == fake_auth

    score, risk_factors, _facts = calculate_security_score(sec)
    assert score == 75.0  # 45 (freeze) + 30 (mint)
    assert len(risk_factors) == 2
    assert any(rf["factor"] == "active_freeze_authority" for rf in risk_factors)
    assert any(rf["factor"] == "active_mint_authority" for rf in risk_factors)


def test_decode_token_2022_permanent_delegate_and_tax():
    """Token-2022 with permanent delegate and custom transfer tax."""
    fake_delegate = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    raw_data = pack_mock_mint_account(
        mint_auth=None,
        freeze_auth=None,
        permanent_delegate=fake_delegate,
        transfer_fee_bp=500,  # 5.0% fee
    )
    sec = decode_mint_account_data(raw_data, owner_program=TOKEN_2022_PROGRAM_ID)

    assert sec is not None
    assert sec.permanent_delegate == fake_delegate
    assert sec.has_transfer_fee is True
    assert sec.transfer_fee_basis_points == 500

    score, risk_factors, _ = calculate_security_score(sec)
    assert score == 75.0  # 50 (perm delegate) + 25 (5% fee)
    assert any(rf["factor"] == "permanent_delegate_enabled" for rf in risk_factors)
    assert any(rf["factor"] == "transfer_fee_enabled" for rf in risk_factors)


# ==============================================================================
# Unit Tests: Liquidity and Multi-Pool Intelligence
# ==============================================================================

@pytest.mark.asyncio
async def test_capture_token_liquidity_multiple_pools():
    session_factory, state = create_fake_session_factory()

    token = Token(
        id=1,
        mint_address="6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        name="Multi Pool Token",
        first_discovered_at=datetime.now(timezone.utc),
        first_discovery_source="pumpportal",
    )
    state["tokens"][token.mint_address] = token

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # 3 mock pairs across PumpSwap, Raydium, and Meteora
    pair1 = MarketPair(
        pair_address="pair_pumpswap",
        dex_id="pumpswap",
        url="https://dexscreener.com/solana/pair_pumpswap",
        base_token_address=token.mint_address,
        base_token_name="Multi Pool Token",
        base_token_symbol="MPT",
        quote_token_address="So11111111111111111111111111111111111111112",
        quote_token_name="SOL",
        quote_token_symbol="SOL",
        price_native=0.0001,
        price_usd=0.015,
        liquidity_usd=12000.0,
        volume_m5=500.0,
        volume_h1=2000.0,
        volume_h6=5000.0,
        volume_h24=10000.0,
        buys_m5=20,
        sells_m5=15,
        price_change_m5=5.0,
        price_change_h1=10.0,
        price_change_h6=None,
        price_change_h24=None,
        market_cap=15000.0,
        fdv=15000.0,
        pair_created_at=now_ms - 600_000,  # 10 min ago (earliest)
    )

    pair2 = MarketPair(
        pair_address="pair_raydium",
        dex_id="raydium",
        url="https://dexscreener.com/solana/pair_raydium",
        base_token_address=token.mint_address,
        base_token_name="Multi Pool Token",
        base_token_symbol="MPT",
        quote_token_address="So11111111111111111111111111111111111111112",
        quote_token_name="SOL",
        quote_token_symbol="SOL",
        price_native=0.00012,
        price_usd=0.018,
        liquidity_usd=55000.0,  # Highest liquidity -> Primary
        volume_m5=2500.0,
        volume_h1=8000.0,
        volume_h6=12000.0,
        volume_h24=25000.0,
        buys_m5=85,
        sells_m5=30,
        price_change_m5=8.0,
        price_change_h1=12.0,
        price_change_h6=None,
        price_change_h24=None,
        market_cap=18000.0,
        fdv=18000.0,
        pair_created_at=now_ms - 120_000,  # 2 min ago
    )

    async with session_factory() as session:
        snapshot = await capture_token_liquidity_snapshot(
            session,
            token=token,
            pairs_override=[pair1, pair2],
        )

    assert snapshot is not None
    assert snapshot.pairs_count == 2
    assert snapshot.primary_pair_address == "pair_raydium"
    assert snapshot.primary_dex_id == "raydium"
    assert snapshot.liquidity_usd == 55000.0
    assert snapshot.earliest_pair_created_at == now_ms - 600_000
    assert snapshot.pool_age_seconds >= 600
    assert len(snapshot.pairs_data) == 2


@pytest.mark.asyncio
async def test_capture_token_liquidity_missing_pools():
    session_factory, state = create_fake_session_factory()
    token = Token(
        id=2,
        mint_address="UnpooledToken111111111111111111111111111111111",
        first_discovered_at=datetime.now(timezone.utc),
        first_discovery_source="pumpportal",
    )
    state["tokens"][token.mint_address] = token

    async with session_factory() as session:
        snapshot = await capture_token_liquidity_snapshot(
            session,
            token=token,
            pairs_override=[],
        )

    assert snapshot.pairs_count == 0
    assert snapshot.primary_pair_address is None
    assert snapshot.primary_dex_id is None
    assert snapshot.liquidity_usd is None
    assert snapshot.pool_age_seconds is None


# ==============================================================================
# Unit Tests: Holder Concentration Analysis
# ==============================================================================

@pytest.mark.asyncio
async def test_capture_token_holder_snapshot_concentration():
    session_factory, state = create_fake_session_factory()
    token = Token(
        id=3,
        mint_address="6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        total_supply=1_000_000_000,
        first_discovered_at=datetime.now(timezone.utc),
        first_discovery_source="pumpportal",
    )
    state["tokens"][token.mint_address] = token

    deployer = "DeployerWallet1111111111111111111111111111111"
    mock_holders = [
        HolderEntry("BondingCurvePool1111111111111111111111111111", 500_000_000, 6, 500.0, 50.0, True),
        HolderEntry(deployer, 150_000_000, 6, 150.0, 15.0, False),
        HolderEntry("Whale111111111111111111111111111111111111111", 80_000_000, 6, 80.0, 8.0, False),
        HolderEntry("Whale222222222222222222222222222222222222222", 50_000_000, 6, 50.0, 5.0, False),
    ]

    async with session_factory() as session:
        snap = await capture_token_holder_snapshot(
            session,
            token=token,
            deployer_address=deployer,
            entries_override=mock_holders,
        )

    assert snap is not None
    assert snap.total_holders_count == 4
    assert snap.top10_concentration_pct == pytest.approx(78.0)
    assert snap.deployer_address == deployer
    assert snap.deployer_holding_pct == 15.0
    assert len(snap.top_holders) == 4


# ==============================================================================
# Unit Tests: Durable Task Queue, Deduplication & Restart Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_enrichment_task_queue_deduplication():
    session_factory, _state = create_fake_session_factory()
    queue = EnrichmentTaskQueue(session_factory=session_factory)

    async with session_factory() as session:
        # Schedule first task
        t1 = await queue.schedule_task(
            session,
            token_id=1,
            mint_address="MintA",
            task_type="initial_enrichment",
            priority=20,
        )

        # Attempt to schedule second duplicate task of same type
        t2 = await queue.schedule_task(
            session,
            token_id=1,
            mint_address="MintA",
            task_type="initial_enrichment",
            priority=10,
        )

    assert t1.id == t2.id  # Same task deduplicated


@pytest.mark.asyncio
async def test_enrichment_task_queue_lease_and_restart_recovery():
    """Verify worker lease timeout recovery on restart."""
    session_factory, state = create_fake_session_factory()
    queue = EnrichmentTaskQueue(session_factory=session_factory, lease_duration_seconds=60)

    now = datetime.now(timezone.utc)

    # Simulate task that crashed while running 5 minutes ago (lease expired)
    expired_task = EnrichmentTask(
        id=99,
        token_id=1,
        mint_address="MintA",
        task_type="initial_enrichment",
        status="running",
        priority=10,
        scheduled_at=now - timedelta(minutes=10),
        started_at=now - timedelta(minutes=5),
        lock_token="dead_worker",
        lock_expires_at=now - timedelta(minutes=3),  # Expired lease
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=5),
    )
    # Store in state
    state.setdefault("enrichment_tasks", {})[expired_task.id] = expired_task

    # New worker acquires task
    async with session_factory() as session:
        # Provide query support in mock session for enrichment_tasks
        def mock_execute(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = expired_task
            return m
        session.execute = AsyncMock(side_effect=mock_execute)

        leased = await queue.acquire_next_task(session, "new_worker_1")

    assert leased is not None
    assert leased.id == 99
    assert leased.status == "running"
    assert leased.lock_token == "new_worker_1"
    assert leased.lock_expires_at > now


# ==============================================================================
# Unit Tests: Lifecycle State Machine Transitions
# ==============================================================================

@pytest.mark.asyncio
async def test_lifecycle_state_transitions():
    session_factory, state = create_fake_session_factory()

    token = Token(
        id=1,
        mint_address="6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        lifecycle_state="discovered",
        first_discovered_at=datetime.now(timezone.utc),
        first_discovery_source="pumpportal",
    )
    state["tokens"][token.mint_address] = token

    async with session_factory() as session:
        # Transition 1: Discovered -> Liquidity Detected
        ev1 = await transition_lifecycle(
            session,
            token=token,
            to_state=TokenLifecycleState.LIQUIDITY_DETECTED,
            reason="DexScreener found liquid pool",
        )
        assert token.lifecycle_state == "liquidity_detected"
        assert ev1.from_state == "discovered"
        assert ev1.to_state == "liquidity_detected"

        # Transition 2: Liquidity Detected -> Trading Active
        ev2 = await transition_lifecycle(
            session,
            token=token,
            to_state=TokenLifecycleState.TRADING_ACTIVE,
            reason="Volume > $1,000 in 5m",
        )
        assert token.lifecycle_state == "trading_active"
        assert ev2.from_state == "liquidity_detected"
        assert ev2.to_state == "trading_active"

        # Transition 3: Flagged Suspicious
        ev3 = await transition_lifecycle(
            session,
            token=token,
            to_state=TokenLifecycleState.SUSPICIOUS,
            reason="Active freeze authority detected",
        )
        assert token.lifecycle_state == "suspicious"
        assert ev3.to_state == "suspicious"


# ==============================================================================
# Integration Test: Token Intelligence Profile Assembly with Provenance
# ==============================================================================

@pytest.mark.asyncio
async def test_consolidated_token_intelligence_profile_assembly():
    session_factory, state = create_fake_session_factory()

    mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    now = datetime.now(timezone.utc)

    token = Token(
        id=1,
        mint_address=mint,
        name="Consolidated Token",
        symbol="CTOKEN",
        decimals=6,
        total_supply=1_000_000_000,
        lifecycle_state="trading_active",
        risk_score=15.0,
        first_discovered_at=now,
        first_discovery_source="pumpportal",
        last_enriched_at=now,
    )
    state["tokens"][mint] = token

    # Mock full selectinload return in fake session
    token.discovery_events = []
    token.sources = []
    token.security_profile = TokenSecurityProfile(
        id=1,
        token_id=1,
        mint_address=mint,
        token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        mint_authority=None,
        is_mintable=False,
        freeze_authority=None,
        is_freezable=False,
        permanent_delegate=None,
        has_transfer_fee=False,
        risk_score=15.0,
        risk_factors=[{"factor": "low_liquidity", "severity": "medium", "evidence": "Pool < $20k"}],
        verified_facts=["Freeze authority REVOKED"],
        updated_at=now,
    )
    token.metadata_record = TokenMetadataRecord(
        id=1,
        token_id=1,
        mint_address=mint,
        name="Consolidated Token",
        symbol="CTOKEN",
        description="Official Test Token",
        website="https://test.io",
        twitter="https://x.com/test",
        is_uri_fetched=True,
        updated_at=now,
    )
    token.holder_snapshots = [
        TokenHolderSnapshot(
            id=1,
            token_id=1,
            mint_address=mint,
            total_holders_count=25,
            top10_concentration_pct=65.5,
            top20_concentration_pct=82.0,
            observed_at=now,
            created_at=now,
        )
    ]
    token.market_snapshots = [
        TokenMarketSnapshot(
            id=1,
            token_id=1,
            mint_address=mint,
            primary_pair_address="pair_123",
            primary_dex_id="raydium",
            price_usd=0.025,
            liquidity_usd=45000.0,
            volume_5m=1200.0,
            pairs_count=1,
            observed_at=now,
            created_at=now,
        )
    ]
    token.lifecycle_events = [
        TokenLifecycleEvent(
            id=1,
            token_id=1,
            mint_address=mint,
            from_state="discovered",
            to_state="trading_active",
            reason="Liquid pair found",
            occurred_at=now,
        )
    ]
    token.enrichment_tasks = []

    async with session_factory() as session:
        # Mock session.execute to return token on select(Token)
        async def mock_exec(stmt):
            m = MagicMock()
            m.scalar_one_or_none.return_value = token
            return m
        session.execute = AsyncMock(side_effect=mock_exec)

        profile = await build_token_intelligence_profile(session, mint)

    assert profile is not None
    assert profile.mint_address == mint
    assert profile.name == "Consolidated Token"
    assert profile.symbol == "CTOKEN"
    assert profile.lifecycle_state == "trading_active"
    assert profile.risk_score == 15.0

    # Verify provenance on metadata, security, and liquidity findings
    assert profile.metadata["website"] == "https://test.io"
    assert profile.metadata["provenance"]["source"] == "metadata_resolver"

    assert profile.security["token_program"] == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    assert profile.security["provenance"]["source"] == "solana_rpc_mint_decode"

    assert profile.liquidity["liquidity_usd"] == 45000.0
    assert profile.liquidity["provenance"]["source"] == "dexscreener_snapshot"

    assert profile.holders["top10_concentration_pct"] == 65.5
    assert profile.holders["provenance"]["source"] == "solana_rpc_token_largest_accounts"

    profile_dict = profile.to_dict()
    assert isinstance(profile_dict, dict)
    assert profile_dict["mint_address"] == mint
