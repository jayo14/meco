import re
from dataclasses import dataclass
from datetime import datetime

SOLANA_ADDRESS_PATTERN = re.compile(
    r"[1-9A-HJ-NP-Za-km-z]{32,44}"
)

CA_PATTERN = re.compile(
    r"(?:"
    r"\bCA\b"
    r"|contract\s+address"
    r"|contract"
    r"|mint"
    r"|mint\s+address"
    r")"
    r"\s*(?:\([^)]*\))?"
    r"\s*[:\-]?\s*"
    r"([1-9A-HJ-NP-Za-km-z]{32,44})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TokenSignal:
    token_address: str
    slippage: float | None

    chat_id: int
    message_id: int
    message_text: str
    message_created_at: datetime
    received_at: datetime


def extract_solana_addresses(text: str) -> list[str]:
    if not text:
        return []

    matches = SOLANA_ADDRESS_PATTERN.findall(text)

    return list(dict.fromkeys(matches))


def extract_token_address(text: str) -> str | None:
    if not text:
        return None

    # Prefer an address explicitly labelled as CA / contract / mint.
    match = CA_PATTERN.search(text)

    if match:
        return match.group(1)

    # Fallback for messages that contain only a bare address.
    addresses = extract_solana_addresses(text)

    if not addresses:
        return None

    return addresses[0]


def extract_slippage(text: str) -> float | None:
    if not text:
        return None

    pattern = re.compile(
        r"slippage\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if not match:
        return None

    return float(match.group(1))


def extract_token_signal(
    text: str,
    *,
    chat_id: int,
    message_id: int,
    message_created_at: datetime,
    received_at: datetime,
) -> TokenSignal | None:
    token_address = extract_token_address(text)

    if not token_address:
        return None

    return TokenSignal(
        token_address=token_address,
        slippage=extract_slippage(text),
        chat_id=chat_id,
        message_id=message_id,
        message_text=text,
        message_created_at=message_created_at,
        received_at=received_at,
    )
