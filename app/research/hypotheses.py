from dataclasses import asdict
from typing import Any, Callable

from app.database.models import MarketObservation, Signal
from app.research.audit import calculate_mean
from app.research.features import extract_signal_features
from app.research.models import HypothesisResult, PaperTradeResult
from app.research.simulation import ExecutionConfig, simulate_paper_trade


def chronological_split(
    signals: list[Signal], train_fraction: float = 0.65
) -> tuple[list[Signal], list[Signal]]:
    """
    Split signals chronologically into earlier training set and later validation set.
    Sorts strictly by message_created_at (with id as tiebreaker) to guarantee zero temporal leakage.
    """
    sorted_signals = sorted(signals, key=lambda s: (s.message_created_at, s.id))
    n = len(sorted_signals)
    split_idx = int(n * train_fraction)
    return sorted_signals[:split_idx], sorted_signals[split_idx:]


def evaluate_hypothesis_on_set(
    signals: list[Signal],
    obs_by_signal: dict[int, list[MarketObservation]],
    filter_fn: Callable[[Signal], bool],
    *,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_holding_seconds: int,
    trailing_stop_pct: float | None = None,
    config: ExecutionConfig | None = None,
) -> list[PaperTradeResult]:
    """Run paper trading simulation on a set of signals matching the filter."""
    trades: list[PaperTradeResult] = []
    for s in signals:
        if not filter_fn(s):
            continue
        sim = simulate_paper_trade(
            s,
            obs_by_signal.get(s.id, []),
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            max_holding_seconds=max_holding_seconds,
            trailing_stop_pct=trailing_stop_pct,
            config=config,
        )
        if sim is not None:
            trades.append(sim)
    return trades


def run_hypotheses_evaluation(
    usable_signals: list[Signal],
    obs_by_signal: dict[int, list[MarketObservation]],
    train_fraction: float = 0.65,
) -> list[HypothesisResult]:
    """
    Evaluate candidate trading hypotheses across train and out-of-sample test splits.
    """
    train_signals, test_signals = chronological_split(
        usable_signals, train_fraction
    )

    hypotheses_defs = [
        {
            "name": "H0: Baseline Naive Follow (All Signals)",
            "rationale": "Test whether blindly trading every valid signal from this channel yields positive EV after realistic slippage and fees.",
            "filter_fn": lambda s: True,
            "feature_condition": "Any valid signal with price > 0 and liquidity >= $5,000",
            "entry_condition": "Market buy at T+0 with 1.5% base slippage + price impact",
            "exit_condition": "Take profit +25% or stop loss -15% or timeout at 180s",
            "stop_loss_pct": -15.0,
            "take_profit_pct": 25.0,
            "max_holding_seconds": 180,
            "trailing_stop_pct": None,
            "known_limitations": "Does not filter for illiquid tokens or post-pump exhaustion.",
            "potential_leakage": "None (pure baseline).",
        },
        {
            "name": "H1: Anti-Climax Filter (Low Volume/Liquidity)",
            "rationale": "Tokens called with low prior 5m volume (< $35k) and low volume-to-liquidity (<= 1.2) have not yet experienced severe volume climax/exhaustion and suffer lower catastrophic drawdowns.",
            "filter_fn": lambda s: (
                (s.volume_5m is not None and s.volume_5m <= 35000.0)
                and (
                    s.liquidity_usd is not None
                    and s.liquidity_usd > 0
                    and (s.volume_5m / s.liquidity_usd) <= 1.2
                )
            ),
            "feature_condition": "volume_5m <= $35,000 AND (volume_5m / liquidity_usd) <= 1.2",
            "entry_condition": "Market buy at T+0 with slippage + impact model",
            "exit_condition": "Take profit +20% or stop loss -12% or timeout at 120s",
            "stop_loss_pct": -12.0,
            "take_profit_pct": 20.0,
            "max_holding_seconds": 120,
            "trailing_stop_pct": None,
            "known_limitations": "Smaller sample size; many low-volume tokens have sluggish price action that times out.",
            "potential_leakage": "Features are strictly T+0 signal-time measurements.",
        },
        {
            "name": "H2: Buy-Pressure Momentum Scalp",
            "rationale": "Tokens with high initial buy/sell ratio (>= 1.30) and healthy liquidity (>= $15,000) have sufficient buy momentum to hit a quick +20% scalp before the inevitable 2-minute peak reversal.",
            "filter_fn": lambda s: (
                (s.sells_5m is not None and s.sells_5m > 0 and (float(s.buys_5m or 0) / s.sells_5m) >= 1.30)
                and (s.liquidity_usd is not None and s.liquidity_usd >= 15000.0)
            ),
            "feature_condition": "buy_sell_ratio >= 1.30 AND liquidity_usd >= $15,000",
            "entry_condition": "Market buy at T+0 with slippage + impact model",
            "exit_condition": "Take profit +20% or stop loss -12% or timeout at 120s",
            "stop_loss_pct": -12.0,
            "take_profit_pct": 20.0,
            "max_holding_seconds": 120,
            "trailing_stop_pct": None,
            "known_limitations": "High buy ratio at T+0 can sometimes represent the tail-end of retail chasing rather than sustained accumulation.",
            "potential_leakage": "Zero lookahead. Buy/sell counts are pre-signal 5m window.",
        },
        {
            "name": "H3: Trailing Stop Momentum Rider",
            "rationale": "Instead of a static take profit, enter tokens with liquidity >= $15k and trailing stop (trail 10% from peak once in profit) to capture outsized upside spikes while capping downside.",
            "filter_fn": lambda s: (
                s.liquidity_usd is not None and s.liquidity_usd >= 15000.0
            ),
            "feature_condition": "liquidity_usd >= $15,000",
            "entry_condition": "Market buy at T+0 with slippage + impact model",
            "exit_condition": "Trailing stop 10% from peak, or stop loss -15%, max hold 300s",
            "stop_loss_pct": -15.0,
            "take_profit_pct": 100.0,  # allow trailing stop to capture runners
            "max_holding_seconds": 300,
            "trailing_stop_pct": 10.0,
            "known_limitations": "Discrete observation checkpoints (10s, 30s, 60s...) underestimate intra-checkpoint wick drawdowns.",
            "potential_leakage": "None.",
        },
    ]

    results: list[HypothesisResult] = []

    for h in hypotheses_defs:
        train_trades = evaluate_hypothesis_on_set(
            train_signals,
            obs_by_signal,
            h["filter_fn"],
            take_profit_pct=h["take_profit_pct"],
            stop_loss_pct=h["stop_loss_pct"],
            max_holding_seconds=h["max_holding_seconds"],
            trailing_stop_pct=h["trailing_stop_pct"],
        )

        test_trades = evaluate_hypothesis_on_set(
            test_signals,
            obs_by_signal,
            h["filter_fn"],
            take_profit_pct=h["take_profit_pct"],
            stop_loss_pct=h["stop_loss_pct"],
            max_holding_seconds=h["max_holding_seconds"],
            trailing_stop_pct=h["trailing_stop_pct"],
        )

        n_train = len(train_trades)
        train_wins = sum(1 for t in train_trades if t.net_pnl_usd > 0)
        train_win_rate = (train_wins / n_train * 100.0) if n_train > 0 else 0.0
        train_mean_net = calculate_mean([t.net_return_pct for t in train_trades]) or 0.0
        train_total_pnl = sum(t.net_pnl_usd for t in train_trades)

        n_test = len(test_trades)
        test_wins = sum(1 for t in test_trades if t.net_pnl_usd > 0)
        test_win_rate = (test_wins / n_test * 100.0) if n_test > 0 else 0.0
        test_mean_net = calculate_mean([t.net_return_pct for t in test_trades]) or 0.0
        test_total_pnl = sum(t.net_pnl_usd for t in test_trades)

        # Survival check: Does it show positive net EV on unseen test data?
        survives = test_total_pnl > 0 and test_win_rate >= 40.0

        if survives:
            verdict = "SURVIVED INITIAL OOS TEST (Candidate for forward paper trading)"
        elif test_total_pnl > -5.0 and test_win_rate > 35.0:
            verdict = "MARGINAL / UNPROVEN (Needs larger forward sample)"
        else:
            verdict = "REJECTED (Negative EV after execution constraints)"

        evidence = (
            f"Train PnL: ${train_total_pnl:+.2f} ({train_win_rate:.1f}% win), "
            f"Test PnL: ${test_total_pnl:+.2f} ({test_win_rate:.1f}% win)"
        )
        counter_evidence = (
            f"Test set mean net return is {test_mean_net:+.2f}%. "
            f"Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains."
        )

        results.append(
            HypothesisResult(
                name=h["name"],
                rationale=h["rationale"],
                feature_condition=h["feature_condition"],
                entry_condition=h["entry_condition"],
                exit_condition=h["exit_condition"],
                stop_loss_pct=h["stop_loss_pct"],
                take_profit_pct=h["take_profit_pct"],
                max_holding_seconds=h["max_holding_seconds"],
                train_signals=n_train,
                train_win_rate_pct=train_win_rate,
                train_mean_net_return_pct=train_mean_net,
                train_total_pnl_usd=train_total_pnl,
                test_signals=n_test,
                test_win_rate_pct=test_win_rate,
                test_mean_net_return_pct=test_mean_net,
                test_total_pnl_usd=test_total_pnl,
                survives_validation=survives,
                evidence=evidence,
                counter_evidence=counter_evidence,
                known_limitations=h["known_limitations"],
                potential_leakage=h["potential_leakage"],
                validation_verdict=verdict,
            )
        )

    return results


def format_hypotheses_markdown(results: list[HypothesisResult]) -> str:
    """Format hypotheses testing and paper trading design as a markdown report."""
    lines: list[str] = [
        "# Meco Strategy Hypotheses & Paper Trading Evaluation",
        "",
        "> [!IMPORTANT]",
        "> Chronological temporal split applied: **Train Set (Earlier 65% of signals)** vs **Validation Set (Later 35% of signals)**. Realistic execution simulation models 1.5% base slippage + price impact + 0.50% roundtrip DEX fees + Solana gas fees.",
        "",
        "## Summary of Hypothesis Performance (Train vs Out-of-Sample Test)",
        "",
        "| Hypothesis | Train Sigs | Train Win% | Train Net PnL | Test Sigs | Test Win% | Test Net PnL | Verdict |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        v_short = "SURVIVED" if r.survives_validation else "REJECTED"
        lines.append(
            f"| {r.name[:32]} | {r.train_signals:>10} | {r.train_win_rate_pct:>9.1f}% | "
            f"${r.train_total_pnl_usd:>+12.2f} | {r.test_signals:>9} | {r.test_win_rate_pct:>8.1f}% | "
            f"${r.test_total_pnl_usd:>+11.2f} | **{v_short}** |"
        )

    lines.extend([
        "",
        "## Detailed Hypotheses Documentation",
        "",
    ])

    for r in results:
        lines.extend([
            f"### {r.name}",
            "",
            f"**Rationale:** {r.rationale}",
            "",
            f"- **Feature Condition:** `{r.feature_condition}`",
            f"- **Entry Condition:** {r.entry_condition}",
            f"- **Exit Condition:** {r.exit_condition}",
            f"- **Stop Loss:** {r.stop_loss_pct:.1f}%",
            f"- **Take Profit:** {r.take_profit_pct:.1f}%",
            f"- **Max Holding Period:** {r.max_holding_seconds}s",
            "",
            "#### Performance Breakdown",
            f"- **In-Sample Train Set:** {r.train_signals} trades, {r.train_win_rate_pct:.1f}% win rate, Mean Net: {r.train_mean_net_return_pct:+.2f}%, Total PnL: ${r.train_total_pnl_usd:+.2f}",
            f"- **Out-of-Sample Test Set:** {r.test_signals} trades, {r.test_win_rate_pct:.1f}% win rate, Mean Net: {r.test_mean_net_return_pct:+.2f}%, Total PnL: ${r.test_total_pnl_usd:+.2f}",
            "",
            f"- **Evidence:** {r.evidence}",
            f"- **Counter-Evidence:** {r.counter_evidence}",
            f"- **Known Limitations:** {r.known_limitations}",
            f"- **Potential Leakage:** {r.potential_leakage}",
            f"- **Verdict:** `{r.validation_verdict}`",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)
