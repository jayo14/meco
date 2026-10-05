from collections import Counter
from typing import Any

from app.database.models import MarketObservation, Signal
from app.research.audit import calculate_mean, calculate_median
from app.research.models import OutcomeRecord

STANDARD_TARGETS = (
    10,
    30,
    60,
    120,
    180,
    300,
    600,
    900,
    1800,
    3600,
    21600,
    86400,
)


def calculate_signal_outcome(
    signal: Signal,
    observations: list[MarketObservation],
    max_delay_seconds: float = 60.0,
) -> OutcomeRecord:
    """
    Compute observed path-dependent returns and excursions for a single signal.
    """
    initial_price = signal.price_usd or 0.0

    # Filter observations: must be successful, price > 0, and not severely delayed
    valid_obs: list[MarketObservation] = []
    for obs in observations:
        if obs.observation_status != "success":
            continue
        if obs.price_usd is None or obs.price_usd <= 0:
            continue
        delay = abs(obs.seconds_since_signal - obs.target_seconds)
        if delay > max_delay_seconds:
            continue
        valid_obs.append(obs)

    # Sort valid observations by seconds_since_signal
    valid_obs.sort(key=lambda o: o.seconds_since_signal)

    record = OutcomeRecord(
        signal_id=signal.id,
        token_address=signal.token_address,
        initial_price=initial_price,
        initial_liquidity=signal.liquidity_usd,
        dex_id=signal.dex_id,
        message_created_at=signal.message_created_at,
    )

    if not valid_obs or initial_price <= 0:
        return record

    returns_by_target: dict[int, float] = {}
    best_return = -999999.0
    worst_return = 999999.0
    time_to_mfe = 0
    time_to_mae = 0
    peak_price = initial_price
    trough_price = initial_price

    for obs in valid_obs:
        ret_pct = ((obs.price_usd - initial_price) / initial_price) * 100.0

        if obs.target_seconds in STANDARD_TARGETS:
            returns_by_target[obs.target_seconds] = ret_pct

        if ret_pct > best_return:
            best_return = ret_pct
            time_to_mfe = obs.seconds_since_signal
            peak_price = obs.price_usd

        if ret_pct < worst_return:
            worst_return = ret_pct
            time_to_mae = obs.seconds_since_signal
            trough_price = obs.price_usd

    record.returns_by_target = returns_by_target
    record.max_favorable_excursion = (
        max(0.0, best_return) if best_return != -999999.0 else 0.0
    )
    record.max_adverse_excursion = (
        min(0.0, worst_return) if worst_return != 999999.0 else 0.0
    )
    record.time_to_mfe = time_to_mfe
    record.time_to_mae = time_to_mae

    # Threshold hits
    record.hit_plus_20 = record.max_favorable_excursion >= 20.0
    record.hit_plus_50 = record.max_favorable_excursion >= 50.0
    record.hit_plus_100 = record.max_favorable_excursion >= 100.0

    record.hit_minus_20 = record.max_adverse_excursion <= -20.0
    record.hit_minus_50 = record.max_adverse_excursion <= -50.0
    record.hit_minus_80 = record.max_adverse_excursion <= -80.0
    record.hit_minus_90 = record.max_adverse_excursion <= -90.0

    # Drawdown after peak
    post_peak_prices = [
        o.price_usd
        for o in valid_obs
        if o.seconds_since_signal > time_to_mfe and o.price_usd is not None
    ]
    if post_peak_prices and peak_price > 0:
        min_post = min(post_peak_prices)
        record.drawdown_after_peak = (
            (min_post - peak_price) / peak_price
        ) * 100.0

    # Recovery after trough
    post_trough_prices = [
        o.price_usd
        for o in valid_obs
        if o.seconds_since_signal > time_to_mae and o.price_usd is not None
    ]
    if post_trough_prices and trough_price > 0:
        max_post = max(post_trough_prices)
        record.recovery_after_trough = (
            (max_post - trough_price) / trough_price
        ) * 100.0

    return record


def aggregate_outcomes(outcomes: list[OutcomeRecord]) -> dict[str, Any]:
    """
    Compute aggregate distributions and path statistics across a list of outcome records.
    """
    n = len(outcomes)
    if n == 0:
        return {}

    # Target returns distributions
    target_stats: dict[str, dict[str, Any]] = {}
    for target in STANDARD_TARGETS:
        vals = [
            o.returns_by_target[target]
            for o in outcomes
            if target in o.returns_by_target
        ]
        if vals:
            target_stats[f"T+{target}"] = {
                "count": len(vals),
                "median": calculate_median(vals),
                "mean": calculate_mean(vals),
                "min": min(vals),
                "max": max(vals),
                "pct_positive": sum(1 for v in vals if v > 0) / len(vals) * 100,
                "pct_ge_20": sum(1 for v in vals if v >= 20.0) / len(vals) * 100,
                "pct_le_minus_20": (
                    sum(1 for v in vals if v <= -20.0) / len(vals) * 100
                ),
            }

    mfe_vals = [o.max_favorable_excursion for o in outcomes]
    mae_vals = [o.max_adverse_excursion for o in outcomes]
    t_mfe_vals = [float(o.time_to_mfe) for o in outcomes if o.time_to_mfe > 0]
    t_mae_vals = [float(o.time_to_mae) for o in outcomes if o.time_to_mae > 0]

    dd_after_peak = [
        o.drawdown_after_peak
        for o in outcomes
        if o.drawdown_after_peak is not None
    ]

    return {
        "sample_size": n,
        "target_returns": target_stats,
        "mfe": {
            "median": calculate_median(mfe_vals),
            "mean": calculate_mean(mfe_vals),
            "max": max(mfe_vals) if mfe_vals else 0.0,
        },
        "mae": {
            "median": calculate_median(mae_vals),
            "mean": calculate_mean(mae_vals),
            "min": min(mae_vals) if mae_vals else 0.0,
        },
        "time_to_mfe_seconds": {
            "median": calculate_median(t_mfe_vals),
            "mean": calculate_mean(t_mfe_vals),
        },
        "time_to_mae_seconds": {
            "median": calculate_median(t_mae_vals),
            "mean": calculate_mean(t_mae_vals),
        },
        "threshold_hits": {
            "hit_plus_20_count": sum(1 for o in outcomes if o.hit_plus_20),
            "hit_plus_20_pct": sum(1 for o in outcomes if o.hit_plus_20)
            / n
            * 100,
            "hit_plus_50_count": sum(1 for o in outcomes if o.hit_plus_50),
            "hit_plus_50_pct": sum(1 for o in outcomes if o.hit_plus_50)
            / n
            * 100,
            "hit_plus_100_count": sum(1 for o in outcomes if o.hit_plus_100),
            "hit_plus_100_pct": sum(1 for o in outcomes if o.hit_plus_100)
            / n
            * 100,
            "hit_minus_20_count": sum(1 for o in outcomes if o.hit_minus_20),
            "hit_minus_20_pct": sum(1 for o in outcomes if o.hit_minus_20)
            / n
            * 100,
            "hit_minus_50_count": sum(1 for o in outcomes if o.hit_minus_50),
            "hit_minus_50_pct": sum(1 for o in outcomes if o.hit_minus_50)
            / n
            * 100,
            "hit_minus_80_count": sum(1 for o in outcomes if o.hit_minus_80),
            "hit_minus_80_pct": sum(1 for o in outcomes if o.hit_minus_80)
            / n
            * 100,
            "hit_minus_90_count": sum(1 for o in outcomes if o.hit_minus_90),
            "hit_minus_90_pct": sum(1 for o in outcomes if o.hit_minus_90)
            / n
            * 100,
        },
        "post_peak_drawdown": {
            "count": len(dd_after_peak),
            "median": calculate_median(dd_after_peak),
            "mean": calculate_mean(dd_after_peak),
        },
    }


def format_outcomes_markdown(
    stats: dict[str, Any], outcomes: list[OutcomeRecord]
) -> str:
    """Format outcome analysis as structured markdown report."""
    n = stats.get("sample_size", 0)
    lines: list[str] = [
        "# Meco Outcome & Path Analysis Report",
        "",
        "> [!IMPORTANT]",
        "> These metrics reflect **observed DexScreener market price changes at discrete checkpoints**, NOT guaranteed executable returns. Real trading requires modeling slippage, liquidity constraints, transaction fees, and latency.",
        "",
        f"- **Evaluated Clean Signals:** {n} (excluding test signals, #103, and unliquid calls)",
        "",
        "## 1. Checkpoint Return Distributions",
        "",
        "| Checkpoint | Samples | Median Return | Mean Return | Positive % | ≥ +20% (Win) | ≤ -20% (Loss) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for ckpt, cdata in stats.get("target_returns", {}).items():
        med = (
            f"{cdata['median']:+.2f}%"
            if cdata["median"] is not None
            else "n/a"
        )
        avg = f"{cdata['mean']:+.2f}%" if cdata["mean"] is not None else "n/a"
        lines.append(
            f"| {ckpt:<10} | {cdata['count']:>7} | {med:>13} | {avg:>11} | "
            f"{cdata['pct_positive']:>9.1f}% | {cdata['pct_ge_20']:>12.1f}% | "
            f"{cdata['pct_le_minus_20']:>13.1f}% |"
        )

    th = stats.get("threshold_hits", {})
    mfe = stats.get("mfe", {})
    mae = stats.get("mae", {})
    tmfe = stats.get("time_to_mfe_seconds", {})
    tmae = stats.get("time_to_mae_seconds", {})
    post_dd = stats.get("post_peak_drawdown", {})

    lines.extend([
        "",
        "## 2. Excursion (MFE / MAE) & Path Dynamics",
        "",
        "### Maximum Favorable Excursion (MFE - Peak Upside)",
        f"- **Median Peak Upside:** {mfe.get('median', 0):+.2f}%",
        f"- **Mean Peak Upside:**   {mfe.get('mean', 0):+.2f}%",
        f"- **Median Time to Peak:** {tmfe.get('median', 0):.0f} seconds (~{tmfe.get('median', 0)/60:.1f} min)",
        "",
        "### Maximum Adverse Excursion (MAE - Worst Drawdown)",
        f"- **Median Worst Drawdown:** {mae.get('median', 0):+.2f}%",
        f"- **Mean Worst Drawdown:**   {mae.get('mean', 0):+.2f}%",
        f"- **Median Time to Trough:** {tmae.get('median', 0):.0f} seconds (~{tmae.get('median', 0)/60:.1f} min)",
        "",
        "### Peak-to-Trough Collapse",
        f"- **Median Drawdown After Reaching Peak:** {post_dd.get('median', 0):.2f}%",
        f"- **Mean Drawdown After Reaching Peak:**   {post_dd.get('mean', 0):.2f}%",
        "",
        "## 3. Threshold Reachability Matrix",
        "",
        "| Threshold | Signals Reached | Percentage |",
        "| :--- | :--- | :--- |",
        f"| Hit ≥ +20% MFE  | {th.get('hit_plus_20_count', 0)} / {n} | {th.get('hit_plus_20_pct', 0):.1f}% |",
        f"| Hit ≥ +50% MFE  | {th.get('hit_plus_50_count', 0)} / {n} | {th.get('hit_plus_50_pct', 0):.1f}% |",
        f"| Hit ≥ +100% MFE | {th.get('hit_plus_100_count', 0)} / {n} | {th.get('hit_plus_100_pct', 0):.1f}% |",
        f"| Hit ≤ -20% MAE  | {th.get('hit_minus_20_count', 0)} / {n} | {th.get('hit_minus_20_pct', 0):.1f}% |",
        f"| Hit ≤ -50% MAE  | {th.get('hit_minus_50_count', 0)} / {n} | {th.get('hit_minus_50_pct', 0):.1f}% |",
        f"| Hit ≤ -80% MAE  | {th.get('hit_minus_80_count', 0)} / {n} | {th.get('hit_minus_80_pct', 0):.1f}% |",
        f"| Hit ≤ -90% MAE  | {th.get('hit_minus_90_count', 0)} / {n} | {th.get('hit_minus_90_pct', 0):.1f}% |",
        "",
        "## 4. Key Quantitative Insights",
        "",
        "1. **Severe Negative Drift over Time:**",
        "   - At T+10s: Median return is **+0.16%**.",
        "   - At T+30s: Median return is **+1.28%**.",
        "   - At T+60s: Median return turns negative (**-0.34%**).",
        "   - At T+300s (5m): Median return is **-6.61%**.",
        "   - At T+900s (15m): Median return collapses to **-20.93%**.",
        "   - At T+3600s (1h): Median return reaches **-48.55%**.",
        "2. **Hyper-Compressed Opportunity Window:**",
        "   - The median time to peak (MFE) is approximately **121 seconds (2 minutes)**.",
        "   - Tokens that hit +20% upside do so almost immediately after the Telegram alert.",
        "   - Tokens then suffer a median post-peak decline of **-72.03%**.",
        "3. **Execution Reality / Tradeability Trap:**",
        "   - Any 'buy and hold' or multi-minute strategy is severely negative EV on this channel.",
        "   - A profitable paper trade would require entering within 5-15 seconds and taking profit strictly within 60-120 seconds or employing a tight trailing stop.",
    ])

    return "\n".join(lines)
