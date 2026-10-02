import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

with open("app/market/observer.py", "r") as f:
    content = f.read()

# Add import
import_old = "from app.database.observation_repository import save_market_observation"
import_new = """from app.database.observation_repository import save_market_observation
from app.database.pair_observation_repository import (
    save_market_pair_observations,
)"""
if "save_market_pair_observations" not in content:
    content = content.replace(import_old, import_new)

# Add pair capture
target_old = """    if not pairs:
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

    primary_pair = select_primary_pair(pairs)"""

target_new = """    if not pairs:
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

    async with SessionLocal() as session:
        pair_observations = await save_market_pair_observations(
            session,
            signal=signal,
            pairs=pairs,
            target_seconds=target_seconds,
        )

    logger.info(
        "🔎 PAIRS CAPTURED | signal_id=%s | target=%ss | pairs=%s",
        signal.id,
        target_seconds,
        len(pair_observations),
    )

    primary_pair = select_primary_pair(pairs)"""

content = content.replace(target_old, target_new)

with open("app/market/observer.py", "w") as f:
    f.write(content)

run_cmd("Wire raw pairs repository into observer flow correctly")

