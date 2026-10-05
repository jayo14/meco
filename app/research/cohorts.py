from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.database.models import Signal

# Exact historical research freeze point
HISTORICAL_RESEARCH_MAX_SIGNAL_ID = 387
HISTORICAL_RESEARCH_FREEZE_TIMESTAMP = "2026-10-05T21:42:00+00:00"


class SignalCohort(str, Enum):
    HISTORICAL_RESEARCH = "historical_research"
    FORWARD_TESTING = "forward_testing"


@dataclass
class CohortSummary:
    cohort: SignalCohort
    min_id: int | None
    max_id: int | None
    total_signals: int
    min_timestamp: str | None
    max_timestamp: str | None
    description: str


def classify_signal_cohort(signal: Signal) -> SignalCohort:
    """Classify a signal into historical research vs forward testing cohort."""
    if signal.id <= HISTORICAL_RESEARCH_MAX_SIGNAL_ID:
        return SignalCohort.HISTORICAL_RESEARCH
    return SignalCohort.FORWARD_TESTING


def partition_by_cohort(
    signals: list[Signal],
) -> dict[SignalCohort, list[Signal]]:
    """Partition signals into historical and forward cohorts."""
    partitioned: dict[SignalCohort, list[Signal]] = {
        SignalCohort.HISTORICAL_RESEARCH: [],
        SignalCohort.FORWARD_TESTING: [],
    }
    for s in signals:
        cohort = classify_signal_cohort(s)
        partitioned[cohort].append(s)
    return partitioned


def summarize_cohort(cohort: SignalCohort, signals: list[Signal]) -> CohortSummary:
    """Summarize a cohort's span and signal count."""
    if not signals:
        return CohortSummary(
            cohort=cohort,
            min_id=None,
            max_id=None,
            total_signals=0,
            min_timestamp=None,
            max_timestamp=None,
            description="Empty cohort",
        )

    min_s = min(signals, key=lambda s: s.id)
    max_s = max(signals, key=lambda s: s.id)

    desc = (
        "Initial local development dataset (Signals 1-387). Used for initial audit, "
        "anomaly discovery, and baseline hypothesis evaluation. Subject to local offline gaps."
        if cohort == SignalCohort.HISTORICAL_RESEARCH
        else "Forward testing dataset (Signals >= 388). Intended for uninterrupted, "
        "continuous 24/7 capture on VPS to forward-test hypotheses with clean T+24h coverage."
    )

    return CohortSummary(
        cohort=cohort,
        min_id=min_s.id,
        max_id=max_s.id,
        total_signals=len(signals),
        min_timestamp=str(min_s.message_created_at),
        max_timestamp=str(max_s.message_created_at),
        description=desc,
    )


def format_baseline_cohort_markdown(
    hist_summary: CohortSummary,
    fwd_summary: CohortSummary,
    usable_hist_count: int,
    excluded_hist_count: int,
) -> str:
    """Format the forward testing baseline and cohort report as Markdown."""
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
        f"- **Clean Usable Signals for Research:** {usable_hist_count}",
        f"- **Excluded Signals:** {excluded_hist_count} (test calls, unliquid pools, anomaly #103)",
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
    return "\n".join(lines)

