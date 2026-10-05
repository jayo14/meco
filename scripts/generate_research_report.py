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
from app.research.cohorts import (
    HISTORICAL_RESEARCH_FREEZE_TIMESTAMP,
    HISTORICAL_RESEARCH_MAX_SIGNAL_ID,
    SignalCohort,
    format_baseline_cohort_markdown,
    partition_by_cohort,
    summarize_cohort,
)
from app.research.presignal import (
    analyze_presignal_cohort,
    reconstruct_presignal_metrics,
)
from app.research.reports import format_executive_summary_markdown
from app.research.simulation import (
    format_execution_audit_markdown,
    run_friction_sensitivity_grid,
)
from scripts.analyze_presignal import format_presignal_research_plan_markdown


async def run_full_research_pipeline(reports_dir: Path | None = None) -> dict[str, Any]:
    if reports_dir is None:
        reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1/8: Loading raw dataset from database...")
    signals = await load_all_signals()
    observations = await load_all_observations()
    pair_observations = await load_all_pair_observations()
    obs_by_signal = group_observations_by_signal(observations)

    print("Step 2/8: Running dataset audit & anomaly detection...")
    audit_report = build_audit_report(signals, observations, pair_observations)
    anomalies = detect_all_anomalies(signals, observations)
    usable_signals, excluded_signals = filter_usable_signals(signals)

    print(f"         Total: {len(signals)} | Usable: {len(usable_signals)} | Excluded: {len(excluded_signals)}")

    print("Step 3/8: Calculating path-dependent outcomes (MFE, MAE, checkpoint returns)...")
    outcomes_by_id = {
        s.id: calculate_signal_outcome(
            s, obs_by_signal.get(s.id, []), max_delay_seconds=60.0
        )
        for s in usable_signals
    }
    outcomes_list = list(outcomes_by_id.values())
    outcome_stats = aggregate_outcomes(outcomes_list)

    print("Step 4/8: Analyzing signal-time features (T+0, zero lookahead)...")
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

    print("Step 5/8: Running chronological hypothesis validation & paper trade simulation...")
    hypotheses_results = run_hypotheses_evaluation(
        usable_signals, obs_by_signal, train_fraction=0.65
    )

    print("Step 6/8: Evaluating execution model audit & friction sensitivity grid...")
    friction_grid = run_friction_sensitivity_grid(usable_signals, obs_by_signal)

    print("Step 7/8: Partitioning historical baseline vs forward-testing cohorts...")
    partitioned = partition_by_cohort(signals)
    hist_signals = partitioned[SignalCohort.HISTORICAL_RESEARCH]
    fwd_signals = partitioned[SignalCohort.FORWARD_TESTING]
    usable_hist, excluded_hist = filter_usable_signals(hist_signals)
    hist_summary = summarize_cohort(SignalCohort.HISTORICAL_RESEARCH, hist_signals)
    fwd_summary = summarize_cohort(SignalCohort.FORWARD_TESTING, fwd_signals)

    print("Step 8/8: Reconstructing on-chain pre-signal pool age & experimental plan...")
    presignal_metrics = reconstruct_presignal_metrics(usable_signals, pair_observations)
    presignal_analysis = analyze_presignal_cohort(presignal_metrics)

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
    (reports_dir / "execution_model_audit.md").write_text(
        format_execution_audit_markdown(friction_grid), encoding="utf-8"
    )
    (reports_dir / "forward_testing_baseline.md").write_text(
        format_baseline_cohort_markdown(
            hist_summary, fwd_summary, len(usable_hist), len(excluded_hist)
        ),
        encoding="utf-8",
    )
    (reports_dir / "presignal_research_plan.md").write_text(
        format_presignal_research_plan_markdown(presignal_analysis), encoding="utf-8"
    )

    exec_summary_md = format_executive_summary_markdown(
        audit_report, outcome_stats, {}, hypotheses_results
    )
    (reports_dir / "executive_summary.md").write_text(
        exec_summary_md, encoding="utf-8"
    )

    # Write Individual JSON Artifacts for Tools
    (reports_dir / "execution_model_audit.json").write_text(
        json.dumps(
            {
                tier: {
                    k: (str(v) if not isinstance(v, (int, float, bool, list, dict)) else v)
                    for k, v in data.items()
                }
                for tier, data in friction_grid.items()
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (reports_dir / "forward_testing_baseline.json").write_text(
        json.dumps(
            {
                "boundary_signal_id": HISTORICAL_RESEARCH_MAX_SIGNAL_ID,
                "freeze_timestamp": HISTORICAL_RESEARCH_FREEZE_TIMESTAMP,
                "historical_summary": asdict(hist_summary),
                "forward_summary": asdict(fwd_summary),
                "usable_historical_count": len(usable_hist),
                "excluded_historical_count": len(excluded_hist),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (reports_dir / "presignal_research_plan.json").write_text(
        json.dumps(
            {
                "cohort_analysis": asdict(presignal_analysis),
                "sample_metrics": [asdict(m) for m in presignal_metrics[:10]],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    # Write Master JSON Package
    (reports_dir / "research_package.json").write_text(
        json.dumps(
            {
                "audit": asdict(audit_report),
                "outcome_stats": outcome_stats,
                "feature_analyses": feature_analyses,
                "hypotheses_results": [asdict(h) for h in hypotheses_results],
                "friction_grid": {
                    tier: {
                        k: (str(v) if not isinstance(v, (int, float, bool, list, dict)) else v)
                        for k, v in data.items()
                    }
                    for tier, data in friction_grid.items()
                },
                "cohorts": {
                    "historical": asdict(hist_summary),
                    "forward": asdict(fwd_summary),
                },
                "presignal": asdict(presignal_analysis),
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
        "friction_grid": friction_grid,
        "cohorts": {"historical": hist_summary, "forward": fwd_summary},
        "presignal": presignal_analysis,
    }


async def main() -> None:
    print("=" * 80)
    print("MECO AUTONOMOUS RESEARCH SUITE: COMPREHENSIVE REPORT GENERATION")
    print("=" * 80)

    result = await run_full_research_pipeline()
    audit: AuditReport = result["audit"]
    hypotheses: list[HypothesisResult] = result["hypotheses"]
    presignal = result["presignal"]

    print()
    print("=" * 80)
    print("RESEARCH SUMMARY")
    print("=" * 80)
    print(f"Total Signals Audited:      {audit.total_signals}")
    print(f"Median Peak Upside (MFE):   {result['outcomes'].get('mfe', {}).get('median', 0):+.2f}%")
    print(f"Median Worst Drawdown (MAE):{result['outcomes'].get('mae', {}).get('median', 0):+.2f}%")
    print(f"Post-Peak Median Collapse:  {result['outcomes'].get('post_peak_drawdown', {}).get('median', 0):.2f}%")
    print()
    if presignal.median_pool_age_seconds is not None:
        print(f"Median Pool Age at Alert:   {presignal.median_pool_age_seconds/60:.1f} minutes ({presignal.median_pool_age_seconds:.0f}s)")
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
    print("  - execution_model_audit.md")
    print("  - forward_testing_baseline.md")
    print("  - presignal_research_plan.md")
    print("  - research_package.json")
    print("=" * 80)



if __name__ == "__main__":
    asyncio.run(main())
