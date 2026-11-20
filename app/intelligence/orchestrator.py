import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from solana.rpc.async_api import AsyncClient
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.models import EnrichmentTask, Token
from app.database.session import SessionLocal
from app.intelligence.holders import capture_token_holder_snapshot
from app.intelligence.lifecycle import TokenLifecycleState, transition_lifecycle
from app.intelligence.liquidity import capture_token_liquidity_snapshot
from app.intelligence.metadata import enrich_token_metadata
from app.intelligence.security import audit_token_security

logger = logging.getLogger("meco.intelligence.orchestrator")


class EnrichmentTaskQueue:
    """
    Durable, database-backed task queue for token intelligence enrichment.
    Provides task deduplication, atomic worker leasing, timeout recovery,
    exponential retry backoff, and restart resilience.
    """

    def __init__(
        self,
        session_factory=SessionLocal,
        *,
        lease_duration_seconds: int = 120,
    ) -> None:
        self.session_factory = session_factory
        self.lease_duration_seconds = lease_duration_seconds

    async def schedule_task(
        self,
        session: AsyncSession,
        *,
        token_id: int,
        mint_address: str,
        task_type: str,
        scheduled_at: datetime | None = None,
        priority: int = 10,
        payload: dict[str, Any] | None = None,
    ) -> EnrichmentTask:
        """
        Idempotently schedule an enrichment task.
        If a task of the same type is already pending or running for this token,
        it deduplicates and avoids creating redundant backlog.
        """
        now = datetime.now(timezone.utc)
        target_time = scheduled_at or now

        # Deduplication check: existing pending or running task
        stmt = select(EnrichmentTask).where(
            EnrichmentTask.token_id == token_id,
            EnrichmentTask.task_type == task_type,
            EnrichmentTask.status.in_(["pending", "running"]),
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            # If new task is scheduled earlier than existing, pull forward
            if target_time < existing.scheduled_at:
                existing.scheduled_at = target_time
                existing.updated_at = now
            return existing

        task = EnrichmentTask(
            token_id=token_id,
            mint_address=mint_address,
            task_type=task_type,
            status="pending",
            priority=priority,
            scheduled_at=target_time,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.flush()
        await session.refresh(task)
        return task

    async def acquire_next_task(
        self,
        session: AsyncSession,
        worker_id: str,
    ) -> EnrichmentTask | None:
        """
        Atomically lease the highest-priority pending task or recover expired running tasks.
        """
        now = datetime.now(timezone.utc)
        lease_expires = now + timedelta(seconds=self.lease_duration_seconds)

        # Select tasks that are either pending and ready, or running with expired lock
        stmt = (
            select(EnrichmentTask)
            .where(
                or_(
                    EnrichmentTask.status == "pending",
                    (EnrichmentTask.status == "running") & (EnrichmentTask.lock_expires_at < now),
                ),
                EnrichmentTask.scheduled_at <= now,
            )
            .order_by(EnrichmentTask.priority.desc(), EnrichmentTask.scheduled_at.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            return None

        task.status = "running"
        task.lock_token = worker_id
        task.lock_expires_at = lease_expires
        task.started_at = now
        task.updated_at = now

        await session.flush()
        await session.refresh(task)
        return task

    async def complete_task(
        self,
        session: AsyncSession,
        task_id: int,
    ) -> None:
        """Mark task as successfully completed."""
        task = await session.get(EnrichmentTask, task_id)
        if task is not None:
            now = datetime.now(timezone.utc)
            task.status = "completed"
            task.completed_at = now
            task.lock_token = None
            task.lock_expires_at = None
            task.updated_at = now
            await session.flush()

    async def fail_task(
        self,
        session: AsyncSession,
        task_id: int,
        error_message: str,
    ) -> None:
        """Handle task failure with retry backoff or terminal failure."""
        task = await session.get(EnrichmentTask, task_id)
        if task is None:
            return

        now = datetime.now(timezone.utc)
        task.retry_count += 1
        task.last_error = error_message
        task.lock_token = None
        task.lock_expires_at = None

        if task.retry_count >= task.max_retries:
            task.status = "failed"
            logger.error(
                "ENRICHMENT TASK TERMINALLY FAILED | task_id=%s | type=%s | mint=%s | retries=%s | error=%s",
                task.id,
                task.task_type,
                task.mint_address,
                task.retry_count,
                error_message,
            )
        else:
            task.status = "pending"
            # Exponential backoff: 10s * (2 ** retry_count)
            delay = 10 * (2 ** task.retry_count)
            task.scheduled_at = now + timedelta(seconds=delay)
            logger.warning(
                "ENRICHMENT TASK RETRY SCHEDULED | task_id=%s | retry=%s/%s | delay=%ss | error=%s",
                task.id,
                task.retry_count,
                task.max_retries,
                delay,
                error_message,
            )

        task.updated_at = now
        await session.flush()


class TokenIntelligenceOrchestrator:
    """
    Asynchronous durable orchestrator managing the token enrichment lifecycle.
    Operates within strict memory bounds via task concurrency semaphores.
    """

    def __init__(
        self,
        session_factory=SessionLocal,
        *,
        max_concurrency: int = 5,
        poll_interval: float = 2.0,
    ) -> None:
        self.session_factory = session_factory
        self.queue = EnrichmentTaskQueue(session_factory)
        self.max_concurrency = max_concurrency
        self.poll_interval = poll_interval
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self.worker_id = f"worker_{uuid.uuid4().hex[:8]}"

    async def schedule_initial_enrichment(
        self,
        token_id: int,
        mint_address: str,
        priority: int = 20,
    ) -> None:
        """Schedule initial comprehensive enrichment for a newly discovered token."""
        async with self.session_factory() as session, session.begin():
            await self.queue.schedule_task(
                session,
                token_id=token_id,
                mint_address=mint_address,
                task_type="initial_enrichment",
                priority=priority,
            )

    async def schedule_reenrichment(
        self,
        token_id: int,
        mint_address: str,
        delay_seconds: int,
        task_type: str = "refresh_enrichment",
    ) -> None:
        """Schedule a durable future re-enrichment checkpoint."""
        target_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        async with self.session_factory() as session, session.begin():
            await self.queue.schedule_task(
                session,
                token_id=token_id,
                mint_address=mint_address,
                task_type=task_type,
                scheduled_at=target_time,
                priority=10,
            )

    async def process_task(self, task: EnrichmentTask) -> None:
        """Execute single enrichment task through all modular intelligence components."""
        async with self._semaphore:
            logger.info(
                "EXECUTING ENRICHMENT TASK | id=%s | type=%s | mint=%s",
                task.id,
                task.task_type,
                task.mint_address,
            )
            settings = get_settings()

            try:
                async with self.session_factory() as session, session.begin():
                    token = await session.get(Token, task.token_id)
                    if token is None:
                        await self.queue.fail_task(session, task.id, "Token not found in database")
                        return

                    # 1. Metadata Enrichment
                    await enrich_token_metadata(session, token=token)

                    # 2. On-Chain Security Audit
                    async with AsyncClient(settings.solana_rpc_url) as rpc:
                        sec_prof = await audit_token_security(session, token=token, rpc_client=rpc)

                    # 3. Liquidity and Pool Intelligence
                    mkt_snap = await capture_token_liquidity_snapshot(session, token=token)

                    # 4. Holder and Wallet Intelligence
                    async with AsyncClient(settings.solana_rpc_url) as rpc:
                        await capture_token_holder_snapshot(session, token=token, rpc_client=rpc)

                    # 5. Evaluate and Transition Lifecycle State
                    if sec_prof and sec_prof.risk_score >= 70.0:
                        await transition_lifecycle(
                            session,
                            token=token,
                            to_state=TokenLifecycleState.SUSPICIOUS,
                            reason=f"High risk score ({sec_prof.risk_score}) in security audit",
                        )
                    elif mkt_snap.liquidity_usd and mkt_snap.liquidity_usd > 0.0:
                        is_active = (mkt_snap.volume_5m or 0.0) > 0.0 or (mkt_snap.buys_5m or 0) > 0
                        target_state = (
                            TokenLifecycleState.TRADING_ACTIVE
                            if is_active
                            else TokenLifecycleState.LIQUIDITY_DETECTED
                        )
                        await transition_lifecycle(
                            session,
                            token=token,
                            to_state=target_state,
                            reason=f"Liquid pool detected on {mkt_snap.primary_dex_id} (${mkt_snap.liquidity_usd:,.2f})",
                        )
                    else:
                        await transition_lifecycle(
                            session,
                            token=token,
                            to_state=TokenLifecycleState.POOL_NOT_FOUND,
                            reason="No liquid DEX pool found during snapshot",
                        )

                    token.last_enriched_at = datetime.now(timezone.utc)
                    await self.queue.complete_task(session, task.id)

                # 6. Schedule durable re-enrichment follow-ups (T+60s, T+5m)
                if task.task_type == "initial_enrichment":
                    await self.schedule_reenrichment(task.token_id, task.mint_address, delay_seconds=60)
                    await self.schedule_reenrichment(task.token_id, task.mint_address, delay_seconds=300)

            except Exception as exc:
                logger.exception("Error executing enrichment task #%s", task.id)
                async with self.session_factory() as session, session.begin():
                    await self.queue.fail_task(session, task.id, str(exc))

    async def _worker_loop(self) -> None:
        """Continuous background worker polling durable task queue."""
        logger.info("Enrichment orchestrator worker started (worker_id=%s)", self.worker_id)
        while self._running:
            try:
                task = None
                async with self.session_factory() as session, session.begin():
                    task = await self.queue.acquire_next_task(session, self.worker_id)

                if task is not None:
                    asyncio.create_task(self.process_task(task))
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error in orchestrator worker loop: %s", exc)
                await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        """Start the orchestrator background worker loop."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop orchestrator worker cleanly."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Enrichment orchestrator stopped.")
