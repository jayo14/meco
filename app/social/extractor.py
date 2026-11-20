"""Social text extraction, sanitization, and cryptographic hashing utilities."""
import hashlib
import html
import re
from urllib.parse import urlparse

# Base58 alphabet for Solana addresses
BASE58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

# Solana address pattern: 32-44 base58 characters.
# Negative lookahead/lookbehind to ensure full token boundary
MINT_PATTERN = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")

# Cashtag pattern: $SYMBOL (2 to 10 letters/numbers)
CASHTAG_PATTERN = re.compile(r"\$([A-Za-z0-9_]{2,10})\b")

# URL pattern
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

# HTML tags stripper
TAG_RE = re.compile(r"<[^>]+>")


def sanitize_social_text(text: str) -> str:
    """Sanitize social post text: unescape HTML, strip tags, normalize spaces."""
    if not text:
        return ""
    clean = TAG_RE.sub(" ", text)
    clean = html.unescape(clean)
    # Normalize multiple whitespace characters
    clean = " ".join(clean.split())
    return clean.strip()


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized lowercase text for duplicate/spam tracking."""
    normalized = " ".join(sanitize_social_text(text).lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_probable_solana_address(candidate: str) -> bool:
    """Check if a string matches Solana base58 address requirements."""
    if not (32 <= len(candidate) <= 44):
        return False
    # Must only contain Base58 characters
    return all(c in BASE58_ALPHABET for c in candidate)


def extract_solana_mints(text: str) -> list[str]:
    """Extract and deduplicate probable Solana mint addresses from text."""
    if not text:
        return []
    matches = MINT_PATTERN.findall(text)
    mints: list[str] = []
    seen: set[str] = set()
    for m in matches:
        if is_probable_solana_address(m) and m not in seen:
            seen.add(m)
            mints.append(m)
    return mints


def extract_cashtags(text: str) -> list[str]:
    """Extract and deduplicate cashtag symbols (e.g., $BONK -> BONK)."""
    if not text:
        return []
    matches = CASHTAG_PATTERN.findall(text)
    symbols: list[str] = []
    seen: set[str] = set()
    for sym in matches:
        upper = sym.upper()
        if upper not in seen:
            seen.add(upper)
            symbols.append(upper)
    return symbols


def extract_urls(text: str) -> list[str]:
    """Extract and validate URLs from text."""
    if not text:
        return []
    matches = URL_PATTERN.findall(text)
    valid_urls: list[str] = []
    seen: set[str] = set()
    for u in matches:
        cleaned = u.rstrip(".,;!?:)]}'\"")
        try:
            parsed = urlparse(cleaned)
            if parsed.scheme in ("http", "https") and parsed.netloc and cleaned not in seen:
                seen.add(cleaned)
                valid_urls.append(cleaned)
        except Exception:  # noqa: BLE001, S112
            continue
    return valid_urls
