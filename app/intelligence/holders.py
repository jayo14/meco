import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.models import Token, TokenHolderSnapshot

logger = logging.getLogger("meco.intelligence.holders")


@dataclass
class HolderEntry:
    address: str
    amount: int
    decimals: int
    ui_amount: float
    pct_of_supply: float
    is_known_pool_or_curve: bool = False
    confidence: float = 1.0
    evidence: str = "on_chain_token_largest_accounts"


async def fetch_token_largest_accounts(
    mint_address: str,
    rpc_client: AsyncClient,
    total_supply: int | None = None,
) -> list[HolderEntry]:
    """
    Query Solana RPC for the top token accounts via getTokenLargestAccounts.
    Calculates percentage of supply held by each top holder.
    """
    try:
        pubkey = Pubkey.from_string(mint_address)
        resp = await rpc_client.get_token_largest_accounts(pubkey)
        if resp.value is None:
            return []

        entries: list[HolderEntry] = []
        supply = total_supply if total_supply and total_supply > 0 else None

        # If supply not passed in, sum largest accounts as lower bound
        if supply is None:
            raw_sum = sum(int(getattr(acc, "amount", 0)) for acc in resp.value)
            supply = max(1, raw_sum)

        for acc in resp.value:
            acc_address = str(acc.address)
            amount = int(acc.amount)
            decimals = acc.decimals
            ui_amount = float(acc.ui_amount) if acc.ui_amount is not None else float(amount / (10 ** decimals))
            pct = min(100.0, (amount / supply) * 100.0)

            # Heuristic check for common curve / pool addresses
            is_pool = False
            if "pump" in acc_address.lower() or "raydium" in acc_address.lower():
                is_pool = True

            entries.append(
                HolderEntry(
                    address=acc_address,
                    amount=amount,
                    decimals=decimals,
                    ui_amount=ui_amount,
                    pct_of_supply=round(pct, 2),
                    is_known_pool_or_curve=is_pool,
                    confidence=1.0,
                    evidence=f"RPC getTokenLargestAccounts for mint {mint_address}",
                )
            )

        # Sort descending by balance
        entries.sort(key=lambda h: h.amount, reverse=True)
        return entries
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed fetching largest accounts for %s: %s", mint_address, exc)
        return []


async def capture_token_holder_snapshot(
    session: AsyncSession,
    *,
    token: Token,
    rpc_client: AsyncClient | None = None,
    deployer_address: str | None = None,
    entries_override: list[HolderEntry] | None = None,
) -> TokenHolderSnapshot:
    """
    Capture a point-in-time snapshot of the token's top holder concentration
    and deployer balances. Persists TokenHolderSnapshot.
    """
    entries = entries_override
    if entries is None:
        settings = get_settings()
        if rpc_client is not None:
            entries = await fetch_token_largest_accounts(token.mint_address, rpc_client, token.total_supply)
        else:
            async with AsyncClient(settings.solana_rpc_url) as client:
                entries = await fetch_token_largest_accounts(token.mint_address, client, token.total_supply)

    # Calculate Top 10 and Top 20 concentration percentages (excluding obvious automated pool reserves)
    top10_entries = entries[:10]
    top20_entries = entries[:20]

    top10_pct = round(sum(h.pct_of_supply for h in top10_entries), 2) if top10_entries else None
    top20_pct = round(sum(h.pct_of_supply for h in top20_entries), 2) if top20_entries else None

    # Check if deployer holding is in largest accounts
    deployer_pct = None
    if deployer_address:
        for h in entries:
            if h.address == deployer_address:
                deployer_pct = h.pct_of_supply
                break

    now = datetime.now(timezone.utc)
    serialized_holders = [
        {
            "address": h.address,
            "amount": h.amount,
            "decimals": h.decimals,
            "ui_amount": h.ui_amount,
            "pct_of_supply": h.pct_of_supply,
            "is_known_pool": h.is_known_pool_or_curve,
            "confidence": h.confidence,
            "evidence": h.evidence,
        }
        for h in entries
    ]

    snapshot = TokenHolderSnapshot(
        token_id=token.id,
        mint_address=token.mint_address,
        total_holders_count=len(entries) if entries else None,
        top10_concentration_pct=top10_pct,
        top20_concentration_pct=top20_pct,
        deployer_address=deployer_address,
        deployer_holding_pct=deployer_pct,
        top_holders=serialized_holders,
        observed_at=now,
        created_at=now,
    )
    session.add(snapshot)

    token.updated_at = now

    await session.flush()
    await session.refresh(snapshot)

    logger.info(
        "HOLDER SNAPSHOT CAPTURED | mint=%s | top_accounts=%s | top10_pct=%s%% | top20_pct=%s%%",
        token.mint_address,
        len(entries),
        top10_pct,
        top20_pct,
    )
    return snapshot
