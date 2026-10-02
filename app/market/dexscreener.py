from dataclasses import dataclass

import httpx


DEXSCREENER_BASE_URL = "https://api.dexscreener.com"


@dataclass(frozen=True)
class MarketPair:
    pair_address: str
    dex_id: str
    url: str

    base_token_address: str
    base_token_name: str
    base_token_symbol: str

    quote_token_address: str | None
    quote_token_name: str | None
    quote_token_symbol: str | None

    price_native: float | None
    price_usd: float | None

    liquidity_usd: float | None

    volume_m5: float
    volume_h1: float
    volume_h6: float
    volume_h24: float

    buys_m5: int
    sells_m5: int

    price_change_m5: float | None
    price_change_h1: float | None
    price_change_h6: float | None
    price_change_h24: float | None

    market_cap: float | None
    fdv: float | None
    pair_created_at: int | None


async def get_token_pairs(token_address: str) -> list[MarketPair]:
    """
    Fetch market pairs for a Solana token from DEX Screener.
    """

    url = (
        f"{DEXSCREENER_BASE_URL}"
        f"/token-pairs/v1/solana/{token_address}"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

    pairs = data.get("pairs") if isinstance(data, dict) else data

    if not pairs:
        return []

    results: list[MarketPair] = []

    for pair in pairs:
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})

        price_native = pair.get("priceNative")
        price_usd = pair.get("priceUsd")

        liquidity = pair.get("liquidity") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        price_change = pair.get("priceChange") or {}

        m5_txns = txns.get("m5") or {}

        results.append(
            MarketPair(
                pair_address=pair.get("pairAddress", ""),
                dex_id=pair.get("dexId", ""),
                url=pair.get("url", ""),

                base_token_address=base_token.get("address", ""),
                base_token_name=base_token.get("name", ""),
                base_token_symbol=base_token.get("symbol", ""),

                quote_token_address=quote_token.get("address"),
                quote_token_name=quote_token.get("name"),
                quote_token_symbol=quote_token.get("symbol"),

                price_native=(
                    float(price_native)
                    if price_native is not None
                    else None
                ),

                price_usd=(
                    float(price_usd)
                    if price_usd is not None
                    else None
                ),

                liquidity_usd=liquidity.get("usd"),

                volume_m5=volume.get("m5", 0.0),
                volume_h1=volume.get("h1", 0.0),
                volume_h6=volume.get("h6", 0.0),
                volume_h24=volume.get("h24", 0.0),

                buys_m5=m5_txns.get("buys", 0),
                sells_m5=m5_txns.get("sells", 0),

                price_change_m5=price_change.get("m5"),
                price_change_h1=price_change.get("h1"),
                price_change_h6=price_change.get("h6"),
                price_change_h24=price_change.get("h24"),

                market_cap=pair.get("marketCap"),
                fdv=pair.get("fdv"),
                pair_created_at=pair.get("pairCreatedAt"),
            )
        )

    return results
