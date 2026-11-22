"""
Meco Live Trading Readiness & Wallet Architecture Specification (Phase 10).
This module provides architectural definitions, policy boundaries, and validation contracts
for a dedicated Meco trading wallet architecture and live trading gatekeeper.

SAFETY ENFORCEMENT:
- THIS MODULE DOES NOT SIGN TRANSACTIONS.
- THIS MODULE DOES NOT LOAD, GENERATE, OR STORE PRIVATE KEYS OR SEED PHRASES.
- THIS MODULE DOES NOT BROADCAST TRANSACTIONS OR MOVE REAL FUNDS.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LiveReadinessStatus(str, Enum):
    NOT_READY = "NOT READY"
    READY_FOR_EXTENDED_PAPER_TRADING = "READY FOR EXTENDED PAPER TRADING"
    READY_FOR_CONTROLLED_LIVE_PILOT = (
        "READY FOR A CONTROLLED LIVE-TRADING PILOT, SUBJECT TO EXPLICIT HUMAN APPROVAL"
    )


# Standard Solana Well-Known Program IDs
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

# Approved DEX & Launchpad Program IDs
RAYDIUM_AMM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM_PROGRAM_ID = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
JUPITER_V6_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"

DEFAULT_ALLOWED_PROGRAMS = {
    SYSTEM_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
    MEMO_PROGRAM_ID,
    RAYDIUM_AMM_V4_PROGRAM_ID,
    RAYDIUM_CPMM_PROGRAM_ID,
    PUMP_FUN_PROGRAM_ID,
    JUPITER_V6_PROGRAM_ID,
}


class MecoWalletPolicy(BaseModel):
    """
    Non-negotiable security boundaries for the proposed Meco dedicated live wallet.
    Any proposed transaction violating ANY parameter is unconditionally rejected.
    """
    model_config = ConfigDict(extra="ignore")

    wallet_address: str = Field(description="Dedicated public address for Meco operations only")
    max_single_tx_sol: Decimal = Field(
        default=Decimal("0.5"),
        description="Hard cap on SOL outlay per individual swap transaction (~$75-$100)",
    )
    max_total_exposure_sol: Decimal = Field(
        default=Decimal("2.0"),
        description="Maximum combined SOL + token value permitted in hot wallet (~$300-$400)",
    )
    max_daily_loss_sol: Decimal = Field(
        default=Decimal("1.0"),
        description="Daily realized loss threshold that latches the emergency kill switch",
    )
    allowed_programs: set[str] = Field(
        default_factory=lambda: set(DEFAULT_ALLOWED_PROGRAMS),
        description="Strict whitelist of program IDs permitted in instructions",
    )
    enforce_whitelisted_recipients_only: bool = Field(
        default=True,
        description="Asserts that token/SOL outputs return strictly to wallet_address",
    )
    prohibit_arbitrary_transfers: bool = Field(
        default=True,
        description="Forbids SOL/SPL transfers to non-DEX, non-custodial external addresses",
    )
    prohibit_authority_mutations: bool = Field(
        default=True,
        description="Forbids SetAuthority, Assign, or account ownership modifications",
    )
    emergency_stop_latched: bool = Field(
        default=False,
        description="Global kill-switch; when True, all transactions are rejected",
    )


class ValidationCode(str, Enum):
    APPROVED = "approved"
    EMERGENCY_STOP_ACTIVE = "emergency_stop_active"
    EXCEEDS_MAX_TX_SIZE = "exceeds_max_tx_size"
    EXCEEDS_TOTAL_EXPOSURE = "exceeds_total_exposure"
    EXCEEDS_DAILY_LOSS = "exceeds_daily_loss"
    UNAUTHORIZED_PROGRAM_ID = "unauthorized_program_id"
    FORBIDDEN_AUTHORITY_CHANGE = "forbidden_authority_change"
    UNAUTHORIZED_DESTINATION = "unauthorized_destination"
    INVALID_INSTRUCTION_DATA = "invalid_instruction_data"


class TransactionValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    validation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    approved: bool
    code: ValidationCode
    reason: str
    inspected_tx_size_sol: Decimal = Decimal(0)
    inspected_program_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransactionPolicyValidator:
    """
    Pre-signing validator. Validates that proposed transaction payloads comply
    strictly with MecoWalletPolicy before ANY request can reach the signing boundary.
    """

    def __init__(self, policy: MecoWalletPolicy) -> None:
        self.policy = policy
        self._daily_realized_loss_sol = Decimal("0.0")

    def record_realized_loss(self, loss_sol: Decimal) -> None:
        """Records realized loss for 24-hour circuit breaker tracking."""
        if loss_sol > Decimal("0.0"):
            self._daily_realized_loss_sol += loss_sol
            if self._daily_realized_loss_sol >= self.policy.max_daily_loss_sol:
                self.policy.emergency_stop_latched = True

    def reset_daily_loss_counter(self) -> None:
        """Resets 24-hour window loss counter."""
        self._daily_realized_loss_sol = Decimal("0.0")

    def trigger_emergency_stop(self) -> None:
        """Manually latches the emergency kill-switch."""
        self.policy.emergency_stop_latched = True

    def reset_emergency_stop(self) -> None:
        """Clears the emergency kill-switch."""
        self.policy.emergency_stop_latched = False

    def validate_transaction_intent(
        self,
        *,
        outlay_sol: Decimal,
        current_wallet_exposure_sol: Decimal,
        program_ids: list[str],
        destination_address: str,
        contains_authority_change: bool = False,
    ) -> TransactionValidationResult:
        """
        Deterministically inspects and validates transaction intent against security policy.
        """
        # 1. Emergency stop check
        if self.policy.emergency_stop_latched:
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.EMERGENCY_STOP_ACTIVE,
                reason="Wallet emergency stop is latched. All transaction execution is blocked.",
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        # 2. Maximum single transaction size check
        if outlay_sol > self.policy.max_single_tx_sol:
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.EXCEEDS_MAX_TX_SIZE,
                reason=(
                    f"Outlay {outlay_sol} SOL exceeds max single transaction limit of "
                    f"{self.policy.max_single_tx_sol} SOL."
                ),
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        # 3. Maximum total portfolio exposure check
        projected_exposure = current_wallet_exposure_sol + outlay_sol
        if projected_exposure > self.policy.max_total_exposure_sol:
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.EXCEEDS_TOTAL_EXPOSURE,
                reason=(
                    f"Projected exposure {projected_exposure} SOL exceeds max hot wallet capacity of "
                    f"{self.policy.max_total_exposure_sol} SOL."
                ),
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        # 4. Daily loss limit check
        if self._daily_realized_loss_sol >= self.policy.max_daily_loss_sol:
            self.policy.emergency_stop_latched = True
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.EXCEEDS_DAILY_LOSS,
                reason=(
                    f"Daily loss {self._daily_realized_loss_sol} SOL reached circuit breaker "
                    f"of {self.policy.max_daily_loss_sol} SOL."
                ),
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        # 5. Program ID whitelist check
        for prog in program_ids:
            if prog not in self.policy.allowed_programs:
                return TransactionValidationResult(
                    approved=False,
                    code=ValidationCode.UNAUTHORIZED_PROGRAM_ID,
                    reason=f"Program ID '{prog}' is not in approved DEX/System whitelist.",
                    inspected_tx_size_sol=outlay_sol,
                    inspected_program_ids=program_ids,
                )

        # 6. Authority change prohibition
        if contains_authority_change:
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.FORBIDDEN_AUTHORITY_CHANGE,
                reason="Transaction contains prohibited SetAuthority or account ownership modification.",
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        # 7. Destination assertion
        if (
            self.policy.enforce_whitelisted_recipients_only
            and destination_address != self.policy.wallet_address
            and destination_address not in self.policy.allowed_programs
        ):
            return TransactionValidationResult(
                approved=False,
                code=ValidationCode.UNAUTHORIZED_DESTINATION,
                reason=(
                    f"Destination '{destination_address}' does not match Meco wallet address "
                    f"'{self.policy.wallet_address}' or approved DEX pool."
                ),
                inspected_tx_size_sol=outlay_sol,
                inspected_program_ids=program_ids,
            )

        return TransactionValidationResult(
            approved=True,
            code=ValidationCode.APPROVED,
            reason="Transaction complies with all MecoWalletPolicy security constraints.",
            inspected_tx_size_sol=outlay_sol,
            inspected_program_ids=program_ids,
        )


@dataclass
class ReadinessGateCriteria:
    """Quantitative thresholds required before live trading can be considered."""
    min_continuous_paper_days: int = 30
    min_completed_paper_trades: int = 500
    min_unique_tokens_traded: int = 150
    min_net_expectancy_usd: float = 0.50
    min_profit_factor: float = 1.30
    max_portfolio_drawdown_pct: float = 15.0
    min_out_of_sample_sharpe: float = 1.20
    independent_discovery_verified: bool = True
    zero_leakage_verified: bool = True
    human_explicit_signoff: bool = False


@dataclass
class ReadinessEvaluationReport:
    """Audit report assessing live trading readiness against empirical criteria."""
    evaluation_timestamp: datetime
    verdict: LiveReadinessStatus
    unmet_criteria: list[str] = field(default_factory=list)
    met_criteria: list[str] = field(default_factory=list)
    measured_metrics: dict[str, Any] = field(default_factory=dict)
    summary_rationale: str = ""

    def is_pilot_eligible(self) -> bool:
        return self.verdict == LiveReadinessStatus.READY_FOR_CONTROLLED_LIVE_PILOT


class LiveTradingReadinessEvaluator:
    """
    Evaluates historical, statistical, and operational evidence to produce
    a definitive, unbiased live trading readiness outcome.
    """

    @classmethod
    def evaluate(
        cls,
        *,
        criteria: ReadinessGateCriteria,
        observed_continuous_paper_days: int,
        observed_completed_trades: int,
        observed_unique_tokens: int,
        observed_net_expectancy_usd: float,
        observed_profit_factor: float,
        observed_max_drawdown_pct: float,
        observed_out_of_sample_sharpe: float,
        independent_discovery_active: bool,
        zero_leakage_guaranteed: bool,
        human_approval_granted: bool = False,
    ) -> ReadinessEvaluationReport:
        now = datetime.now(timezone.utc)
        met: list[str] = []
        unmet: list[str] = []
        metrics: dict[str, Any] = {
            "continuous_paper_days": observed_continuous_paper_days,
            "completed_paper_trades": observed_completed_trades,
            "unique_tokens_traded": observed_unique_tokens,
            "net_expectancy_usd": observed_net_expectancy_usd,
            "profit_factor": observed_profit_factor,
            "max_drawdown_pct": observed_max_drawdown_pct,
            "out_of_sample_sharpe": observed_out_of_sample_sharpe,
            "independent_discovery_active": independent_discovery_active,
            "zero_leakage_guaranteed": zero_leakage_guaranteed,
            "human_approval_granted": human_approval_granted,
        }

        # 1. Continuous Paper Trading Duration
        if observed_continuous_paper_days >= criteria.min_continuous_paper_days:
            met.append(f"Continuous paper duration: {observed_continuous_paper_days}d >= {criteria.min_continuous_paper_days}d")
        else:
            unmet.append(
                f"Continuous paper duration insufficient: observed {observed_continuous_paper_days}d < "
                f"required {criteria.min_continuous_paper_days}d."
            )

        # 2. Completed Trade Sample Size
        if observed_completed_trades >= criteria.min_completed_paper_trades:
            met.append(f"Completed trades: {observed_completed_trades} >= {criteria.min_completed_paper_trades}")
        else:
            unmet.append(
                f"Trade sample size too small: observed {observed_completed_trades} < "
                f"required {criteria.min_completed_paper_trades}."
            )

        # 3. Unique Tokens Traded
        if observed_unique_tokens >= criteria.min_unique_tokens_traded:
            met.append(f"Unique tokens: {observed_unique_tokens} >= {criteria.min_unique_tokens_traded}")
        else:
            unmet.append(
                f"Token diversity insufficient: observed {observed_unique_tokens} < "
                f"required {criteria.min_unique_tokens_traded}."
            )

        # 4. Realistic Net Expectancy
        if observed_net_expectancy_usd >= criteria.min_net_expectancy_usd:
            met.append(f"Net expectancy positive: ${observed_net_expectancy_usd:.2f} >= ${criteria.min_net_expectancy_usd:.2f}")
        else:
            unmet.append(
                f"Net expectancy negative or inadequate: observed ${observed_net_expectancy_usd:.2f} < "
                f"required +${criteria.min_net_expectancy_usd:.2f} per trade."
            )

        # 5. Profit Factor
        if observed_profit_factor >= criteria.min_profit_factor:
            met.append(f"Profit factor: {observed_profit_factor:.2f} >= {criteria.min_profit_factor:.2f}")
        else:
            unmet.append(
                f"Profit factor sub-threshold: observed {observed_profit_factor:.2f} < "
                f"required {criteria.min_profit_factor:.2f}."
            )

        # 6. Maximum Drawdown
        if observed_max_drawdown_pct <= criteria.max_portfolio_drawdown_pct:
            met.append(f"Max drawdown controlled: {observed_max_drawdown_pct:.1f}% <= {criteria.max_portfolio_drawdown_pct:.1f}%")
        else:
            unmet.append(
                f"Excessive portfolio drawdown: observed {observed_max_drawdown_pct:.1f}% > "
                f"threshold {criteria.max_portfolio_drawdown_pct:.1f}%."
            )

        # 7. Out of Sample Sharpe
        if observed_out_of_sample_sharpe >= criteria.min_out_of_sample_sharpe:
            met.append(f"Out-of-sample Sharpe: {observed_out_of_sample_sharpe:.2f} >= {criteria.min_out_of_sample_sharpe:.2f}")
        else:
            unmet.append(
                f"Out-of-sample Sharpe poor: observed {observed_out_of_sample_sharpe:.2f} < "
                f"required {criteria.min_out_of_sample_sharpe:.2f}."
            )

        # 8. Independent Discovery
        if independent_discovery_active:
            met.append("Independent discovery architecture (PumpPortal WS + RPC) verified and active.")
        else:
            unmet.append("Independent discovery architecture not operational.")

        # 9. Zero Data Leakage
        if zero_leakage_guaranteed:
            met.append("Chronological train/test splits and zero-leakage feature guards confirmed.")
        else:
            unmet.append("Potential data leakage or forward contamination detected.")

        # 10. Human Explicit Approval
        if human_approval_granted:
            met.append("Explicit operator sign-off in writing confirmed.")
        else:
            unmet.append("No explicit human operator approval has been granted for live trading.")

        # Determine Verdict
        if len(unmet) == 0 and human_approval_granted:
            verdict = LiveReadinessStatus.READY_FOR_CONTROLLED_LIVE_PILOT
            rationale = "All quantitative, statistical, operational, and safety gates are satisfied."
        elif (
            independent_discovery_active
            and zero_leakage_guaranteed
            and observed_net_expectancy_usd <= 0.0
        ):
            # System infrastructure is sound, but underlying strategy has not proven positive forward expectancy
            verdict = LiveReadinessStatus.READY_FOR_EXTENDED_PAPER_TRADING
            rationale = (
                "System architecture, safety guards, and data pipelines are fully operational, but "
                "forward trading strategies have not yet established statistically significant positive "
                "net expectancy after realistic execution friction. The platform must remain in 24/7 "
                "extended paper-trading mode."
            )
        else:
            verdict = LiveReadinessStatus.NOT_READY
            rationale = "Fundamental infrastructure, sample size, or safety criteria are not satisfied."

        return ReadinessEvaluationReport(
            evaluation_timestamp=now,
            verdict=verdict,
            unmet_criteria=unmet,
            met_criteria=met,
            measured_metrics=metrics,
            summary_rationale=rationale,
        )
