import asyncio

from app.market.dexscreener import get_token_pairs


async def main() -> None:
    address = "So11111111111111111111111111111111111111112"

    pairs = await get_token_pairs(address)

    print(f"Found {len(pairs)} pairs")

    for pair in pairs[:5]:
        print()
        print(f"DEX: {pair.dex_id}")
        print(f"Pair: {pair.base_token_symbol}/{pair.quote_token_symbol}")
        print(f"Price USD: {pair.price_usd}")
        print(f"Liquidity USD: {pair.liquidity_usd}")
        print(f"5m Volume: {pair.volume_m5}")
        print(f"5m Buys: {pair.buys_m5}")
        print(f"5m Sells: {pair.sells_m5}")


if __name__ == "__main__":
    asyncio.run(main())
