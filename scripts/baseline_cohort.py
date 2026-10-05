import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.research.anomalies import filter_usable_signals
from app.research.cohorts import (
    HISTORICAL_RESEARCH_FREEZE_TIMESTAMP,
    HISTORICAL_RESEARCH_MAX_SIGNAL_ID,
    SignalCohort,
    partition_by_cohort,
    summarize_cohort,
)
from app.research.loader import load_all_signals


async def main() -> None:
    print("=" * 80)
    print("MECO FORWARD-TESTING BASELINE FREEZE & COHORT PARTITION")
    print("=" * 80)

    signals = await load_all_signals()
    partitioned = partition_by_cohort(signals)

    hist_signals = partitioned[SignalCohort.HISTORICAL_RESEARCH]
    fwd_signals = partitioned[SignalCohort.FORWARD_TESTING]

    usable_hist, excluded_hist = filter_usable_signals(hist_signals)

    hist_summary = summarize_cohort(SignalCohort.HISTORICAL_RESEARCH, hist_signals)
    fwd_summary = summarize_cohort(SignalCohort.FORWARD_TESTING, fwd_signals)

    print(f"Historical Research Cohort (Frozen at #{HISTORICAL_RESEARCH_MAX_SIGNAL_ID}):")
    print(f"  - Total Signals:      {hist_summary.total_signals}")
    print(f"  - Usable Signals:     {len(usable_hist)}")
    print(f"  - Excluded Signals:   {len(excluded_hist)}")
    print(f"  - Span:               Signal #{hist_summary.min_id} to #{hist_summary.max_id}")
    print(f"  - Timestamp Window:   {hist_summary.min_timestamp} -> {hist_summary.max_timestamp}")
    print()
    print(f"Forward Testing Cohort (Signals > #{HISTORICAL_RESEARCH_MAX_SIGNAL_ID}):")
    print(f"  - Total Signals:      {fwd_summary.total_signals}")
    print(f"  - Span:               Signal #{fwd_summary.min_id or 'none'} to #{fwd_summary.max_id or 'none'}")
    print()

    # Generate Report
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Meco Forward-Testing Baseline & Cohort Specification",
        "",
        "## 1. Dataset Partition Boundary",
        "",
        "To prevent historical contamination and establish a scientific boundary between retrospective exploration and prospective forward evaluation, the dataset is split into two immutable cohorts:",
        "",
        "| Cohort | Signal ID Range | Timestamp Range | Status | Purpose |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **`HISTORICAL_RESEARCH`** | `1` to `{HISTORICAL_RESEARCH_MAX_SIGNAL_ID}` | `2026-10-02` to `{HISTORICAL_RESEARCH_FREEZE_TIMESTAMP[:10]}` | **FROZEN** | Initial data audit, anomaly detection, feature exploration, and initial hypothesis falsification. |",
        f"| **`FORWARD_TESTING`** | `{HISTORICAL_RESEARCH_MAX_SIGNAL_ID + 1}+` | Ongoing | **ACTIVE** | Uninterrupted 24/7 VPS forward collection. Tests whether future signals exhibit different dynamics. |",
        "",
        "---",
        "",
        "## 2. Historical Research Baseline Metrics (Cohort 1)",
        "",
        f"- **Total Captured Signals:** {hist_summary.total_signals}",
        f"- **Clean Usable Signals for Research:** {len(usable_hist)}",
        f"- **Excluded Signals:** {len(excluded_hist)} (test calls, unliquid pools, anomaly #103)",
        "- **Identified Phenomena:**",
        "  - Median time to peak: **121 seconds** (~2.0 minutes)",
        "  - Median peak upside (MFE): **+12.9%**",
        "  - Median post-peak collapse: **-72.0%**",
        "  - Falsified hypotheses: All 4 tested strategies produced negative net EV after realistic friction.",
        "",
        "---",
        "",
        "## 3. Forward Collection Protocol & Integrity Rules",
        "",
        "1. **Never Backfill or Mutate Historical Cohort:** Historical signals (1 to 387) are immutable baseline ground truth.",
        "2. **Stale Target Protection:** The active listener enforces `max_tolerance = 60s` (300s for >=1h targets). If the collector is delayed or offline, expired checkpoints are logged as `missed_offline` rather than recording stale prices.",
        "3. **Complete Observation Schedule:** The continuous VPS deployment will capture uninterrupted observations across all 12 targets:",
        "   - `T+10s, T+30s, T+60s, T+120s, T+180s, T+300s, T+600s, T+900s, T+1800s, T+3600s, T+21600s, T+86400s`",
        "4. **Prospective Forward Testing:** Any future hypothesis must be frozen before evaluating on the `FORWARD_TESTING` cohort to guarantee zero data snooping.",
    ]

    md_path = reports_dir / "forward_testing_baseline.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    json_path = reports_dir / "forward_testing_baseline.json"
    json_path.write_text(
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

    print(f"Forward-testing baseline report saved to: {md_path}")
    print(f"JSON metrics saved to:                    {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
