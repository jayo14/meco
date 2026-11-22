"""
Security Log Redaction Module for Meco (Phase 9).
Automatically redacts API keys, credentials, private keys, database passwords,
Telegram session tokens, and Bearer tokens across all logs.
"""
import logging
import re

# Sensitive patterns that must never appear in logs
REDACTION_PATTERNS = [
    # 1. Database URLs containing passwords: postgresql://user:password@host
    (
        re.compile(r"(postgresql(?:\+asyncpg)?://[^:]+:)([^@]+)(@)", re.IGNORECASE),
        r"\1***\3",
    ),
    # 2. Bearer tokens: Bearer <token>
    (
        re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{12,}", re.IGNORECASE),
        r"\1[REDACTED_BEARER_TOKEN]",
    ),
    # 3. OpenAI / Anthropic / Generic LLM API keys: sk-...
    (
        re.compile(r"sk-[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
        "[REDACTED_LLM_API_KEY]",
    ),
    # 4. Query string API keys: api-key=..., api_key=..., token=...
    (
        re.compile(r"((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret)=\s*)([^\s&,;'\"]+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # 5. Telegram API Hash or Session Name secrets
    (
        re.compile(r"(telegram_api_hash['\":\s=]+)([a-f0-9]{32})", re.IGNORECASE),
        r"\1[REDACTED_TELEGRAM_HASH]",
    ),
    # 6. Solana base58 private keys (approx 87-88 characters)
    (
        re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{85,90}\b"),
        "[REDACTED_SOLANA_PRIVATE_KEY]",
    ),
    # 7. Solana Byte Array Private Key (e.g., [142, 23, ... 64 ints])
    (
        re.compile(r"\[(?:\s*\d{1,3}\s*,){60,}\s*\d{1,3}\s*\]"),
        "[REDACTED_BYTE_ARRAY_PRIVATE_KEY]",
    ),
]


def redact_sensitive_string(message: str) -> str:
    """Applies all redaction regular expressions to a log message string."""
    if not isinstance(message, str):
        return message

    redacted = message
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class LogRedactionFilter(logging.Filter):
    """
    Standard library logging filter that intercepts LogRecord instances
    and redacts secrets from msg and args before formatting.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_string(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_string(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    redact_sensitive_string(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True


def setup_secure_logging() -> None:
    """Configures the root logger with LogRedactionFilter."""
    root_logger = logging.getLogger()
    filter_installed = any(isinstance(f, LogRedactionFilter) for f in root_logger.filters)
    if not filter_installed:
        redaction_filter = LogRedactionFilter()
        root_logger.addFilter(redaction_filter)
        for handler in root_logger.handlers:
            handler.addFilter(redaction_filter)
