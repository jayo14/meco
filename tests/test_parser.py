from datetime import datetime, timezone

from app.telegram.parser import (
    extract_slippage,
    extract_solana_addresses,
    extract_token_signal,
)


TEST_TIME = datetime.now(timezone.utc)


def test_extract_solana_address():
    address = "So11111111111111111111111111111111111111112"

    text = f"BUY THIS TOKEN\nCA: {address}"

    result = extract_solana_addresses(text)

    assert result == [address]


def test_extract_slippage():
    text = "🔥 NEW TOKEN\nSLIPPAGE: 15%"

    result = extract_slippage(text)

    assert result == 15.0


def test_extract_token_signal():
    address = "So11111111111111111111111111111111111111112"

    text = f"""
    🚀 NEW CALL

    CA: {address}

    SLIPPAGE: 10%
    """

    result = extract_token_signal(
        text,
        chat_id=123456,
        message_id=789,
        detected_at=TEST_TIME,
    )

    assert result is not None
    assert result.token_address == address
    assert result.slippage == 10.0
    assert result.chat_id == 123456
    assert result.message_id == 789
    assert result.message_text == text
    assert result.detected_at == TEST_TIME


def test_no_token_returns_none():
    text = "Hey, this is just a normal Telegram message."

    result = extract_token_signal(
        text,
        chat_id=123456,
        message_id=789,
        detected_at=TEST_TIME,
    )

    assert result is None
