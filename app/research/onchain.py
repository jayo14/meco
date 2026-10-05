from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
RAYDIUM_V4_PROGRAM_ID = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")


@dataclass
class OnChainSourceReview:
    source_name: str
    data_available: str
    latency_ms: str
    rate_limits: str
    cost_usd: str
    reliability: str
    implementation_complexity: str
    verdict: str


ON_CHAIN_SOURCE_MATRIX: list[OnChainSourceReview] = [
    OnChainSourceReview(
        source_name="Standard Solana RPC (HTTP JSON-RPC)",
        data_available="getSignaturesForAddress, getTransaction, getAccountInfo, getTokenSupply",
        latency_ms="600ms - 1,500ms",
        rate_limits="Strict (10-40 req/s on public RPC; 429 errors under heavy load)",
        cost_usd="$0 (public) / $50-$250/mo (dedicated node)",
        reliability="Medium (public RPC has intermittent rate limits and dropped requests)",
        implementation_complexity="High (requires manual pagination and transaction instruction parsing)",
        verdict="Suitable for ad-hoc point checks and account state polling; unsuitable for full historical transaction backfills across hundreds of tokens without dedicated node.",
    ),
    OnChainSourceReview(
        source_name="Solana RPC WebSocket Subscriptions (WSS)",
        data_available="logsSubscribe, programSubscribe, accountSubscribe, slotSubscribe",
        latency_ms="50ms - 200ms",
        rate_limits="Persistent socket; connection limits apply",
        cost_usd="$0 (public) / $49-$199/mo (dedicated)",
        reliability="High for active stream; vulnerable to silent disconnects without heartbeat",
        implementation_complexity="Medium (requires event loop reconnects and instruction filter)",
        verdict="Best technical approach for real-time pre-signal detection of new pool creations or whale swaps directly from validators.",
    ),
    OnChainSourceReview(
        source_name="Pump.fun Bonding Curve PDA State Polling",
        data_available="Virtual/real SOL & token reserves, curve completion status (151 bytes account data)",
        latency_ms="200ms - 500ms",
        rate_limits="Single getAccountInfo call per token",
        cost_usd="$0",
        reliability="High (deterministic state on-chain, avoids paginating thousands of transaction signatures)",
        implementation_complexity="Low (simple PDA derivation: ['bonding-curve', mint_bytes])",
        verdict="Highly practical for pump.fun tokens: allows instant measurement of pool progress and pre-signal bonding curve state with 1 RPC call.",
    ),
    OnChainSourceReview(
        source_name="DexScreener Token & Pair API (Current Architecture)",
        data_available="DEX pairs, 5m/1h/24h volume, buy/sell transaction counts, liquidity, pairCreatedAt",
        latency_ms="200ms - 400ms",
        rate_limits="300 req/min (generous free tier)",
        cost_usd="$0",
        reliability="High (~98% success rate in Meco audit)",
        implementation_complexity="Low (already fully integrated)",
        verdict="Ideal for signal-time market snapshot and post-signal checkpoint tracking; lacks sub-minute pre-signal candle history.",
    ),
    OnChainSourceReview(
        source_name="Specialized Indexer / Webhook APIs (Helius / Birdeye)",
        data_available="Enriched swap events, whale buy alerts, pre-parsed token creation webhooks, 1m historical OHLCV",
        latency_ms="100ms - 300ms",
        rate_limits="Generous credit-based tiers",
        cost_usd="Free tier (50k credits) / $49-$199/mo",
        reliability="High (managed indexing infrastructure)",
        implementation_complexity="Low / Medium",
        verdict="Recommended when scaling beyond point prototypes into production pre-signal ingestion.",
    ),
]


def derive_pump_bonding_curve(token_address: str) -> Pubkey | None:
    """Derive the deterministic Pump.fun bonding curve PDA for a token mint."""
    try:
        mint = Pubkey.from_string(token_address)
        bonding_curve, _ = Pubkey.find_program_address(
            [b"bonding-curve", bytes(mint)], PUMP_PROGRAM_ID
        )
        return bonding_curve
    except Exception:
        return None


async def inspect_bonding_curve_state(
    token_address: str, client: AsyncClient
) -> dict[str, Any]:
    """Inspect the on-chain bonding curve account for a pump.fun token."""
    bc = derive_pump_bonding_curve(token_address)
    if bc is None:
        return {"exists": False, "reason": "invalid_mint"}

    try:
        resp = await client.get_account_info(bc)
        if resp.value is None:
            return {"exists": False, "bonding_curve_pda": str(bc)}

        data = resp.value.data
        return {
            "exists": True,
            "bonding_curve_pda": str(bc),
            "owner": str(resp.value.owner),
            "lamports": resp.value.lamports,
            "data_len": len(data),
            "is_pump_owned": resp.value.owner == PUMP_PROGRAM_ID,
        }
    except Exception as exc:
        return {"exists": False, "error": str(exc)}
