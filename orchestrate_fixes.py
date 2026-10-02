import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update app/telegram/client.py
with open("app/telegram/client.py", "r") as f:
    client_content = f.read()

old_handle_start = """    message = event.message

    if not message.text:
        return

    if (
        settings.telegram_channel_ids
        and event.chat_id not in settings.telegram_channel_ids
    ):
        return

    chat = await event.get_chat()
    source_name = getattr(chat, "title", None)
    source_username = getattr(chat, "username", None)

    logger.info(
        "New Telegram message | source=%s | username=%s | "
        "chat_id=%s | message_id=%s",
        source_name,
        source_username,
        event.chat_id,
        message.id,
    )"""

new_handle_start = """    message = event.message

    if not message.text:
        return

    if (
        settings.telegram_channel_ids
        and event.chat_id not in settings.telegram_channel_ids
    ):
        logger.info(
            "IGNORED MESSAGE | chat_id=%s | message_id=%s",
            event.chat_id,
            message.id,
        )
        return

    chat = await event.get_chat()
    source_name = getattr(chat, "title", None)
    source_username = getattr(chat, "username", None)

    logger.info(
        "New Telegram message | source=%s | username=%s | "
        "chat_id=%s | message_id=%s",
        source_name,
        source_username,
        event.chat_id,
        message.id,
    )"""

client_content = client_content.replace(old_handle_start, new_handle_start)
with open("app/telegram/client.py", "w") as f:
    f.write(client_content)
run_cmd("Log explicitly ignored Telegram messages")

# 2. Update app/telegram/parser.py
parser_content = """import re
from dataclasses import dataclass
from datetime import datetime


SOLANA_ADDRESS_PATTERN = re.compile(
    r"[1-9A-HJ-NP-Za-km-z]{32,44}"
)

CA_PATTERN = re.compile(
    r"(?:"
    r"\\bCA\\b"
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
    detected_at: datetime


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
    detected_at: datetime,
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
        detected_at=detected_at,
    )
"""
with open("app/telegram/parser.py", "w") as f:
    f.write(parser_content)
run_cmd("Upgrade token address extraction to recognize CA context")

# 3. Update tests/test_parser.py
tests_content = """from datetime import datetime, timezone

from app.telegram.parser import (
    extract_token_address,
    extract_token_signal,
)


def test_extracts_address_after_ca():
    text = \"\"\"
    Aping into $PUMPKINU at $110K!

    CA (Tap to copy): B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM
    \"\"\"

    assert (
        extract_token_address(text)
        == "B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM"
    )


def test_extracts_address_after_contract_address():
    address = "B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM"

    text = f"Contract Address: {address}"

    assert extract_token_address(text) == address


def test_falls_back_to_bare_address():
    address = "B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM"

    text = f"Buy this token: {address}"

    assert extract_token_address(text) == address


def test_extract_token_signal():
    address = "B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM"

    signal = extract_token_signal(
        f"CA: {address}\\nSlippage: 15%",
        chat_id=-100123,
        message_id=123,
        detected_at=datetime.now(timezone.utc),
    )

    assert signal is not None
    assert signal.token_address == address
    assert signal.slippage == 15.0
"""
with open("tests/test_parser.py", "w") as f:
    f.write(tests_content)
run_cmd("Add token signal extraction tests")
