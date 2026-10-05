from collections import Counter
from datetime import datetime, timezone

from app.database.models import MarketObservation, MarketPairObservation, Signal
from app.research.models import AuditReport, TargetCoverage

STANDARD_TARGETS = (
    10,
    30,
    60,
    120,
    180,
    300,
    600,
    900,
    1800,
    3600,
    21600,
    86400,
)


def calculate_median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def calculate_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def build_audit_report(
    signals: list[Signal],
    observations: list[MarketObservation],
    pair_observations: list[MarketPairObservation],
    now: datetime | None = None,
) -> AuditReport:
    """
    Construct a comprehensive audit of historical signals, observations, and pair data.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    total_signals = len(signals)

    # Unique signals by chat_id + message_id
    seen_chat_msgs = set()
    unique_signals = 0
    for s in signals:
        key = (s.chat_id, s.message_id)
        if key not in seen_chat_msgs:
            seen_chat_msgs.add(key)
            unique_signals += 1

    # Unique tokens
    unique_tokens = len({s.token_address for s in signals})
    duplicate_rate = (
        ((total_signals - unique_tokens) / total_signals * 100)
        if total_signals > 0
        else 0.0
    )

    # Source distribution
    source_counts = Counter(s.source_name or "Unknown/Test" for s in signals)

    # Date distribution
    date_counts = Counter(
        s.message_created_at.strftime("%Y-%m-%d") for s in signals
    )

    # Validation distribution
    val_counts = Counter(s.validation_status or "unvalidated" for s in signals)

    # Market status distribution
    mkt_counts = Counter(s.market_status or "unknown" for s in signals)

    # DEX distribution (from initial signal snapshot)
    dex_counts = Counter(s.dex_id or "none" for s in signals)

    # Group observations by (signal_id, target_seconds)
    obs_by_signal_target: dict[tuple[int, int], MarketObservation] = {}
    for obs in observations:
        obs_by_signal_target[(obs.signal_id, obs.target_seconds)] = obs

    # Target coverage calculation for standard targets
    target_coverage_list: list[TargetCoverage] = []

    # Filter to real market-available signals for observation eligibility
    available_signals = [s for s in signals if s.market_status == "available"]

    for target in STANDARD_TARGETS:
        # A signal is eligible for target T if it arrived at least T seconds before 'now'
        eligible = [
            s
            for s in available_signals
            if (
                now - (s.received_at or s.message_created_at)
            ).total_seconds()
            >= target
        ]
        eligible_count = len(eligible)

        captured: list[MarketObservation] = []
        successes: list[MarketObservation] = []
        failures: list[MarketObservation] = []
        failure_reasons: Counter[str] = Counter()
        delays: list[float] = []

        for s in eligible:
            obs = obs_by_signal_target.get((s.id, target))
            if obs is not None:
                captured.append(obs)
                delay = float(obs.seconds_since_signal - obs.target_seconds)
                delays.append(delay)
                if obs.observation_status == "success":
                    successes.append(obs)
                else:
                    failures.append(obs)
                    failure_reasons[obs.observation_status] += 1

        coverage_pct = (
            (len(captured) / eligible_count * 100.0)
            if eligible_count > 0
            else 0.0
        )

        target_coverage_list.append(
            TargetCoverage(
                target_seconds=target,
                eligible_count=eligible_count,
                captured_count=len(captured),
                coverage_pct=coverage_pct,
                success_count=len(successes),
                failure_count=len(failures),
                failure_reasons=dict(failure_reasons),
                median_delay_seconds=calculate_median(delays),
                max_delay_seconds=max(delays) if delays else None,
                min_delay_seconds=min(delays) if delays else None,
            )
        )

    # Pair statistics
    pair_counts_per_checkpoint: list[int] = []
    pair_checkpoints: dict[tuple[int, int], int] = Counter()
    for p in pair_observations:
        pair_checkpoints[(p.signal_id, p.target_seconds)] += 1

    pair_counts_per_checkpoint = list(pair_checkpoints.values())
    signals_with_pairs = len({p.signal_id for p in pair_observations})

    pair_stats = {
        "total_pair_rows": len(pair_observations),
        "signals_with_pair_observations": signals_with_pairs,
        "first_signal_id_with_pairs": (
            min((p.signal_id for p in pair_observations), default=0)
        ),
        "min_pairs_per_checkpoint": (
            min(pair_counts_per_checkpoint) if pair_counts_per_checkpoint else 0
        ),
        "max_pairs_per_checkpoint": (
            max(pair_counts_per_checkpoint) if pair_counts_per_checkpoint else 0
        ),
        "avg_pairs_per_checkpoint": (
            calculate_mean([float(x) for x in pair_counts_per_checkpoint]) or 0.0
        ),
        "median_pairs_per_checkpoint": (
            calculate_median([float(x) for x in pair_counts_per_checkpoint]) or 0.0
        ),
    }

    pair_dex_counts = Counter(p.dex_id for p in pair_observations)

    return AuditReport(
        total_signals=total_signals,
        unique_signals=unique_signals,
        unique_tokens=unique_tokens,
        duplicate_rate=duplicate_rate,
        source_distribution=dict(source_counts),
        date_distribution=dict(sorted(date_counts.items())),
        validation_distribution=dict(val_counts),
        market_status_distribution=dict(mkt_counts),
        dex_distribution=dict(dex_counts),
        target_coverage=target_coverage_list,
        pair_stats=pair_stats,
        pair_dex_distribution=dict(pair_dex_counts.most_common()),
        generated_at=now.isoformat(),
    )


def format_audit_markdown(report: AuditReport) -> str:
    """Format AuditReport as clean markdown documentation."""
    lines: list[str] = [
        "# Meco Dataset Audit Report",
        "",
        f"**Generated at:** {report.generated_at}",
        "",
        "## 1. High-Level Signal Summary",
        "",
        f"- **Total Signals:** {report.total_signals}",
        f"- **Unique Telegram Messages:** {report.unique_signals}",
        f"- **Unique Token Addresses:** {report.unique_tokens}",
        f"- **Token Repetition / Duplicate Rate:** {report.duplicate_rate:.2f}%",
        "",
        "### Source Distribution",
        "",
        "| Source Channel | Signal Count | Share |",
        "| :--- | :--- | :--- |",
    ]

    for src, count in report.source_distribution.items():
        share = count / report.total_signals * 100
        lines.append(f"| {src} | {count} | {share:.1f}% |")

    lines.extend([
        "",
        "### Date Distribution",
        "",
        "| Date | Signal Count |",
        "| :--- | :--- |",
    ])
    for dt, count in report.date_distribution.items():
        lines.append(f"| {dt} | {count} |")

    lines.extend([
        "",
        "### Solana Mint Validation Status",
        "",
        "| Validation Status | Count | Notes |",
        "| :--- | :--- | :--- |",
    ])
    for st, count in report.validation_distribution.items():
        notes = (
            "Pre-validation phase (Signals 1-73)"
            if st == "unvalidated"
            else "Valid SPL Token mint"
            if st == "valid"
            else "Solana RPC error during validation"
        )
        lines.append(f"| {st} | {count} | {notes} |")

    lines.extend([
        "",
        "### Market Availability Status",
        "",
        "| Market Status | Count | Notes |",
        "| :--- | :--- | :--- |",
    ])
    for st, count in report.market_status_distribution.items():
        notes = (
            "Valid liquid pair found, observations scheduled"
            if st == "available"
            else "DexScreener found no pool with liquidity"
            if st == "no_liquid_pair"
            else "DexScreener API network/timeout error"
            if st == "fetch_failed"
            else "Pipeline pending/aborted"
        )
        lines.append(f"| {st} | {count} | {notes} |")

    lines.extend([
        "",
        "### Primary DEX Distribution (Signal Time)",
        "",
        "| DEX ID | Initial Signals | Share |",
        "| :--- | :--- | :--- |",
    ])
    for dex, count in report.dex_distribution.items():
        share = count / report.total_signals * 100
        lines.append(f"| {dex} | {count} | {share:.1f}% |")

    lines.extend([
        "",
        "## 2. Observation Coverage by Target Checkpoint",
        "",
        "| Target | Eligible | Captured | Coverage % | Success | Failed | Med Delay (s) | Max Delay (s) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for tc in report.target_coverage:
        med_d = (
            f"{tc.median_delay_seconds:+.1f}s"
            if tc.median_delay_seconds is not None
            else "n/a"
        )
        max_d = (
            f"{tc.max_delay_seconds:+.1f}s"
            if tc.max_delay_seconds is not None
            else "n/a"
        )
        lines.append(
            f"| T+{tc.target_seconds:<5} | {tc.eligible_count:>8} | "
            f"{tc.captured_count:>8} | {tc.coverage_pct:>9.1f}% | "
            f"{tc.success_count:>7} | {tc.failure_count:>6} | "
            f"{med_d:>13} | {max_d:>13} |"
        )

    lines.extend([
        "",
        "## 3. Pair-Level Observation Coverage",
        "",
        f"- **Total Stored Pair Rows:** {report.pair_stats['total_pair_rows']}",
        f"- **Signals with Pair History:** {report.pair_stats['signals_with_pair_observations']} (Started at Signal #{report.pair_stats['first_signal_id_with_pairs']})",
        f"- **Average Pairs per Checkpoint:** {report.pair_stats['avg_pairs_per_checkpoint']:.2f}",
        f"- **Median Pairs per Checkpoint:** {report.pair_stats['median_pairs_per_checkpoint']:.1f}",
        f"- **Max Pairs per Checkpoint:** {report.pair_stats['max_pairs_per_checkpoint']}",
        "",
        "### DEX Breakdown Across All Stored Pairs",
        "",
        "| DEX | Pair Rows Captured |",
        "| :--- | :--- |",
    ])

    for dex, count in report.pair_dex_distribution.items():
        lines.append(f"| {dex} | {count} |")

    lines.extend([
        "",
        "## 4. Key Audit Findings & Structural Realities",
        "",
        "1. **Test Signals:** 5 early signals (#1, #2, #3, #5, #10) were manually or locally injected test runs (Wrapped SOL and test mints) with `source_name=None`. They must be isolated from strategy research.",
        "2. **Feature Timeline Evolution:**",
        "   - Signals 1-73: Solana mint validation had not yet been deployed.",
        "   - Signal #74+: Solana on-chain mint validation was operational (309 valid, 1 rpc_failed).",
        "   - Signals 1-113: Pair-level snapshots were not yet stored in `market_pair_observations`.",
        "   - Signal #114+: Full candidate pair snapshots captured for all observations.",
        "   - Observation intervals: Early signals only targeted 30, 60, 300, 900s. Targets 10, 120, 180, 600s were added later; 21600s (6h) was added around signal 170+; 86400s (24h) has 0 captures due to local sleep/offline cycles.",
        "3. **Observation Timing Precision:** When the process is active, median delay is exactly 1.0s. However, 69 observations exhibit delays >300s (up to ~15.6 hours) caused by laptop sleep/restarts catching up on expired targets.",
        "4. **No-Liquid-Pair Rate:** 65 of 383 signals (17.0%) had no liquid DexScreener pair at arrival time, meaning the signal called a token that could not be verified on automated DEX pools immediately.",
    ])

    return "\n".join(lines)
