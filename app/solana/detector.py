import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import struct
from typing import Any

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from app.research.onchain import PUMP_PROGRAM_ID, derive_pump_bonding_curve

# Target SOL lamports required for bonding curve completion (~85 SOL)
PUMP_TARGET_SOL_LAMPORTS = 85_000_000_000
PUMP_DISCRIMINATOR_LENGTH = 8
PUMP_CURVE_DATA_MIN_LENGTH = 49  # 8 byte discriminator + 41 bytes struct


@dataclass(frozen=True)
class BondingCurveMetrics:
    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool
    price_sol: float
    curve_progress_pct: float
    real_sol_reserves_sol: float


@dataclass(frozen=True)
class TokenCurveSnapshot:
    mint: str
    bonding_curve_address: str
    exists: bool
    lamports: int
    metrics: BondingCurveMetrics | None
    observed_at: datetime
    error: str | None = None


def decode_bonding_curve_data(data: bytes) -> BondingCurveMetrics | None:
    """
    Decode the on-chain Pump.fun bonding curve account state from raw binary bytes.

    Layout (starts at offset 8 following the 8-byte Anchor discriminator):
      - virtual_token_reserves: u64 (little-endian)
      - virtual_sol_reserves:   u64 (little-endian)
      - real_token_reserves:    u64 (little-endian)
      - real_sol_reserves:      u64 (little-endian)
      - token_total_supply:     u64 (little-endian)
      - complete:               bool (1 byte)
    """
    if len(data) < PUMP_CURVE_DATA_MIN_LENGTH:
        return None

    try:
        (
            virtual_token,
            virtual_sol,
            real_token,
            real_sol,
            total_supply,
            complete,
        ) = struct.unpack_from("<QQQQQ?", data, PUMP_DISCRIMINATOR_LENGTH)

        # Price in SOL per token: (virtual_sol in SOL) / (virtual_tokens in standard units)
        price_sol = 0.0
        if virtual_token > 0:
            sol_amount = virtual_sol / 1e9
            token_amount = virtual_token / 1e6
            price_sol = sol_amount / token_amount if token_amount > 0 else 0.0

        # Progress toward the 85 SOL bonding curve cap
        progress_pct = min(100.0, (real_sol / PUMP_TARGET_SOL_LAMPORTS) * 100.0)
        real_sol_val = real_sol / 1e9

        return BondingCurveMetrics(
            virtual_token_reserves=virtual_token,
            virtual_sol_reserves=virtual_sol,
            real_token_reserves=real_token,
            real_sol_reserves=real_sol,
            token_total_supply=total_supply,
            complete=bool(complete),
            price_sol=price_sol,
            curve_progress_pct=progress_pct,
            real_sol_reserves_sol=real_sol_val,
        )
    except Exception:
        return None


def parse_pump_instruction_logs(logs: list[str]) -> dict[str, Any]:
    """
    Parse instruction logs from a Solana transaction or WebSocket log notification
    for Pump.fun program interactions.
    """
    is_pump = False
    instruction_type = "unknown"

    pump_str = str(PUMP_PROGRAM_ID)

    for line in logs:
        if pump_str in line:
            is_pump = True
        if "Instruction: Create" in line:
            instruction_type = "create"
        elif "Instruction: Buy" in line:
            instruction_type = "buy"
        elif "Instruction: Sell" in line:
            instruction_type = "sell"

    return {
        "is_pump_program": is_pump,
        "instruction_type": instruction_type,
        "is_creation": instruction_type == "create",
        "is_trade": instruction_type in ("buy", "sell"),
    }


def build_pump_logs_subscription_request(subscription_id: int = 1) -> dict[str, Any]:
    """
    Build standard Solana JSON-RPC WebSocket payload for logsSubscribe
    filtering on the Pump.fun program address.
    """
    return {
        "jsonrpc": "2.0",
        "id": subscription_id,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [str(PUMP_PROGRAM_ID)]},
            {"commitment": "processed"},
        ],
    }


async def inspect_token_curve(
    mint: str,
    client: AsyncClient,
) -> TokenCurveSnapshot:
    """
    Inspect the deterministic Pump.fun bonding curve account for a token mint.
    """
    now = datetime.now(timezone.utc)
    bc = derive_pump_bonding_curve(mint)

    if bc is None:
        return TokenCurveSnapshot(
            mint=mint,
            bonding_curve_address="",
            exists=False,
            lamports=0,
            metrics=None,
            observed_at=now,
            error="invalid_mint_address",
        )

    bc_str = str(bc)
    try:
        resp = await client.get_account_info(bc)
        if resp.value is None:
            return TokenCurveSnapshot(
                mint=mint,
                bonding_curve_address=bc_str,
                exists=False,
                lamports=0,
                metrics=None,
                observed_at=now,
            )

        account = resp.value
        lamports = account.lamports
        data = account.data

        metrics = decode_bonding_curve_data(data)

        return TokenCurveSnapshot(
            mint=mint,
            bonding_curve_address=bc_str,
            exists=True,
            lamports=lamports,
            metrics=metrics,
            observed_at=now,
        )
    except Exception as exc:
        return TokenCurveSnapshot(
            mint=mint,
            bonding_curve_address=bc_str,
            exists=False,
            lamports=0,
            metrics=None,
            observed_at=now,
            error=str(exc),
        )


async def scan_bonding_curves(
    mints: list[str],
    client: AsyncClient,
    max_concurrency: int = 5,
) -> dict[str, TokenCurveSnapshot]:
    """
    Concurrently inspect bonding curve states for a list of mints.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _safe_inspect(mint: str) -> tuple[str, TokenCurveSnapshot]:
        async with semaphore:
            res = await inspect_token_curve(mint, client)
            return mint, res

    tasks = [_safe_inspect(m) for m in mints]
    results = await asyncio.gather(*tasks)
    return dict(results)
