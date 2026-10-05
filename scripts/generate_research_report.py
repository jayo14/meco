import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.research.anomalies import (
    detect_all_anomalies,
    filter_usable_signals,
    format_anomaly_markdown,
)
from app.research.audit import build_audit_report, format_audit_markdown
from app.research.features import (
    analyze_categorical_feature,
    analyze_feature_vs_outcomes,
    extract_signal_features,
    format_features_markdown,
)
from app.research.hypotheses import (
    format_hypotheses_markdown,
    run_hypotheses_evaluation,
)
from app.research.loader import (
    group_observations_by_signal,
    load_all_observations,
    load_all_pair_observations,
    load_all_signals,
)
from app.research.outcomes import (
    aggregate_outcomes,
    calculate_signal_outcome,
    format_outcomes_markdown,
)
from app.research.reports import format_executive_summary_markdown


async def run_full_research_pipeline(reports_dir: Path | None = None) -> dict[str, Any]:
    if reports_dir is None:
        reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1/5: Loading raw dataset from database...")
    signals = await load_all_signals()
    observations = await load_all_observations()
    pair_observations = await load_all_pair_observations()
    obs_by_signal = group_observations_by_signal(observations)

    print("Step 2/5: Running dataset audit & anomaly detection...")
    audit_report = build_audit_report(signals, observations, pair_observations)
    anomalies = detect_all_anomalies(signals, observations)
    usable_signals, excluded_signals = filter_usable_signals(signals)

    print(f"         Total: {len(signals)} | Usable: {len(usable_signals)} | Excluded: {len(excluded_signals)}")

    print("Step 3/5: Calculating path-dependent outcomes (MFE, MAE, checkpoint returns)...")
    outcomes_by_id = {
        s.id: calculate_signal_outcome(
            s, obs_by_signal.get(s.id, []), max_delay_seconds=60.0
        )
        for s in usable_signals
    }
    outcomes_list = list(outcomes_by_id.values())
    outcome_stats = aggregate_outcomes(outcomes_list)

    print("Step 4/5: Analyzing signal-time features (T+0, zero lookahead)...")
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
    feature_analyses = [
        analyze_feature_vs_outcomes(features, outcomes_by_id, fname, n_bins=3)
        for fname in feature_names
    ]
    feature_analyses.append(
        analyze_categorical_feature(features, outcomes_by_id, "dex_id")
    )

    print("Step 5/5: Running chronological hypothesis validation & paper trade simulation...")
    hypotheses_results = run_hypotheses_evaluation(
        usable_signals, obs_by_signal, train_fraction=0.65
    )

    # Write Markdown Reports
    (reports_dir / "dataset_audit.md").write_text(
        format_audit_markdown(audit_report), encoding="utf-8"
    )
    (reports_dir / "anomaly_report.md").write_text(
        format_anomaly_markdown(anomalies), encoding="utf-8"
    )
    (reports_dir / "outcome_analysis.md").write_text(
        format_outcomes_markdown(outcome_stats, outcomes_list), encoding="utf-8"
    )
    (reports_dir / "feature_analysis.md").write_text(
        format_features_markdown(feature_analyses), encoding="utf-8"
    )
    (reports_dir / "hypotheses_and_strategy.md").write_text(
        format_hypotheses_markdown(hypotheses_results), encoding="utf-8"
    )

    exec_summary_md = format_executive_summary_markdown(
        audit_report, outcome_stats, {}, hypotheses_results
    )
    (reports_dir / "executive_summary.md").write_text(
        exec_summary_md, encoding="utf-8"
    )

    # Write JSON Artifacts
    (reports_dir / "research_package.json").write_text(
        json.dumps(
            {
                "audit": asdict(audit_report),
                "outcome_stats": outcome_stats,
                "feature_analyses": feature_analyses,
                "hypotheses_results": [asdict(h) for h in hypotheses_results],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return {
        "audit": audit_report,
        "outcomes": outcome_stats,
        "hypotheses": hypotheses_results,
    }


async def main() -> None:
    print("=" * 80)
    print("MECO AUTONOMOUS RESEARCH SUITE: COMPREHENSIVE REPORT GENERATION")
    print("=" * 80)

    result = await run_full_research_pipeline()
    audit: AuditReport = result["audit"]
    hypotheses: list[HypothesisResult] = result["hypotheses"]

    print()
    print("=" * 80)
    print("RESEARCH SUMMARY")
    print("=" * 80)
    print(f"Total Signals Audited:      {audit.total_signals}")
    print(f"Usable Signals:             {len(result['outcomes'].get('target_returns', {}).get('T+30', {}).get('count', 0)) if isinstance(result['outcomes'].get('target_returns', {}).get('T+30', {}).get('count', 0), list) else result['outcomes'].get('sample_size', 0)}")
    print(f"Median Peak Upside (MFE):   {result['outcomes'].get('mfe', {}).get('median', 0):+.2f}%")
    print(f"Median Worst Drawdown (MAE):{result['outcomes'].get('mae', {}).get('median', 0):+.2f}%")
    print(f"Post-Peak Median Collapse:  {result['outcomes'].get('post_peak_drawdown', {}).get('median', 0):.2f}%")
    print()
    print("Hypothesis Validation Results:")
    for h in hypotheses:
        print(f"  - {h.name:<40}: {h.validation_verdict}")
    print()
    print("Reports Generated in research/reports/:")
    print("  - executive_summary.md")
    print("  - dataset_audit.md")
    print("  - anomaly_report.md")
    print("  - outcome_analysis.md")
    print("  - feature_analysis.md")
    print("  - hypotheses_and_strategy.md")
    print("  - research_package.json")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
