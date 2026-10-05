import asyncio
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.research.anomalies import (
    detect_all_anomalies,
    filter_usable_signals,
    format_anomaly_markdown,
)
from app.research.loader import load_all_observations, load_all_signals


async def main() -> None:
    print("=" * 80)
    print("MECO ANOMALY & DATA QUALITY DETECTOR")
    print("=" * 80)

    signals = await load_all_signals()
    observations = await load_all_observations()

    anomalies = detect_all_anomalies(signals, observations)
    usable_signals, excluded_signals = filter_usable_signals(signals)

    counts = Counter(a.anomaly_type for a in anomalies)
    severities = Counter(a.severity for a in anomalies)

    print(f"Total Signals Inspected:      {len(signals)}")
    print(f"Usable Signals for Research:  {len(usable_signals)}")
    print(f"Excluded Signals:             {len(excluded_signals)}")
    print(f"Total Anomaly Events Flagged: {len(anomalies)}")
    print()
    print("Severity Breakdown:")
    print(f"  - Critical:                 {severities['critical']}")
    print(f"  - High:                     {severities['high']}")
    print(f"  - Medium:                   {severities['medium']}")
    print(f"  - Info:                     {severities['info']}")
    print()
    print("Anomaly Event Breakdown:")
    for atype, cnt in counts.most_common():
        print(f"  - {atype:<30}: {cnt:>4}")
    print()
    print("Exclusion Reasons for Discarded Signals:")
    reason_counts = Counter()
    for _, reasons in excluded_signals:
        for r in reasons:
            reason_counts[r] += 1
    for r, cnt in reason_counts.most_common():
        print(f"  - {r:<50}: {cnt:>3}")
    print()

    # Save reports
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_anomaly_markdown(anomalies)
    md_path = reports_dir / "anomaly_report.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "anomaly_report.json"
    json_path.write_text(
        json.dumps(
            {
                "total_signals": len(signals),
                "usable_count": len(usable_signals),
                "excluded_count": len(excluded_signals),
                "total_anomalies": len(anomalies),
                "severities": dict(severities),
                "anomalies": [asdict(a) for a in anomalies],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"Anomaly report saved to: {md_path}")
    print(f"JSON data saved to:       {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
