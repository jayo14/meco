import logging
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.models import Token, TokenSecurityProfile

logger = logging.getLogger("meco.intelligence.security")

# Canonical Solana Token Programs
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_2022_PROGRAM_ID = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")

# Standard SPL Mint binary layout is 82 bytes:
# [0..4]   COption mint_authority (u32)
# [4..36]  mint_authority (32 bytes)
# [36..44] supply (u64)
# [44..45] decimals (u8)
# [45..46] is_initialized (u8)
# [46..50] COption freeze_authority (u32)
# [50..82] freeze_authority (32 bytes)
SPL_MINT_STRUCT_LEN = 82


@dataclass
class DecodedMintSecurity:
    token_program: str
    mint_authority: str | None
    is_mintable: bool
    freeze_authority: str | None
    is_freezable: bool
    decimals: int
    supply: int
    is_initialized: bool
    permanent_delegate: str | None = None
    has_transfer_fee: bool = False
    transfer_fee_basis_points: int | None = None
    raw_data_len: int = 0


def decode_mint_account_data(
    data: bytes,
    owner_program: str | Pubkey = TOKEN_PROGRAM_ID,
) -> DecodedMintSecurity | None:
    """
    Decode on-chain SPL Token or Token-2022 Mint account data.
    Direct binary parsing without external RPC dependencies.
    """
    if len(data) < SPL_MINT_STRUCT_LEN:
        return None

    try:
        # Mint authority
        mint_auth_opt = struct.unpack_from("<I", data, 0)[0]
        mint_auth = None
        if mint_auth_opt != 0:
            mint_auth_bytes = data[4:36]
            mint_auth = str(Pubkey(mint_auth_bytes))

        # Supply & decimals
        supply, decimals, is_init = struct.unpack_from("<QBB", data, 36)

        # Freeze authority
        freeze_auth_opt = struct.unpack_from("<I", data, 46)[0]
        freeze_auth = None
        if freeze_auth_opt != 0:
            freeze_auth_bytes = data[50:82]
            freeze_auth = str(Pubkey(freeze_auth_bytes))

        prog_str = str(owner_program)
        perm_delegate = None
        has_transfer_fee = False
        transfer_fee_bp = None

        # Inspect Token-2022 TLV Extensions (if account length > 82)
        if len(data) > SPL_MINT_STRUCT_LEN and prog_str == str(TOKEN_2022_PROGRAM_ID):
            offset = SPL_MINT_STRUCT_LEN
            while offset + 4 <= len(data):
                ext_type, ext_len = struct.unpack_from("<HH", data, offset)
                offset += 4
                if offset + ext_len > len(data):
                    break
                ext_bytes = data[offset : offset + ext_len]

                # Type 1 = TransferFeeConfig
                if ext_type == 1 and len(ext_bytes) >= 12:
                    transfer_fee_bp = struct.unpack_from("<H", ext_bytes, 8)[0]
                    has_transfer_fee = transfer_fee_bp > 0

                # Type 13 = PermanentDelegate
                elif ext_type == 13 and len(ext_bytes) >= 32:
                    perm_delegate = str(Pubkey(ext_bytes[:32]))

                offset += ext_len

        return DecodedMintSecurity(
            token_program=prog_str,
            mint_authority=mint_auth,
            is_mintable=mint_auth is not None,
            freeze_authority=freeze_auth,
            is_freezable=freeze_auth is not None,
            decimals=decimals,
            supply=supply,
            is_initialized=bool(is_init),
            permanent_delegate=perm_delegate,
            has_transfer_fee=has_transfer_fee,
            transfer_fee_basis_points=transfer_fee_bp,
            raw_data_len=len(data),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed decoding mint account bytes: %s", exc)
        return None


def calculate_security_score(
    sec: DecodedMintSecurity,
) -> tuple[float, list[dict[str, Any]], list[str]]:
    """
    Calculate deterministic risk score (0-100) and extract verified facts vs inferred risk factors.
    """
    score = 0.0
    risk_factors: list[dict[str, Any]] = []
    verified_facts: list[str] = [
        f"Token Program: {sec.token_program}",
        f"Supply: {sec.supply} with {sec.decimals} decimals",
    ]

    # 1. Freeze Authority (Critical Risk)
    if sec.is_freezable and sec.freeze_authority:
        score += 45.0
        risk_factors.append({
            "factor": "active_freeze_authority",
            "severity": "critical",
            "confidence": 1.0,
            "evidence": f"Freeze authority is set to {sec.freeze_authority}",
        })
        verified_facts.append(f"Freeze authority is ENABLED ({sec.freeze_authority})")
    else:
        verified_facts.append("Freeze authority is REVOKED (cannot blacklist holders)")

    # 2. Mint Authority (High Risk)
    if sec.is_mintable and sec.mint_authority:
        score += 30.0
        risk_factors.append({
            "factor": "active_mint_authority",
            "severity": "high",
            "confidence": 1.0,
            "evidence": f"Mint authority is set to {sec.mint_authority}",
        })
        verified_facts.append(f"Mint authority is ENABLED ({sec.mint_authority}) - supply can be diluted")
    else:
        verified_facts.append("Mint authority is REVOKED (supply is capped)")

    # 3. Permanent Delegate (Critical Token-2022 Risk)
    if sec.permanent_delegate:
        score += 50.0
        risk_factors.append({
            "factor": "permanent_delegate_enabled",
            "severity": "critical",
            "confidence": 1.0,
            "evidence": f"Token has permanent delegate: {sec.permanent_delegate}",
        })
        verified_facts.append(f"Permanent delegate is ACTIVE ({sec.permanent_delegate})")

    # 4. Transfer Fee (Medium Risk)
    if sec.has_transfer_fee and sec.transfer_fee_basis_points is not None:
        fee_pct = sec.transfer_fee_basis_points / 100.0
        if fee_pct > 0.0:
            score += min(30.0, fee_pct * 5.0)
            risk_factors.append({
                "factor": "transfer_fee_enabled",
                "severity": "medium",
                "confidence": 1.0,
                "evidence": f"Token charges {fee_pct}% transfer fee",
            })
            verified_facts.append(f"Transfer fee of {fee_pct}% enabled")

    clamped_score = min(100.0, score)
    return round(clamped_score, 1), risk_factors, verified_facts


async def inspect_token_security_onchain(
    mint_address: str,
    rpc_client: AsyncClient,
) -> DecodedMintSecurity | None:
    """Fetch on-chain account info and decode mint security state."""
    try:
        pubkey = Pubkey.from_string(mint_address)
        resp = await rpc_client.get_account_info(pubkey)
        if resp.value is None:
            return None

        account = resp.value
        owner = str(account.owner)
        data = account.data

        return decode_mint_account_data(data, owner_program=owner)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed on-chain security inspection for %s: %s", mint_address, exc)
        return None


async def audit_token_security(
    session: AsyncSession,
    *,
    token: Token,
    rpc_client: AsyncClient | None = None,
    decoded_hint: DecodedMintSecurity | None = None,
) -> TokenSecurityProfile | None:
    """
    Perform a complete security and authority audit on a token.
    Updates or creates TokenSecurityProfile and syncs risk_score back to Token.
    """
    sec = decoded_hint

    if sec is None:
        settings = get_settings()
        if rpc_client is not None:
            sec = await inspect_token_security_onchain(token.mint_address, rpc_client)
        else:
            async with AsyncClient(settings.solana_rpc_url) as client:
                sec = await inspect_token_security_onchain(token.mint_address, client)

    if sec is None:
        return None

    score, risk_factors, verified_facts = calculate_security_score(sec)

    now = datetime.now(timezone.utc)
    stmt = select(TokenSecurityProfile).where(TokenSecurityProfile.token_id == token.id)
    result = await session.execute(stmt)
    prof = result.scalar_one_or_none()

    if prof is None:
        prof = TokenSecurityProfile(
            token_id=token.id,
            mint_address=token.mint_address,
            token_program=sec.token_program,
            mint_authority=sec.mint_authority,
            is_mintable=sec.is_mintable,
            freeze_authority=sec.freeze_authority,
            is_freezable=sec.is_freezable,
            permanent_delegate=sec.permanent_delegate,
            metadata_update_authority=None,
            is_mutable=None,
            has_transfer_fee=sec.has_transfer_fee,
            transfer_fee_basis_points=sec.transfer_fee_basis_points,
            is_lp_burned_or_locked=None,
            risk_score=score,
            risk_factors=risk_factors,
            verified_facts=verified_facts,
            raw_onchain_data={
                "decimals": sec.decimals,
                "supply": sec.supply,
                "is_initialized": sec.is_initialized,
            },
            updated_at=now,
        )
        session.add(prof)
    else:
        prof.token_program = sec.token_program
        prof.mint_authority = sec.mint_authority
        prof.is_mintable = sec.is_mintable
        prof.freeze_authority = sec.freeze_authority
        prof.is_freezable = sec.is_freezable
        prof.permanent_delegate = sec.permanent_delegate
        prof.has_transfer_fee = sec.has_transfer_fee
        prof.transfer_fee_basis_points = sec.transfer_fee_basis_points
        prof.risk_score = score
        prof.risk_factors = risk_factors
        prof.verified_facts = verified_facts
        prof.updated_at = now

    token.risk_score = score
    token.updated_at = now

    await session.flush()
    await session.refresh(prof)
    return prof
