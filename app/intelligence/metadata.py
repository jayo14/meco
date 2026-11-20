import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Token, TokenMetadataRecord

logger = logging.getLogger("meco.intelligence.metadata")

# Maximum bytes to download for off-chain metadata (protect against memory exhaustion)
MAX_METADATA_BYTES = 256 * 1024  # 256 KB
DEFAULT_FETCH_TIMEOUT = 5.0      # 5 seconds


def sanitize_text(val: Any, max_len: int = 500) -> str | None:
    """Sanitize and clamp untrusted external string inputs."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # Truncate to maximum safe length
    return s[:max_len]


def normalize_metadata_uri(uri: str | None) -> str | None:
    """Normalize IPFS and Arweave URIs to HTTP gateways."""
    if not uri or not isinstance(uri, str):
        return None
    uri = uri.strip()
    if uri.startswith("ipfs://"):
        cid = uri[7:].lstrip("/")
        return f"https://ipfs.io/ipfs/{cid}"
    if uri.startswith("ar://"):
        txid = uri[5:].lstrip("/")
        return f"https://arweave.net/{txid}"
    return uri


def extract_social_links(metadata: dict[str, Any]) -> dict[str, str | None]:
    """
    Extract website, twitter, telegram, and discord links from various standard
    and non-standard Solana metadata schemas (Metaplex, Pump.fun, DexScreener).
    """
    links: dict[str, str | None] = {
        "website": None,
        "twitter": None,
        "telegram": None,
        "discord": None,
    }

    # 1. Direct top-level fields
    for k in ("website", "external_url", "web"):
        if metadata.get(k):
            links["website"] = sanitize_text(metadata[k], 255)
            break

    for k in ("twitter", "twitter_url", "x"):
        if metadata.get(k):
            links["twitter"] = sanitize_text(metadata[k], 255)
            break

    for k in ("telegram", "tg", "telegram_url"):
        if metadata.get(k):
            links["telegram"] = sanitize_text(metadata[k], 255)
            break

    for k in ("discord", "discord_url"):
        if metadata.get(k):
            links["discord"] = sanitize_text(metadata[k], 255)
            break

    # 2. Nested extensions / links dict
    extensions = metadata.get("extensions") or metadata.get("links") or {}
    if isinstance(extensions, dict):
        if not links["website"] and extensions.get("website"):
            links["website"] = sanitize_text(extensions.get("website"), 255)
        if not links["twitter"] and (extensions.get("twitter") or extensions.get("x")):
            links["twitter"] = sanitize_text(extensions.get("twitter") or extensions.get("x"), 255)
        if not links["telegram"] and (extensions.get("telegram") or extensions.get("tg")):
            links["telegram"] = sanitize_text(extensions.get("telegram") or extensions.get("tg"), 255)
        if not links["discord"] and extensions.get("discord"):
            links["discord"] = sanitize_text(extensions.get("discord"), 255)

    return links


async def fetch_offchain_metadata(
    uri: str,
    *,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Safely download and parse off-chain JSON metadata from an untrusted URI.
    Enforces maximum payload size and timeouts. Returns (parsed_dict, error_string).
    """
    normalized_url = normalize_metadata_uri(uri)
    if not normalized_url:
        return None, "invalid_or_empty_uri"

    parsed = urlparse(normalized_url)
    if parsed.scheme not in ("http", "https"):
        return None, f"unsupported_scheme_{parsed.scheme}"

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(normalized_url)
            if response.status_code != 200:
                return None, f"http_{response.status_code}"

            content = response.content
            if len(content) > MAX_METADATA_BYTES:
                return None, "payload_exceeded_max_bytes"

            data = response.json()
            if not isinstance(data, dict):
                return None, "invalid_json_root_not_dict"

            return data, None

    except httpx.TimeoutException:
        return None, "fetch_timeout"
    except httpx.RequestError as exc:
        return None, f"request_error_{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return None, f"json_parse_error_{type(exc).__name__}"


async def enrich_token_metadata(
    session: AsyncSession,
    *,
    token: Token,
    metadata_uri: str | None = None,
    launchpad: str | None = None,
    name_hint: str | None = None,
    symbol_hint: str | None = None,
) -> TokenMetadataRecord:
    """
    Enrich token metadata from on-chain hints and off-chain URI.
    Persists/updates TokenMetadataRecord and updates Token summary fields.
    """
    target_uri = metadata_uri or token.metadata_uri

    # Lookup existing record
    stmt = select(TokenMetadataRecord).where(TokenMetadataRecord.token_id == token.id)
    result = await session.execute(stmt)
    rec = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    offchain_data = None
    fetch_error = None
    is_fetched = False

    if target_uri:
        offchain_data, fetch_error = await fetch_offchain_metadata(target_uri)
        is_fetched = offchain_data is not None

    # Extract fields from off-chain payload or fall back to hints
    name = None
    symbol = None
    description = None
    image_uri = None
    socials = {"website": None, "twitter": None, "telegram": None, "discord": None}

    if offchain_data:
        name = sanitize_text(offchain_data.get("name"), 255)
        symbol = sanitize_text(offchain_data.get("symbol"), 64)
        description = sanitize_text(offchain_data.get("description"), 2000)
        image_uri = sanitize_text(offchain_data.get("image"), 1000)
        socials = extract_social_links(offchain_data)

    name = name or name_hint or token.name
    symbol = symbol or symbol_hint or token.symbol

    if rec is None:
        rec = TokenMetadataRecord(
            token_id=token.id,
            mint_address=token.mint_address,
            name=name,
            symbol=symbol,
            description=description,
            image_uri=image_uri,
            metadata_uri=target_uri,
            website=socials["website"],
            telegram=socials["telegram"],
            twitter=socials["twitter"],
            discord=socials["discord"],
            launchpad=launchpad,
            is_uri_fetched=is_fetched,
            uri_fetch_error=fetch_error,
            raw_offchain_metadata=offchain_data,
            updated_at=now,
        )
        session.add(rec)
    else:
        if name:
            rec.name = name
        if symbol:
            rec.symbol = symbol
        if description:
            rec.description = description
        if image_uri:
            rec.image_uri = image_uri
        if target_uri:
            rec.metadata_uri = target_uri
        if socials["website"]:
            rec.website = socials["website"]
        if socials["telegram"]:
            rec.telegram = socials["telegram"]
        if socials["twitter"]:
            rec.twitter = socials["twitter"]
        if socials["discord"]:
            rec.discord = socials["discord"]
        if launchpad:
            rec.launchpad = launchpad
        rec.is_uri_fetched = is_fetched
        rec.uri_fetch_error = fetch_error
        if offchain_data:
            rec.raw_offchain_metadata = offchain_data
        rec.updated_at = now

    # Sync clean name/symbol to parent Token if missing
    if name and not token.name:
        token.name = name
    if symbol and not token.symbol:
        token.symbol = symbol
    if target_uri and not token.metadata_uri:
        token.metadata_uri = target_uri
    token.updated_at = now

    await session.flush()
    await session.refresh(rec)
    return rec
