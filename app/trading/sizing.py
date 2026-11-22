"""
Configurable Position Sizing Engine for Meco Paper Trading Engine (Phase 6).
Computes risk-adjusted, liquidity-constrained trade allocations.
Never assumes fixed capital percentage is always appropriate.
Persists all sizing inputs and applied constraints.
"""
from decimal import Decimal
from enum import Enum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.trading.accounting import quantize_usd


class SizingMethod(str, Enum):
    FIXED_NOTIONAL = "fixed_notional"
    PERCENT_OF_EQUITY = "percent_of_equity"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    LIQUIDITY_CONSTRAINED = "liquidity_constrained"


class PositionSizingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_method: SizingMethod = SizingMethod.LIQUIDITY_CONSTRAINED
    base_notional_usd: Decimal = Field(default=Decimal("100.00"), description="Default fixed trade size")
    base_equity_pct: Decimal = Field(default=Decimal("2.5"), description="Base percent of total equity (e.g. 2.5%)")
    max_position_size_usd: Decimal = Field(default=Decimal("500.00"), description="Hard ceiling for any single position")
    min_position_size_usd: Decimal = Field(default=Decimal("25.00"), description="Minimum viable position size")
    max_pool_fraction_pct: Decimal = Field(default=Decimal("1.0"), description="Max percent of pool liquidity (e.g. 1%)")
    max_acceptable_price_impact_pct: Decimal = Field(default=Decimal("2.5"), description="Max acceptable price impact")
    max_total_exposure_pct: Decimal = Field(default=Decimal("50.0"), description="Max portfolio capital exposure")
    max_concurrent_positions: int = Field(default=5, description="Max simultaneous open positions")
    daily_loss_limit_usd: Decimal = Field(default=Decimal("800.00"), description="Circuit breaker daily loss limit")


class SizingDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allocated_size_usd: Decimal
    method_used: SizingMethod
    is_approved: bool
    rejection_reason: str | None = None
    inputs_used: dict[str, Any] = Field(default_factory=dict)
    constraints_applied: list[str] = Field(default_factory=list)


class PositionSizer:
    """
    Evaluates available capital, portfolio exposure, liquidity, expected impact,
    volatility, and daily loss limits to determine safe position sizing.
    """

    def __init__(self, config: PositionSizingConfig | None = None) -> None:
        self.config = config or PositionSizingConfig()

    def calculate_size(
        self,
        available_capital: Decimal,
        net_equity: Decimal,
        pool_liquidity_usd: Decimal,
        current_open_positions_count: int,
        current_total_exposure_usd: Decimal,
        daily_loss_today_usd: Decimal = Decimal("0.00"),
        risk_penalty_pct: Decimal = Decimal("0.00"),  # 0 to 100 risk penalty
        volatility_pct: Decimal | None = None,
        method_override: SizingMethod | None = None,
    ) -> SizingDecision:
        """
        Calculates position size strictly respecting all pre-trade constraints.
        """
        method = method_override or self.config.default_method
        constraints: list[str] = []

        inputs = {
            "available_capital": str(available_capital),
            "net_equity": str(net_equity),
            "pool_liquidity_usd": str(pool_liquidity_usd),
            "current_open_positions_count": current_open_positions_count,
            "current_total_exposure_usd": str(current_total_exposure_usd),
            "daily_loss_today_usd": str(daily_loss_today_usd),
            "risk_penalty_pct": str(risk_penalty_pct),
            "volatility_pct": str(volatility_pct) if volatility_pct is not None else None,
            "method": method.value,
        }

        # 1. Circuit breaker: Daily loss limit
        if daily_loss_today_usd >= self.config.daily_loss_limit_usd:
            return SizingDecision(
                allocated_size_usd=Decimal("0.00"),
                method_used=method,
                is_approved=False,
                rejection_reason=(
                    f"Daily loss limit breached: ${daily_loss_today_usd} >= "
                    f"${self.config.daily_loss_limit_usd} threshold."
                ),
                inputs_used=inputs,
                constraints_applied=["daily_loss_circuit_breaker"],
            )

        # 2. Maximum concurrent positions check
        if current_open_positions_count >= self.config.max_concurrent_positions:
            return SizingDecision(
                allocated_size_usd=Decimal("0.00"),
                method_used=method,
                is_approved=False,
                rejection_reason=(
                    f"Maximum concurrent positions reached: {current_open_positions_count} >= "
                    f"{self.config.max_concurrent_positions} limit."
                ),
                inputs_used=inputs,
                constraints_applied=["max_concurrent_positions_limit"],
            )

        # 3. Maximum total portfolio exposure check
        max_allowed_exposure = quantize_usd(net_equity * (self.config.max_total_exposure_pct / Decimal("100.00")))
        remaining_exposure_room = quantize_usd(max(Decimal("0.00"), max_allowed_exposure - current_total_exposure_usd))

        if remaining_exposure_room <= Decimal("0.00"):
            return SizingDecision(
                allocated_size_usd=Decimal("0.00"),
                method_used=method,
                is_approved=False,
                rejection_reason=(
                    f"Maximum portfolio exposure breached: total exposure ${current_total_exposure_usd} "
                    f"exceeds ${max_allowed_exposure} ({self.config.max_total_exposure_pct}% of equity)."
                ),
                inputs_used=inputs,
                constraints_applied=["portfolio_exposure_ceiling"],
            )

        # 4. Base Sizing Calculation
        if method == SizingMethod.FIXED_NOTIONAL:
            base_size = self.config.base_notional_usd
        elif method == SizingMethod.PERCENT_OF_EQUITY:
            base_size = quantize_usd(net_equity * (self.config.base_equity_pct / Decimal("100.00")))
        elif method == SizingMethod.VOLATILITY_ADJUSTED:
            # Scale down if token has high volatility (> 10%), scale up if lower
            vol = volatility_pct or Decimal("10.0")
            vol_factor = max(Decimal("0.25"), min(Decimal("1.50"), Decimal("10.0") / max(Decimal("1.0"), vol)))
            base_size = quantize_usd(net_equity * (self.config.base_equity_pct / Decimal("100.00")) * vol_factor)
            constraints.append(f"volatility_adjustment_factor_{vol_factor}")
        elif method == SizingMethod.LIQUIDITY_CONSTRAINED:
            # Base starts at equity percentage
            base_size = quantize_usd(net_equity * (self.config.base_equity_pct / Decimal("100.00")))
        else:
            base_size = self.config.base_notional_usd

        # 5. Risk-Penalty Scaling
        # If risk penalty is > 0 (e.g. higher risk agent warning), scale down proportionally
        if risk_penalty_pct > Decimal("0.0"):
            discount = max(Decimal("0.40"), Decimal("1.0") - (risk_penalty_pct / Decimal("150.0")))
            base_size = quantize_usd(base_size * discount)
            constraints.append(f"risk_discount_{discount}")

        # 6. Liquidity Ceiling Constraint (AMM Pool Fraction & Price Impact)
        max_pool_allowed = quantize_usd(pool_liquidity_usd * (self.config.max_pool_fraction_pct / Decimal("100.00")))
        if base_size > max_pool_allowed:
            base_size = max_pool_allowed
            constraints.append(f"capped_by_pool_liquidity_${max_pool_allowed}")

        # AMM Price Impact ceiling check: OrderSize / (Pool / 2) <= MaxImpact
        if pool_liquidity_usd > Decimal("0.0"):
            max_size_for_impact = quantize_usd(
                (pool_liquidity_usd / Decimal("2.0")) * (self.config.max_acceptable_price_impact_pct / Decimal("100.0"))
            )
            if base_size > max_size_for_impact:
                base_size = max_size_for_impact
                constraints.append(f"capped_by_price_impact_${max_size_for_impact}")

        # 7. Apply Hard Position Sizing Cap ($500)
        if base_size > self.config.max_position_size_usd:
            base_size = self.config.max_position_size_usd
            constraints.append(f"capped_by_max_position_size_${self.config.max_position_size_usd}")

        # 8. Available Capital and Exposure Room Cap
        final_size = min(base_size, available_capital, remaining_exposure_room)
        if final_size < base_size:
            constraints.append("capped_by_available_capital_or_exposure_room")

        final_size = quantize_usd(final_size)

        # 9. Minimum Viable Size Check
        if final_size < self.config.min_position_size_usd:
            return SizingDecision(
                allocated_size_usd=Decimal("0.00"),
                method_used=method,
                is_approved=False,
                rejection_reason=(
                    f"Calculated size ${final_size} is below minimum viable trade threshold "
                    f"${self.config.min_position_size_usd}."
                ),
                inputs_used=inputs,
                constraints_applied=constraints,
            )

        return SizingDecision(
            allocated_size_usd=final_size,
            method_used=method,
            is_approved=True,
            rejection_reason=None,
            inputs_used=inputs,
            constraints_applied=constraints,
        )
