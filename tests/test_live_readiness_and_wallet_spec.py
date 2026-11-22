"""
Test Suite for Live Trading Readiness Assessment and Wallet Architecture Specification (Phase 10).
Validates:
- Non-negotiable wallet policy enforcement (max tx, max exposure, daily loss circuit breaker).
- Unauthorized program rejection (DEX/System whitelist enforcement).
- Forbidden authority modification checks (SetAuthority, Assign).
- Emergency stop latching and recovery.
- Live trading readiness gating against empirical criteria (not ready vs extended paper trading).
- Strict human approval prerequisite enforcement.
"""
from decimal import Decimal

import pytest

from app.trading.wallet_spec import (
    PUMP_FUN_PROGRAM_ID,
    RAYDIUM_AMM_V4_PROGRAM_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    LiveReadinessStatus,
    LiveTradingReadinessEvaluator,
    MecoWalletPolicy,
    ReadinessGateCriteria,
    TransactionPolicyValidator,
    ValidationCode,
)


@pytest.fixture
def wallet_policy():
    return MecoWalletPolicy(
        wallet_address="MecoLivePilotWallet111111111111111111111111111",
        max_single_tx_sol=Decimal("0.5"),
        max_total_exposure_sol=Decimal("2.0"),
        max_daily_loss_sol=Decimal("1.0"),
    )


@pytest.fixture
def validator(wallet_policy):
    return TransactionPolicyValidator(policy=wallet_policy)


def test_wallet_policy_approves_compliant_transaction(validator, wallet_policy):
    """Compliant DEX swap within limits and whitelisted programs is approved."""
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.25"),
        current_wallet_exposure_sol=Decimal("0.5"),
        program_ids=[SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID, RAYDIUM_AMM_V4_PROGRAM_ID],
        destination_address=wallet_policy.wallet_address,
    )
    assert res.approved is True
    assert res.code == ValidationCode.APPROVED


def test_wallet_policy_rejects_exceeding_single_tx_limit(validator):
    """Transactions exceeding max single transaction size must be rejected."""
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.75"),  # Limit is 0.5 SOL
        current_wallet_exposure_sol=Decimal("0.0"),
        program_ids=[SYSTEM_PROGRAM_ID, PUMP_FUN_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res.approved is False
    assert res.code == ValidationCode.EXCEEDS_MAX_TX_SIZE
    assert "exceeds max single transaction limit" in res.reason


def test_wallet_policy_rejects_exceeding_total_exposure(validator):
    """Transactions pushing total hot wallet exposure past max capacity must be rejected."""
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.4"),
        current_wallet_exposure_sol=Decimal("1.8"),  # 1.8 + 0.4 = 2.2 SOL > 2.0 SOL cap
        program_ids=[SYSTEM_PROGRAM_ID, PUMP_FUN_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res.approved is False
    assert res.code == ValidationCode.EXCEEDS_TOTAL_EXPOSURE
    assert "exceeds max hot wallet capacity" in res.reason


def test_wallet_policy_rejects_unauthorized_programs(validator):
    """Any instruction targeting an unapproved program ID must be rejected immediately."""
    malicious_program_id = "MaliciousHackerProgram11111111111111111111111"
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.2"),
        current_wallet_exposure_sol=Decimal("0.5"),
        program_ids=[TOKEN_PROGRAM_ID, malicious_program_id],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res.approved is False
    assert res.code == ValidationCode.UNAUTHORIZED_PROGRAM_ID
    assert "is not in approved DEX/System whitelist" in res.reason


def test_wallet_policy_rejects_authority_mutations(validator):
    """Prohibited authority transfers (e.g. SetAuthority) must be unconditionally rejected."""
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.1"),
        current_wallet_exposure_sol=Decimal("0.2"),
        program_ids=[TOKEN_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
        contains_authority_change=True,
    )
    assert res.approved is False
    assert res.code == ValidationCode.FORBIDDEN_AUTHORITY_CHANGE


def test_wallet_policy_rejects_unauthorized_destination(validator):
    """Transactions sending assets to unknown external addresses must be blocked."""
    external_wallet = "UnknownThirdPartyAddress11111111111111111111"
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.2"),
        current_wallet_exposure_sol=Decimal("0.5"),
        program_ids=[SYSTEM_PROGRAM_ID],
        destination_address=external_wallet,
    )
    assert res.approved is False
    assert res.code == ValidationCode.UNAUTHORIZED_DESTINATION


def test_daily_loss_circuit_breaker_latches_emergency_stop(validator):
    """Accumulating daily losses beyond the circuit breaker latches the emergency kill-switch."""
    validator.record_realized_loss(Decimal("0.6"))
    assert validator.policy.emergency_stop_latched is False

    # Second loss crosses threshold 1.0 SOL
    validator.record_realized_loss(Decimal("0.5"))
    assert validator.policy.emergency_stop_latched is True

    # Any subsequent transaction attempt is blocked
    res = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.1"),
        current_wallet_exposure_sol=Decimal("0.1"),
        program_ids=[SYSTEM_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res.approved is False
    assert res.code == ValidationCode.EMERGENCY_STOP_ACTIVE


def test_emergency_stop_manual_trigger_and_reset(validator):
    """Manual emergency stop immediately blocks all attempts until explicitly cleared."""
    validator.trigger_emergency_stop()
    res1 = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.1"),
        current_wallet_exposure_sol=Decimal("0.1"),
        program_ids=[SYSTEM_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res1.approved is False
    assert res1.code == ValidationCode.EMERGENCY_STOP_ACTIVE

    validator.reset_emergency_stop()
    res2 = validator.validate_transaction_intent(
        outlay_sol=Decimal("0.1"),
        current_wallet_exposure_sol=Decimal("0.1"),
        program_ids=[SYSTEM_PROGRAM_ID],
        destination_address="MecoLivePilotWallet111111111111111111111111111",
    )
    assert res2.approved is True


# ==============================================================================
# Live Trading Readiness Evaluator Tests
# ==============================================================================

def test_readiness_evaluator_verdict_extended_paper_trading_on_negative_expectancy():
    """
    When system architecture and independent discovery are sound, but forward
    strategy performance exhibits negative or unproven net expectancy, the
    evaluator must strictly declare: READY FOR EXTENDED PAPER TRADING.
    """
    criteria = ReadinessGateCriteria()
    report = LiveTradingReadinessEvaluator.evaluate(
        criteria=criteria,
        observed_continuous_paper_days=4,
        observed_completed_trades=284,
        observed_unique_tokens=220,
        observed_net_expectancy_usd=-2.68,  # Negative EV from historical Telegram channel
        observed_profit_factor=0.68,
        observed_max_drawdown_pct=28.5,
        observed_out_of_sample_sharpe=-0.45,
        independent_discovery_active=True,
        zero_leakage_guaranteed=True,
        human_approval_granted=False,
    )
    assert report.verdict == LiveReadinessStatus.READY_FOR_EXTENDED_PAPER_TRADING
    assert report.is_pilot_eligible() is False
    assert len(report.unmet_criteria) > 0
    assert any("Net expectancy negative" in u for u in report.unmet_criteria)
    assert any("Explicit operator sign-off" not in u for u in report.met_criteria)


def test_readiness_evaluator_requires_human_approval_for_pilot():
    """Even if all statistical gates pass, lack of human explicit sign-off blocks pilot approval."""
    criteria = ReadinessGateCriteria()
    report = LiveTradingReadinessEvaluator.evaluate(
        criteria=criteria,
        observed_continuous_paper_days=45,
        observed_completed_trades=750,
        observed_unique_tokens=320,
        observed_net_expectancy_usd=1.45,
        observed_profit_factor=1.65,
        observed_max_drawdown_pct=8.5,
        observed_out_of_sample_sharpe=1.85,
        independent_discovery_active=True,
        zero_leakage_guaranteed=True,
        human_approval_granted=False,  # Human has not signed off
    )
    assert report.is_pilot_eligible() is False
    assert any("No explicit human operator approval" in u for u in report.unmet_criteria)


def test_readiness_evaluator_approves_pilot_only_when_all_conditions_and_human_signoff_met():
    """When all quantitative, operational, and human sign-off criteria are satisfied, pilot is approved."""
    criteria = ReadinessGateCriteria()
    report = LiveTradingReadinessEvaluator.evaluate(
        criteria=criteria,
        observed_continuous_paper_days=45,
        observed_completed_trades=750,
        observed_unique_tokens=320,
        observed_net_expectancy_usd=1.45,
        observed_profit_factor=1.65,
        observed_max_drawdown_pct=8.5,
        observed_out_of_sample_sharpe=1.85,
        independent_discovery_active=True,
        zero_leakage_guaranteed=True,
        human_approval_granted=True,  # Human explicitly approved
    )
    assert report.verdict == LiveReadinessStatus.READY_FOR_CONTROLLED_LIVE_PILOT
    assert report.is_pilot_eligible() is True
    assert len(report.unmet_criteria) == 0
