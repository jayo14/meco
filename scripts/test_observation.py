import asyncio

from app.database.observation_repository import save_market_observation
from app.database.session import SessionLocal
from app.market.dexscreener import get_token_pairs
from app.market.snapshot import create_market_snapshot, select_primary_pair


TOKEN_ADDRESS = "So11111111111111111111111111111111111111112"
SIGNAL_ID = 1


async def main() -> None:
    pairs = await get_token_pairs(TOKEN_ADDRESS)

    if not pairs:
        print("No market pairs found.")
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        print("No liquid pair found.")
        return

    snapshot = create_market_snapshot(
        TOKEN_ADDRESS,
        primary_pair,
    )

    async with SessionLocal() as session:
        observation = await save_market_observation(
            session,
            signal_id=SIGNAL_ID,
            token_address=TOKEN_ADDRESS,
            seconds_since_signal=60,
            snapshot=snapshot,
        )

    print("=== OBSERVATION SAVED ===")
    print(f"ID: {observation.id}")
    print(f"Signal ID: {observation.signal_id}")
    print(f"Token: {observation.token_address}")
    print(f"Observed at: {observation.observed_at}")
    print(f"Seconds since signal: {observation.seconds_since_signal}")
    print(f"Price: ${observation.price_usd}")
    print(f"Liquidity: ${observation.liquidity_usd}")
    print(f"5m volume: ${observation.volume_5m}")
    print(f"Buys: {observation.buys_5m}")
    print(f"Sells: {observation.sells_5m}")


if __name__ == "__main__":
    asyncio.run(main())
