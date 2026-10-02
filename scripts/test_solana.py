import asyncio

from app.solana.validator import get_mint_info


async def main() -> None:
    address = "DefinitelyNotASolanaAddress"

    result = await get_mint_info(address)

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
