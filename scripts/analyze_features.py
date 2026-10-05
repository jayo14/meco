import asyncio
import json
from pathlib import Path

from app.research.anomalies import filter_usable_signals
from app.research.features import (
    analyze_categorical_feature,
    analyze_feature_vs_outcomes,
    extract_signal_features,
    format_features_markdown,
)
from app.research.loader import (
    group_observations_by_signal,
    load_all_observations,
    load_all_signals,
)
from app.research.outcomes import calculate_signal_outcome


async def main() -> None:
    print("=" * 80)
    print("MECO SIGNAL FEATURE ANALYSIS")
    print("=" * 80)

    signals = await load_all_signals()
    observations = await load_all_observations()

    usable_signals, _ = filter_usable_signals(signals)
    obs_by_signal = group_observations_by_signal(observations)

    outcomes_by_id = {
        s.id: calculate_signal_outcome(
            s, obs_by_signal.get(s.id, []), max_delay_seconds=60.0
        )
        for s in usable_signals
    }

    features = [extract_signal_features(s) for s in usable_signals]

    feature_names = [
        "liquidity_usd",
        "volume_5m",
        "total_txns_5m",
        "buy_sell_ratio",
        "buy_fraction",
        "volume_to_liquidity",
        "telegram_latency",
    ]

    analyses = []
    print("Quantitative Features vs Outcomes (Quantile Bins):")
    print(
        f"  {'Feature':<22} {'Bin':<5} {'Range':<22} {'Med T+300':>10} "
        f"{'Med MFE':>9} {'Win (≥20%)':>12} {'Loss (≤-50%)':>13}"
    )

    for fname in feature_names:
        res = analyze_feature_vs_outcomes(features, outcomes_by_id, fname, n_bins=3)
        analyses.append(res)
        for b in res.get("bins", []):
            r_str = f"[{b['range'][0]:,.1f} - {b['range'][1]:,.1f}]"
            t300_str = (
                f"{b['median_t300']:+.1f}%"
                if b["median_t300"] is not None
                else "n/a"
            )
            mfe_str = (
                f"{b['median_mfe']:+.1f}%"
                if b["median_mfe"] is not None
                else "n/a"
            )
            print(
                f"  {fname:<22} {b['label']:<5} {r_str:<22} {t300_str:>10} "
                f"{mfe_str:>9} {b['win_plus_20_pct']:>11.1f}% {b['loss_minus_50_pct']:>12.1f}%"
            )
        sp = res.get("spearman_t300")
        sp_str = f"{sp:+.3f}" if sp is not None else "n/a"
        print(f"  --> Rank Correlation (Spearman vs T+300): {sp_str}")
        print()

    # Categorical: dex_id
    dex_res = analyze_categorical_feature(features, outcomes_by_id, "dex_id")
    analyses.append(dex_res)
    print("Categorical Feature (DEX Venue):")
    for c in dex_res.get("categories", []):
        t300_str = (
            f"{c['median_t300']:+.1f}%"
            if c["median_t300"] is not None
            else "n/a"
        )
        mfe_str = (
            f"{c['median_mfe']:+.1f}%" if c["median_mfe"] is not None else "n/a"
        )
        print(
            f"  {c['category']:<12} count={c['count']:>3} | med T+300={t300_str:>7} | "
            f"med MFE={mfe_str:>7} | win%={c['win_plus_20_pct']:>5.1f}% | loss%={c['loss_minus_50_pct']:>5.1f}%"
        )
    print()

    # Save reports
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_features_markdown(analyses)
    md_path = reports_dir / "feature_analysis.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "feature_analysis.json"
    json_path.write_text(
        json.dumps(analyses, indent=2, default=str), encoding="utf-8"
    )

    print(f"Feature report saved to: {md_path}")
    print(f"JSON data saved to:       {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
