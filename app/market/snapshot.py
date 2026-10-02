from app.market.dexscreener import MarketPair
from app.market.models import MarketSnapshot


def select_primary_pair(
    pairs: list[MarketPair],
) -> MarketPair | None:
    """
    Select the most liquid market pair.

    Pairs without liquidity data are ignored.
    """
    pairs_with_liquidity = [
        pair
        for pair in pairs
        if pair.liquidity_usd is not None
    ]

    if not pairs_with_liquidity:
        return None

    return max(
        pairs_with_liquidity,
        key=lambda pair: pair.liquidity_usd,
    )


def create_market_snapshot(
    token_address: str,
    pair: MarketPair,
) -> MarketSnapshot:
    """
    Convert a raw DEX Screener pair into Meco's
    normalized market snapshot.
    """

    return MarketSnapshot(
        token_address=token_address,
        pair_address=pair.pair_address,
        dex_id=pair.dex_id,

        price_usd=pair.price_usd,
        liquidity_usd=pair.liquidity_usd,

        volume_5m=pair.volume_m5,
        volume_1h=pair.volume_h1,
        volume_24h=pair.volume_h24,

        buys_5m=pair.buys_m5,
        sells_5m=pair.sells_m5,

        price_change_5m=pair.price_change_m5,
        price_change_1h=pair.price_change_h1,
        price_change_24h=pair.price_change_h24,

        market_cap=pair.market_cap,
        fdv=pair.fdv,

        pair_created_at=pair.pair_created_at,
    )
