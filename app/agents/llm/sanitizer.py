import json
import logging
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("meco.agents.llm.sanitizer")

# Patterns commonly used in prompt injection and delimiter breakout attacks
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|directives|prompts)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|rules|constraints)", re.IGNORECASE),
    re.compile(r"override\s+(the\s+)?system\s+(prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?(unrestricted|dan|developer|system\s+admin)", re.IGNORECASE),
    re.compile(r"(do\s+not|never)\s+report\s+(any\s+)?(risk|warning|threat|danger)", re.IGNORECASE),
    re.compile(r"(mark|classify|declare)\s+this\s+token\s+as\s+(100%?\s+)?(safe|clean|verified|legit)", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(safety|risk|security)\s+(filters|rules|checks)", re.IGNORECASE),
    re.compile(r"drop\s+(all\s+)?(security|hard\s+risk)\s+(flags|warnings)", re.IGNORECASE),
    re.compile(r"system\s*:\s*override", re.IGNORECASE),
    re.compile(r"\[/?(system|instruction|admin|developer)\]", re.IGNORECASE),
]

# Delimiter boundary tags that must not be permitted inside payload
DELIMITER_ESCAPE_PATTERN = re.compile(r"</?untrusted_external_data[^>]*>", re.IGNORECASE)


class SanitizedContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    original: str
    clean_text: str
    injections_detected: list[str] = Field(default_factory=list)
    is_suspicious: bool = False


def sanitize_untrusted_text(text: str | None, source_label: str = "untrusted") -> SanitizedContent:
    """
    Sanitize untrusted text from token descriptions, website metadata, social posts,
    or external APIs to neutralize prompt injection attacks.
    """
    if text is None:
        return SanitizedContent(original="", clean_text="", injections_detected=[], is_suspicious=False)

    original = str(text)
    clean = original
    detected = []

    # 1. Neutralize delimiter escape attempts
    if DELIMITER_ESCAPE_PATTERN.search(clean):
        detected.append("delimiter_escape_attempt")
        clean = DELIMITER_ESCAPE_PATTERN.sub("[ESCAPED_DELIMITER_TAG]", clean)

    # 2. Neutralize known prompt injection attacks
    for pattern in INJECTION_PATTERNS:
        matches = pattern.findall(clean)
        if matches:
            pattern_name = pattern.pattern[:40]
            detected.append(pattern_name)
            clean = pattern.sub("[NEUTRALIZED_PROMPT_INJECTION_ATTEMPT]", clean)

    is_suspicious = len(detected) > 0
    if is_suspicious:
        logger.warning(
            f"Prompt injection pattern detected in untrusted content from source '{source_label}': {detected}"
        )

    return SanitizedContent(
        original=original,
        clean_text=clean,
        injections_detected=detected,
        is_suspicious=is_suspicious,
    )


def wrap_untrusted_data(data: Any, source_label: str = "external_untrusted") -> str:
    """
    Sanitizes external data and encapsulates it within strict untrusted boundary tags.
    """
    if isinstance(data, (dict, list)):
        raw_str = json.dumps(data, default=str)
    else:
        raw_str = str(data or "")

    sanitized = sanitize_untrusted_text(raw_str, source_label=source_label)

    return (
        f'<untrusted_external_data source="{source_label}" '
        f'suspicious="{str(sanitized.is_suspicious).lower()}">\n'
        f"{sanitized.clean_text}\n"
        f"</untrusted_external_data>"
    )
