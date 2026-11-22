"""
Point-In-Time Strategy Backtesting Engine for Meco (Phase 7).

Simulates trading strategies across historical checkpoints with realistic execution:
- Execution latency drift.
- AMM constant-product price impact ($x \\cdot y = k$).
- Roundtrip DEX fees (Raydium 0.25%, Pump.fun 1.0%) + Solana network fees.
- Liquidity constraints & maximum exit size.
- Multi-stage exits: stop loss, trailing stop, take profit stages, timeouts, liquidity collapse.
- Portfolio capital tracking, position limits, and execution failure handling.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.research.dataset import PointInTimeFeatures
from app.research.models_ml import BaseMLModel


@dataclass
class BacktestExecutionConfig:
    """Realistic execution environment settings."""
    initial_capital_usd: float = 10000.0
    position_size_usd: float = 100.0
    max_concurrent_positions: int = 5
    max_total_exposure_pct: float = 25.0
    execution_delay_seconds: float = 2.0  # Network + parsing latency
    base_slippage_pct: float = 1.5
    price_impact_factor: float = 2.0  # size / (pool / 2) * factor
    dex_fee_pct: float = 0.25  # per side
    solana_tx_fee_usd: float = 0.01  # lamports + priority fee per swap
    min_pool_liquidity_usd: float = 5000.0
    max_pool_fraction_pct: float = 2.0  # cannot buy more than 2% of pool
    max_acceptable_price_impact_pct: float = 5.0


@dataclass
class SimulatedTrade:
    """Record of a simulated backtest trade."""
    trade_id: str
    token_mint: str
    strategy_id: str
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime | None = None
    requested_entry_price: float = 0.0
    executed_entry_price: float = 0.0
    exit_price: float = 0.0
    position_size_usd: float = 0.0
    token_quantity: float = 0.0
    entry_friction_usd: float = 0.0
    exit_friction_usd: float = 0.0
    total_fees_usd: float = 0.0
    gross_pnl_usd: float = 0.0
    net_pnl_usd: float = 0.0
    return_pct: float = 0.0
    holding_duration_seconds: float = 0.0
    exit_reason: str = "timeout"
    peak_price: float = 0.0
    mfe_usd: float = 0.0
    mae_usd: float = 0.0
    is_executed: bool = True
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Comprehensive backtest outcome."""
    strategy_id: str
    total_signals_evaluated: int
    trades_executed: int
    trades_rejected: int
    completed_trades: list[SimulatedTrade]
    portfolio_equity_curve: list[tuple[str, float]]
    final_equity_usd: float
    net_profit_usd: float
    total_fees_paid_usd: float


class BacktestEngine:
    """
    Simulates strategy execution chronologically across historical event streams.
    Enforces realistic fills and portfolio constraints.
    """

    def __init__(self, config: BacktestExecutionConfig | None = None) -> None:
        self.config = config or BacktestExecutionConfig()

    def run_backtest(
        self,
        signals: list[PointInTimeFeatures],
        checkpoints_by_token: dict[str, list[dict[str, Any]]],
        model: BaseMLModel | None = None,
        probability_threshold: float = 0.60,
        strategy_id: str = "ml_momentum_v1",
        take_profit_pct: float = 25.0,
        stop_loss_pct: float = -15.0,
        trailing_stop_activation_pct: float | None = 15.0,
        trailing_stop_delta_pct: float | None = 10.0,
        max_holding_seconds: int = 1800,
        feature_columns: list[str] | None = None,
    ) -> BacktestResult:
        """
        Executes strategy chronologically across signals.
        """
        sorted_signals = sorted(signals, key=lambda s: s.timestamp)
        current_equity = self.config.initial_capital_usd
        available_capital = current_equity
        open_trades: list[SimulatedTrade] = []
        completed_trades: list[SimulatedTrade] = []
        equity_curve: list[tuple[str, float]] = [(sorted_signals[0].timestamp.isoformat() if sorted_signals else "", current_equity)]

        executed_count = 0
        rejected_count = 0
        total_fees = 0.0

        for idx, sig in enumerate(sorted_signals):
            token_mint = sig.token_mint
            t_sig = sig.timestamp
            if t_sig.tzinfo is None:
                t_sig = t_sig.replace(tzinfo=timezone.utc)

            # 1. Model Prediction Filter (if model provided)
            should_enter = True
            pred_prob = 1.0
            if model:
                vec = sig.to_feature_vector(feature_columns)
                probas = model.predict_proba([vec])
                pred_prob = probas[0] if probas else 0.0
                if pred_prob < probability_threshold:
                    should_enter = False

            if not should_enter:
                continue

            # 2. Portfolio Limits Check
            if len(open_trades) >= self.config.max_concurrent_positions:
                rejected_count += 1
                continue

            exposure_usd = sum(t.position_size_usd for t in open_trades)
            max_allowed_exposure = current_equity * (self.config.max_total_exposure_pct / 100.0)
            if (exposure_usd + self.config.position_size_usd) > max_allowed_exposure:
                rejected_count += 1
                continue

            if available_capital < self.config.position_size_usd:
                rejected_count += 1
                continue

            # 3. Liquidity & Price Impact Pre-Check
            liq = sig.liquidity_usd
            if liq < self.config.min_pool_liquidity_usd:
                rejected_count += 1
                continue

            max_allowed_size_by_pool = liq * (self.config.max_pool_fraction_pct / 100.0)
            if self.config.position_size_usd > max_allowed_size_by_pool:
                rejected_count += 1
                continue

            # 4. Realistic Execution Simulation with Latency Drift
            t_entry = t_sig + timedelta(seconds=self.config.execution_delay_seconds)
            token_cps = checkpoints_by_token.get(token_mint, [])

            # Find price at entry time (t >= t_entry)
            future_cps = [
                cp for cp in token_cps
                if (datetime.fromisoformat(cp["timestamp"]) if isinstance(cp["timestamp"], str) else cp["timestamp"]).replace(tzinfo=timezone.utc) >= t_entry
            ]

            if not future_cps or sig.price_usd <= 0.0:
                rejected_count += 1
                continue

            first_fill_cp = future_cps[0]
            fill_price_raw = float(first_fill_cp.get("price_usd", sig.price_usd))

            # Entry Friction: slippage + AMM impact + dex fee + network fee
            reserve_side = liq / 2.0
            impact_pct = (self.config.position_size_usd / reserve_side) * 100.0 * (self.config.price_impact_factor / 2.0)
            if impact_pct > self.config.max_acceptable_price_impact_pct:
                rejected_count += 1
                continue

            entry_slippage_and_impact = (self.config.base_slippage_pct + impact_pct) / 100.0
            executed_entry_price = fill_price_raw * (1.0 + entry_slippage_and_impact)

            entry_dex_fee = self.config.position_size_usd * (self.config.dex_fee_pct / 100.0)
            entry_friction = (executed_entry_price - fill_price_raw) * (self.config.position_size_usd / executed_entry_price) + entry_dex_fee + self.config.solana_tx_fee_usd

            qty = (self.config.position_size_usd - entry_friction) / executed_entry_price
            available_capital -= self.config.position_size_usd
            total_fees += entry_friction

            trade = SimulatedTrade(
                trade_id=f"trade_{idx}_{token_mint[:8]}",
                token_mint=token_mint,
                strategy_id=strategy_id,
                signal_timestamp=t_sig,
                entry_timestamp=t_entry,
                requested_entry_price=sig.price_usd,
                executed_entry_price=executed_entry_price,
                position_size_usd=self.config.position_size_usd,
                token_quantity=qty,
                entry_friction_usd=entry_friction,
                peak_price=executed_entry_price,
                metadata={"pred_prob": pred_prob},
            )
            executed_count += 1

            # 5. Simulate Forward Trajectory & Exits
            trade_closed = False
            best_p = executed_entry_price
            worst_p = executed_entry_price

            for cp in future_cps:
                cp_ts = cp["timestamp"]
                if isinstance(cp_ts, str):
                    cp_ts = datetime.fromisoformat(cp_ts)
                if cp_ts.tzinfo is None:
                    cp_ts = cp_ts.replace(tzinfo=timezone.utc)

                curr_p = float(cp.get("price_usd", executed_entry_price))
                curr_liq = float(cp.get("liquidity_usd", liq))
                elapsed_sec = (cp_ts - t_entry).total_seconds()

                if curr_p > best_p:
                    best_p = curr_p
                if curr_p < worst_p:
                    worst_p = curr_p

                gain_pct = ((curr_p - executed_entry_price) / executed_entry_price) * 100.0

                # Exit Condition 1: Fixed Stop Loss
                if gain_pct <= stop_loss_pct:
                    self._close_trade(trade, curr_p, curr_liq, cp_ts, elapsed_sec, "stop_loss")
                    trade_closed = True
                    break

                # Exit Condition 2: Trailing Stop
                if trailing_stop_activation_pct and trailing_stop_delta_pct:
                    peak_gain = ((best_p - executed_entry_price) / executed_entry_price) * 100.0
                    if peak_gain >= trailing_stop_activation_pct:
                        trail_price = best_p * (1.0 - trailing_stop_delta_pct / 100.0)
                        if curr_p <= trail_price:
                            self._close_trade(trade, curr_p, curr_liq, cp_ts, elapsed_sec, "trailing_stop")
                            trade_closed = True
                            break

                # Exit Condition 3: Take Profit
                if gain_pct >= take_profit_pct:
                    self._close_trade(trade, curr_p, curr_liq, cp_ts, elapsed_sec, "take_profit")
                    trade_closed = True
                    break

                # Exit Condition 4: Liquidity Collapse (>35% drop)
                if liq > 0 and ((liq - curr_liq) / liq * 100.0) >= 35.0:
                    self._close_trade(trade, curr_p, curr_liq, cp_ts, elapsed_sec, "liquidity_drain")
                    trade_closed = True
                    break

                # Exit Condition 5: Timeout
                if elapsed_sec >= max_holding_seconds:
                    self._close_trade(trade, curr_p, curr_liq, cp_ts, elapsed_sec, "max_holding_time")
                    trade_closed = True
                    break

            if not trade_closed and future_cps:
                last_cp = future_cps[-1]
                last_ts = last_cp["timestamp"]
                if isinstance(last_ts, str):
                    last_ts = datetime.fromisoformat(last_ts)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                self._close_trade(
                    trade,
                    float(last_cp.get("price_usd", executed_entry_price)),
                    float(last_cp.get("liquidity_usd", liq)),
                    last_ts,
                    (last_ts - t_entry).total_seconds(),
                    "horizon_end",
                )

            # Record excursions
            trade.peak_price = best_p
            trade.mfe_usd = max(0.0, (best_p - executed_entry_price) * trade.token_quantity)
            trade.mae_usd = abs(min(0.0, (worst_p - executed_entry_price) * trade.token_quantity))

            # Settle accounting
            available_capital += (self.config.position_size_usd + trade.net_pnl_usd)
            current_equity += trade.net_pnl_usd
            total_fees += trade.exit_friction_usd
            completed_trades.append(trade)

            equity_curve.append((trade.exit_timestamp.isoformat() if trade.exit_timestamp else t_entry.isoformat(), round(current_equity, 2)))

        net_profit = round(current_equity - self.config.initial_capital_usd, 2)

        return BacktestResult(
            strategy_id=strategy_id,
            total_signals_evaluated=len(signals),
            trades_executed=executed_count,
            trades_rejected=rejected_count,
            completed_trades=completed_trades,
            portfolio_equity_curve=equity_curve,
            final_equity_usd=round(current_equity, 2),
            net_profit_usd=net_profit,
            total_fees_paid_usd=round(total_fees, 2),
        )

    def _close_trade(
        self,
        trade: SimulatedTrade,
        exit_price_raw: float,
        exit_liq: float,
        exit_time: datetime,
        elapsed_sec: float,
        reason: str,
    ) -> None:
        """Calculate exit friction, net proceeds, and pnl."""
        reserve_side = max(500.0, exit_liq / 2.0)
        exit_notional = trade.token_quantity * exit_price_raw
        exit_impact_pct = (exit_notional / reserve_side) * 100.0 * (self.config.price_impact_factor / 2.0)
        exit_friction_pct = (self.config.base_slippage_pct + exit_impact_pct) / 100.0

        executed_exit_price = exit_price_raw * (1.0 - exit_friction_pct)
        exit_dex_fee = exit_notional * (self.config.dex_fee_pct / 100.0)
        exit_friction = (exit_price_raw - executed_exit_price) * trade.token_quantity + exit_dex_fee + self.config.solana_tx_fee_usd

        gross_proceeds = trade.token_quantity * exit_price_raw
        net_proceeds = trade.token_quantity * executed_exit_price - exit_dex_fee - self.config.solana_tx_fee_usd

        trade.exit_price = round(executed_exit_price, 8)
        trade.exit_timestamp = exit_time
        trade.holding_duration_seconds = round(elapsed_sec, 1)
        trade.exit_reason = reason
        trade.exit_friction_usd = round(exit_friction, 2)
        trade.total_fees_usd = round(trade.entry_friction_usd + exit_friction, 2)
        trade.gross_pnl_usd = round(gross_proceeds - trade.position_size_usd, 2)
        trade.net_pnl_usd = round(net_proceeds - trade.position_size_usd, 2)
        trade.return_pct = round((trade.net_pnl_usd / trade.position_size_usd) * 100.0, 2)
