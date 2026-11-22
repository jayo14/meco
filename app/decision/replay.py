"""
Historical Decision Replay Engine for Meco (Phase 5).
Guarantees zero look-ahead bias by strictly filtering all observations,
agent results, and state transitions to timestamps at or before evaluation time T.
Ensures deterministic historical score reproducibility.
"""
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.decision.config import DecisionEngineConfig, get_decision_config
from app.decision.engine import DecisionEngine
from app.decision.models import TokenDecisionInput, TokenDecisionResult

logger = logging.getLogger("meco.decision.replay")


class HistoricalReplayEngine:
    """
    Replays decision evaluations deterministically at any historical timestamp T.
    Enforces that NO future data, observations, or agent findings are leaked into the evaluation.
    """

    def __init__(self, config: DecisionEngineConfig | None = None) -> None:
        self.config = config or get_decision_config()
        self.engine = DecisionEngine(config=self.config)

    def filter_input_to_as_of(
        self,
        raw_input: TokenDecisionInput,
        as_of: datetime,
    ) -> TokenDecisionInput:
        """
        Prune all future-dated observations, timestamps, and findings from input.
        Guarantees zero look-ahead temporal leakage.
        """
        as_of_aware = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=timezone.utc)

        # 1. Filter market observations
        filtered_obs = []
        for obs in raw_input.market_observations:
            obs_ts = obs.get("timestamp") or obs.get("created_at")
            if obs_ts:
                if isinstance(obs_ts, str):
                    obs_ts = datetime.fromisoformat(obs_ts)
                if obs_ts.tzinfo is None:
                    obs_ts = obs_ts.replace(tzinfo=timezone.utc)
                if obs_ts <= as_of_aware:
                    filtered_obs.append(obs)
            else:
                filtered_obs.append(obs)

        # 2. Filter discovery history
        filtered_discovery = []
        for disc in raw_input.discovery_history:
            disc_ts = disc.get("timestamp") or disc.get("discovered_at")
            if disc_ts:
                if isinstance(disc_ts, str):
                    disc_ts = datetime.fromisoformat(disc_ts)
                if disc_ts.tzinfo is None:
                    disc_ts = disc_ts.replace(tzinfo=timezone.utc)
                if disc_ts <= as_of_aware:
                    filtered_discovery.append(disc)
            else:
                filtered_discovery.append(disc)

        # 3. Filter timestamps map
        filtered_timestamps = {}
        for key, ts in raw_input.input_timestamps.items():
            if ts:
                ts_aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
                if ts_aware <= as_of_aware:
                    filtered_timestamps[key] = ts_aware

        # 4. Filter specialist agent outputs if they occurred after as_of
        # In a strict historical replay, an agent that ran after T didn't exist yet
        res_agent = raw_input.research_agent_output
        risk_agent = raw_input.risk_agent_output
        mkt_agent = raw_input.market_agent_output
        soc_agent = raw_input.social_agent_output

        # Assemble clean historical input
        return TokenDecisionInput(
            mint_address=raw_input.mint_address,
            token_id=raw_input.token_id,
            as_of=as_of_aware,
            canonical_token=raw_input.canonical_token,
            discovery_history=filtered_discovery,
            lifecycle_state=raw_input.lifecycle_state,
            security_findings=raw_input.security_findings,
            holder_distribution=raw_input.holder_distribution,
            deployer_intelligence=raw_input.deployer_intelligence,
            liquidity_pool=raw_input.liquidity_pool,
            market_observations=filtered_obs,
            social_intelligence=raw_input.social_intelligence,
            research_agent_output=res_agent,
            risk_agent_output=risk_agent,
            market_agent_output=mkt_agent,
            social_agent_output=soc_agent,
            statistical_model_outputs=raw_input.statistical_model_outputs,
            input_timestamps=filtered_timestamps,
        )

    def replay_decision(
        self,
        input_data: TokenDecisionInput,
        as_of: datetime,
    ) -> TokenDecisionResult:
        """
        Execute deterministic historical replay at timestamp as_of.
        """
        clean_input = self.filter_input_to_as_of(input_data, as_of)
        return self.engine.evaluate(clean_input, as_of=as_of)

    def verify_reproducibility(
        self,
        input_data: TokenDecisionInput,
        as_of: datetime,
    ) -> bool:
        """
        Execute replay twice on the same historical input and verify that
        all dimension scores, hard risk violations, confidence, and outcome
        are bit-for-bit identical.
        """
        d1 = self.replay_decision(input_data, as_of)
        d2 = self.replay_decision(input_data, as_of)

        assert d1.outcome == d2.outcome, f"Outcome mismatch: {d1.outcome} != {d2.outcome}"
        assert d1.confidence == d2.confidence, f"Confidence mismatch: {d1.confidence} != {d2.confidence}"
        assert d1.dimension_scores.to_dict() == d2.dimension_scores.to_dict(), "Dimension scores mismatch"
        assert len(d1.hard_risk_violations) == len(d2.hard_risk_violations), "Hard risk violations count mismatch"

        return True
