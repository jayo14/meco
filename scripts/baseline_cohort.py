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

    from app.research.cohorts import format_baseline_cohort_markdown

    md_content = format_baseline_cohort_markdown(
        hist_summary, fwd_summary, len(usable_hist), len(excluded_hist)
    )
    md_path = reports_dir / "forward_testing_baseline.md"
    md_path.write_text(md_content, encoding="utf-8")


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
