import asyncio
import logging
import signal
import sys
from typing import Any

from app.config.settings import get_settings
from app.discovery.engine import DiscoveryEngine
from app.discovery.models import NormalizedDiscoveryEvent
from app.discovery.pumpportal import PumpPortalDiscoveryAdapter
from app.discovery.solana_rpc import SolanaRpcDiscoveryAdapter

logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("meco.discovery.runner")


async def on_token_discovered(token: Any, event: NormalizedDiscoveryEvent, is_new: bool) -> None:
    status_label = "🌟 NEW CANONICAL TOKEN" if is_new else "🔁 DUP DISCOVERY"
    logger.info(
        "%s | mint=%s | source=%s | name=%s | symbol=%s | sig=%s",
        status_label,
        event.mint_address,
        event.source,
        event.name or token.name,
        event.symbol or token.symbol,
        event.signature or "n/a",
    )


async def main() -> None:
    settings = get_settings()
    logger.info("Initializing Meco Independent Token Discovery Subsystem...")

    engine = DiscoveryEngine()

    if settings.enable_pumpportal_discovery:
        pumpportal_adapter = PumpPortalDiscoveryAdapter(
            ws_url=settings.pumpportal_ws_url,
            heartbeat_interval=settings.discovery_ws_heartbeat_interval,
            reconnect_min_delay=settings.discovery_reconnect_min_delay,
            reconnect_max_delay=settings.discovery_reconnect_max_delay,
        )
        engine.register_adapter(pumpportal_adapter)

    if settings.enable_solana_rpc_discovery:
        solana_rpc_adapter = SolanaRpcDiscoveryAdapter(
            ws_url=settings.resolved_solana_ws_url,
            rpc_http_url=settings.solana_rpc_url,
            commitment="confirmed",
            heartbeat_interval=settings.discovery_ws_heartbeat_interval,
            reconnect_min_delay=settings.discovery_reconnect_min_delay,
            reconnect_max_delay=settings.discovery_reconnect_max_delay,
        )
        engine.register_adapter(solana_rpc_adapter)

    engine.subscribe_token_discovered(on_token_discovered)

    await engine.start()
    logger.info("Discovery engine active. Press Ctrl+C to terminate.")

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        while not stop_event.is_set():
            await asyncio.sleep(60.0)
            # Periodic health summary log
            healths = engine.get_all_health()
            for name, h in healths.items():
                logger.info(
                    "STREAM HEALTH | source=%s | status=%s | events_in=%s | valid=%s | new_tokens=%s | dups=%s | proc_latency=%.2fms",
                    name,
                    h.status.value,
                    h.events_received,
                    h.valid_events,
                    h.new_tokens_count,
                    h.duplicate_events,
                    h.last_processing_latency_ms or 0.0,
                )
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down discovery engine...")
        await engine.stop()
        logger.info("Discovery engine shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
