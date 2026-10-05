from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.database.models import MarketPairObservation, Signal
from app.research.audit import calculate_mean, calculate_median


@dataclass
class PreSignalMetrics:
    signal_id: int
    token_address: str
    pair_address: str | None
    dex_id: str | None
    telegram_created_at: datetime
    pool_created_at: datetime | None
    pool_age_at_signal_seconds: float | None
    pre_signal_volume_5m: float | None
    pre_signal_buys_5m: int | None
    pre_signal_sells_5m: int | None
    pre_signal_buy_ratio: float | None
    volume_to_liquidity: float | None
    is_telegram_called: bool = True


@dataclass
class PreSignalCohortAnalysis:
    total_evaluated: int
    median_pool_age_seconds: float | None
    mean_pool_age_seconds: float | None
    pct_under_2_minutes: float
    pct_under_5_minutes: float
    pct_under_15_minutes: float
    pct_over_1_hour: float


def reconstruct_presignal_metrics(
    signals: list[Signal],
    pair_observations: list[MarketPairObservation],
) -> list[PreSignalMetrics]:
    """
    Reconstruct pre-signal metrics and on-chain pool age relative to Telegram alert time.
    """
    # Map earliest pair_created_at by signal_id
    pair_created_by_signal: dict[int, tuple[int, str, str]] = {}
    for p in pair_observations:
        if p.pair_created_at is not None:
            existing = pair_created_by_signal.get(p.signal_id)
            if existing is None or p.pair_created_at < existing[0]:
                pair_created_by_signal[p.signal_id] = (
                    p.pair_created_at,
                    p.pair_address,
                    p.dex_id,
                )

    metrics_list: list[PreSignalMetrics] = []

    for s in signals:
        pool_info = pair_created_by_signal.get(s.id)
        pool_created_dt = None
        age_seconds = None
        pair_addr = s.pair_address
        dex = s.dex_id

        if pool_info is not None:
            created_ms, p_addr, p_dex = pool_info
            pool_created_dt = datetime.fromtimestamp(
                created_ms / 1000.0, tz=timezone.utc
            )
            age_seconds = (s.message_created_at - pool_created_dt).total_seconds()
            pair_addr = pair_addr or p_addr
            dex = dex or p_dex

        buys = s.buys_5m or 0
        sells = s.sells_5m or 0
        total = buys + sells
        buy_ratio = (buys / total) if total > 0 else None

        liq = s.liquidity_usd
        vol5m = s.volume_5m
        vol_liq = (vol5m / liq) if (liq and liq > 0 and vol5m) else None

        metrics_list.append(
            PreSignalMetrics(
                signal_id=s.id,
                token_address=s.token_address,
                pair_address=pair_addr,
                dex_id=dex,
                telegram_created_at=s.message_created_at,
                pool_created_at=pool_created_dt,
                pool_age_at_signal_seconds=age_seconds,
                pre_signal_volume_5m=vol5m,
                pre_signal_buys_5m=s.buys_5m,
                pre_signal_sells_5m=s.sells_5m,
                pre_signal_buy_ratio=buy_ratio,
                volume_to_liquidity=vol_liq,
                is_telegram_called=True,
            )
        )

    return metrics_list


def analyze_presignal_cohort(
    metrics: list[PreSignalMetrics],
) -> PreSignalCohortAnalysis:
    """Analyze empirical pool age and pre-signal timing across tokens."""
    valid_ages = [
        m.pool_age_at_signal_seconds
        for m in metrics
        if m.pool_age_at_signal_seconds is not None and m.pool_age_at_signal_seconds >= 0
    ]

    n = len(valid_ages)
    if n == 0:
        return PreSignalCohortAnalysis(
            total_evaluated=0,
            median_pool_age_seconds=None,
            mean_pool_age_seconds=None,
            pct_under_2_minutes=0.0,
            pct_under_5_minutes=0.0,
            pct_under_15_minutes=0.0,
            pct_over_1_hour=0.0,
        )

    return PreSignalCohortAnalysis(
        total_evaluated=n,
        median_pool_age_seconds=calculate_median(valid_ages),
        mean_pool_age_seconds=calculate_mean(valid_ages),
        pct_under_2_minutes=sum(1 for a in valid_ages if a <= 120) / n * 100.0,
        pct_under_5_minutes=sum(1 for a in valid_ages if a <= 300) / n * 100.0,
        pct_under_15_minutes=sum(1 for a in valid_ages if a <= 900) / n * 100.0,
        pct_over_1_hour=sum(1 for a in valid_ages if a > 3600) / n * 100.0,
    )
