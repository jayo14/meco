from collections import Counter
from typing import Any

from app.database.models import MarketObservation, Signal
from app.research.models import AnomalyRecord, ExclusionCriteria


def detect_all_anomalies(
    signals: list[Signal],
    observations: list[MarketObservation],
) -> list[AnomalyRecord]:
    """
    Detect all anomalies in historical signals and market observations.
    Never mutates or deletes database rows.
    """
    anomalies: list[AnomalyRecord] = []

    # 1. Signal #103 known anomaly
    for s in signals:
        if s.id == 103:
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="extreme_liquidity_drop",
                    description=(
                        "Initial observation reported $345.8M liquidity which collapsed "
                        "to $20.8K at T+900. Raydium pool pair manipulation or LP glitch."
                    ),
                    severity="critical",
                    recommended_action="exclude_from_returns",
                    details={
                        "initial_liquidity": s.liquidity_usd,
                        "initial_price": s.price_usd,
                        "pair_address": s.pair_address,
                    },
                )
            )

    # 2. Test signals (source_name is None)
    for s in signals:
        if s.source_name is None:
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="test_signal",
                    description=f"Injected test signal with source_name=None ({s.token_address[:10]}...)",
                    severity="high",
                    recommended_action="exclude_all",
                    details={"token_address": s.token_address},
                )
            )

    # 3. Market status failures at arrival time
    for s in signals:
        if s.market_status == "no_liquid_pair":
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="no_liquid_pair_at_signal",
                    description="No liquid pool was discoverable by DexScreener when signal arrived.",
                    severity="medium",
                    recommended_action="exclude_all",
                    details={"market_status": s.market_status},
                )
            )
        elif s.market_status == "fetch_failed":
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="dexscreener_fetch_failed",
                    description="DexScreener API timed out or errored on initial signal capture.",
                    severity="medium",
                    recommended_action="exclude_all",
                    details={"market_status": s.market_status},
                )
            )
        elif s.market_status == "pending":
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="signal_status_pending",
                    description="Signal pipeline remained in pending state without market resolution.",
                    severity="high",
                    recommended_action="exclude_all",
                    details={"validation_status": s.validation_status},
                )
            )

    # 4. Solana RPC failure during validation
    for s in signals:
        if s.validation_status == "rpc_failed":
            anomalies.append(
                AnomalyRecord(
                    signal_id=s.id,
                    token_address=s.token_address,
                    anomaly_type="solana_rpc_failed",
                    description="Solana RPC timed out or failed to validate mint account info.",
                    severity="high",
                    recommended_action="exclude_all",
                    details={"token_address": s.token_address},
                )
            )

    # 5. Non-standard observation targets
    standard_targets = {
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
    }
    for obs in observations:
        if obs.target_seconds not in standard_targets:
            anomalies.append(
                AnomalyRecord(
                    signal_id=obs.signal_id,
                    token_address=obs.token_address,
                    anomaly_type="non_standard_target",
                    description=(
                        f"Observation captured with non-standard target={obs.target_seconds}s "
                        f"(actual={obs.seconds_since_signal}s)"
                    ),
                    severity="info",
                    recommended_action="exclude_from_returns",
                    details={
                        "target_seconds": obs.target_seconds,
                        "seconds_since_signal": obs.seconds_since_signal,
                    },
                )
            )

    # 6. Severe observation delays (>300 seconds late)
    for obs in observations:
        delay = obs.seconds_since_signal - obs.target_seconds
        if delay > 300:
            anomalies.append(
                AnomalyRecord(
                    signal_id=obs.signal_id,
                    token_address=obs.token_address,
                    anomaly_type="severe_observation_delay",
                    description=(
                        f"Observation target={obs.target_seconds}s captured with delay of {delay}s "
                        f"(actual elapsed={obs.seconds_since_signal}s). Caused by offline/sleep gap."
                    ),
                    severity="high",
                    recommended_action="exclude_from_returns",
                    details={
                        "target_seconds": obs.target_seconds,
                        "seconds_since_signal": obs.seconds_since_signal,
                        "delay_seconds": delay,
                    },
                )
            )

    # 7. Signals where primary pair switched across checkpoints
    obs_by_signal: dict[int, list[MarketObservation]] = {}
    for obs in observations:
        obs_by_signal.setdefault(obs.signal_id, []).append(obs)

    for sig_id, sig_obs in obs_by_signal.items():
        distinct_pairs = {
            o.pair_address for o in sig_obs if o.pair_address is not None
        }
        if len(distinct_pairs) > 1:
            token = sig_obs[0].token_address
            anomalies.append(
                AnomalyRecord(
                    signal_id=sig_id,
                    token_address=token,
                    anomaly_type="primary_pair_switched",
                    description=(
                        f"Primary pair switched between {len(distinct_pairs)} different pools "
                        f"across checkpoints. Indicates token migration or shifting liquidity."
                    ),
                    severity="medium",
                    recommended_action="inspect",
                    details={"pairs": list(distinct_pairs)},
                )
            )

    return anomalies


def filter_usable_signals(
    signals: list[Signal],
    criteria: ExclusionCriteria | None = None,
) -> tuple[list[Signal], list[tuple[Signal, list[str]]]]:
    """
    Separate signals into usable and excluded based on research-grade criteria.
    Returns: (usable_signals, excluded_signals_with_reasons)
    """
    if criteria is None:
        criteria = ExclusionCriteria()

    usable: list[Signal] = []
    excluded: list[tuple[Signal, list[str]]] = []

    for s in signals:
        reasons: list[str] = []

        if criteria.exclude_test_signals and s.source_name is None:
            reasons.append("Test signal (source_name is None)")

        if criteria.exclude_signal_103 and s.id == 103:
            reasons.append("Known anomaly #103 ($345M liquidity collapse)")

        if criteria.exclude_failed_market and s.market_status != "available":
            reasons.append(f"Market status: {s.market_status}")

        if criteria.exclude_invalid_mint and s.validation_status in (
            "invalid",
            "rpc_failed",
        ):
            reasons.append(f"Validation status: {s.validation_status}")

        if s.price_usd is None or s.price_usd <= 0:
            reasons.append("Missing or invalid initial price")

        if (
            criteria.min_initial_liquidity_usd > 0
            and s.liquidity_usd is not None
            and s.liquidity_usd < criteria.min_initial_liquidity_usd
        ):
            reasons.append(
                f"Initial liquidity below minimum (${s.liquidity_usd:,.0f} < ${criteria.min_initial_liquidity_usd})"
            )

        if reasons:
            excluded.append((s, reasons))
        else:
            usable.append(s)

    return usable, excluded


def format_anomaly_markdown(anomalies: list[AnomalyRecord]) -> str:
    """Format anomaly records as clean markdown documentation."""
    counts = Counter(a.anomaly_type for a in anomalies)
    severities = Counter(a.severity for a in anomalies)

    lines: list[str] = [
        "# Meco Anomaly & Data Quality Report",
        "",
        "## Summary of Detected Anomalies",
        "",
        f"- **Total Anomaly Events Flagged:** {len(anomalies)}",
        f"- **Critical:** {severities['critical']}",
        f"- **High:** {severities['high']}",
        f"- **Medium:** {severities['medium']}",
        f"- **Informational:** {severities['info']}",
        "",
        "### Breakdown by Anomaly Category",
        "",
        "| Anomaly Type | Occurrences | Default Action |",
        "| :--- | :--- | :--- |",
    ]

    for atype, cnt in counts.most_common():
        sample = next(a for a in anomalies if a.anomaly_type == atype)
        lines.append(f"| {atype} | {cnt} | {sample.recommended_action} |")

    lines.extend([
        "",
        "## Critical & High Severity Details",
        "",
        "### 1. Signal #103 Liquidity Anomaly",
        "- **Signal ID:** 103",
        "- **Token:** `ETXqxfVoPN9f1qX1EV9qPWNqYuu5TUUUXMUM4SsniJga` ($COZY)",
        "- **Initial Recorded State:** $345,863,635.06 liquidity, $0.3146 price on Raydium pool.",
        "- **Subsequent State (T+900):** $20,824.37 liquidity, $0.00001863 price (-99.994%).",
        "- **Cause / Hypothesis:** Artificial pool pairing with inflated token valuation or wash liquidity that was de-indexed/withdrawn.",
        "- **Research Handling:** Kept intact in database, strictly excluded from outcome and return statistics to avoid contaminating aggregates.",
        "",
        "### 2. Severe Observation Delays (Catch-up Gaps)",
        f"- Flagged count: {counts['severe_observation_delay']} observations with delay > 300 seconds.",
        "- **Cause:** When the development machine was asleep or offline (e.g. 15.69-hour gap between IDs 232 and 233), in-flight asyncio observation tasks executed immediately upon resumption with zero delay, recording `target_seconds=3600` or `21600` but an actual elapsed `seconds_since_signal` of 56,000s - 78,000s.",
        "- **Research Handling:** An observation is only considered valid for a target checkpoint if `abs(seconds_since_signal - target_seconds) <= 60s`.",
        "",
        "### 3. Primary Pair Switches Across Checkpoints",
        "- **Signal #52:** Started on Raydium (`AZuZu...`), at T+900 switched to Meteora (`8yXp...`), then at T+1800 returned to Raydium as Raydium liquidity surpassed Meteora ($88.7K vs $65.8K).",
        "- **Signal #223:** Started on PumpSwap (`2B8t...`) with $65K liquidity, subsequently created a Meteora pool (`4s2b...`) with $340K liquidity.",
        "",
        "### 4. Market Availability Failures",
        "- **65 signals (17.0%)** arrived with `market_status = 'no_liquid_pair'`. No pools with valid liquidity existed on DexScreener at signal time.",
        "- **8 signals (2.1%)** suffered DexScreener HTTP timeouts/fetch failures at signal time.",
        "- **1 signal (#226)** suffered Solana RPC validator timeout, leaving it in `pending` state.",
    ])

    return "\n".join(lines)
