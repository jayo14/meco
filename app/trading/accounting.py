"""
Decimal Portfolio Accounting System for Meco Paper Trading Engine (Phase 6).
Guarantees strict financial precision without floating point inaccuracies.
Enforces double-entry balance reconciliation and tracking of capital reservations,
realised/unrealised PnL, drawdowns, and portfolio exposures.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any

from app.trading.models import PaperPosition, PortfolioSnapshot, PositionStatus

logger = logging.getLogger("meco.trading.accounting")

USD_PRECISION = Decimal("0.01")
TOKEN_PRECISION = Decimal("0.00000001")


def quantize_usd(value: Decimal | float | int | str) -> Decimal:
    """Format decimal to standard USD 2-decimal precision."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(USD_PRECISION, rounding=ROUND_HALF_UP)


class PortfolioAccount:
    """
    Manages capital allocations, reservations, PnL tracking, and drawdown calculations.
    """

    def __init__(self, starting_capital_usd: Decimal | str = Decimal("10000.00")) -> None:
        self.starting_capital: Decimal = quantize_usd(starting_capital_usd)
        self.available_capital: Decimal = self.starting_capital
        self.reserved_capital: Decimal = Decimal("0.00")
        self.realised_pnl: Decimal = Decimal("0.00")
        self.total_fees_paid: Decimal = Decimal("0.00")
        self.peak_equity: Decimal = self.starting_capital
        self.daily_realised_pnl: dict[str, Decimal] = {}  # YYYY-MM-DD -> pnl

    def reserve_capital(self, amount: Decimal) -> bool:
        """
        Temporarily earmark capital for an in-flight proposal or order.
        Fails if insufficient available capital.
        """
        amount = quantize_usd(amount)
        if amount <= Decimal("0.00"):
            return False
        if self.available_capital < amount:
            return False

        self.available_capital = quantize_usd(self.available_capital - amount)
        self.reserved_capital = quantize_usd(self.reserved_capital + amount)
        return True

    def release_capital(self, amount: Decimal) -> None:
        """Release reserved capital back to available (e.g. rejected or cancelled proposal)."""
        amount = quantize_usd(amount)
        release_amount = min(self.reserved_capital, amount)
        self.reserved_capital = quantize_usd(self.reserved_capital - release_amount)
        self.available_capital = quantize_usd(self.available_capital + release_amount)

    def commit_entry(self, amount_committed: Decimal, fee: Decimal) -> None:
        """
        Deduct reserved capital upon successful trade execution and account for buy fees.
        """
        amount_committed = quantize_usd(amount_committed)
        fee = quantize_usd(fee)

        # Release reservation; if entering without prior reservation, debit available capital directly
        if self.reserved_capital >= amount_committed:
            self.reserved_capital = quantize_usd(self.reserved_capital - amount_committed)
        else:
            unreserved = quantize_usd(amount_committed - self.reserved_capital)
            self.reserved_capital = Decimal("0.00")
            self.available_capital = quantize_usd(self.available_capital - unreserved)

        # Deduct transaction fee from available capital
        self.available_capital = quantize_usd(self.available_capital - fee)
        self.total_fees_paid = quantize_usd(self.total_fees_paid + fee)

    def record_exit(
        self,
        capital_returned: Decimal,
        realised_pnl: Decimal,
        fee: Decimal,
        as_of: datetime | None = None,
    ) -> None:
        """
        Process a partial or full position exit:
        Credit returned capital + realised profit/loss, deduct exit fee.
        """
        capital_returned = quantize_usd(capital_returned)
        realised_pnl = quantize_usd(realised_pnl)
        fee = quantize_usd(fee)

        net_proceeds = quantize_usd(capital_returned + realised_pnl - fee)
        self.available_capital = quantize_usd(self.available_capital + net_proceeds)
        self.realised_pnl = quantize_usd(self.realised_pnl + realised_pnl)
        self.total_fees_paid = quantize_usd(self.total_fees_paid + fee)

        # Track daily realised PnL for circuit breaker
        ts = as_of or datetime.now(timezone.utc)
        day_key = ts.strftime("%Y-%m-%d")
        prior_day_pnl = self.daily_realised_pnl.get(day_key, Decimal("0.00"))
        self.daily_realised_pnl[day_key] = quantize_usd(prior_day_pnl + realised_pnl - fee)

    def get_open_positions_value(self, positions: list[PaperPosition]) -> Decimal:
        """Calculate total current mark-to-market value of open positions."""
        total = Decimal("0.00")
        for p in positions:
            if p.status in (PositionStatus.OPEN, PositionStatus.PARTIALLY_EXITED):
                val = p.quantity * p.current_mark_price
                total += val
        return quantize_usd(total)

    def get_unrealised_pnl(self, positions: list[PaperPosition]) -> Decimal:
        """Sum unrealised PnL across all open positions."""
        total = Decimal("0.00")
        for p in positions:
            if p.status in (PositionStatus.OPEN, PositionStatus.PARTIALLY_EXITED):
                total += p.unrealised_pnl_usd
        return quantize_usd(total)

    def get_net_equity(self, positions: list[PaperPosition]) -> Decimal:
        """
        Net Equity = Available Capital + Reserved Capital + Current Open Positions Value
        """
        open_val = self.get_open_positions_value(positions)
        equity = quantize_usd(self.available_capital + self.reserved_capital + open_val)

        # Update high watermark peak equity
        if equity > self.peak_equity:
            self.peak_equity = equity

        return equity

    def get_drawdown_pct(self, positions: list[PaperPosition]) -> Decimal:
        """Calculate drawdown percentage from historical peak equity."""
        equity = self.get_net_equity(positions)
        if self.peak_equity <= Decimal("0.00"):
            return Decimal("0.00")
        drawdown_usd = self.peak_equity - equity
        if drawdown_usd <= Decimal("0.00"):
            return Decimal("0.00")
        return quantize_usd((drawdown_usd / self.peak_equity) * Decimal("100.00"))

    def get_exposure_by_token(self, positions: list[PaperPosition]) -> dict[str, Decimal]:
        """Aggregate current position value exposure by token mint."""
        exposure: dict[str, Decimal] = {}
        for p in positions:
            if p.status in (PositionStatus.OPEN, PositionStatus.PARTIALLY_EXITED):
                val = quantize_usd(p.quantity * p.current_mark_price)
                exposure[p.mint_address] = exposure.get(p.mint_address, Decimal("0.00")) + val
        return exposure

    def get_exposure_by_strategy(self, positions: list[PaperPosition]) -> dict[str, Decimal]:
        """Aggregate current position value exposure by strategy ID."""
        exposure: dict[str, Decimal] = {}
        for p in positions:
            if p.status in (PositionStatus.OPEN, PositionStatus.PARTIALLY_EXITED):
                val = quantize_usd(p.quantity * p.current_mark_price)
                exposure[p.strategy_id] = exposure.get(p.strategy_id, Decimal("0.00")) + val
        return exposure

    def get_daily_loss_today(self, as_of: datetime | None = None) -> Decimal:
        """Return net daily realised PnL for today (returns positive number if in loss)."""
        ts = as_of or datetime.now(timezone.utc)
        day_key = ts.strftime("%Y-%m-%d")
        today_pnl = self.daily_realised_pnl.get(day_key, Decimal("0.00"))
        if today_pnl < Decimal("0.00"):
            return abs(today_pnl)
        return Decimal("0.00")

    def reconcile(self, positions: list[PaperPosition]) -> tuple[bool, str]:
        """
        Verify fundamental accounting invariant:
        Net Equity == Starting Capital + Realised PnL + Unrealised PnL - Total Fees Paid
        """
        net_equity = self.get_net_equity(positions)
        unrealised = self.get_unrealised_pnl(positions)
        expected_equity = quantize_usd(
            self.starting_capital + self.realised_pnl + unrealised - self.total_fees_paid
        )

        diff = abs(net_equity - expected_equity)
        # Allow at most 2 cents rounding discrepancy across multiple positions
        if diff > Decimal("0.02"):
            err_msg = (
                f"Accounting reconciliation mismatch: net_equity={net_equity} != "
                f"expected={expected_equity} (diff={diff}). "
                f"Starting={self.starting_capital}, Realised={self.realised_pnl}, "
                f"Unrealised={unrealised}, Fees={self.total_fees_paid}."
            )
            logger.error(err_msg)
            return False, err_msg

        return True, "Reconciliation successful."

    def get_snapshot(
        self,
        positions: list[PaperPosition],
        as_of: datetime | None = None,
    ) -> PortfolioSnapshot:
        """Produce an immutable snapshot of current portfolio accounting state."""
        eval_time = as_of or datetime.now(timezone.utc)
        open_val = self.get_open_positions_value(positions)
        unrealised = self.get_unrealised_pnl(positions)
        equity = self.get_net_equity(positions)
        drawdown = self.get_drawdown_pct(positions)
        open_count = sum(
            1 for p in positions if p.status in (PositionStatus.OPEN, PositionStatus.PARTIALLY_EXITED)
        )

        return PortfolioSnapshot(
            timestamp=eval_time,
            starting_capital=self.starting_capital,
            available_capital=self.available_capital,
            reserved_capital=self.reserved_capital,
            open_positions_value=open_val,
            realised_pnl=self.realised_pnl,
            unrealised_pnl=unrealised,
            total_fees=self.total_fees_paid,
            net_equity=equity,
            peak_equity=self.peak_equity,
            current_drawdown_pct=drawdown,
            open_positions_count=open_count,
            exposure_by_token=self.get_exposure_by_token(positions),
            exposure_by_strategy=self.get_exposure_by_strategy(positions),
        )
