"""Runner script for Meco social intelligence subsystem."""
import asyncio
import logging
import signal

from app.config.settings import get_settings
from app.database.session import SessionLocal
from app.social.correlation import SocialMarketCorrelator
from app.social.ingestion import SocialIngestionService
from app.social.matcher import TokenSocialMatcher
from app.social.narratives import NarrativeEngine
from app.social.rss_adapter import RSSSocialAdapter
from app.social.x_adapter import XSocialAdapter

logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("meco.social.runner")


async def main() -> None:
    settings = get_settings()
    logger.info("Starting Meco Social Intelligence Subsystem...")

    ingestion_service = SocialIngestionService(SessionLocal)
    matcher = TokenSocialMatcher(SessionLocal)
    narrative_engine = NarrativeEngine(SessionLocal)
    correlator = SocialMarketCorrelator(SessionLocal)

    # 1. Initialize baseline narratives
    async with SessionLocal() as session, session.begin():
        await narrative_engine.initialize_baseline_narratives(session)

    # 2. Setup adapters
    adapters = []
    if settings.enable_rss_social:
        feeds = [f.strip() for f in settings.rss_feeds.split(",") if f.strip()]
        rss_adapter = RSSSocialAdapter(feed_urls=feeds)
        adapters.append(rss_adapter)

    if settings.enable_x_social and settings.x_api_bearer_token:
        x_adapter = XSocialAdapter(bearer_token=settings.x_api_bearer_token)
        adapters.append(x_adapter)

    running = True

    def stop_signal():
        nonlocal running
        logger.info("Received stop signal, shutting down social subsystem...")
        running = False

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_signal)
        except NotImplementedError:
            pass

    for a in adapters:
        await a.start(lambda post: None)

    logger.info("Social adapters active: %s", [a.source_name for a in adapters])

    try:
        while running:
            # Poll each adapter
            for a in adapters:
                if not running:
                    break
                try:
                    raw_posts = await a.poll_once()
                    if raw_posts:
                        logger.info("Polled %d posts from %s", len(raw_posts), a.source_name)
                        async with SessionLocal() as session, session.begin():
                            for p in raw_posts:
                                db_post = await ingestion_service.ingest_post(session, p)
                                if db_post:
                                    token_matches = await matcher.associate_post(session, db_post)
                                    _narr_matches = await narrative_engine.associate_post_narratives(session, db_post)
                                    # For each matched token, evaluate market correlations
                                    for tm in token_matches:
                                        findings = await correlator.evaluate_token_social_correlations(
                                            session, tm.token_id
                                        )
                                        if findings:
                                            await correlator.save_findings(session, findings)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error in social polling loop for %s: %s", a.source_name, exc)

            await asyncio.sleep(settings.social_poll_interval)
    finally:
        for a in adapters:
            await a.stop()
        logger.info("Meco Social Intelligence Subsystem stopped.")


if __name__ == "__main__":
    asyncio.run(main())
