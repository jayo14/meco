import subprocess
import os

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Fix the strict Telegram filter
with open("app/telegram/client.py", "r") as f:
    client_content = f.read()

old_filter = """    if (
        settings.telegram_channel_ids
        and event.chat_id not in settings.telegram_channel_ids
    ):"""
new_filter = """    if event.chat_id not in settings.telegram_channel_ids:"""
client_content = client_content.replace(old_filter, new_filter)

with open("app/telegram/client.py", "w") as f:
    f.write(client_content)
run_cmd("Make Telegram channel filtering strictly allowlist only")


# 2. Add target_seconds to models.py
with open("app/database/models.py", "r") as f:
    models_content = f.read()

models_content = models_content.replace(
    '"seconds_since_signal",\n            name="uq_market_observation_signal_time",',
    '"target_seconds",\n            name="uq_market_observation_signal_target",'
)

models_content = models_content.replace(
    "    seconds_since_signal: Mapped[int] = mapped_column(Integer)",
    "    target_seconds: Mapped[int] = mapped_column(Integer)\n\n    seconds_since_signal: Mapped[int] = mapped_column(Integer)"
)
with open("app/database/models.py", "w") as f:
    f.write(models_content)


# 3. Update observation_repository.py
with open("app/database/observation_repository.py", "r") as f:
    repo_content = f.read()

repo_content = repo_content.replace(
    "snapshot: MarketSnapshot,\n) -> MarketObservation:",
    "snapshot: MarketSnapshot,\n    target_seconds: int,\n) -> MarketObservation:"
)
repo_content = repo_content.replace(
    "observed_at=observed_at,\n        seconds_since_signal=seconds_since_signal,",
    "observed_at=observed_at,\n        target_seconds=target_seconds,\n        seconds_since_signal=seconds_since_signal,"
)
with open("app/database/observation_repository.py", "w") as f:
    f.write(repo_content)


# 4. Update observer.py
with open("app/market/observer.py", "r") as f:
    observer_content = f.read()

observer_content = observer_content.replace(
    "async def capture_observation(signal: Signal) -> None:",
    "async def capture_observation(signal: Signal, target_seconds: int) -> None:"
)
observer_content = observer_content.replace(
    "snapshot=snapshot,\n        )",
    "snapshot=snapshot,\n            target_seconds=target_seconds,\n        )"
)
old_log = """    logger.info(
        "📈 OBSERVATION | signal_id=%s | elapsed=%ss | "
        "price=$%s | liquidity=$%s",
        signal.id,
        observation.seconds_since_signal,"""
new_log = """    logger.info(
        "📈 OBSERVATION | signal_id=%s | target=%ss | actual=%ss | "
        "price=$%s | liquidity=$%s",
        signal.id,
        observation.target_seconds,
        observation.seconds_since_signal,"""
observer_content = observer_content.replace(old_log, new_log)

observer_content = observer_content.replace(
    "        await capture_observation(signal)",
    "        await capture_observation(signal, target_seconds)"
)

with open("app/market/observer.py", "w") as f:
    f.write(observer_content)

run_cmd("Add target_seconds to observation schema and repository")

