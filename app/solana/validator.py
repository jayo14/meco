import asyncio
import logging
from dataclasses import dataclass

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from app.config.settings import get_settings


logger = logging.getLogger("meco.solana")


@dataclass(frozen=True)
class MintInfo:
    address: str
    decimals: int
    supply: int


async def get_mint_info(
    token_address: str,
    *,
    retries: int = 2,
) -> MintInfo | None:
    """
    Check whether a Solana address is a valid SPL token mint.

    Returns:
        MintInfo if the address is a valid token mint.
        None if the address is invalid or the RPC cannot validate it
        after all retries.
    """

    settings = get_settings()

    try:
        pubkey = Pubkey.from_string(token_address)
    except ValueError:
        return None

    for attempt in range(retries + 1):
        try:
            async with AsyncClient(settings.solana_rpc_url) as client:
                response = await client.get_token_supply(pubkey)

            if response.value is None:
                return None

            return MintInfo(
                address=token_address,
                decimals=response.value.decimals,
                supply=int(response.value.amount),
            )

        except Exception as exc:
            if attempt >= retries:
                logger.exception(
                    "SOLANA RPC FAILED | mint=%s | attempts=%s",
                    token_address,
                    attempt + 1,
                )
                return None

            delay = 1.0 * (2 ** attempt)

            logger.warning(
                "SOLANA RPC RETRY | mint=%s | attempt=%s/%s | "
                "error=%s | retry_in=%.1fs",
                token_address,
                attempt + 1,
                retries,
                type(exc).__name__,
                delay,
            )

            await asyncio.sleep(delay)

    return None
