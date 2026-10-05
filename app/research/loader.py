from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketObservation, MarketPairObservation, Signal
from app.database.session import SessionLocal


async def load_all_signals(session: AsyncSession | None = None) -> list[Signal]:
    """
    Safely load all signals ordered chronologically by ID.
    Never modifies database records.
    """
    if session is not None:
        result = await session.execute(select(Signal).order_by(Signal.id.asc()))
        return list(result.scalars().all())

    async with SessionLocal() as s:
        result = await s.execute(select(Signal).order_by(Signal.id.asc()))
        return list(result.scalars().all())


async def load_all_observations(
    session: AsyncSession | None = None,
) -> list[MarketObservation]:
    """
    Safely load all market observations ordered by signal_id and target_seconds.
    """
    if session is not None:
        result = await session.execute(
            select(MarketObservation).order_by(
                MarketObservation.signal_id.asc(),
                MarketObservation.target_seconds.asc(),
                MarketObservation.seconds_since_signal.asc(),
            )
        )
        return list(result.scalars().all())

    async with SessionLocal() as s:
        result = await s.execute(
            select(MarketObservation).order_by(
                MarketObservation.signal_id.asc(),
                MarketObservation.target_seconds.asc(),
                MarketObservation.seconds_since_signal.asc(),
            )
        )
        return list(result.scalars().all())


async def load_all_pair_observations(
    session: AsyncSession | None = None,
) -> list[MarketPairObservation]:
    """
    Safely load all pair-level market observations.
    """
    if session is not None:
        result = await session.execute(
            select(MarketPairObservation).order_by(
                MarketPairObservation.signal_id.asc(),
                MarketPairObservation.target_seconds.asc(),
            )
        )
        return list(result.scalars().all())

    async with SessionLocal() as s:
        result = await s.execute(
            select(MarketPairObservation).order_by(
                MarketPairObservation.signal_id.asc(),
                MarketPairObservation.target_seconds.asc(),
            )
        )
        return list(result.scalars().all())


def group_observations_by_signal(
    observations: list[MarketObservation],
) -> dict[int, list[MarketObservation]]:
    """Group observations by signal_id preserving order."""
    grouped: dict[int, list[MarketObservation]] = {}
    for obs in observations:
        grouped.setdefault(obs.signal_id, []).append(obs)
    return grouped


def group_pairs_by_signal(
    pairs: list[MarketPairObservation],
) -> dict[int, list[MarketPairObservation]]:
    """Group pair observations by signal_id."""
    grouped: dict[int, list[MarketPairObservation]] = {}
    for p in pairs:
        grouped.setdefault(p.signal_id, []).append(p)
    return grouped
