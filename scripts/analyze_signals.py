import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.database.models import MarketObservation, Signal
from app.database.session import SessionLocal


SOURCE = "Bullish Calls - Solana"

OUTCOME_TARGET = 900

WINNER_THRESHOLD = 20.0
LOSER_THRESHOLD = -20.0


@dataclass
class SignalOutcome:
    signal: Signal
    observation: MarketObservation
    return_pct: float


def percent_change(
    initial: float | None,
    current: float | None,
) -> float | None:
    if initial is None or current is None:
        return None

    if initial <= 0:
        return None

    return ((current - initial) / initial) * 100


def safe_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if numerator is None or denominator is None:
        return None

    if denominator <= 0:
        return None

    return numerator / denominator


def median(values: list[float]) -> float | None:
    if not values:
        return None

    values = sorted(values)
    middle = len(values) // 2

    if len(values) % 2:
        return values[middle]

    return (values[middle - 1] + values[middle]) / 2


def average(values: list[float]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


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
            .where(
                MarketObservation.target_seconds == OUTCOME_TARGET
            )
            .order_by(MarketObservation.signal_id)
        )

        signals = list(signals_result.scalars().all())
        observations = list(observations_result.scalars().all())

    return signals, observations


def build_outcomes(
    signals: list[Signal],
    observations: list[MarketObservation],
) -> list[SignalOutcome]:
    signals_by_id = {
        signal.id: signal
        for signal in signals
    }

    outcomes: list[SignalOutcome] = []

    for observation in observations:
        signal = signals_by_id.get(observation.signal_id)

        if signal is None:
            continue

        if observation.observation_status != "success":
            continue

        return_pct = percent_change(
            signal.price_usd,
            observation.price_usd,
        )

        if return_pct is None:
            continue

        outcomes.append(
            SignalOutcome(
                signal=signal,
                observation=observation,
                return_pct=return_pct,
            )
        )

    return outcomes


def classify_outcome(
    return_pct: float,
) -> str:
    if return_pct >= WINNER_THRESHOLD:
        return "winner"

    if return_pct <= LOSER_THRESHOLD:
        return "loser"

    return "middle"


def print_outcome_summary(
    outcomes: list[SignalOutcome],
) -> None:
    winners = [
        outcome
        for outcome in outcomes
        if classify_outcome(outcome.return_pct) == "winner"
    ]

    losers = [
        outcome
        for outcome in outcomes
        if classify_outcome(outcome.return_pct) == "loser"
    ]

    middle = [
        outcome
        for outcome in outcomes
        if classify_outcome(outcome.return_pct) == "middle"
    ]

    print("=" * 80)
    print("MECO WINNER VS LOSER ANALYSIS")
    print("=" * 80)
    print()
    print(f"Source:             {SOURCE}")
    print(f"Outcome checkpoint: T+{OUTCOME_TARGET}")
    print(f"Total outcomes:     {len(outcomes)}")
    print()
    print(
        f"Winners >= +{WINNER_THRESHOLD:.0f}%: "
        f"{len(winners)}"
    )
    print(
        f"Losers <= {LOSER_THRESHOLD:.0f}%: "
        f"{len(losers)}"
    )
    print(
        f"Middle:             "
        f"{len(middle)}"
    )
    print()


def feature_values(
    outcomes: list[SignalOutcome],
    feature: str,
) -> list[float]:
    values: list[float] = []

    for outcome in outcomes:
        signal = outcome.signal

        value = getattr(signal, feature, None)

        if value is None:
            continue

        values.append(float(value))

    return values


def print_feature_comparison(
    winners: list[SignalOutcome],
    losers: list[SignalOutcome],
) -> None:
    print("-" * 80)
    print("INITIAL FEATURE COMPARISON")
    print("-" * 80)

    print(
        f"{'Feature':<24}"
        f"{'Winner Avg':>16}"
        f"{'Winner Med':>16}"
        f"{'Loser Avg':>16}"
        f"{'Loser Med':>16}"
    )

    features = [
        ("Liquidity USD", "liquidity_usd"),
        ("5m Volume USD", "volume_5m"),
        ("Buys (5m)", "buys_5m"),
        ("Sells (5m)", "sells_5m"),
        ("Initial Price", "price_usd"),
        ("Market Cap", "market_cap"),
        ("FDV", "fdv"),
    ]

    for label, feature in features:
        winner_values = feature_values(
            winners,
            feature,
        )

        loser_values = feature_values(
            losers,
            feature,
        )

        print(
            f"{label:<24}"
            f"{average(winner_values) or 0:>16.2f}"
            f"{median(winner_values) or 0:>16.2f}"
            f"{average(loser_values) or 0:>16.2f}"
            f"{median(loser_values) or 0:>16.2f}"
        )

    print()


def get_buy_sell_ratio(
    signal: Signal,
) -> float | None:
    return safe_ratio(
        signal.buys_5m,
        signal.sells_5m,
    )


def print_trading_activity_comparison(
    winners: list[SignalOutcome],
    losers: list[SignalOutcome],
) -> None:
    winner_ratios = [
        ratio
        for outcome in winners
        if (
            ratio := get_buy_sell_ratio(outcome.signal)
        ) is not None
    ]

    loser_ratios = [
        ratio
        for outcome in losers
        if (
            ratio := get_buy_sell_ratio(outcome.signal)
        ) is not None
    ]

    winner_trades = [
        float(
            (outcome.signal.buys_5m or 0)
            + (outcome.signal.sells_5m or 0)
        )
        for outcome in winners
    ]

    loser_trades = [
        float(
            (outcome.signal.buys_5m or 0)
            + (outcome.signal.sells_5m or 0)
        )
        for outcome in losers
    ]

    print("-" * 80)
    print("INITIAL TRADING ACTIVITY")
    print("-" * 80)

    print(
        f"{'Metric':<24}"
        f"{'Winner Avg':>16}"
        f"{'Winner Med':>16}"
        f"{'Loser Avg':>16}"
        f"{'Loser Med':>16}"
    )

    print(
        f"{'Buy/Sell Ratio':<24}"
        f"{average(winner_ratios) or 0:>16.2f}"
        f"{median(winner_ratios) or 0:>16.2f}"
        f"{average(loser_ratios) or 0:>16.2f}"
        f"{median(loser_ratios) or 0:>16.2f}"
    )

    print(
        f"{'Total Trades (5m)':<24}"
        f"{average(winner_trades) or 0:>16.2f}"
        f"{median(winner_trades) or 0:>16.2f}"
        f"{average(loser_trades) or 0:>16.2f}"
        f"{median(loser_trades) or 0:>16.2f}"
    )

    print()


def get_latency(
    outcome: SignalOutcome,
) -> float | None:
    signal = outcome.signal

    if (
        signal.message_created_at is None
        or signal.received_at is None
    ):
        return None

    latency = (
        signal.received_at
        - signal.message_created_at
    ).total_seconds()

    if latency < 0:
        return None

    return latency


def print_latency_comparison(
    winners: list[SignalOutcome],
    losers: list[SignalOutcome],
) -> None:
    winner_latencies = [
        latency
        for outcome in winners
        if (
            latency := get_latency(outcome)
        ) is not None
    ]

    loser_latencies = [
        latency
        for outcome in losers
        if (
            latency := get_latency(outcome)
        ) is not None
    ]

    print("-" * 80)
    print("TELEGRAM LATENCY")
    print("-" * 80)

    print(
        f"{'Group':<24}"
        f"{'Samples':>10}"
        f"{'Average':>16}"
        f"{'Median':>16}"
    )

    print(
        f"{'Winners':<24}"
        f"{len(winner_latencies):>10}"
        f"{average(winner_latencies) or 0:>16.2f}s"
        f"{median(winner_latencies) or 0:>16.2f}s"
    )

    print(
        f"{'Losers':<24}"
        f"{len(loser_latencies):>10}"
        f"{average(loser_latencies) or 0:>16.2f}s"
        f"{median(loser_latencies) or 0:>16.2f}s"
    )

    print()


def print_individual_outcomes(
    outcomes: list[SignalOutcome],
) -> None:
    print("-" * 80)
    print("INDIVIDUAL OUTCOMES")
    print("-" * 80)

    sorted_outcomes = sorted(
        outcomes,
        key=lambda outcome: outcome.return_pct,
        reverse=True,
    )

    for outcome in sorted_outcomes:
        signal = outcome.signal

        ratio = get_buy_sell_ratio(signal)

        print(
            f"Signal #{signal.id:<4} "
            f"{classify_outcome(outcome.return_pct):<7} "
            f"return={outcome.return_pct:+8.2f}% "
            f"liq=${signal.liquidity_usd or 0:,.0f} "
            f"vol5m=${signal.volume_5m or 0:,.0f} "
            f"buys={signal.buys_5m or 0} "
            f"sells={signal.sells_5m or 0} "
            f"ratio={ratio if ratio is not None else 'n/a'}"
        )

    print()


async def main() -> None:
    signals, observations = await load_data()

    outcomes = build_outcomes(
        signals,
        observations,
    )

    print_outcome_summary(outcomes)

    winners = [
        outcome
        for outcome in outcomes
        if classify_outcome(outcome.return_pct) == "winner"
    ]

    losers = [
        outcome
        for outcome in outcomes
        if classify_outcome(outcome.return_pct) == "loser"
    ]

    print_feature_comparison(
        winners,
        losers,
    )

    print_trading_activity_comparison(
        winners,
        losers,
    )

    print_latency_comparison(
        winners,
        losers,
    )

    print_individual_outcomes(outcomes)

    print("=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
