"""
Unified Application Runner & Daemon Supervisor for Meco (Phase 9).
Provides a resilient, single-process or multi-subsystem daemon entrypoint for Ubuntu systemd.
Coordinates:
- Database connection verification & auto-reconnect.
- Pending observation task recovery.
- Token discovery and enrichment orchestrator.
- FastAPI Dashboard & Control Centre server.
- Graceful shutdown on SIGTERM / SIGINT with task draining.
"""
import asyncio
import logging
import signal
import sys
from typing import Any

import uvicorn

from app.config.settings import get_settings
from app.database.session import SessionLocal
from app.discovery.engine import DiscoveryEngine
from app.discovery.models import NormalizedDiscoveryEvent
from app.discovery.pumpportal import PumpPortalDiscoveryAdapter
from app.discovery.solana_rpc import SolanaRpcDiscoveryAdapter
from app.intelligence.orchestrator import TokenIntelligenceOrchestrator
from app.market.observer import recover_pending_observations
from app.security.redaction import setup_secure_logging

logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)
setup_secure_logging()
logger = logging.getLogger("meco.runner")


async def run_supervisor(
    run_discovery: bool = True,
    run_api: bool = True,
) -> None:
    """Supervised runner for Meco production daemon."""
    settings = get_settings()
    logger.info("Initializing Meco Production Platform Daemon (Phase 9 Hardened)...")

    # 1. Recover any unrecorded observation checkpoints from prior restart
    try:
        recovered = await recover_pending_observations(SessionLocal, lookback_hours=25)
        if recovered > 0:
            logger.info("Durable checkpoint recovery: %d unrecorded observations resumed/cataloged.", recovered)
    except Exception as e:
        logger.warning("Checkpoint recovery warning: %s", e)

    discovery_engine: DiscoveryEngine | None = None
    orchestrator: TokenIntelligenceOrchestrator | None = None
    server_task: asyncio.Task | None = None
    api_server: uvicorn.Server | None = None

    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Termination signal received (SIGINT/SIGTERM). Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    # 2. Start Discovery & Enrichment if enabled
    if run_discovery:
        discovery_engine = DiscoveryEngine()
        orchestrator = TokenIntelligenceOrchestrator(SessionLocal)

        async def on_token_discovered(token: Any, event: NormalizedDiscoveryEvent, is_new: bool) -> None:
            if is_new and orchestrator:
                try:
                    await orchestrator.schedule_initial_enrichment(token.id, token.mint_address)
                except Exception as err:
                    logger.warning("Failed scheduling initial enrichment for %s: %s", token.mint_address, err)

        if settings.enable_pumpportal_discovery:
            pumpportal_adapter = PumpPortalDiscoveryAdapter(
                ws_url=settings.pumpportal_ws_url,
                heartbeat_interval=settings.discovery_ws_heartbeat_interval,
                reconnect_min_delay=settings.discovery_reconnect_min_delay,
                reconnect_max_delay=settings.discovery_reconnect_max_delay,
            )
            discovery_engine.register_adapter(pumpportal_adapter)

        if settings.enable_solana_rpc_discovery:
            solana_rpc_adapter = SolanaRpcDiscoveryAdapter(
                ws_url=settings.resolved_solana_ws_url,
                rpc_http_url=settings.solana_rpc_url,
                commitment="confirmed",
                heartbeat_interval=settings.discovery_ws_heartbeat_interval,
                reconnect_min_delay=settings.discovery_reconnect_min_delay,
                reconnect_max_delay=settings.discovery_reconnect_max_delay,
            )
            discovery_engine.register_adapter(solana_rpc_adapter)

        discovery_engine.subscribe_token_discovered(on_token_discovered)
        await discovery_engine.start()
        await orchestrator.start()
        logger.info("Discovery and Enrichment engines operational.")

    # 3. Start FastAPI Dashboard Server if enabled
    if run_api:
        config = uvicorn.Config(
            "app.api.app:app",
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.log_level.lower(),
            access_log=True,
        )
        api_server = uvicorn.Server(config)
        server_task = asyncio.create_task(api_server.serve())
        logger.info("API & Control Centre server listening on http://%s:%d", settings.api_host, settings.api_port)

    # 4. Main supervision loop
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1.0)
            if server_task and server_task.done():
                logger.warning("API Server task completed unexpectedly. Triggering shutdown.")
                break
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Beginning graceful shutdown sequence...")
        if api_server:
            api_server.should_exit = True
            if server_task:
                await server_task
            logger.info("API server stopped.")

        if discovery_engine:
            await discovery_engine.stop()
            logger.info("Discovery engine stopped.")

        if orchestrator:
            await orchestrator.stop()
            logger.info("Intelligence orchestrator stopped.")

        logger.info("All Meco subsystems gracefully shut down.")


def main():
    """Command-line entrypoint for systemd or local execution."""
    run_discovery = "--no-discovery" not in sys.argv
    run_api = "--no-api" not in sys.argv
    try:
        asyncio.run(run_supervisor(run_discovery=run_discovery, run_api=run_api))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
