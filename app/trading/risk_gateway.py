"""
Independent Pre-Trade Risk Gateway for Meco Paper Trading Engine (Phase 6).
Enforces non-negotiable hard risk constraints before ANY simulated trade execution.
Completely independent of LLM recommendations and decision engine soft scoring.
Persists every risk evaluation and rejection reason.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.trading.accounting import quantize_usd
from app.trading.models import PortfolioSnapshot, RiskGatewayDecision, TradeProposal

logger = logging.getLogger("meco.trading.risk_gateway")


class RiskGatewayConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_position_size_usd: Decimal = Field(default=Decimal("500.00"), description="Hard cap on single position size")
    max_total_exposure_pct: Decimal = Field(default=Decimal("50.0"), description="Max aggregate portfolio exposure %")
    max_concurrent_positions: int = Field(default=5, description="Max open positions allowed simultaneously")
    max_daily_loss_usd: Decimal = Field(default=Decimal("800.00"), description="Daily realised loss circuit breaker")
    max_drawdown_pct: Decimal = Field(default=Decimal("20.0"), description="Max portfolio drawdown % before halting new entries")
    min_pool_liquidity_usd: Decimal = Field(default=Decimal("5000.00"), description="Minimum required pool liquidity in USD")
    max_price_impact_pct: Decimal = Field(default=Decimal("3.0"), description="Maximum allowed simulated price impact %")
    max_slippage_pct: Decimal = Field(default=Decimal("4.0"), description="Maximum allowed total slippage %")
    emergency_stop_active: bool = Field(default=False, description="Manual or automatic kill switch")


class PreTradeRiskGateway:
    """
    Independent deterministic gatekeeper. Every proposed paper trade MUST pass
    all checks here before execution is permitted.
    """

    def __init__(self, config: RiskGatewayConfig | None = None) -> None:
        self.config = config or RiskGatewayConfig()
        self.audit_log: list[RiskGatewayDecision] = []
        self._emergency_stop_reason: str | None = None

    def trigger_emergency_stop(self, reason: str = "Manual emergency stop initiated") -> None:
        """Activate the emergency kill switch to immediately halt all entries."""
        self.config.emergency_stop_active = True
        self._emergency_stop_reason = reason
        logger.warning(f"EMERGENCY STOP ACTIVATED: {reason}")

    def reset_emergency_stop(self) -> None:
        """Clear the emergency kill switch."""
        self.config.emergency_stop_active = False
        self._emergency_stop_reason = None
        logger.info("Emergency stop deactivated.")

    @property
    def is_emergency_stop_active(self) -> bool:
        return self.config.emergency_stop_active

    def validate_proposal(
        self,
        proposal: TradeProposal,
        portfolio: PortfolioSnapshot,
        pool_liquidity_usd: Decimal,
        estimated_price_impact_pct: Decimal,
        daily_loss_today_usd: Decimal = Decimal("0.00"),
        as_of: datetime | None = None,
    ) -> RiskGatewayDecision:
        """
        Validate trade proposal against hard risk limits.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        rejections: list[str] = []
        rule_evals: dict[str, Any] = {}

        # 1. Emergency Kill Switch Check
        rule_evals["emergency_stop"] = self.config.emergency_stop_active
        if self.config.emergency_stop_active:
            rejections.append(f"Emergency stop is ACTIVE: {self._emergency_stop_reason or 'No reason provided'}.")

        # 2. Proposal Expiration Check
        rule_evals["proposal_expired"] = proposal.is_expired(eval_time)
        if proposal.is_expired(eval_time):
            rejections.append(f"Proposal is expired: expiration was {proposal.proposal_expiration.isoformat()}.")

        # 3. Minimum Liquidity Check
        rule_evals["pool_liquidity_usd"] = str(pool_liquidity_usd)
        if pool_liquidity_usd < self.config.min_pool_liquidity_usd:
            rejections.append(
                f"Insufficient pool liquidity: ${pool_liquidity_usd:,.2f} is below minimum ${self.config.min_pool_liquidity_usd:,.2f}."
            )

        # 4. Maximum Price Impact Check
        rule_evals["estimated_price_impact_pct"] = str(estimated_price_impact_pct)
        if estimated_price_impact_pct > self.config.max_price_impact_pct:
            rejections.append(
                f"Excessive price impact: {estimated_price_impact_pct:.2f}% exceeds max {self.config.max_price_impact_pct:.2f}%."
            )

        # 5. Maximum Position Size Check
        size_usd = proposal.proposed_position_size_usd
        rule_evals["proposed_size_usd"] = str(size_usd)
        if size_usd > self.config.max_position_size_usd:
            rejections.append(
                f"Proposed size ${size_usd} exceeds hard max position size ${self.config.max_position_size_usd}."
            )

        # 6. Maximum Concurrent Positions Check
        rule_evals["open_positions_count"] = portfolio.open_positions_count
        if portfolio.open_positions_count >= self.config.max_concurrent_positions:
            rejections.append(
                f"Max concurrent positions limit reached: {portfolio.open_positions_count} >= {self.config.max_concurrent_positions}."
            )

        # 7. Portfolio Maximum Drawdown Check
        rule_evals["current_drawdown_pct"] = str(portfolio.current_drawdown_pct)
        if portfolio.current_drawdown_pct >= self.config.max_drawdown_pct:
            rejections.append(
                f"Portfolio drawdown limit breached: {portfolio.current_drawdown_pct:.1f}% >= {self.config.max_drawdown_pct:.1f}%."
            )

        # 8. Daily Loss Limit Check
        rule_evals["daily_loss_today_usd"] = str(daily_loss_today_usd)
        if daily_loss_today_usd >= self.config.max_daily_loss_usd:
            rejections.append(
                f"Daily loss limit breached: ${daily_loss_today_usd} >= ${self.config.max_daily_loss_usd}."
            )

        # 9. Maximum Total Portfolio Exposure Check
        max_allowed_exposure = quantize_usd(portfolio.net_equity * (self.config.max_total_exposure_pct / Decimal("100.0")))
        new_total_exposure = quantize_usd(portfolio.open_positions_value + size_usd)
        rule_evals["new_total_exposure_usd"] = str(new_total_exposure)
        rule_evals["max_allowed_exposure_usd"] = str(max_allowed_exposure)
        if new_total_exposure > max_allowed_exposure:
            rejections.append(
                f"Total portfolio exposure ceiling breached: ${new_total_exposure} > max allowed ${max_allowed_exposure} "
                f"({self.config.max_total_exposure_pct}% of equity)."
            )

        # 10. Available Capital Sufficiency Check
        rule_evals["available_capital"] = str(portfolio.available_capital)
        if portfolio.available_capital < size_usd:
            rejections.append(
                f"Insufficient available capital: ${portfolio.available_capital} < proposed size ${size_usd}."
            )

        approved = len(rejections) == 0
        decision = RiskGatewayDecision(
            approved=approved,
            rejection_reasons=rejections,
            adjusted_size_usd=size_usd if approved else Decimal("0.00"),
            checked_at=eval_time,
            rule_evaluations=rule_evals,
        )

        self.audit_log.append(decision)
        return decision
