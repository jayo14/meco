"""
Realistic Paper Execution Simulator for Meco (Phase 6).
Simulates decentralized exchange execution dynamics with deterministic slippage,
constant-product AMM price impact, DEX fees, Solana priority fees, latency drift,
partial fills, and failure modes.
Clearly labels all assumptions. Never represents estimated fills as real exchange fills.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.trading.accounting import quantize_usd
from app.trading.models import OrderSide, SimulatedExecutionResult

logger = logging.getLogger("meco.trading.execution")


class ExecutionSimulatorConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_slippage_pct: Decimal = Field(default=Decimal("1.0"), description="Baseline execution slippage %")
    dex_fee_pct: Decimal = Field(default=Decimal("0.25"), description="Standard DEX swap fee % (e.g. 0.25% Raydium)")
    solana_priority_fee_usd: Decimal = Field(default=Decimal("0.02"), description="Solana compute unit priority fee in USD")
    quote_validity_seconds: float = Field(default=30.0, description="Max acceptable quote freshness age")
    latency_drift_seconds: float = Field(default=1.5, description="Average network + RPC execution arrival latency")
    latency_drift_pct_per_sec: Decimal = Field(default=Decimal("0.15"), description="Drift penalty per second of latency")
    max_acceptable_price_impact_pct: Decimal = Field(default=Decimal("5.0"), description="Hard ceiling for price impact")
    enable_partial_fills: bool = Field(default=True, description="Enable partial fills when liquidity is limited")
    min_fill_fraction: Decimal = Field(default=Decimal("0.35"), description="Minimum fill fraction before failing order")


class PaperExecutionSimulator:
    """
    Simulates realistic order execution on Solana DEXes (Raydium, Meteora, Orca, Pump.fun).
    """

    def __init__(self, config: ExecutionSimulatorConfig | None = None) -> None:
        self.config = config or ExecutionSimulatorConfig()

    def simulate_order(
        self,
        side: OrderSide,
        requested_size_usd: Decimal,
        displayed_spot_price: Decimal,
        pool_liquidity_usd: Decimal,
        quote_timestamp: datetime,
        execution_timestamp: datetime | None = None,
        dex_id: str = "raydium",
        transfer_fee_bps: int = 0,
        max_slippage_override_pct: Decimal | None = None,
    ) -> SimulatedExecutionResult:
        """
        Simulate order fill with realistic cost and friction mechanics.
        """
        now = execution_timestamp or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        q_time = quote_timestamp
        if q_time.tzinfo is None:
            q_time = q_time.replace(tzinfo=timezone.utc)

        requested_size_usd = quantize_usd(requested_size_usd)
        displayed_spot_price = Decimal(str(displayed_spot_price))

        # 1. Quote Expiration Check
        quote_age_seconds = max(0.0, (now - q_time).total_seconds())
        if quote_age_seconds > self.config.quote_validity_seconds:
            return SimulatedExecutionResult(
                success=False,
                side=side,
                requested_size_usd=requested_size_usd,
                requested_price=displayed_spot_price,
                failure_reason=f"Quote expired: age {quote_age_seconds:.1f}s > max {self.config.quote_validity_seconds}s limit.",
                is_simulated=True,
                assumptions_logged={"quote_age_seconds": quote_age_seconds},
            )

        # 2. Pool Liquidity Sanity Check
        if pool_liquidity_usd <= Decimal("0.00"):
            return SimulatedExecutionResult(
                success=False,
                side=side,
                requested_size_usd=requested_size_usd,
                requested_price=displayed_spot_price,
                failure_reason="Execution failed: Pool liquidity is zero or undefined.",
                is_simulated=True,
                assumptions_logged={"pool_liquidity_usd": str(pool_liquidity_usd)},
            )

        # 3. Constant Product AMM Price Impact Model
        # In a constant product x*y=k pool, reserve of base token in USD = pool_liquidity / 2
        reserve_side_usd = pool_liquidity_usd / Decimal("2.0")
        raw_price_impact_pct = (requested_size_usd / (reserve_side_usd + requested_size_usd)) * Decimal("100.0")

        fill_fraction = Decimal("1.0")
        executed_size_usd = requested_size_usd
        is_partial = False

        max_allowed_impact = max_slippage_override_pct or self.config.max_acceptable_price_impact_pct

        # Check if price impact exceeds threshold
        if raw_price_impact_pct > max_allowed_impact:
            if self.config.enable_partial_fills:
                # Calculate maximum size that satisfies max_allowed_impact
                # impact = size / (reserve + size) => size = reserve * (impact / (1 - impact))
                impact_fraction = max_allowed_impact / Decimal("100.0")
                max_viable_size = reserve_side_usd * (impact_fraction / (Decimal("1.0") - impact_fraction))
                max_viable_size = quantize_usd(max_viable_size)

                fill_fraction = max_viable_size / requested_size_usd
                if fill_fraction >= self.config.min_fill_fraction:
                    is_partial = True
                    executed_size_usd = max_viable_size
                    # Recalculate impact on partial size
                    raw_price_impact_pct = (executed_size_usd / (reserve_side_usd + executed_size_usd)) * Decimal("100.0")
                else:
                    return SimulatedExecutionResult(
                        success=False,
                        side=side,
                        requested_size_usd=requested_size_usd,
                        requested_price=displayed_spot_price,
                        failure_reason=(
                            f"Price impact {raw_price_impact_pct:.2f}% exceeds max {max_allowed_impact:.2f}%. "
                            f"Partial fill viable size ${max_viable_size} below minimum fill fraction {self.config.min_fill_fraction}."
                        ),
                        is_simulated=True,
                        assumptions_logged={"raw_price_impact_pct": str(raw_price_impact_pct)},
                    )
            else:
                return SimulatedExecutionResult(
                    success=False,
                    side=side,
                    requested_size_usd=requested_size_usd,
                    requested_price=displayed_spot_price,
                    failure_reason=f"Price impact {raw_price_impact_pct:.2f}% exceeds max {max_allowed_impact:.2f}%.",
                    is_simulated=True,
                    assumptions_logged={"raw_price_impact_pct": str(raw_price_impact_pct)},
                )

        # 4. Latency Drift Model
        # Between order submission and on-chain inclusion, price moves adversely
        drift_seconds = Decimal(str(self.config.latency_drift_seconds))
        latency_drift_pct = drift_seconds * self.config.latency_drift_pct_per_sec

        # 5. Base Slippage
        base_slippage_pct = self.config.base_slippage_pct

        # Total adverse execution price shift
        total_slippage_pct = raw_price_impact_pct + base_slippage_pct + latency_drift_pct

        if side == OrderSide.BUY:
            # Buyers pay higher price
            price_multiplier = Decimal("1.0") + (total_slippage_pct / Decimal("100.0"))
            executed_price = displayed_spot_price * price_multiplier
        else:
            # Sellers receive lower price
            price_multiplier = max(Decimal("0.0001"), Decimal("1.0") - (total_slippage_pct / Decimal("100.0")))
            executed_price = displayed_spot_price * price_multiplier

        # 6. Quantity Executed
        executed_quantity = executed_size_usd / executed_price

        # 7. Fees Calculation
        dex_fee_rate = self.config.dex_fee_pct / Decimal("100.0")
        if dex_id.lower() == "pumpfun":
            dex_fee_rate = Decimal("0.01")  # 1% standard on bonding curves

        dex_fee_usd = quantize_usd(executed_size_usd * dex_fee_rate)

        # Transfer tax
        transfer_tax_usd = Decimal("0.00")
        if transfer_fee_bps > 0:
            transfer_tax_usd = quantize_usd(executed_size_usd * (Decimal(transfer_fee_bps) / Decimal("10000.0")))

        network_fee_usd = self.config.solana_priority_fee_usd
        total_fees_usd = quantize_usd(dex_fee_usd + transfer_tax_usd + network_fee_usd)

        # Value breakdown of friction
        price_impact_usd = quantize_usd(executed_size_usd * (raw_price_impact_pct / Decimal("100.0")))
        base_slippage_usd = quantize_usd(executed_size_usd * (base_slippage_pct / Decimal("100.0")))

        assumptions = {
            "model": "constant_product_amm_xy_k",
            "dex_id": dex_id,
            "simulated_latency_drift_ms": int(self.config.latency_drift_seconds * 1000),
            "latency_drift_pct": str(latency_drift_pct),
            "base_slippage_pct": str(base_slippage_pct),
            "raw_price_impact_pct": str(raw_price_impact_pct),
            "total_effective_slippage_pct": str(total_slippage_pct),
            "is_partial_fill": is_partial,
            "fill_fraction": str(fill_fraction),
            "pool_reserve_usd": str(reserve_side_usd),
            "solana_priority_fee_usd": str(network_fee_usd),
            "simulated_label": "NOT_AN_EXCHANGE_FILL_ESTIMATED_SIMULATION",
        }

        return SimulatedExecutionResult(
            success=True,
            side=side,
            requested_size_usd=requested_size_usd,
            executed_size_usd=executed_size_usd,
            executed_quantity=executed_quantity,
            requested_price=displayed_spot_price,
            executed_price=executed_price,
            base_slippage_usd=base_slippage_usd,
            price_impact_usd=price_impact_usd,
            dex_fee_usd=dex_fee_usd,
            network_fee_usd=network_fee_usd,
            total_fee_usd=total_fees_usd,
            is_partial_fill=is_partial,
            fill_fraction=quantize_usd(fill_fraction),
            failure_reason=None,
            executed_at=now,
            assumptions_logged=assumptions,
            is_simulated=True,
        )
