import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)


# 1. Update models.py
with open("app/database/models.py", "r") as f:
    content = f.read()

content = content.replace(
    "    dex_id: Mapped[str | None] = mapped_column(\n        String(64),\n    )",
    "    dex_id: Mapped[str | None] = mapped_column(\n        String(64),\n    )\n\n    observation_status: Mapped[str] = mapped_column(\n        String(32),\n        index=True,\n        default=\"success\",\n    )"
)
with open("app/database/models.py", "w") as f:
    f.write(content)


# 2. Update observation_repository.py
content = """from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketObservation, Signal
from app.market.models import MarketSnapshot


async def save_market_observation(
    session: AsyncSession,
    *,
    signal: Signal,
    snapshot: MarketSnapshot | None,
    target_seconds: int,
    observation_status: str,
) -> MarketObservation:
    observed_at = datetime.now(timezone.utc)

    anchor = signal.received_at or signal.message_created_at

    seconds_since_signal = max(
        0,
        int((observed_at - anchor).total_seconds()),
    )

    observation = MarketObservation(
        signal_id=signal.id,
        token_address=signal.token_address,

        pair_address=(
            snapshot.pair_address
            if snapshot is not None
            else None
        ),
        dex_id=(
            snapshot.dex_id
            if snapshot is not None
            else None
        ),

        observed_at=observed_at,

        target_seconds=target_seconds,
        seconds_since_signal=seconds_since_signal,

        observation_status=observation_status,

        price_usd=(
            snapshot.price_usd
            if snapshot is not None
            else None
        ),
        liquidity_usd=(
            snapshot.liquidity_usd
            if snapshot is not None
            else None
        ),
        volume_5m=(
            snapshot.volume_5m
            if snapshot is not None
            else None
        ),
        buys_5m=(
            snapshot.buys_5m
            if snapshot is not None
            else None
        ),
        sells_5m=(
            snapshot.sells_5m
            if snapshot is not None
            else None
        ),
        price_change_5m=(
            snapshot.price_change_5m
            if snapshot is not None
            else None
        ),
    )

    session.add(observation)

    await session.commit()
    await session.refresh(observation)

    return observation
"""
with open("app/database/observation_repository.py", "w") as f:
    f.write(content)


# 3. Update dexscreener.py
with open("app/market/dexscreener.py", "r") as f:
    content = f.read()

import_old = "import httpx"
import_new = "import asyncio\nimport logging\nimport httpx\n\nlogger = logging.getLogger(\"meco.market.dexscreener\")"
content = content.replace(import_old, import_new)

func_old = """async def get_token_pairs(token_address: str) -> list[MarketPair]:
    url = f"{DEXSCREENER_BASE_URL}/token-pairs/v1/solana/{token_address}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    pairs = data.get("pairs") if isinstance(data, dict) else data

    if not pairs:
        return []

    results: list[MarketPair] = []

    for pair in pairs:
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        price_native = pair.get("priceNative")
        price_usd = pair.get("priceUsd")
        liquidity = pair.get("liquidity") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        price_change = pair.get("priceChange") or {}
        m5_txns = txns.get("m5") or {}

        results.append(
            MarketPair(
                pair_address=pair.get("pairAddress", ""),
                dex_id=pair.get("dexId", ""),
                url=pair.get("url", ""),
                base_token_address=base_token.get("address", ""),
                base_token_name=base_token.get("name", ""),
                base_token_symbol=base_token.get("symbol", ""),
                quote_token_address=quote_token.get("address"),
                quote_token_name=quote_token.get("name"),
                quote_token_symbol=quote_token.get("symbol"),
                price_native=(
                    float(price_native)
                    if price_native is not None
                    else None
                ),
                price_usd=(
                    float(price_usd)
                    if price_usd is not None
                    else None
                ),
                liquidity_usd=liquidity.get("usd"),
                volume_m5=volume.get("m5", 0.0),
                volume_h1=volume.get("h1", 0.0),
                volume_h6=volume.get("h6", 0.0),
                volume_h24=volume.get("h24", 0.0),
                buys_m5=m5_txns.get("buys", 0),
                sells_m5=m5_txns.get("sells", 0),
                price_change_m5=price_change.get("m5"),
                price_change_h1=price_change.get("h1"),
                price_change_h6=price_change.get("h6"),
                price_change_h24=price_change.get("h24"),
                market_cap=pair.get("marketCap"),
                fdv=pair.get("fdv"),
                pair_created_at=pair.get("pairCreatedAt"),
            )
        )

    return results"""

func_new = """async def get_token_pairs(
    token_address: str,
    *,
    retries: int = 2,
) -> list[MarketPair]:
    url = (
        f"{DEXSCREENER_BASE_URL}"
        f"/token-pairs/v1/solana/{token_address}"
    )

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            pairs = data.get("pairs") if isinstance(data, dict) else data

            if not pairs:
                return []

            results: list[MarketPair] = []

            for pair in pairs:
                base_token = pair.get("baseToken", {})
                quote_token = pair.get("quoteToken", {})
                price_native = pair.get("priceNative")
                price_usd = pair.get("priceUsd")
                liquidity = pair.get("liquidity") or {}
                volume = pair.get("volume") or {}
                txns = pair.get("txns") or {}
                price_change = pair.get("priceChange") or {}
                m5_txns = txns.get("m5") or {}

                results.append(
                    MarketPair(
                        pair_address=pair.get("pairAddress", ""),
                        dex_id=pair.get("dexId", ""),
                        url=pair.get("url", ""),
                        base_token_address=base_token.get("address", ""),
                        base_token_name=base_token.get("name", ""),
                        base_token_symbol=base_token.get("symbol", ""),
                        quote_token_address=quote_token.get("address"),
                        quote_token_name=quote_token.get("name"),
                        quote_token_symbol=quote_token.get("symbol"),
                        price_native=(
                            float(price_native)
                            if price_native is not None
                            else None
                        ),
                        price_usd=(
                            float(price_usd)
                            if price_usd is not None
                            else None
                        ),
                        liquidity_usd=liquidity.get("usd"),
                        volume_m5=volume.get("m5", 0.0),
                        volume_h1=volume.get("h1", 0.0),
                        volume_h6=volume.get("h6", 0.0),
                        volume_h24=volume.get("h24", 0.0),
                        buys_m5=m5_txns.get("buys", 0),
                        sells_m5=m5_txns.get("sells", 0),
                        price_change_m5=price_change.get("m5"),
                        price_change_h1=price_change.get("h1"),
                        price_change_h6=price_change.get("h6"),
                        price_change_h24=price_change.get("h24"),
                        market_cap=pair.get("marketCap"),
                        fdv=pair.get("fdv"),
                        pair_created_at=pair.get("pairCreatedAt"),
                    )
                )

            return results

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt >= retries:
                raise

            delay = 1.0 * (2 ** attempt)

            logger.warning(
                "DEXSCREENER RETRY | mint=%s | attempt=%s/%s | "
                "error=%s | retry_in=%.1fs",
                token_address,
                attempt + 1,
                retries,
                type(exc).__name__,
                delay,
            )

            await asyncio.sleep(delay)"""

content = content.replace(func_old, func_new)
with open("app/market/dexscreener.py", "w") as f:
    f.write(content)


# 4. Update observer.py
with open("app/market/observer.py", "r") as f:
    content = f.read()

obs_old = """async def capture_observation(signal: Signal, target_seconds: int) -> None:
    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "NO MARKET DATA | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "NO LIQUID PAIR | signal_id=%s | mint=%s",
            signal.id,
            signal.token_address,
        )
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        observation = await save_market_observation(
            session,
            signal=signal,
            snapshot=snapshot,
            target_seconds=target_seconds,
        )

    logger.info(
        "📈 OBSERVATION | signal_id=%s | target=%ss | actual=%ss | "
        "price=$%s | liquidity=$%s | dex=%s | pair=%s",
        observation.signal_id,
        observation.target_seconds,
        observation.seconds_since_signal,
        observation.price_usd,
        observation.liquidity_usd,
        observation.dex_id,
        observation.pair_address,
    )"""

obs_new = """async def capture_observation(
    signal: Signal,
    target_seconds: int,
) -> None:
    try:
        pairs = await get_token_pairs(signal.token_address)
    except Exception:
        logger.exception(
            "MARKET FETCH FAILED | signal_id=%s | target=%ss",
            signal.id,
            target_seconds,
        )

        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="fetch_failed",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=fetch_failed | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
        )

        return

    if not pairs:
        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="no_market_data",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=no_market_data | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
        )

        return

    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        async with SessionLocal() as session:
            observation = await save_market_observation(
                session,
                signal=signal,
                snapshot=None,
                target_seconds=target_seconds,
                observation_status="no_liquid_pair",
            )

        logger.warning(
            "⚠️ OBSERVATION | signal_id=%s | target=%ss | "
            "status=no_liquid_pair | actual=%ss",
            signal.id,
            target_seconds,
            observation.seconds_since_signal,
        )

        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    async with SessionLocal() as session:
        observation = await save_market_observation(
            session,
            signal=signal,
            snapshot=snapshot,
            target_seconds=target_seconds,
            observation_status="success",
        )

    logger.info(
        "📈 OBSERVATION | signal_id=%s | target=%ss | actual=%ss | "
        "status=%s | price=$%s | liquidity=$%s | dex=%s | pair=%s",
        observation.signal_id,
        observation.target_seconds,
        observation.seconds_since_signal,
        observation.observation_status,
        observation.price_usd,
        observation.liquidity_usd,
        observation.dex_id,
        observation.pair_address,
    )"""

content = content.replace(obs_old, obs_new)
with open("app/market/observer.py", "w") as f:
    f.write(content)

run_cmd("Add observation status and Dexscreener fallback retries")

