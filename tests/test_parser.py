from datetime import datetime, timezone

from app.telegram.parser import (
    extract_token_address,
    extract_token_signal,
)


def test_extracts_address_after_ca():
    text = """
    Aping into $PUMPKINU at $110K!

    CA (Tap to copy): B7yfFFkX4NtxtQwGdegi2DuaVssitc3FGpqF2pxUH1zM
    """

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
        f"CA: {address}\nSlippage: 15%",
        chat_id=-100123,
        message_id=123,
        detected_at=datetime.now(timezone.utc),
    )

    assert signal is not None
    assert signal.token_address == address
    assert signal.slippage == 15.0
