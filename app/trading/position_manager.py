"""
Autonomous Position Manager and Exit Evaluator for Meco (Phase 6).
Evaluates open positions on market and risk events, enforcing:
- Fixed and trailing stop losses.
- Multi-stage partial take profits.
- Maximum holding duration timeouts.
- Liquidity deterioration exits.
- Risk-triggered exits.
- MFE / MAE excursion tracking.
Guarantees AI agents cannot override mandatory risk limits.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.trading.accounting import PortfolioAccount, quantize_usd
from app.trading.execution import PaperExecutionSimulator
from app.trading.models import (
    ExitConditions,
    ExitReason,
    OrderSide,
    OrderType,
    PaperOrder,
    PaperPosition,
    PositionStatus,
    SimulatedExecutionResult,
)

logger = logging.getLogger("meco.trading.position_manager")


class ExitSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    should_exit: bool
    reason: ExitReason | None = None
    fraction: Decimal = Decimal("1.0")
    details: str = ""


class ExitEvaluator:
    """
    Evaluates open positions against deterministic exit triggers.
    AI agents cannot override these safety gates.
    """

    @classmethod
    def evaluate(
        cls,
        position: PaperPosition,
        current_price: Decimal,
        current_liquidity_usd: Decimal | None = None,
        initial_liquidity_usd: Decimal | None = None,
        is_token_in_hard_risk: bool = False,
        volume_collapse: bool = False,
        as_of: datetime | None = None,
    ) -> ExitSignal:
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        conditions = position.exit_conditions
        entry_price = position.entry_price

        # 1. Mandatory Critical Risk Triggered Exit
        if is_token_in_hard_risk and conditions.exit_on_critical_risk:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.RISK_TRIGGERED,
                fraction=Decimal("1.0"),
                details="Emergency risk-triggered exit: token flagged with critical hard risk.",
            )

        # 2. Liquidity Deterioration Exit
        if current_liquidity_usd is not None and initial_liquidity_usd is not None and initial_liquidity_usd > Decimal("0.0"):
            liq_drop_pct = ((initial_liquidity_usd - current_liquidity_usd) / initial_liquidity_usd) * Decimal("100.0")
            if liq_drop_pct >= conditions.max_liquidity_drop_pct:
                return ExitSignal(
                    should_exit=True,
                    reason=ExitReason.LIQUIDITY_DETERIORATION,
                    fraction=Decimal("1.0"),
                    details=f"Liquidity drained by {liq_drop_pct:.1f}% >= threshold {conditions.max_liquidity_drop_pct:.1f}%.",
                )

        # 3. Strategy Invalidation (Volume Collapse) Exit
        if volume_collapse:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.STRATEGY_INVALIDATION,
                fraction=Decimal("1.0"),
                details="Trading volume and order flow collapsed to near zero.",
            )

        # 4. Trailing Stop Loss Check
        sl_cfg = conditions.stop_loss
        if sl_cfg.is_trailing:
            # Check if profit reached activation threshold
            peak_gain_pct = ((position.peak_price - entry_price) / entry_price) * Decimal("100.0")
            if peak_gain_pct >= sl_cfg.trailing_activation_pct:
                trail_stop_price = position.peak_price * (Decimal("1.0") - (sl_cfg.trailing_delta_pct / Decimal("100.0")))
                if current_price <= trail_stop_price:
                    return ExitSignal(
                        should_exit=True,
                        reason=ExitReason.TRAILING_STOP,
                        fraction=Decimal("1.0"),
                        details=(
                            f"Trailing stop triggered: price {current_price} fell below trail level "
                            f"{trail_stop_price} ({sl_cfg.trailing_delta_pct}% from peak {position.peak_price})."
                        ),
                    )

        # 5. Fixed Stop Loss Check
        fixed_stop_price = entry_price * (Decimal("1.0") - (sl_cfg.stop_loss_pct / Decimal("100.0")))
        if current_price <= fixed_stop_price:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                fraction=Decimal("1.0"),
                details=f"Fixed stop loss hit: price {current_price} <= stop level {fixed_stop_price}.",
            )

        # 6. Take Profit Stages Check (Supports Partial Exits)
        gain_pct = ((current_price - entry_price) / entry_price) * Decimal("100.0")
        tp_stages = conditions.take_profit.stages
        # Identify how many exits have already occurred
        completed_tp_exits = sum(
            1 for o in position.exit_history if o.details.get("reason") in (ExitReason.TAKE_PROFIT_PARTIAL, ExitReason.TAKE_PROFIT_FULL)
        )

        if completed_tp_exits < len(tp_stages):
            stage = tp_stages[completed_tp_exits]
            if gain_pct >= stage.target_gain_pct:
                is_last_stage = (completed_tp_exits + 1) >= len(tp_stages) or stage.close_fraction >= Decimal("1.0")
                reason = ExitReason.TAKE_PROFIT_FULL if is_last_stage else ExitReason.TAKE_PROFIT_PARTIAL
                return ExitSignal(
                    should_exit=True,
                    reason=reason,
                    fraction=stage.close_fraction,
                    details=f"Take-Profit stage {completed_tp_exits + 1} reached: gain {gain_pct:.1f}% >= target {stage.target_gain_pct}%.",
                )

        # 7. Max Holding Duration Timeout
        elapsed_seconds = position.holding_duration_seconds(at_time=eval_time)
        if elapsed_seconds >= conditions.max_holding_seconds:
            return ExitSignal(
                should_exit=True,
                reason=ExitReason.MAX_HOLDING_TIME,
                fraction=Decimal("1.0"),
                details=f"Max holding time reached: {elapsed_seconds:.0f}s >= {conditions.max_holding_seconds}s limit.",
            )

        return ExitSignal(should_exit=False)


class PositionManager:
    """
    Tracks and updates all active paper positions, evaluates exit rules,
    and coordinates position exits with the execution simulator and portfolio account.
    """

    def __init__(self) -> None:
        self.open_positions: dict[str, PaperPosition] = {}
        self.positions_history: list[PaperPosition] = []

    def open_position(
        self,
        proposal_id: str,
        mint_address: str,
        strategy_id: str,
        entry_price: Decimal,
        quantity: Decimal,
        capital_committed: Decimal,
        exit_conditions: ExitConditions,
        token_id: int | None = None,
        initial_pool_liquidity_usd: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> PaperPosition:
        """Create and track a new active position upon simulated buy fill."""
        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        pos = PaperPosition(
            proposal_id=proposal_id,
            mint_address=mint_address,
            token_id=token_id,
            strategy_id=strategy_id,
            status=PositionStatus.OPEN,
            entry_time=now,
            entry_price=entry_price,
            quantity=quantity,
            capital_committed=capital_committed,
            current_mark_price=entry_price,
            unrealised_pnl_usd=Decimal("0.00"),
            realised_pnl_usd=Decimal("0.00"),
            total_fees_paid_usd=Decimal("0.00"),
            exit_history=[],
            exit_conditions=exit_conditions,
            peak_price=entry_price,
            initial_pool_liquidity_usd=initial_pool_liquidity_usd,
            max_favourable_excursion_usd=Decimal("0.00"),
            max_adverse_excursion_usd=Decimal("0.00"),
            updated_at=now,
        )
        self.open_positions[pos.position_id] = pos
        return pos

    def update_mark_price(
        self,
        position_id: str,
        current_price: Decimal,
        as_of: datetime | None = None,
    ) -> None:
        """
        Update position mark price, unrealised PnL, and MFE/MAE excursions.
        """
        pos = self.open_positions.get(position_id)
        if not pos:
            return

        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        pos.current_mark_price = current_price
        pos.updated_at = now

        # Update peak price for trailing stops
        if current_price > pos.peak_price:
            pos.peak_price = current_price

        # Unrealised PnL = (current_price - entry_price) * remaining_quantity
        pnl = (current_price - pos.entry_price) * pos.quantity
        pos.unrealised_pnl_usd = quantize_usd(pnl)

        # Track Maximum Favourable Excursion (MFE)
        if pos.unrealised_pnl_usd > pos.max_favourable_excursion_usd:
            pos.max_favourable_excursion_usd = pos.unrealised_pnl_usd

        # Track Maximum Adverse Excursion (MAE)
        if pos.unrealised_pnl_usd < Decimal("0.00"):
            adverse = abs(pos.unrealised_pnl_usd)
            if adverse > pos.max_adverse_excursion_usd:
                pos.max_adverse_excursion_usd = adverse

    def evaluate_and_execute_exits(
        self,
        mark_prices: dict[str, Decimal],
        pool_liquidities: dict[str, Decimal],
        execution_simulator: PaperExecutionSimulator,
        account: PortfolioAccount,
        risk_flags: dict[str, bool] | None = None,
        as_of: datetime | None = None,
    ) -> list[PaperOrder]:
        """
        Evaluate all open positions against exit triggers and execute necessary exits.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        executed_exit_orders: list[PaperOrder] = []
        positions_to_close: list[str] = []

        risk_flags = risk_flags or {}

        for pos_id, pos in list(self.open_positions.items()):
            price = mark_prices.get(pos.mint_address, pos.current_mark_price)
            self.update_mark_price(pos_id, price, as_of=eval_time)

            current_liq = pool_liquidities.get(pos.mint_address)
            is_risk = risk_flags.get(pos.mint_address, False)

            # Evaluate exit conditions
            exit_sig = ExitEvaluator.evaluate(
                position=pos,
                current_price=price,
                current_liquidity_usd=current_liq,
                initial_liquidity_usd=pos.initial_pool_liquidity_usd or current_liq,
                is_token_in_hard_risk=is_risk,
                as_of=eval_time,
            )

            if exit_sig.should_exit and exit_sig.reason is not None:
                qty_to_exit = pos.quantity * exit_sig.fraction
                size_usd_to_exit = quantize_usd(qty_to_exit * price)

                # Simulate execution on exit order
                sim_res = execution_simulator.simulate_order(
                    side=OrderSide.SELL,
                    requested_size_usd=size_usd_to_exit,
                    displayed_spot_price=price,
                    pool_liquidity_usd=current_liq or Decimal("50000.00"),
                    quote_timestamp=eval_time,
                    execution_timestamp=eval_time,
                )

                if sim_res.success:
                    # Calculate cost basis of the exited slice
                    cost_basis_slice = quantize_usd(pos.capital_committed * (qty_to_exit / (pos.quantity or Decimal("1.0"))))
                    realised_on_slice = quantize_usd(sim_res.executed_size_usd - cost_basis_slice)

                    # Record exit in portfolio accounting
                    account.record_exit(
                        capital_returned=cost_basis_slice,
                        realised_pnl=realised_on_slice,
                        fee=sim_res.total_fee_usd,
                        as_of=eval_time,
                    )

                    # Create and store paper order
                    order = PaperOrder(
                        position_id=pos.position_id,
                        mint_address=pos.mint_address,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        requested_size_usd=size_usd_to_exit,
                        executed_size_usd=sim_res.executed_size_usd,
                        executed_price=sim_res.executed_price,
                        executed_quantity=sim_res.executed_quantity,
                        total_fees_usd=sim_res.total_fee_usd,
                        status="completed",
                        created_at=eval_time,
                        executed_at=eval_time,
                        details={"reason": exit_sig.reason, "explanation": exit_sig.details},
                    )
                    pos.exit_history.append(order)
                    pos.realised_pnl_usd = quantize_usd(pos.realised_pnl_usd + realised_on_slice)
                    pos.total_fees_paid_usd = quantize_usd(pos.total_fees_paid_usd + sim_res.total_fee_usd)

                    # Update remaining position quantity and capital committed
                    pos.quantity = pos.quantity - qty_to_exit
                    pos.capital_committed = quantize_usd(pos.capital_committed - cost_basis_slice)

                    executed_exit_orders.append(order)

                    if pos.quantity <= Decimal("0.00000001") or exit_sig.fraction >= Decimal("1.0"):
                        # Full close
                        pos.status = PositionStatus.CLOSED
                        pos.closed_at = eval_time
                        pos.exit_reason = exit_sig.reason
                        pos.quantity = Decimal("0.00")
                        pos.unrealised_pnl_usd = Decimal("0.00")
                        positions_to_close.append(pos_id)
                    else:
                        # Partial exit
                        pos.status = PositionStatus.PARTIALLY_EXITED
                        # Recalculate remaining unrealised PnL
                        pos.unrealised_pnl_usd = quantize_usd((price - pos.entry_price) * pos.quantity)

        # Move closed positions to history
        for pid in positions_to_close:
            closed_pos = self.open_positions.pop(pid)
            self.positions_history.append(closed_pos)

        return executed_exit_orders

    def all_active_positions(self) -> list[PaperPosition]:
        return list(self.open_positions.values())

    def close_position(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_time: datetime,
        exit_reason: ExitReason = ExitReason.MANUAL_EXIT,
        fee_usd: Decimal = Decimal("0.00"),
    ) -> PaperPosition:
        """Manually close an open position and move it to positions_history."""
        pos = self.open_positions.pop(position_id)
        pos.status = PositionStatus.CLOSED
        pos.closed_at = exit_time
        pos.exit_reason = exit_reason
        gross_pnl = (exit_price - pos.entry_price) * pos.quantity
        pos.realised_pnl_usd = quantize_usd(gross_pnl - fee_usd)
        pos.unrealised_pnl_usd = Decimal("0.00")
        pos.total_fees_paid_usd = quantize_usd(pos.total_fees_paid_usd + fee_usd)
        pos.quantity = Decimal("0.00")
        self.positions_history.append(pos)
        return pos

    def all_closed_positions(self) -> list[PaperPosition]:
        return self.positions_history
