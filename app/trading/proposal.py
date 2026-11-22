"""
Trade Proposal Generator for Meco Paper Trading Engine (Phase 6).
Translates Decision Engine institutional findings and candidate verdicts
into structured, executable trade proposals without directly executing them.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Any

from app.decision.models import DecisionOutcome, TokenDecisionInput, TokenDecisionResult
from app.trading.accounting import quantize_usd
from app.trading.models import (
    ExitConditions,
    PortfolioSnapshot,
    ProposalStatus,
    StopLossConfig,
    TakeProfitConfig,
    TakeProfitStage,
    TradeProposal,
)
from app.trading.sizing import PositionSizer

logger = logging.getLogger("meco.trading.proposal")


class ProposalGenerator:
    """
    Constructs well-formed TradeProposals from DecisionEngine results and sizing rules.
    Decouples decision making from execution gating.
    """

    def __init__(self, default_validity_seconds: int = 120) -> None:
        self.default_validity_seconds = default_validity_seconds

    def generate_proposal(
        self,
        decision: TokenDecisionResult,
        token_input: TokenDecisionInput,
        portfolio: PortfolioSnapshot,
        sizer: PositionSizer,
        strategy_id: str = "momentum_breakout",
        strategy_version: str = "1.0.0",
        validity_seconds: int | None = None,
        as_of: datetime | None = None,
    ) -> TradeProposal | None:
        """
        Produce a TradeProposal for qualifying candidates (e.g. PAPER_TRADE_CANDIDATE).
        Returns None if token is rejected or not qualified for trade consideration.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # 1. Eligibility Check: Decision Outcome
        if decision.outcome != DecisionOutcome.PAPER_TRADE_CANDIDATE:
            logger.info(
                f"Token {decision.mint_address} has outcome {decision.outcome.value}; ineligible for trade proposal."
            )
            return None

        # 2. Decision Expiration Check
        if decision.is_expired(at_time=eval_time):
            logger.warning(f"Decision {decision.decision_id} for {decision.mint_address} is expired.")
            return None

        # 3. Extract Market Reference Price and Liquidity
        pool = token_input.liquidity_pool or {}
        obs = token_input.market_observations or []
        latest_obs = obs[-1] if obs else {}

        spot_price_float = float(
            latest_obs.get("price_usd") or pool.get("price_usd") or 0.0
        )
        if spot_price_float <= 0.0:
            logger.warning(f"No valid spot price for token {decision.mint_address}.")
            return None
        spot_price = Decimal(str(spot_price_float))

        pool_liq_float = float(pool.get("liquidity_usd") or 0.0)
        pool_liq_usd = Decimal(str(pool_liq_float))

        # 4. Position Sizing
        # Pull risk penalty from decision dimension scores
        risk_penalty = Decimal(str(decision.dimension_scores.composite_risk_penalty()))
        volatility_float = float(latest_obs.get("price_change_5m") or 10.0)
        volatility_pct = Decimal(str(abs(volatility_float)))

        sizing = sizer.calculate_size(
            available_capital=portfolio.available_capital,
            net_equity=portfolio.net_equity,
            pool_liquidity_usd=pool_liq_usd,
            current_open_positions_count=portfolio.open_positions_count,
            current_total_exposure_usd=portfolio.open_positions_value,
            daily_loss_today_usd=Decimal("0.00"),
            risk_penalty_pct=risk_penalty,
            volatility_pct=volatility_pct,
        )

        val_secs = validity_seconds or self.default_validity_seconds
        expiration = eval_time + timedelta(seconds=val_secs)

        if not sizing.is_approved:
            # Return rejected proposal recording the sizing denial
            return TradeProposal(
                mint_address=decision.mint_address,
                token_id=decision.token_id,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                decision_id=decision.decision_id,
                proposed_entry_price=spot_price,
                proposed_position_size_usd=Decimal("0.00"),
                proposal_timestamp=eval_time,
                proposal_expiration=expiration,
                status=ProposalStatus.REJECTED,
                rejection_reason=f"Position sizing rejected: {sizing.rejection_reason}",
                risk_assessment={"decision_confidence": decision.confidence},
            )

        # 5. Estimate Expected Price Impact
        reserve_side = pool_liq_usd / Decimal("2.0") if pool_liq_usd > 0 else Decimal("1.0")
        expected_impact_pct = quantize_usd(
            (sizing.allocated_size_usd / (reserve_side + sizing.allocated_size_usd)) * Decimal("100.0")
        )

        # 6. Configure Strategy-Specific Exit Conditions
        if "breakout" in strategy_id:
            exit_conditions = ExitConditions(
                stop_loss=StopLossConfig(
                    stop_loss_pct=Decimal("12.0"),
                    is_trailing=True,
                    trailing_activation_pct=Decimal("15.0"),
                    trailing_delta_pct=Decimal("8.0"),
                ),
                take_profit=TakeProfitConfig(
                    stages=[
                        TakeProfitStage(target_gain_pct=Decimal("25.0"), close_fraction=Decimal("0.50")),
                        TakeProfitStage(target_gain_pct=Decimal("60.0"), close_fraction=Decimal("1.00")),
                    ]
                ),
                max_holding_seconds=5400,  # 90 minutes
                max_liquidity_drop_pct=Decimal("25.0"),
                exit_on_critical_risk=True,
            )
        else:
            exit_conditions = ExitConditions(
                stop_loss=StopLossConfig(stop_loss_pct=Decimal("15.0")),
                take_profit=TakeProfitConfig(
                    stages=[
                        TakeProfitStage(target_gain_pct=Decimal("30.0"), close_fraction=Decimal("0.50")),
                        TakeProfitStage(target_gain_pct=Decimal("80.0"), close_fraction=Decimal("1.00")),
                    ]
                ),
                max_holding_seconds=7200,
                max_liquidity_drop_pct=Decimal("30.0"),
                exit_on_critical_risk=True,
            )

        risk_assessment = {
            "decision_confidence": decision.confidence,
            "security_risk_score": decision.dimension_scores.security_risk.score,
            "wallet_risk_score": decision.dimension_scores.wallet_deployer_risk.score,
            "opportunity_score": decision.dimension_scores.opportunity_quality.score,
            "scoring_config_version": decision.scoring_config_version,
            "sizing_constraints": sizing.constraints_applied,
        }

        return TradeProposal(
            mint_address=decision.mint_address,
            token_id=decision.token_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            decision_id=decision.decision_id,
            proposed_entry_price=spot_price,
            proposed_position_size_usd=sizing.allocated_size_usd,
            expected_slippage_pct=Decimal("1.5"),
            max_acceptable_price_impact_pct=Decimal("3.0"),
            exit_conditions=exit_conditions,
            risk_assessment=risk_assessment,
            proposal_timestamp=eval_time,
            proposal_expiration=expiration,
            status=ProposalStatus.PENDING,
        )
