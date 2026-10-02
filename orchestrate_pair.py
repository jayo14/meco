import subprocess

def run_cmd(msg):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

# 1. Update models.py
with open("app/database/models.py", "r") as f:
    content = f.read()

old_fields = """    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    observed_at: Mapped[datetime] = mapped_column("""

new_fields = """    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    pair_address: Mapped[str | None] = mapped_column(
        String(128),
    )

    dex_id: Mapped[str | None] = mapped_column(
        String(64),
    )

    observed_at: Mapped[datetime] = mapped_column("""

content = content.replace(old_fields, new_fields)
with open("app/database/models.py", "w") as f:
    f.write(content)

# 2. Update observation_repository.py
with open("app/database/observation_repository.py", "r") as f:
    repo = f.read()

repo_old = """    observation = MarketObservation(
        signal_id=signal.id,
        token_address=signal.token_address,
        observed_at=observed_at,
        target_seconds=target_seconds,
        seconds_since_signal=seconds_since_signal,"""

repo_new = """    observation = MarketObservation(
        signal_id=signal.id,
        token_address=signal.token_address,

        pair_address=snapshot.pair_address,
        dex_id=snapshot.dex_id,

        observed_at=observed_at,

        target_seconds=target_seconds,
        seconds_since_signal=seconds_since_signal,"""

repo = repo.replace(repo_old, repo_new)
with open("app/database/observation_repository.py", "w") as f:
    f.write(repo)

# 3. Update observer.py
with open("app/market/observer.py", "r") as f:
    observer = f.read()

obs_old = """    logger.info(
        "📈 OBSERVATION | signal_id=%s | target=%ss | actual=%ss | "
        "price=$%s | liquidity=$%s",
        signal.id,
        observation.target_seconds,
        observation.seconds_since_signal,
        observation.price_usd,
        observation.liquidity_usd,
    )"""

obs_new = """    logger.info(
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

observer = observer.replace(obs_old, obs_new)
with open("app/market/observer.py", "w") as f:
    f.write(observer)

run_cmd("Add pair and dex to MarketObservation schema")

