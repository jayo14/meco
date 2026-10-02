import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from app.config.settings import get_settings

logger = logging.getLogger("meco.solana")


class MintValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    RPC_FAILED = "rpc_failed"


@dataclass(frozen=True)
class MintInfo:
    address: str
    decimals: int
    supply: int


@dataclass(frozen=True)
class MintValidationResult:
    status: MintValidationStatus
    mint_info: MintInfo | None = None


async def get_mint_info(
    token_address: str,
    *,
    retries: int = 2,
) -> MintValidationResult:

    settings = get_settings()

    # Address itself is malformed.
    try:
        pubkey = Pubkey.from_string(token_address)
    except ValueError:
        return MintValidationResult(
            status=MintValidationStatus.INVALID,
        )

    for attempt in range(retries + 1):
        try:
            async with AsyncClient(settings.solana_rpc_url) as client:
                response = await client.get_token_supply(pubkey)

            # RPC responded successfully, but this address is not
            # recognized as a token mint.
            if response.value is None:
                return MintValidationResult(
                    status=MintValidationStatus.INVALID,
                )

            mint_info = MintInfo(
                address=token_address,
                decimals=response.value.decimals,
                supply=int(response.value.amount),
            )

            return MintValidationResult(
                status=MintValidationStatus.VALID,
                mint_info=mint_info,
            )

        except Exception as exc:
            if attempt >= retries:
                logger.exception(
                    "SOLANA RPC FAILED | mint=%s | attempts=%s",
                    token_address,
                    attempt + 1,
                )

                return MintValidationResult(
                    status=MintValidationStatus.RPC_FAILED,
                )

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

    return MintValidationResult(
        status=MintValidationStatus.RPC_FAILED,
    )
