import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)


# 1. Update app/solana/validator.py
content_validator = """import asyncio
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
"""
with open("app/solana/validator.py", "w") as f:
    f.write(content_validator)


# 2. Update app/telegram/client.py
with open("app/telegram/client.py", "r") as f:
    content = f.read()

import_old = "from app.solana.validator import get_mint_info"
import_new = "from app.solana.validator import (\n    MintValidationStatus,\n    get_mint_info,\n)"
content = content.replace(import_old, import_new)


val_old = """    # ---------------------------------------------------------
    # STEP 2: SOLANA VALIDATION
    # ---------------------------------------------------------

    mint_info = await get_mint_info(
        signal.token_address,
    )

    if mint_info is None:
        logger.warning(
            "❌ TOKEN VALIDATION FAILED | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="failed",
            )

        return

    logger.info(
        "✅ VALID TOKEN MINT | signal_id=%s | mint=%s | "
        "decimals=%s | supply=%s",
        saved_signal.id,
        mint_info.address,
        mint_info.decimals,
        mint_info.supply,
    )

    async with SessionLocal() as session:
        await update_signal_validation(
            session,
            signal_id=saved_signal.id,
            mint_info=mint_info,
            validation_status="valid",
        )"""

val_new = """    # ---------------------------------------------------------
    # STEP 2: SOLANA VALIDATION
    # ---------------------------------------------------------

    validation = await get_mint_info(
        signal.token_address,
    )

    if validation.status == MintValidationStatus.INVALID:
        logger.warning(
            "❌ INVALID TOKEN MINT | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="invalid",
            )

        return

    if validation.status == MintValidationStatus.RPC_FAILED:
        logger.error(
            "⚠️ SOLANA RPC FAILED | signal_id=%s | mint=%s",
            saved_signal.id,
            signal.token_address,
        )

        async with SessionLocal() as session:
            await update_signal_validation(
                session,
                signal_id=saved_signal.id,
                mint_info=None,
                validation_status="rpc_failed",
            )

        return

    mint_info = validation.mint_info

    if mint_info is None:
        raise RuntimeError(
            "VALID validation result has no mint info"
        )

    logger.info(
        "✅ VALID TOKEN MINT | signal_id=%s | mint=%s | "
        "decimals=%s | supply=%s",
        saved_signal.id,
        mint_info.address,
        mint_info.decimals,
        mint_info.supply,
    )

    async with SessionLocal() as session:
        await update_signal_validation(
            session,
            signal_id=saved_signal.id,
            mint_info=mint_info,
            validation_status="valid",
        )"""
content = content.replace(val_old, val_new)
with open("app/telegram/client.py", "w") as f:
    f.write(content)

run_cmd("Distinguish between invalid tokens and RPC failures")

