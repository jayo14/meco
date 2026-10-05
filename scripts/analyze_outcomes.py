import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.research.anomalies import filter_usable_signals
from app.research.loader import (
    group_observations_by_signal,
    load_all_observations,
    load_all_signals,
)
from app.research.outcomes import (
    aggregate_outcomes,
    calculate_signal_outcome,
    format_outcomes_markdown,
)


async def main() -> None:
    print("=" * 80)
    print("MECO OUTCOME & PATH ANALYSIS")
    print("=" * 80)

    signals = await load_all_signals()
    observations = await load_all_observations()

    usable_signals, excluded = filter_usable_signals(signals)
    obs_by_signal = group_observations_by_signal(observations)

    outcomes = [
        calculate_signal_outcome(
            s, obs_by_signal.get(s.id, []), max_delay_seconds=60.0
        )
        for s in usable_signals
    ]

    stats = aggregate_outcomes(outcomes)

    print(f"Evaluated Usable Signals: {stats.get('sample_size', 0)}")
    print(f"Excluded Signals:         {len(excluded)}")
    print()

    print("Checkpoint Observed Returns:")
    print(
        f"  {'Checkpoint':<12} {'Count':>7} {'Median':>10} {'Mean':>10} "
        f"{'Positive%':>11} {'≥ +20% (Win)':>14} {'≤ -20% (Loss)':>15}"
    )
    for ckpt, data in stats.get("target_returns", {}).items():
        med_str = (
            f"{data['median']:+.2f}%"
            if data["median"] is not None
            else "n/a"
        )
        avg_str = (
            f"{data['mean']:+.2f}%" if data["mean"] is not None else "n/a"
        )
        print(
            f"  {ckpt:<12} {data['count']:>7} {med_str:>10} {avg_str:>10} "
            f"{data['pct_positive']:>10.1f}% {data['pct_ge_20']:>13.1f}% "
            f"{data['pct_le_minus_20']:>14.1f}%"
        )
    print()

    mfe = stats.get("mfe", {})
    mae = stats.get("mae", {})
    tmfe = stats.get("time_to_mfe_seconds", {})
    tmae = stats.get("time_to_mae_seconds", {})
    post_dd = stats.get("post_peak_drawdown", {})

    print("Excursion (MFE / MAE) Dynamics:")
    print(
        f"  - Peak Upside (MFE):       Median = {mfe.get('median', 0):+.2f}% | Mean = {mfe.get('mean', 0):+.2f}%"
    )
    print(
        f"  - Time to Peak:            Median = {tmfe.get('median', 0):.0f}s (~{tmfe.get('median', 0)/60:.1f}m)"
    )
    print(
        f"  - Worst Drawdown (MAE):    Median = {mae.get('median', 0):+.2f}% | Mean = {mae.get('mean', 0):+.2f}%"
    )
    print(
        f"  - Time to Trough:          Median = {tmae.get('median', 0):.0f}s (~{tmae.get('median', 0)/60:.1f}m)"
    )
    print(
        f"  - Drawdown After Peak:     Median = {post_dd.get('median', 0):.2f}% | Mean = {post_dd.get('mean', 0):.2f}%"
    )
    print()

    th = stats.get("threshold_hits", {})
    n = stats.get("sample_size", 1)
    print("Threshold Hit Frequencies:")
    print(
        f"  - Hit ≥ +20% MFE:  {th.get('hit_plus_20_count', 0):>3} / {n} ({th.get('hit_plus_20_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≥ +50% MFE:  {th.get('hit_plus_50_count', 0):>3} / {n} ({th.get('hit_plus_50_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≥ +100% MFE: {th.get('hit_plus_100_count', 0):>3} / {n} ({th.get('hit_plus_100_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≤ -20% MAE:  {th.get('hit_minus_20_count', 0):>3} / {n} ({th.get('hit_minus_20_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≤ -50% MAE:  {th.get('hit_minus_50_count', 0):>3} / {n} ({th.get('hit_minus_50_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≤ -80% MAE:  {th.get('hit_minus_80_count', 0):>3} / {n} ({th.get('hit_minus_80_pct', 0):.1f}%)"
    )
    print(
        f"  - Hit ≤ -90% MAE:  {th.get('hit_minus_90_count', 0):>3} / {n} ({th.get('hit_minus_90_pct', 0):.1f}%)"
    )
    print()

    # Save reports
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_outcomes_markdown(stats, outcomes)
    md_path = reports_dir / "outcome_analysis.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "outcome_analysis.json"
    json_path.write_text(
        json.dumps(
            {"stats": stats, "outcomes": [asdict(o) for o in outcomes]},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"Outcome report saved to: {md_path}")
    print(f"JSON metrics saved to:   {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
