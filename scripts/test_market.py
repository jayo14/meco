import asyncio

from app.market.dexscreener import get_token_pairs
from app.market.snapshot import create_market_snapshot


async def main() -> None:
    address = "So11111111111111111111111111111111111111112"

    pairs = await get_token_pairs(address)

    print(f"Found {len(pairs)} pairs")

    if not pairs:
        print("No market pairs found.")
        return

    snapshot = create_market_snapshot(
        token_address=address,
        pair=pairs[0],
    )

    print()
    print("=== MARKET SNAPSHOT ===")
    print(f"Token: {snapshot.token_address}")
    print(f"DEX: {snapshot.dex_id}")
    print(f"Pair: {snapshot.pair_address}")
    print(f"Price USD: {snapshot.price_usd}")
    print(f"Liquidity USD: {snapshot.liquidity_usd}")
    print(f"5m Volume: {snapshot.volume_5m}")
    print(f"1h Volume: {snapshot.volume_1h}")
    print(f"24h Volume: {snapshot.volume_24h}")
    print(f"5m Buys: {snapshot.buys_5m}")
    print(f"5m Sells: {snapshot.sells_5m}")
    print(f"5m Buy/Sell Ratio: {snapshot.buy_sell_ratio_5m}")
    print(f"5m Total Trades: {snapshot.total_trades_5m}")
    print(f"5m Price Change: {snapshot.price_change_5m}%")
    print(f"Market Cap: {snapshot.market_cap}")
    print(f"FDV: {snapshot.fdv}")


if __name__ == "__main__":
    asyncio.run(main())
