import asyncio
import logging

from sqlalchemy import select

from app.database.models import Signal
from app.database.session import SessionLocal
from app.market.observer import observe_signal


logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)


async def main() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Signal)
            .order_by(Signal.id.desc())
            .limit(1)
        )

        signal = result.scalar_one_or_none()

    if signal is None:
        print("No signal found.")
        return

    print(
        f"Observing signal #{signal.id} "
        f"for {signal.token_address}"
    )

    await observe_signal(signal)


if __name__ == "__main__":
    asyncio.run(main())
