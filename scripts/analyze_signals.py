import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.database.models import MarketObservation, Signal
from app.database.session import SessionLocal


SOURCE = "Bullish Calls - Solana"

TARGETS = (30, 60, 300, 900)


@dataclass
class ReturnStats:
    target_seconds: int
    samples: int
    positive: int
    negative: int
    unchanged: int
    average_return_pct: float | None
    median_return_pct: float | None
    average_liquidity_change_pct: float | None


def percent_change(
    initial: float | None,
    current: float | None,
) -> float | None:
    if initial is None or current is None:
        return None

    if initial <= 0:
        return None

    return ((current - initial) / initial) * 100


def median(values: list[float]) -> float | None:
    if not values:
        return None

    values = sorted(values)
    middle = len(values) // 2

    if len(values) % 2:
        return values[middle]

    return (values[middle - 1] + values[middle]) / 2


async def load_data() -> tuple[
    list[Signal],
    list[MarketObservation],
]:
    async with SessionLocal() as session:
        signals_result = await session.execute(
            select(Signal)
            .where(Signal.source_name == SOURCE)
            .order_by(Signal.id)
        )

        observations_result = await session.execute(
            select(MarketObservation)
            .order_by(
                MarketObservation.signal_id,
                MarketObservation.target_seconds,
            )
        )

        signals = list(signals_result.scalars().all())
        observations = list(observations_result.scalars().all())

    return signals, observations


def build_observation_map(
    observations: list[MarketObservation],
) -> dict[tuple[int, int], MarketObservation]:
    return {
        (
            observation.signal_id,
            observation.target_seconds,
        ): observation
        for observation in observations
    }


def calculate_stats(
    signals: list[Signal],
    observation_map: dict[tuple[int, int], MarketObservation],
    target_seconds: int,
) -> ReturnStats:
    returns: list[float] = []
    liquidity_changes: list[float] = []

    positive = 0
    negative = 0
    unchanged = 0

    for signal in signals:
        if signal.price_usd is None:
            continue

        observation = observation_map.get(
            (signal.id, target_seconds)
        )

        if observation is None:
            continue

        if observation.observation_status != "success":
            continue

        return_pct = percent_change(
            signal.price_usd,
            observation.price_usd,
        )

        if return_pct is None:
            continue

        returns.append(return_pct)

        if return_pct > 0:
            positive += 1
        elif return_pct < 0:
            negative += 1
        else:
            unchanged += 1

        liquidity_change = percent_change(
            signal.liquidity_usd,
            observation.liquidity_usd,
        )

        if liquidity_change is not None:
            liquidity_changes.append(liquidity_change)

    average_return = (
        sum(returns) / len(returns)
        if returns
        else None
    )

    average_liquidity_change = (
        sum(liquidity_changes) / len(liquidity_changes)
        if liquidity_changes
        else None
    )

    return ReturnStats(
        target_seconds=target_seconds,
        samples=len(returns),
        positive=positive,
        negative=negative,
        unchanged=unchanged,
        average_return_pct=average_return,
        median_return_pct=median(returns),
        average_liquidity_change_pct=average_liquidity_change,
    )


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"

    return f"{value:+.2f}%"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"

    return f"{seconds:.2f}s"


def print_overview(
    signals: list[Signal],
    observations: list[MarketObservation],
) -> None:
    with_market = sum(
        1
        for signal in signals
        if signal.price_usd is not None
    )

    with_liquidity = sum(
        1
        for signal in signals
        if signal.liquidity_usd is not None
    )

    valid = sum(
        1
        for signal in signals
        if signal.validation_status == "valid"
    )

    print("=" * 80)
    print("MECO SIGNAL ANALYSIS")
    print("=" * 80)
    print()
    print(f"Source:                    {SOURCE}")
    print(f"Signals:                   {len(signals)}")
    print(f"With market data:          {with_market}")
    print(f"With liquidity data:       {with_liquidity}")
    print(f"Explicitly valid mints:    {valid}")
    print(
        f"Successful observations:   "
        f"{sum(1 for o in observations if o.observation_status == 'success')}"
    )
    print()


def print_checkpoint_analysis(
    signals: list[Signal],
    observation_map: dict[
        tuple[int, int],
        MarketObservation,
    ],
) -> None:
    print("-" * 80)
    print("PRICE PATH")
    print("-" * 80)

    print(
        f"{'Target':<10}"
        f"{'Samples':>8}"
        f"{'Positive':>10}"
        f"{'Negative':>10}"
        f"{'Avg':>12}"
        f"{'Median':>12}"
        f"{'Avg Liq':>12}"
    )

    for target in TARGETS:
        stats = calculate_stats(
            signals,
            observation_map,
            target,
        )

        print(
            f"T+{target:<7}"
            f"{stats.samples:>8}"
            f"{stats.positive:>10}"
            f"{stats.negative:>10}"
            f"{format_pct(stats.average_return_pct):>12}"
            f"{format_pct(stats.median_return_pct):>12}"
            f"{format_pct(stats.average_liquidity_change_pct):>12}"
        )

    print()


def get_observed_extremes(
    signals: list[Signal],
    observations: list[MarketObservation],
    observation_map: dict[
        tuple[int, int],
        MarketObservation,
    ],
) -> tuple[
    list[tuple[float, Signal, MarketObservation]],
    list[tuple[float, Signal, MarketObservation]],
]:
    upsides = []
    drawdowns = []

    for signal in signals:
        if signal.price_usd is None:
            continue

        for target in TARGETS:
            observation = observation_map.get(
                (signal.id, target)
            )

            if observation is None:
                continue

            if observation.observation_status != "success":
                continue

            return_pct = percent_change(
                signal.price_usd,
                observation.price_usd,
            )

            if return_pct is None:
                continue

            upsides.append(
                (return_pct, signal, observation)
            )

            drawdowns.append(
                (return_pct, signal, observation)
            )

    upsides.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    drawdowns.sort(
        key=lambda item: item[0]
    )

    return upsides, drawdowns


def print_extremes(
    signals: list[Signal],
    observations: list[MarketObservation],
    observation_map: dict[
        tuple[int, int],
        MarketObservation,
    ],
) -> None:
    upsides, drawdowns = get_observed_extremes(
        signals,
        observations,
        observation_map,
    )

    print("-" * 80)
    print("TOP OBSERVED UPSIDE")
    print("-" * 80)

    for rank, (return_pct, signal, observation) in enumerate(
        upsides[:10],
        start=1,
    ):
        print(
            f"{rank:>2}. "
            f"Signal #{signal.id:<4} "
            f"T+{observation.target_seconds:<5} "
            f"{format_pct(return_pct):>9} "
            f"price={observation.price_usd}"
        )

    print()

    print("-" * 80)
    print("TOP OBSERVED DRAWDOWN")
    print("-" * 80)

    for rank, (return_pct, signal, observation) in enumerate(
        drawdowns[:10],
        start=1,
    ):
        print(
            f"{rank:>2}. "
            f"Signal #{signal.id:<4} "
            f"T+{observation.target_seconds:<5} "
            f"{format_pct(return_pct):>9} "
            f"price={observation.price_usd}"
        )

    print()


def print_latency_analysis(
    signals: list[Signal],
) -> None:
    latencies: list[float] = []

    for signal in signals:
        if (
            signal.message_created_at is None
            or signal.received_at is None
        ):
            continue

        latency = (
            signal.received_at
            - signal.message_created_at
        ).total_seconds()

        if latency >= 0:
            latencies.append(latency)

    print("-" * 80)
    print("TELEGRAM DELIVERY LATENCY")
    print("-" * 80)

    if not latencies:
        print("No latency data available.")
        print()
        return

    print(f"Samples:     {len(latencies)}")
    print(
        f"Average:     "
        f"{format_duration(sum(latencies) / len(latencies))}"
    )
    print(
        f"Median:      "
        f"{format_duration(median(latencies))}"
    )
    print(
        f"Minimum:     "
        f"{format_duration(min(latencies))}"
    )
    print(
        f"Maximum:     "
        f"{format_duration(max(latencies))}"
    )
    print()


def print_latency_extremes(
    signals: list[Signal],
) -> None:
    rows: list[tuple[float, Signal]] = []

    for signal in signals:
        if (
            signal.message_created_at is None
            or signal.received_at is None
        ):
            continue

        latency = (
            signal.received_at
            - signal.message_created_at
        ).total_seconds()

        if latency >= 0:
            rows.append((latency, signal))

    rows.sort(key=lambda item: item[0], reverse=True)

    print("-" * 80)
    print("HIGHEST TELEGRAM LATENCIES")
    print("-" * 80)

    for rank, (latency, signal) in enumerate(
        rows[:10],
        start=1,
    ):
        print(
            f"{rank:>2}. "
            f"Signal #{signal.id:<4} "
            f"{format_duration(latency):>9} "
            f"mint={signal.token_address}"
        )

    print()


def print_data_quality(
    signals: list[Signal],
    observation_map: dict[
        tuple[int, int],
        MarketObservation,
    ],
) -> None:
    print("-" * 80)
    print("OBSERVATION COVERAGE")
    print("-" * 80)

    for target in TARGETS:
        total = 0
        success = 0
        failed = 0

        for signal in signals:
            observation = observation_map.get(
                (signal.id, target)
            )

            if observation is None:
                continue

            total += 1

            if observation.observation_status == "success":
                success += 1
            else:
                failed += 1

        coverage_pct = (
            (success / total) * 100
            if total
            else 0
        )

        print(
            f"T+{target:<5} "
            f"total={total:<4} "
            f"success={success:<4} "
            f"failed={failed:<4} "
            f"success_rate={coverage_pct:.1f}%"
        )

    print()


async def main() -> None:
    signals, observations = await load_data()

    observation_map = build_observation_map(
        observations
    )

    print_overview(
        signals,
        observations,
    )

    print_checkpoint_analysis(
        signals,
        observation_map,
    )

    print_extremes(
        signals,
        observations,
        observation_map,
    )

    print_latency_analysis(signals)

    print_latency_extremes(signals)

    print_data_quality(
        signals,
        observation_map,
    )

    print("=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
