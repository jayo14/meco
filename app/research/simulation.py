from dataclasses import dataclass
from typing import Any

from app.database.models import MarketObservation, Signal
from app.research.models import PaperTradeResult


@dataclass
class ExecutionConfig:
    position_size_usd: float = 100.0
    base_slippage_pct: float = 1.5
    price_impact_factor: float = 2.0  # (position / liquidity) * factor
    dex_fee_pct: float = 0.25  # 0.25% each way
    solana_tx_fee_usd: float = 0.01  # ~$0.01 in SOL per swap
    min_pool_liquidity_usd: float = 5000.0


def simulate_paper_trade(
    signal: Signal,
    observations: list[MarketObservation],
    *,
    take_profit_pct: float = 20.0,
    stop_loss_pct: float = -15.0,
    max_holding_seconds: int = 180,
    trailing_stop_pct: float | None = None,
    config: ExecutionConfig | None = None,
) -> PaperTradeResult | None:
    """
    Simulate a paper trade on a signal through its observed path.
    Applies realistic execution constraints: slippage, liquidity, fees, and latency.
    """
    if config is None:
        config = ExecutionConfig()

    initial_price = signal.price_usd or 0.0
    initial_liq = signal.liquidity_usd or 0.0

    if initial_price <= 0 or initial_liq < config.min_pool_liquidity_usd:
        return None

    # Calculate entry price with slippage and impact
    liq_impact = (config.position_size_usd / initial_liq) * config.price_impact_factor * 100.0
    entry_slippage_pct = config.base_slippage_pct + liq_impact
    effective_entry_price = initial_price * (1.0 + entry_slippage_pct / 100.0)

    # Filter on-time valid observations sorted chronologically
    valid_obs = [
        o for o in observations
        if o.observation_status == "success"
        and o.price_usd is not None
        and o.price_usd > 0
        and abs(o.seconds_since_signal - o.target_seconds) <= 60
    ]
    valid_obs.sort(key=lambda o: o.seconds_since_signal)

    if not valid_obs:
        return None

    peak_price = effective_entry_price
    trough_price = effective_entry_price

    exit_price = effective_entry_price
    exit_reason = "timeout"
    exit_time = signal.received_at or signal.message_created_at
    holding_seconds = max_holding_seconds

    for obs in valid_obs:
        p = obs.price_usd
        sec = obs.seconds_since_signal

        if p > peak_price:
            peak_price = p
        if p < trough_price:
            trough_price = p

        ret_from_entry = ((p - effective_entry_price) / effective_entry_price) * 100.0

        # Check Stop Loss
        if ret_from_entry <= stop_loss_pct:
            exit_price = p
            exit_reason = "stop_loss"
            exit_time = obs.observed_at
            holding_seconds = sec
            break

        # Check Take Profit
        if ret_from_entry >= take_profit_pct:
            exit_price = p
            exit_reason = "take_profit"
            exit_time = obs.observed_at
            holding_seconds = sec
            break

        # Check Trailing Stop (if configured)
        if trailing_stop_pct is not None and peak_price > effective_entry_price:
            dd_from_peak = ((p - peak_price) / peak_price) * 100.0
            if dd_from_peak <= -trailing_stop_pct and ret_from_entry > 0:
                exit_price = p
                exit_reason = "trailing_stop"
                exit_time = obs.observed_at
                holding_seconds = sec
                break

        # Check Max Holding Time
        if sec >= max_holding_seconds:
            exit_price = p
            exit_reason = "timeout"
            exit_time = obs.observed_at
            holding_seconds = sec
            break
    else:
        # If no exit triggered in loop, exit at last observed price
        last_obs = valid_obs[-1]
        exit_price = last_obs.price_usd
        exit_reason = "timeout"
        exit_time = last_obs.observed_at
        holding_seconds = last_obs.seconds_since_signal

    # Calculate exit slippage
    exit_liq = initial_liq  # conservative approximation
    exit_impact = (config.position_size_usd / max(exit_liq, 1.0)) * config.price_impact_factor * 100.0
    exit_slippage_pct = config.base_slippage_pct + exit_impact
    effective_exit_price = exit_price * (1.0 - exit_slippage_pct / 100.0)

    # Returns
    gross_return_pct = ((exit_price - initial_price) / initial_price) * 100.0
    net_return_pct = ((effective_exit_price - effective_entry_price) / effective_entry_price) * 100.0

    # Total fees: roundtrip DEX fees + 2x network tx fee
    total_dex_fees_usd = config.position_size_usd * (config.dex_fee_pct * 2 / 100.0)
    total_tx_fees_usd = config.solana_tx_fee_usd * 2
    total_fees_usd = total_dex_fees_usd + total_tx_fees_usd

    net_pnl_usd = (config.position_size_usd * (net_return_pct / 100.0)) - total_fees_usd

    mfe_pct = ((peak_price - effective_entry_price) / effective_entry_price) * 100.0
    mae_pct = ((trough_price - effective_entry_price) / effective_entry_price) * 100.0

    return PaperTradeResult(
        signal_id=signal.id,
        token_address=signal.token_address,
        entry_timestamp=str(signal.received_at or signal.message_created_at),
        entry_price=effective_entry_price,
        entry_liquidity=initial_liq,
        position_size_usd=config.position_size_usd,
        exit_timestamp=str(exit_time),
        exit_price=effective_exit_price,
        exit_reason=exit_reason,
        holding_seconds=holding_seconds,
        gross_return_pct=gross_return_pct,
        estimated_fees_usd=total_fees_usd,
        estimated_slippage_pct=entry_slippage_pct + exit_slippage_pct,
        net_return_pct=net_return_pct,
        net_pnl_usd=net_pnl_usd,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
    )
