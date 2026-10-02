from dataclasses import dataclass

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from app.config.settings import get_settings


@dataclass(frozen=True)
class MintInfo:
    address: str
    decimals: int
    supply: int


async def get_mint_info(token_address: str) -> MintInfo | None:
    """
    Check whether a Solana address is a valid SPL token mint.

    Returns MintInfo if valid, otherwise None.
    """
    settings = get_settings()

    try:
        pubkey = Pubkey.from_string(token_address)
    except ValueError:
        return None

    async with AsyncClient(settings.solana_rpc_url) as client:
        response = await client.get_token_supply(pubkey)

    if response.value is None:
        return None

    return MintInfo(
        address=token_address,
        decimals=response.value.decimals,
        supply=int(response.value.amount),
    )
