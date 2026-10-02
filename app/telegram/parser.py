import re
from dataclasses import dataclass
from datetime import datetime


SOLANA_ADDRESS_PATTERN = re.compile(
    r"(?<![1-9A-HJ-NP-Za-km-z])"
    r"[1-9A-HJ-NP-Za-km-z]{32,44}"
    r"(?![1-9A-HJ-NP-Za-km-z])"
)


@dataclass(frozen=True)
class TokenSignal:
    token_address: str
    slippage: float | None

    chat_id: int
    message_id: int
    message_text: str
    detected_at: datetime


def extract_solana_addresses(text: str) -> list[str]:
    """
    Extract possible Solana addresses from arbitrary text.

    This only finds candidates. It does not prove that an
    address exists on Solana.
    """
    if not text:
        return []

    matches = SOLANA_ADDRESS_PATTERN.findall(text)

    return list(dict.fromkeys(matches))


def extract_slippage(text: str) -> float | None:
    """
    Extract a percentage explicitly associated with 'slippage'.

    Examples:
        SLIPPAGE: 15% -> 15.0
        slippage 5%   -> 5.0
    """
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
    detected_at: datetime,
) -> TokenSignal | None:
    """
    Extract a token signal and preserve its Telegram context.
    """
    addresses = extract_solana_addresses(text)

    if not addresses:
        return None

    return TokenSignal(
        token_address=addresses[0],
        slippage=extract_slippage(text),
        chat_id=chat_id,
        message_id=message_id,
        message_text=text,
        detected_at=detected_at,
    )
