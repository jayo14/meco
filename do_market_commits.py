import subprocess

def run_cmd(msg):
    subprocess.run(["git", "commit", "-a", "-m", msg], check=True)

with open("app/telegram/client.py", "r") as f:
    content = f.read()

# 1. Imports
imports_target = """from app.config.settings import get_settings
from app.solana.validator import get_mint_info"""
imports_replacement = """from app.config.settings import get_settings
from app.market.dexscreener import get_token_pairs
from app.market.snapshot import create_market_snapshot, select_primary_pair
from app.solana.validator import get_mint_info"""
content = content.replace(imports_target, imports_replacement)
with open("app/telegram/client.py", "w") as f: f.write(content)
run_cmd("Import market module dependencies")

# 2. Pairs logic
pairs_logic = """
    pairs = await get_token_pairs(signal.token_address)

    if not pairs:
        logger.warning(
            "⚠️ NO MARKET DATA | mint=%s",
            signal.token_address,
        )
        return
"""
target_after_validation = """        signal.detected_at,
    )
"""
content = content.replace(target_after_validation, target_after_validation + pairs_logic)
with open("app/telegram/client.py", "w") as f: f.write(content)
run_cmd("Fetch token pairs and handle no market data")

# 3. Snapshot logic
snapshot_logic = """
    primary_pair = select_primary_pair(pairs)

    if primary_pair is None:
        logger.warning(
            "⚠️ NO LIQUID MARKET PAIR | mint=%s",
            signal.token_address,
        )
        return

    snapshot = create_market_snapshot(
        signal.token_address,
        primary_pair,
    )

    logger.info(
        "📊 MARKET SNAPSHOT | price=$%s | liquidity=$%s | "
        "5m_volume=$%s | buys=%s | sells=%s | dex=%s",
        snapshot.price_usd,
        snapshot.liquidity_usd,
        snapshot.volume_5m,
        snapshot.buys_5m,
        snapshot.sells_5m,
        snapshot.dex_id,
    )
"""
target_after_pairs = """        logger.warning(
            "⚠️ NO MARKET DATA | mint=%s",
            signal.token_address,
        )
        return
"""
content = content.replace(target_after_pairs, target_after_pairs + snapshot_logic)
with open("app/telegram/client.py", "w") as f: f.write(content)
run_cmd("Select primary pair and log market snapshot")
