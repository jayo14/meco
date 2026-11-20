import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Token, TokenMarketSnapshot
from app.market.dexscreener import MarketPair, get_token_pairs
from app.market.snapshot import select_primary_pair

logger = logging.getLogger("meco.intelligence.liquidity")


def pair_to_dict(p: MarketPair) -> dict[str, Any]:
    """Serialize a MarketPair into a clean serializable dictionary."""
    return {
        "pair_address": p.pair_address,
        "dex_id": p.dex_id,
        "url": p.url,
        "base_token_address": p.base_token_address,
        "base_token_symbol": p.base_token_symbol,
        "quote_token_address": p.quote_token_address,
        "quote_token_symbol": p.quote_token_symbol,
        "price_usd": p.price_usd,
        "price_native": p.price_native,
        "liquidity_usd": p.liquidity_usd,
        "volume_m5": p.volume_m5,
        "volume_h1": p.volume_h1,
        "volume_h24": p.volume_h24,
        "buys_m5": p.buys_m5,
        "sells_m5": p.sells_m5,
        "price_change_m5": p.price_change_m5,
        "market_cap": p.market_cap,
        "fdv": p.fdv,
        "pair_created_at": p.pair_created_at,
    }


async def capture_token_liquidity_snapshot(
    session: AsyncSession,
    *,
    token: Token,
    pairs_override: list[MarketPair] | None = None,
) -> TokenMarketSnapshot:
    """
    Query DexScreener for all candidate pairs, select the primary liquid pair,
    compute pool age and cross-pool metrics, and persist a point-in-time
    TokenMarketSnapshot.
    """
    pairs = pairs_override
    if pairs is None:
        try:
            pairs = await get_token_pairs(token.mint_address)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DexScreener fetch failed for %s: %s", token.mint_address, exc)
            pairs = []

    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    primary = select_primary_pair(pairs) if pairs else None

    # Calculate earliest pool creation timestamp across all pairs
    created_timestamps = [
        p.pair_created_at
        for p in pairs
        if p.pair_created_at is not None and p.pair_created_at > 0
    ]
    earliest_created = min(created_timestamps) if created_timestamps else None
    pool_age_sec = None
    if earliest_created is not None:
        pool_age_sec = max(0, int((now_ms - earliest_created) / 1000))

    serialized_pairs = [pair_to_dict(p) for p in pairs]

    snapshot = TokenMarketSnapshot(
        token_id=token.id,
        mint_address=token.mint_address,
        primary_pair_address=primary.pair_address if primary else None,
        primary_dex_id=primary.dex_id if primary else None,
        price_usd=primary.price_usd if primary else None,
        liquidity_usd=primary.liquidity_usd if primary else None,
        market_cap=primary.market_cap if primary else None,
        fdv=primary.fdv if primary else None,
        volume_5m=primary.volume_m5 if primary else None,
        volume_1h=primary.volume_h1 if primary else None,
        volume_24h=primary.volume_h24 if primary else None,
        buys_5m=primary.buys_m5 if primary else None,
        sells_5m=primary.sells_m5 if primary else None,
        price_change_5m=primary.price_change_m5 if primary else None,
        price_change_1h=primary.price_change_h1 if primary else None,
        price_change_24h=primary.price_change_h24 if primary else None,
        pairs_count=len(pairs),
        earliest_pair_created_at=earliest_created,
        pool_age_seconds=pool_age_sec,
        pairs_data=serialized_pairs,
        observed_at=now,
        created_at=now,
    )
    session.add(snapshot)

    token.updated_at = now

    await session.flush()
    await session.refresh(snapshot)

    logger.info(
        "LIQUIDITY SNAPSHOT CAPTURED | mint=%s | pairs=%s | primary=%s | liq=$%s | price=$%s | age=%ss",
        token.mint_address,
        len(pairs),
        snapshot.primary_dex_id or "none",
        snapshot.liquidity_usd,
        snapshot.price_usd,
        pool_age_sec,
    )
    return snapshot
