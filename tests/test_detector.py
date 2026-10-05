import struct
from unittest.mock import AsyncMock
import pytest

from app.research.onchain import PUMP_PROGRAM_ID
from app.solana.detector import (
    PUMP_DISCRIMINATOR_LENGTH,
    PUMP_TARGET_SOL_LAMPORTS,
    BondingCurveMetrics,
    build_pump_logs_subscription_request,
    decode_bonding_curve_data,
    inspect_token_curve,
    parse_pump_instruction_logs,
    scan_bonding_curves,
)


def _pack_mock_curve(
    virtual_token: int = 1_073_000_000_000_000,
    virtual_sol: int = 30_000_000_000,
    real_token: int = 793_100_000_000_000,
    real_sol: int = 42_500_000_000,  # 42.5 SOL (50% progress)
    total_supply: int = 1_000_000_000_000_000,
    complete: bool = False,
) -> bytes:
    discriminator = b"\x17\xb7\xf8\x37\x60\xd8\xac\x60"
    data = discriminator + struct.pack(
        "<QQQQQ?",
        virtual_token,
        virtual_sol,
        real_token,
        real_sol,
        total_supply,
        complete,
    )
    # Pad to standard account size
    return data.ljust(151, b"\x00")


def test_decode_bonding_curve_data_valid():
    raw_data = _pack_mock_curve(
        virtual_token=1_000_000_000_000_000,  # 1B tokens with 6 decimals = 1B standard units
        virtual_sol=30_000_000_000,           # 30 SOL
        real_sol=42_500_000_000,              # 42.5 SOL (50% of 85 SOL)
        complete=False,
    )

    metrics = decode_bonding_curve_data(raw_data)
    assert metrics is not None
    assert metrics.virtual_token_reserves == 1_000_000_000_000_000
    assert metrics.virtual_sol_reserves == 30_000_000_000
    assert metrics.real_sol_reserves_sol == pytest.approx(42.5)
    assert metrics.curve_progress_pct == pytest.approx(50.0)
    assert metrics.complete is False
    assert metrics.price_sol > 0.0


def test_decode_bonding_curve_data_too_short():
    short_data = b"\x00" * 30
    assert decode_bonding_curve_data(short_data) is None


def test_parse_pump_instruction_logs():
    pump_id_str = str(PUMP_PROGRAM_ID)

    create_logs = [
        f"Program {pump_id_str} invoke [1]",
        "Program log: Instruction: Create",
        f"Program {pump_id_str} success",
    ]
    parsed_create = parse_pump_instruction_logs(create_logs)
    assert parsed_create["is_pump_program"] is True
    assert parsed_create["is_creation"] is True
    assert parsed_create["instruction_type"] == "create"

    buy_logs = [
        f"Program {pump_id_str} invoke [1]",
        "Program log: Instruction: Buy",
        f"Program {pump_id_str} success",
    ]
    parsed_buy = parse_pump_instruction_logs(buy_logs)
    assert parsed_buy["is_pump_program"] is True
    assert parsed_buy["is_trade"] is True
    assert parsed_buy["instruction_type"] == "buy"

    other_logs = [
        "Program 11111111111111111111111111111111 invoke [1]",
        "Program log: Instruction: Transfer",
        "Program 11111111111111111111111111111111 success",
    ]
    parsed_other = parse_pump_instruction_logs(other_logs)
    assert parsed_other["is_pump_program"] is False
    assert parsed_other["is_creation"] is False


def test_build_pump_logs_subscription_request():
    req = build_pump_logs_subscription_request(subscription_id=42)
    assert req["id"] == 42
    assert req["method"] == "logsSubscribe"
    assert req["params"][0]["mentions"] == [str(PUMP_PROGRAM_ID)]


@pytest.mark.asyncio
async def test_inspect_token_curve_and_scan():
    mock_client = AsyncMock()

    valid_mint = "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump"
    raw_data = _pack_mock_curve(real_sol=85_000_000_000, complete=True)

    mock_account = AsyncMock()
    mock_account.lamports = 85_000_000_000
    mock_account.data = raw_data
    mock_resp = AsyncMock()
    mock_resp.value = mock_account
    mock_client.get_account_info.return_value = mock_resp

    snapshot = await inspect_token_curve(valid_mint, mock_client)
    assert snapshot.exists is True
    assert snapshot.metrics is not None
    assert snapshot.metrics.complete is True
    assert snapshot.metrics.curve_progress_pct == pytest.approx(100.0)

    # Test invalid mint
    bad_snapshot = await inspect_token_curve("invalid_mint_address", mock_client)
    assert bad_snapshot.exists is False
    assert bad_snapshot.error == "invalid_mint_address"

    # Test scan_bonding_curves concurrency
    mints = [
        "6HEDwKSR1UpV8dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
        "5DkXk8P1w3kG9dJW7sVjFQoh2UnXKCZZCWi8uZVgpump",
    ]
    results = await scan_bonding_curves(mints, mock_client, max_concurrency=2)
    assert len(results) == 2
    assert results[valid_mint].exists is True
