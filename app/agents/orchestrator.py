import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.base import (
    AgentConfig,
    AgentOutput,
    AgentStatus,
    BaseAgent,
    FindingType,
    InvestigationContext,
)
from app.agents.llm.client import LLMClient
from app.agents.market_agent import MarketAnalysisAgent
from app.agents.models import DecisionEngineHandoffPackage, TokenInvestigationRequest
from app.agents.research_agent import ResearchAgent
from app.agents.risk_agent import RiskAgent
from app.agents.social_agent import SocialIntelligenceAgent
from app.database.models import AgentInvestigationResult, Token, TokenInvestigation
from app.intelligence.profile import build_token_intelligence_profile

logger = logging.getLogger("meco.agents.orchestrator")


class AgentOrchestrator:
    """
    Coordinated intelligence agent orchestrator.
    Manages dynamic agent dispatch, concurrent investigation execution,
    shared state persistence, retry policies, cancellation, restart recovery,
    and structured evidence handover for decision evaluation.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        custom_agents: dict[str, BaseAgent] | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.agents: dict[str, BaseAgent] = custom_agents or {
            "research": ResearchAgent(llm_client=self.llm_client),
            "risk": RiskAgent(llm_client=self.llm_client),
            "market_analysis": MarketAnalysisAgent(llm_client=self.llm_client),
            "social": SocialIntelligenceAgent(llm_client=self.llm_client),
        }
        # In-flight task tracker for live cancellation
        self._in_flight_tasks: dict[str, set[asyncio.Task]] = {}

    def determine_relevant_agents(
        self,
        profile_dict: dict[str, Any] | None,
        requested_agents: list[str] | None = None,
    ) -> list[str]:
        """
        Dynamically determine which specialist agents need to execute.
        Avoids running expensive or irrelevant agents (e.g. market analysis on tokens with no liquidity).
        """
        if requested_agents:
            return [a for a in requested_agents if a in self.agents]

        if not profile_dict:
            # Fallback to base investigative duo
            return ["research", "risk"]

        relevant = ["research", "risk"]

        # Market Analysis: Only relevant if token has an initialized pool or recorded volume/liquidity
        liquidity = profile_dict.get("liquidity") or {}
        liq_usd = float(liquidity.get("liquidity_usd") or 0.0)
        has_pairs = bool(liquidity.get("primary_pair_address") or liquidity.get("pairs_count", 0) > 0)
        if liq_usd > 0.0 or has_pairs:
            relevant.append("market_analysis")

        # Social Intelligence: Relevant if project has metadata socials, discovered via social/telegram, or has trading activity
        metadata = profile_dict.get("metadata") or {}
        has_social_links = bool(metadata.get("website") or metadata.get("twitter") or metadata.get("telegram"))
        sources = profile_dict.get("sources") or []
        has_social_source = any(s.get("source") in ("telegram_channel", "x_post", "rss_feed") for s in sources)
        if has_social_links or has_social_source or liq_usd > 1000.0:
            relevant.append("social")

        return relevant

    async def investigate_token(
        self,
        session: AsyncSession,
        request: TokenInvestigationRequest,
    ) -> DecisionEngineHandoffPackage:
        """
        Execute full token investigation lifecycle:
        1. Receive request.
        2. Load canonical token and intelligence profile.
        3. Check idempotency / create investigation record in DB.
        4. Dynamically determine relevant agents.
        5. Execute independent investigations concurrently.
        6. Persist each agent's result to shared DB state.
        7. Track progress and handle failures/timeouts.
        8. Synthesize findings into DecisionEngineHandoffPackage.
        """
        now_utc = datetime.now(timezone.utc)
        mint_address = request.mint_address

        # 1. Load canonical token
        stmt = select(Token).where(Token.mint_address == mint_address)
        res = await session.execute(stmt)
        token = res.scalar_one_or_none()
        token_id = token.id if token else None

        # 2. Check for existing active investigation (Idempotency)
        if not request.force_refresh:
            active_stmt = (
                select(TokenInvestigation)
                .where(
                    TokenInvestigation.mint_address == mint_address,
                    TokenInvestigation.status.in_(["pending", "running"]),
                )
                .order_by(TokenInvestigation.created_at.desc())
            )
            active_res = await session.execute(active_stmt)
            existing_active = active_res.scalar_one_or_none()
            if existing_active:
                logger.info(
                    f"Investigation {existing_active.id} for mint {mint_address} is already in progress ({existing_active.status})."
                )
                # Re-hydrate package if available or wait/return partial
                return DecisionEngineHandoffPackage(
                    investigation_id=existing_active.id,
                    mint_address=mint_address,
                    token_id=token_id,
                    verdict="HOLD",
                    risk_level="MEDIUM",
                    overall_confidence=0.5,
                    ready_for_trade_decision=False,
                )

        # 3. Load or build canonical intelligence profile
        profile = await build_token_intelligence_profile(session, mint_address)
        profile_dict = profile.to_dict() if profile else None

        # 4. Determine relevant agents
        relevant_agents = self.determine_relevant_agents(profile_dict, request.requested_agents)

        # 5. Create persistent investigation record in DB
        investigation_id = str(uuid.uuid4())
        investigation = TokenInvestigation(
            id=investigation_id,
            token_id=token_id,
            mint_address=mint_address,
            trigger=request.trigger,
            status="running",
            requested_agents=relevant_agents,
            completed_agents=[],
            failed_agents=[],
            start_time=now_utc,
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(investigation)

        # Pre-seed AgentInvestigationResult records as pending
        agent_records: dict[str, AgentInvestigationResult] = {}
        for agent_name in relevant_agents:
            rec = AgentInvestigationResult(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                agent_name=agent_name,
                status="pending",
                confidence=0.0,
                insufficient_evidence=False,
                created_at=now_utc,
            )
            session.add(rec)
            agent_records[agent_name] = rec

        await session.commit()

        # 6. Build execution context
        context = InvestigationContext(
            investigation_id=investigation_id,
            token_id=token_id,
            mint_address=mint_address,
            profile=profile,
            market_data=(profile_dict.get("liquidity") if profile_dict else {}) or {},
            social_data={},
        )

        # 7. Execute independent investigations concurrently
        async def _run_agent_with_persistence(agent_name: str) -> AgentOutput:
            agent = self.agents[agent_name]
            # Update status to running
            agent_rec = agent_records[agent_name]
            agent_rec.status = "running"
            agent_rec.started_at = datetime.now(timezone.utc)
            await session.commit()

            try:
                out = await agent.run(context)
            except Exception as exc:
                out = AgentOutput(
                    agent_name=agent_name,
                    status=AgentStatus.FAILED,
                    confidence=0.0,
                    error_message=str(exc),
                    insufficient_evidence=True,
                )

            # Persist result
            agent_rec.status = out.status.value
            agent_rec.confidence = out.confidence
            agent_rec.insufficient_evidence = out.insufficient_evidence
            agent_rec.findings = [f.model_dump(mode="json") for f in out.findings]
            agent_rec.evidence_references = [e.model_dump(mode="json") for e in out.evidence_references]
            agent_rec.unanswered_questions = out.unanswered_questions
            agent_rec.hard_risks = [h.model_dump(mode="json") for h in out.hard_risks]
            agent_rec.soft_warnings = [w.model_dump(mode="json") for w in out.soft_warnings]
            agent_rec.metrics = out.metrics
            agent_rec.error_message = out.error_message
            agent_rec.model_provider = out.model_provider
            agent_rec.model_name = out.model_name
            agent_rec.prompt_version = out.prompt_version
            agent_rec.tokens_used = out.tokens_used
            agent_rec.execution_duration_ms = out.execution_duration_ms
            agent_rec.completed_at = datetime.now(timezone.utc)
            await session.commit()

            return out

        tasks = [
            asyncio.create_task(_run_agent_with_persistence(name))
            for name in relevant_agents
        ]
        self._in_flight_tasks[investigation_id] = set(tasks)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=request.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Investigation {investigation_id} reached overall timeout of {request.timeout_seconds}s")
            for t in tasks:
                if not t.done():
                    t.cancel()
            results = []
            for name in relevant_agents:
                rec = agent_records[name]
                if rec.status != "completed":
                    rec.status = "timed_out"
                    rec.error_message = f"Investigation timed out after {request.timeout_seconds}s"
            await session.commit()
        finally:
            self._in_flight_tasks.pop(investigation_id, None)

        # 8. Collect completed and failed agents
        completed_agents = []
        failed_agents = []
        agent_outputs: dict[str, AgentOutput] = {}

        for name, res_item in zip(relevant_agents, results, strict=False):
            if isinstance(res_item, AgentOutput) and res_item.status == AgentStatus.COMPLETED:
                completed_agents.append(name)
                agent_outputs[name] = res_item
            else:
                failed_agents.append(name)
                if isinstance(res_item, AgentOutput):
                    agent_outputs[name] = res_item

        # 9. Synthesize overall verdict and build decision package
        package = self._synthesize_investigation(
            investigation_id=investigation_id,
            mint_address=mint_address,
            token_id=token_id,
            agent_outputs=agent_outputs,
            relevant_agents=relevant_agents,
        )

        # Update investigation record in DB
        inv_status = "completed"
        if not completed_agents:
            inv_status = "failed"
        elif failed_agents:
            inv_status = "partial"

        investigation.status = inv_status
        investigation.completed_agents = completed_agents
        investigation.failed_agents = failed_agents
        investigation.completion_time = datetime.now(timezone.utc)
        investigation.verdict = package.model_dump(mode="json")
        investigation.updated_at = datetime.now(timezone.utc)
        await session.commit()

        return package

    def _synthesize_investigation(
        self,
        investigation_id: str,
        mint_address: str,
        token_id: int | None,
        agent_outputs: dict[str, AgentOutput],
        relevant_agents: list[str],
    ) -> DecisionEngineHandoffPackage:
        """
        Synthesizes agent outputs into an institutional evidence handoff package.
        Deterministic risk rules strictly govern the verdict:
        - If ANY hard risk is flagged -> verdict is FAIL, risk_level is CRITICAL.
        - If risk is clean and market/research is strong -> verdict is PASS.
        - If missing critical data -> verdict is INSUFFICIENT_DATA or HOLD.
        """
        hard_risks: list[str] = []
        soft_warnings_count = 0
        all_facts = []
        all_evidence = []
        all_unanswered = []
        confidences = []

        for out in agent_outputs.values():
            for h in out.hard_risks:
                hard_risks.append(f"{out.agent_name}:{h.code}")
            soft_warnings_count += len(out.soft_warnings)
            all_facts.extend(out.facts())
            all_evidence.extend(out.evidence_references)
            all_unanswered.extend(out.unanswered_questions)
            if out.status == AgentStatus.COMPLETED:
                confidences.append(out.confidence)

        overall_confidence = round(sum(confidences) / max(1, len(confidences)), 2) if confidences else 0.0

        # Verdict logic
        if hard_risks:
            verdict = "FAIL"
            risk_level = "CRITICAL"
            ready_for_trade_decision = False
        elif any(out.insufficient_evidence for out in agent_outputs.values()):
            verdict = "INSUFFICIENT_DATA"
            risk_level = "HIGH" if soft_warnings_count > 2 else "MEDIUM"
            ready_for_trade_decision = False
        elif soft_warnings_count >= 3:
            verdict = "HOLD"
            risk_level = "HIGH"
            ready_for_trade_decision = False
        else:
            verdict = "PASS"
            risk_level = "LOW" if soft_warnings_count == 0 else "MEDIUM"
            ready_for_trade_decision = True

        return DecisionEngineHandoffPackage(
            investigation_id=investigation_id,
            mint_address=mint_address,
            token_id=token_id,
            verdict=verdict,
            risk_level=risk_level,
            hard_risks_detected=hard_risks,
            soft_warnings_count=soft_warnings_count,
            overall_confidence=overall_confidence,
            agent_results={k: v.model_dump(mode="json") for k, v in agent_outputs.items()},
            consolidated_facts=all_facts,
            consolidated_evidence=all_evidence,
            unanswered_questions=list(dict.fromkeys(all_unanswered)),
            ready_for_trade_decision=ready_for_trade_decision,
        )

    async def cancel_investigation(
        self,
        session: AsyncSession,
        investigation_id: str,
        reason: str = "Investigation cancelled by system",
    ) -> bool:
        """
        Cancel an in-progress investigation.
        Terminates running asyncio tasks and updates DB record to CANCELLED.
        """
        stmt = select(TokenInvestigation).where(TokenInvestigation.id == investigation_id)
        res = await session.execute(stmt)
        inv = res.scalar_one_or_none()
        if not inv:
            return False

        # Cancel running tasks
        tasks = self._in_flight_tasks.get(investigation_id, set())
        for t in tasks:
            if not t.done():
                t.cancel()

        inv.status = "cancelled"
        inv.error_message = reason
        inv.completion_time = datetime.now(timezone.utc)
        inv.updated_at = datetime.now(timezone.utc)

        # Cancel any pending/running agent records
        rec_stmt = (
            select(AgentInvestigationResult)
            .where(
                AgentInvestigationResult.investigation_id == investigation_id,
                AgentInvestigationResult.status.in_(["pending", "running"]),
            )
        )
        rec_res = await session.execute(rec_stmt)
        for rec in rec_res.scalars().all():
            rec.status = "cancelled"
            rec.error_message = reason

        await session.commit()
        logger.info(f"Investigation {investigation_id} successfully cancelled.")
        return True

    async def retry_investigation(
        self,
        session: AsyncSession,
        investigation_id: str,
    ) -> DecisionEngineHandoffPackage | None:
        """
        Retry a failed or partial investigation with fresh context.
        """
        stmt = select(TokenInvestigation).where(TokenInvestigation.id == investigation_id)
        res = await session.execute(stmt)
        inv = res.scalar_one_or_none()
        if not inv:
            return None

        req = TokenInvestigationRequest(
            mint_address=inv.mint_address,
            trigger=f"retry:{inv.trigger}",
            requested_agents=inv.requested_agents,
            force_refresh=True,
        )
        return await self.investigate_token(session, req)

    async def recover_in_progress_investigations(
        self,
        session: AsyncSession,
        stale_threshold_seconds: float = 300.0,
    ) -> int:
        """
        Restart recovery routine called on system startup.
        Identifies investigations stuck in 'pending' or 'running' state after a crash or restart,
        and cleanly marks them as 'timed_out' with an informative error message.
        """
        stmt = select(TokenInvestigation).where(TokenInvestigation.status.in_(["pending", "running"]))
        res = await session.execute(stmt)
        stuck_invs = res.scalars().all()

        recovered_count = 0
        now_utc = datetime.now(timezone.utc)

        for inv in stuck_invs:
            inv.status = "timed_out"
            inv.error_message = "System restarted while investigation was in progress. Marked timed_out by recovery worker."
            inv.completion_time = now_utc
            inv.updated_at = now_utc

            # Also update child agent records
            rec_stmt = select(AgentInvestigationResult).where(
                AgentInvestigationResult.investigation_id == inv.id,
                AgentInvestigationResult.status.in_(["pending", "running"]),
            )
            rec_res = await session.execute(rec_stmt)
            for rec in rec_res.scalars().all():
                rec.status = "timed_out"
                rec.error_message = "System crash/restart recovery."
                rec.completed_at = now_utc

            recovered_count += 1

        if recovered_count > 0:
            await session.commit()
            logger.info(f"Restart recovery: Cleaned up {recovered_count} stalled investigations.")

        return recovered_count
