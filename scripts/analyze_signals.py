import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.database.models import MarketObservation, Signal
from app.database.session import SessionLocal


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


async def load_data() -> tuple[list[Signal], list[MarketObservation]]:
    async with SessionLocal() as session:
        signals_result = await session.execute(
            select(Signal).order_by(Signal.id)
        )

        observations_result = await session.execute(
            select(MarketObservation).order_by(
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
        (observation.signal_id, observation.target_seconds): observation
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


def print_report(
    signals: list[Signal],
    observations: list[MarketObservation],
    observation_map: dict[tuple[int, int], MarketObservation],
) -> None:
    total_signals = len(signals)

    signals_with_market = sum(
        1
        for signal in signals
        if signal.price_usd is not None
        and signal.liquidity_usd is not None
    )

    successful_observations = sum(
        1
        for observation in observations
        if observation.observation_status == "success"
    )

    print()
    print("=" * 72)
    print("MECO SIGNAL ANALYSIS")
    print("=" * 72)
    print()

    print(f"Total signals:             {total_signals}")
    print(f"Signals with market data:  {signals_with_market}")
    print(f"Successful observations:   {successful_observations}")
    print()

    print("-" * 72)
    print("PRICE PATH")
    print("-" * 72)

    print(
        f"{'Target':>8} "
        f"{'Samples':>8} "
        f"{'Positive':>10} "
        f"{'Negative':>10} "
        f"{'Avg':>12} "
        f"{'Median':>12} "
        f"{'Avg Liq':>12}"
    )

    for target in TARGETS:
        stats = calculate_stats(
            signals,
            observation_map,
            target,
        )

        print(
            f"T+{target:<4} "
            f"{stats.samples:>8} "
            f"{stats.positive:>10} "
            f"{stats.negative:>10} "
            f"{format_pct(stats.average_return_pct):>12} "
            f"{format_pct(stats.median_return_pct):>12} "
            f"{format_pct(stats.average_liquidity_change_pct):>12}"
        )

    print()

    print("-" * 72)
    print("INDIVIDUAL SIGNALS")
    print("-" * 72)

    for signal in signals:
        if signal.price_usd is None:
            continue

        print()
        print(
            f"Signal #{signal.id} | "
            f"{signal.token_address} | "
            f"{signal.source_name or 'unknown source'}"
        )

        print(
            f"Initial: price={signal.price_usd} | "
            f"liquidity={signal.liquidity_usd} | "
            f"volume_5m={signal.volume_5m}"
        )

        for target in TARGETS:
            observation = observation_map.get(
                (signal.id, target)
            )

            if observation is None:
                continue

            if observation.observation_status != "success":
                print(
                    f"T+{target}: "
                    f"{observation.observation_status}"
                )
                continue

            return_pct = percent_change(
                signal.price_usd,
                observation.price_usd,
            )

            liquidity_pct = percent_change(
                signal.liquidity_usd,
                observation.liquidity_usd,
            )

            print(
                f"T+{target}: "
                f"price={observation.price_usd} "
                f"({format_pct(return_pct)}) | "
                f"liquidity={observation.liquidity_usd} "
                f"({format_pct(liquidity_pct)}) | "
                f"actual={observation.seconds_since_signal}s"
            )


async def main() -> None:
    signals, observations = await load_data()

    observation_map = build_observation_map(observations)

    print_report(
        signals,
        observations,
        observation_map,
    )


if __name__ == "__main__":
    asyncio.run(main())
