import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.research.audit import build_audit_report, format_audit_markdown
from app.research.loader import (
    load_all_observations,
    load_all_pair_observations,
    load_all_signals,
)


async def main() -> None:
    print("=" * 80)
    print("MECO DATASET AUDIT")
    print("=" * 80)

    signals = await load_all_signals()
    observations = await load_all_observations()
    pair_observations = await load_all_pair_observations()

    report = build_audit_report(signals, observations, pair_observations)

    # Print concise terminal summary
    print(f"Total Signals:                   {report.total_signals}")
    print(f"Unique Signals (chat+msg):       {report.unique_signals}")
    print(f"Unique Tokens:                   {report.unique_tokens}")
    print(f"Duplicate Token Rate:            {report.duplicate_rate:.2f}%")
    print()
    print("Source Distribution:")
    for src, count in report.source_distribution.items():
        print(f"  - {src:<32}: {count:>4} ({count/report.total_signals*100:.1f}%)")
    print()
    print("Market Status Distribution:")
    for status, count in report.market_status_distribution.items():
        print(f"  - {status:<32}: {count:>4} ({count/report.total_signals*100:.1f}%)")
    print()
    print("Observation Coverage by Target Checkpoint:")
    print(
        f"  {'Target':<8} {'Eligible':>8} {'Captured':>8} {'Coverage':>10} "
        f"{'Success':>8} {'Failed':>7} {'Med Delay':>10}"
    )
    for tc in report.target_coverage:
        med_delay_str = (
            f"{tc.median_delay_seconds:+.1f}s"
            if tc.median_delay_seconds is not None
            else "n/a"
        )
        print(
            f"  T+{tc.target_seconds:<6} {tc.eligible_count:>8} {tc.captured_count:>8} "
            f"{tc.coverage_pct:>9.1f}% {tc.success_count:>8} {tc.failure_count:>7} "
            f"{med_delay_str:>10}"
        )
    print()
    print("Pair Observations:")
    print(f"  - Total Pair Rows:             {report.pair_stats['total_pair_rows']}")
    print(
        f"  - Signals with Pairs:          "
        f"{report.pair_stats['signals_with_pair_observations']} "
        f"(Started at Signal #{report.pair_stats['first_signal_id_with_pairs']})"
    )
    print(
        f"  - Avg Pairs per Checkpoint:    "
        f"{report.pair_stats['avg_pairs_per_checkpoint']:.2f}"
    )
    print(
        f"  - Median Pairs per Checkpoint: "
        f"{report.pair_stats['median_pairs_per_checkpoint']:.1f}"
    )
    print()

    # Save reports
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_audit_markdown(report)
    md_path = reports_dir / "dataset_audit.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "dataset_audit.json"
    json_path.write_text(
        json.dumps(asdict(report), indent=2, default=str), encoding="utf-8"
    )

    print(f"Audit report saved to: {md_path}")
    print(f"JSON metrics saved to: {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
