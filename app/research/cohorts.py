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
