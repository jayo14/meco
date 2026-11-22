"""
Comprehensive test suite for Meco Evidence-Based Decision Engine (Phase 5).
Validates:
- Hard risk rejection.
- Incomplete evidence.
- Conflicting agent findings.
- Stale data.
- Score reproducibility.
- Decision expiration.
- Reassessment triggers.
- Historical replay without look-ahead bias.
- Missing agent outputs.
- Decision versioning.
- Opportunity ranking and tiers.
- Decision explainability (the 7 institutional questions).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.agents.base import (
    AgentConfig,
    AgentFinding,
    AgentOutput,
    AgentStatus,
    EvidenceItem,
    FindingType,
    HardRiskCondition,
    SoftWarning,
)
from app.decision import (
    DecisionAuditTracer,
    DecisionDimension,
    DecisionEngine,
    DecisionEngineConfig,
    DecisionExplanation,
    DecisionOutcome,
    FreshnessConfig,
    HardRiskRuleConfig,
    HistoricalReplayEngine,
    OpportunityRanker,
    ReassessmentConfig,
    ReassessmentDecision,
    ReassessmentManager,
    ReassessmentTriggerEvent,
    ReassessmentTriggerType,
    TokenDecisionInput,
    TokenDecisionResult,
    build_decision_input_from_db,
    evaluate_hard_risk_rules,
    evaluate_input_freshness,
    get_decision_config,
    register_decision_config,
)


@pytest.fixture
def base_valid_input() -> TokenDecisionInput:
    """Fixture providing a baseline timestamped valid token decision input."""
    now = datetime.now(timezone.utc)
    return TokenDecisionInput(
        mint_address="So11111111111111111111111111111111111111112",
        token_id=1,
        as_of=now,
        canonical_token={
            "mint_address": "So11111111111111111111111111111111111111112",
            "name": "Meco Alpha Token",
            "symbol": "MECO",
            "decimals": 9,
            "total_supply": 1_000_000_000,
            "verification_status": "verified",
            "lifecycle_state": "graduated",
        },
        discovery_history=[
            {
                "source": "raydium_detector",
                "event_type": "pool_created",
                "timestamp": now - timedelta(hours=2),
            }
        ],
        lifecycle_state="graduated",
        security_findings={
            "mint_authority": None,
            "freeze_authority": None,
            "has_mint_authority": False,
            "has_freeze_authority": False,
            "is_mutable": False,
            "is_token_2022": False,
            "transfer_fee_bps": 0,
            "lp_burned_percentage": 100.0,
            "top_10_holder_percent": 18.5,
            "is_honeypot": False,
        },
        holder_distribution={
            "top_10_percentage": 18.5,
            "max_single_holder_pct": 3.0,
            "deployer_holding_pct": 0.0,
            "unique_holders_count": 250,
        },
        deployer_intelligence={
            "known_rug_count": 0,
            "is_blacklisted": False,
            "wash_trading_score": 0.05,
            "total_deployed_tokens": 3,
        },
        liquidity_pool={
            "pair_address": "Pool11111111111111111111111111111111111111",
            "dex": "raydium",
            "liquidity_usd": 65000.0,
            "volume_5m": 4500.0,
            "volume_1h": 22000.0,
            "volume_24h": 120000.0,
            "buys_5m": 65,
            "sells_5m": 15,
            "price_change_5m": 12.0,
            "price_change_1h": 28.0,
            "pair_created_at": int((now - timedelta(hours=4)).timestamp() * 1000),
        },
        market_observations=[
            {
                "price_usd": 0.0025,
                "volume_5m": 4500.0,
                "volume_1h": 22000.0,
                "buys_5m": 65,
                "sells_5m": 15,
                "price_change_5m": 12.0,
                "timestamp": now - timedelta(minutes=1),
            }
        ],
        social_intelligence={
            "mention_count": 60,
            "mention_velocity": 18.0,
            "unique_authors_count": 42,
            "author_concentration": 0.08,
            "sentiment_positive": 0.75,
            "sentiment_negative": 0.10,
            "spam_score": 0.02,
        },
        research_agent_output=AgentOutput(
            agent_name="research",
            status=AgentStatus.COMPLETED,
            confidence=0.88,
            findings=[
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Liquidity Verified",
                    statement="Raydium pool locked and burned at 100%.",
                )
            ],
            evidence_references=[
                EvidenceItem(source="solana_rpc", reference="burn_tx_hash_123")
            ],
        ),
        risk_agent_output=AgentOutput(
            agent_name="risk",
            status=AgentStatus.COMPLETED,
            confidence=0.92,
            hard_risks=[],
            soft_warnings=[],
            evidence_references=[],
        ),
        market_agent_output=AgentOutput(
            agent_name="market_analysis",
            status=AgentStatus.COMPLETED,
            confidence=0.85,
            metrics={"volatility_5m": 0.04, "depth_score": 85.0},
        ),
        social_agent_output=AgentOutput(
            agent_name="social",
            status=AgentStatus.COMPLETED,
            confidence=0.82,
            metrics={"viral_score": 78.0},
        ),
        statistical_model_outputs={
            "expected_win_rate": 0.72,
            "expected_payoff": 2.4,
            "anomaly_score": 0.8,
        },
        input_timestamps={
            "price": now - timedelta(minutes=1),
            "liquidity_pool": now - timedelta(minutes=1),
            "security_findings": now - timedelta(minutes=10),
            "social_intelligence": now - timedelta(minutes=5),
        },
    )


# ==============================================================================
# 1. Hard Risk Rejection Tests
# ==============================================================================

def test_hard_risk_rejection_active_mint_authority(base_valid_input: TokenDecisionInput):
    """Token with active mint authority must be rejected regardless of high opportunity."""
    base_valid_input.security_findings["mint_authority"] = "MaliciousCreator11111111111111111111"
    base_valid_input.security_findings["has_mint_authority"] = True

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-MINT-AUTH-ACTIVE" for v in result.hard_risk_violations)
    assert "mint authority is active" in result.reasoning_summary.lower()


def test_hard_risk_rejection_active_freeze_authority(base_valid_input: TokenDecisionInput):
    """Token with active freeze authority must be rejected."""
    base_valid_input.security_findings["freeze_authority"] = "Freezer1111111111111111111111111"
    base_valid_input.security_findings["has_freeze_authority"] = True

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-FREEZE-AUTH-ACTIVE" for v in result.hard_risk_violations)


def test_hard_risk_rejection_honeypot(base_valid_input: TokenDecisionInput):
    """Token flagged as honeypot must be rejected immediately."""
    base_valid_input.security_findings["is_honeypot"] = True

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-HONEYPOT-DETECTED" for v in result.hard_risk_violations)


def test_hard_risk_rejection_insufficient_liquidity(base_valid_input: TokenDecisionInput):
    """Token with liquidity below $500 hard minimum must be rejected."""
    base_valid_input.liquidity_pool["liquidity_usd"] = 250.0

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-INSUFFICIENT-LIQUIDITY" for v in result.hard_risk_violations)


def test_hard_risk_rejection_top_10_concentration(base_valid_input: TokenDecisionInput):
    """Token with top 10 concentration > 85% must be rejected."""
    base_valid_input.holder_distribution["top_10_percentage"] = 92.5

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-TOP10-CONCENTRATION-EXCESSIVE" for v in result.hard_risk_violations)


def test_hard_risk_rejection_malicious_deployer(base_valid_input: TokenDecisionInput):
    """Token created by a deployer with confirmed rug pulls must be rejected."""
    base_valid_input.deployer_intelligence = {
        "address": "RuggerWallet111111111111111111111111",
        "known_rug_count": 3,
        "is_blacklisted": True,
    }

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any(v.rule_code == "HR-MALICIOUS-DEPLOYER" for v in result.hard_risk_violations)


def test_hard_risk_rejection_from_risk_agent_finding(base_valid_input: TokenDecisionInput):
    """Hard risks emitted by specialist Risk Agent must be directly ingested and rejected."""
    base_valid_input.risk_agent_output.hard_risks = [
        HardRiskCondition(
            code="SUSPICIOUS-BYTECODE-DRAIN",
            description="Hidden drain instruction detected in token escrow proxy.",
            severity="critical",
        )
    ]

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    assert any("SUSPICIOUS-BYTECODE-DRAIN" in v.rule_code for v in result.hard_risk_violations)


# ==============================================================================
# 2. Incomplete Evidence and Missing Data Tests
# ==============================================================================

def test_incomplete_evidence_missing_security_profile(base_valid_input: TokenDecisionInput):
    """Evaluation must halt with INSUFFICIENT_EVIDENCE if critical security findings are missing."""
    base_valid_input.security_findings = None

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE
    assert "security_findings" in result.missing_information
    assert "insufficient or stale evidence" in result.reasoning_summary.lower()


def test_incomplete_evidence_missing_liquidity_pool(base_valid_input: TokenDecisionInput):
    """Evaluation must halt with INSUFFICIENT_EVIDENCE if liquidity pool info is missing."""
    base_valid_input.liquidity_pool = None

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE
    assert "liquidity_pool" in result.missing_information


# ==============================================================================
# 3. Stale Data Rejection Tests
# ==============================================================================

def test_stale_price_data_rejection(base_valid_input: TokenDecisionInput):
    """Stale price data (older than max 600s allowed) must reject evaluation."""
    now = datetime.now(timezone.utc)
    base_valid_input.as_of = now
    # Set price observation timestamp to 20 minutes ago (1200 seconds)
    base_valid_input.input_timestamps["price"] = now - timedelta(seconds=1200)

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE
    assert any("stale_price" in m for m in result.missing_information)


def test_stale_security_data_rejection(base_valid_input: TokenDecisionInput):
    """Stale security profile (older than max 3600s allowed) must reject evaluation."""
    now = datetime.now(timezone.utc)
    base_valid_input.as_of = now
    base_valid_input.input_timestamps["security_findings"] = now - timedelta(seconds=7200)

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert result.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE
    assert any("stale_security_findings" in m for m in result.missing_information)


# ==============================================================================
# 4. Conflicting Agent Findings Tests
# ==============================================================================

def test_conflicting_agent_findings_handling(base_valid_input: TokenDecisionInput):
    """
    When research agent is highly confident bullish, but risk agent flags severe warnings,
    data confidence must apply a disagreement penalty and contradictory evidence is recorded.
    """
    base_valid_input.research_agent_output.confidence = 0.95
    base_valid_input.risk_agent_output.soft_warnings = [
        SoftWarning(code="WAR-HIGH-INSIDER-CLUSTERING", description="5 wallets funded by same CEX deposit address"),
        SoftWarning(code="WAR-WASH-TRADING-SUSPECTED", description="Circular trading between top 3 holders"),
    ]

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    # Contradictory evidence must capture the risk warnings
    assert len(result.contradictory_evidence) > 0
    # Conflict detected should be reflected in data confidence components
    conf_comp = result.dimension_scores.data_confidence.components
    assert conf_comp.get("conflict_detected") == 1.0


# ==============================================================================
# 5. Missing Agent Outputs (Graceful Degradation) Tests
# ==============================================================================

def test_missing_agent_outputs_graceful_degradation(base_valid_input: TokenDecisionInput):
    """Engine must execute gracefully when non-critical specialist agents (market/social) are absent."""
    base_valid_input.market_agent_output = None
    base_valid_input.social_agent_output = None

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    # Should not crash; produces a valid decision
    assert result.outcome in (
        DecisionOutcome.PAPER_TRADE_CANDIDATE,
        DecisionOutcome.WATCHLIST,
        DecisionOutcome.MONITOR,
        DecisionOutcome.INVESTIGATE_FURTHER,
    )
    # The contributing agents list in explanation reflects only available agents
    expl = result.explain()
    agent_names = [a["agent"] for a in expl.contributing_agents]
    assert "research" in agent_names
    assert "risk" in agent_names
    assert "market_analysis" not in agent_names


# ==============================================================================
# 6. Score Reproducibility Tests
# ==============================================================================

def test_score_reproducibility(base_valid_input: TokenDecisionInput):
    """Running identical inputs through the DecisionEngine multiple times must yield exact identical scores."""
    engine = DecisionEngine()
    res1 = engine.evaluate(base_valid_input)
    res2 = engine.evaluate(base_valid_input)

    assert res1.outcome == res2.outcome
    assert res1.confidence == res2.confidence
    assert res1.dimension_scores.to_dict() == res2.dimension_scores.to_dict()
    assert res1.reasoning_summary == res2.reasoning_summary


# ==============================================================================
# 7. Decision Expiration Tests
# ==============================================================================

def test_decision_expiration(base_valid_input: TokenDecisionInput):
    """Decisions must expire accurately after their configured validity period."""
    now = datetime.now(timezone.utc)
    base_valid_input.as_of = now

    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    assert not result.is_expired(at_time=now)
    assert not result.is_expired(at_time=now + timedelta(minutes=15))
    # Expiration is default 30 minutes (1800s)
    assert result.is_expired(at_time=now + timedelta(minutes=31))


# ==============================================================================
# 8. Reassessment Triggers and Cooldowns Tests
# ==============================================================================

def test_reassessment_triggers_and_cooldowns():
    """Verify event-driven triggers, thresholds, deduplication, and cooldown periods."""
    now = datetime.now(timezone.utc)
    mgr = ReassessmentManager()
    mint = "ReassessMint1111111111111111111111111"

    # Event 1: Small price movement (5%) should NOT trigger reassessment
    ev_small = ReassessmentTriggerEvent(
        mint_address=mint,
        trigger_type=ReassessmentTriggerType.SIGNIFICANT_PRICE_MOVEMENT,
        delta_metrics={"price_delta_pct": 5.0},
        detected_at=now,
    )
    d1 = mgr.evaluate_event(ev_small, as_of=now)
    assert not d1.should_reassess

    # Event 2: Meaningful price movement (25%) MUST trigger
    ev_large = ReassessmentTriggerEvent(
        mint_address=mint,
        trigger_type=ReassessmentTriggerType.SIGNIFICANT_PRICE_MOVEMENT,
        delta_metrics={"price_delta_pct": 25.0},
        detected_at=now,
    )
    d2 = mgr.evaluate_event(ev_large, as_of=now)
    assert d2.should_reassess

    # Mark reassessment performed
    mgr.record_reassessment(mint, as_of=now)

    # Event 3: Next event within 300s cooldown should be blocked
    ev_soon = ReassessmentTriggerEvent(
        mint_address=mint,
        trigger_type=ReassessmentTriggerType.LIQUIDITY_CHANGE,
        delta_metrics={"liquidity_delta_pct": 20.0},
        detected_at=now + timedelta(seconds=60),
    )
    d3 = mgr.evaluate_event(ev_soon, as_of=now + timedelta(seconds=60))
    assert not d3.should_reassess
    assert d3.cooldown_active
    assert d3.seconds_until_cooldown_expires > 0

    # Event 4: Emergency authority change overrides normal cooldown after emergency threshold
    ev_emergency = ReassessmentTriggerEvent(
        mint_address=mint,
        trigger_type=ReassessmentTriggerType.AUTHORITY_CHANGE,
        delta_metrics={"details": "Mint authority enabled"},
        detected_at=now + timedelta(seconds=40),
    )
    d4 = mgr.evaluate_event(ev_emergency, as_of=now + timedelta(seconds=40))
    assert d4.should_reassess
    assert d4.is_emergency


# ==============================================================================
# 9. Historical Replay Without Look-Ahead Bias Tests
# ==============================================================================

def test_historical_replay_without_future_leakage(base_valid_input: TokenDecisionInput):
    """Historical replay strictly isolates observations up to timestamp T."""
    t_eval = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Add observations from before, at, and after t_eval
    base_valid_input.market_observations = [
        {"timestamp": t_eval - timedelta(hours=1), "price_usd": 0.001, "volume_5m": 500.0},
        {"timestamp": t_eval, "price_usd": 0.0012, "volume_5m": 800.0},
        # Future observations (must be stripped):
        {"timestamp": t_eval + timedelta(minutes=15), "price_usd": 0.005, "volume_5m": 50000.0},
        {"timestamp": t_eval + timedelta(hours=2), "price_usd": 0.010, "volume_5m": 100000.0},
    ]

    replay_engine = HistoricalReplayEngine()
    clean_input = replay_engine.filter_input_to_as_of(base_valid_input, t_eval)

    # Future observations must be strictly pruned
    assert len(clean_input.market_observations) == 2
    assert clean_input.market_observations[-1]["timestamp"] == t_eval

    # Replay must be fully reproducible
    assert replay_engine.verify_reproducibility(clean_input, t_eval)


# ==============================================================================
# 10. Decision Versioning and Config Registry Tests
# ==============================================================================

def test_decision_versioning():
    """Custom scoring configs can be versioned, registered, and retrieved for historical audit."""
    custom_cfg = DecisionEngineConfig(
        version="2.0.0-experimental",
        name="aggressive_opportunity_v2",
        reassessment=ReassessmentConfig(decision_validity_seconds=600),
    )
    register_decision_config(custom_cfg)

    retrieved = get_decision_config("2.0.0-experimental")
    assert retrieved.version == "2.0.0-experimental"
    assert retrieved.reassessment.decision_validity_seconds == 600

    # Ensure hash signatures are unique per configuration
    v1_cfg = get_decision_config("1.0.0")
    assert v1_cfg.hash_signature() != custom_cfg.hash_signature()


# ==============================================================================
# 11. Opportunity Ranking and Classification Tests
# ==============================================================================

def test_opportunity_ranking_and_tiers(base_valid_input: TokenDecisionInput):
    """
    Ranks multiple opportunities correctly into institutional tiers without
    collapsing risk into a hidden blended score.
    """
    engine = DecisionEngine()

    # Candidate 1: Prime paper trade candidate
    d1 = engine.evaluate(base_valid_input)

    # Candidate 2: Danger token (mint authority active)
    inp_danger = base_valid_input.model_copy(deep=True)
    inp_danger.mint_address = "DangerMint11111111111111111111111111111"
    inp_danger.security_findings["mint_authority"] = "Rugger111"
    inp_danger.security_findings["has_mint_authority"] = True
    d2 = engine.evaluate(inp_danger)

    # Candidate 3: Low opportunity monitor token
    inp_monitor = base_valid_input.model_copy(deep=True)
    inp_monitor.mint_address = "MonitorMint111111111111111111111111"
    inp_monitor.liquidity_pool["volume_5m"] = 50.0
    inp_monitor.liquidity_pool["volume_1h"] = 200.0
    inp_monitor.social_intelligence["mention_count"] = 2
    inp_monitor.social_intelligence["mention_velocity"] = 0.5
    d3 = engine.evaluate(inp_monitor)

    ranked = OpportunityRanker.rank_opportunities([d2, d3, d1])

    # Rank 1 must be the prime candidate
    assert ranked[0].mint_address == base_valid_input.mint_address
    assert "PAPER_TRADE" in ranked[0].tier

    # The hard risk token must be ranked at the bottom in UNQUALIFIED_HARD_RISK
    assert ranked[-1].mint_address == inp_danger.mint_address
    assert ranked[-1].tier == "UNQUALIFIED_HARD_RISK"
    assert ranked[-1].risk_adjusted_rank_score == -1000.0


# ==============================================================================
# 12. Decision Explainability (7 Questions) Tests
# ==============================================================================

def test_decision_explainability_seven_questions(base_valid_input: TokenDecisionInput):
    """Every decision must answer all 7 institutional explainability questions."""
    engine = DecisionEngine()
    result = engine.evaluate(base_valid_input)

    answers = DecisionAuditTracer.answer_seven_questions(result)
    assert "q1_evidence_available" in answers
    assert "q2_token_state_at_time" in answers
    assert "q3_contributing_agents" in answers
    assert "q4_critical_risk_factors" in answers
    assert "q5_missing_information" in answers
    assert "q6_scoring_config_used" in answers
    assert "q7_outcome_selection_rationale" in answers

    # Audit markdown report generation
    report = DecisionAuditTracer.generate_audit_report(result)
    assert "# Decision Audit Report" in report
    assert "## Dimension Scores Breakdown" in report
    assert "## 7-Question Explainability Audit" in report
    assert len(result.supporting_evidence) > 0


# ==============================================================================
# 13. Async Database Bridge Test
# ==============================================================================

@pytest.mark.asyncio
async def test_database_bridge_reconstruction():
    """Verify build_decision_input_from_db reconstructs input correctly from mock session."""
    session = AsyncMock()

    mock_token = MagicMock()
    mock_token.id = 42
    mock_token.mint_address = "BridgeMint11111111111111111111111111"
    mock_token.name = "Bridge Test"
    mock_token.symbol = "BRG"
    mock_token.decimals = 9
    mock_token.total_supply = 1_000_000
    mock_token.verification_status = "verified"
    mock_token.lifecycle_state = "graduated"

    mock_sec = MagicMock()
    mock_sec.mint_authority = None
    mock_sec.freeze_authority = None
    mock_sec.is_mintable = False
    mock_sec.is_freezable = False
    mock_sec.is_mutable = False
    mock_sec.transfer_fee_basis_points = 0
    mock_sec.is_lp_burned_or_locked = True
    mock_sec.top10_concentration_pct = 25.0
    mock_sec.updated_at = datetime.now(timezone.utc)

    mock_pool = MagicMock()
    mock_pool.pair_address = "Pair123"
    mock_pool.dex_id = "raydium"
    mock_pool.liquidity_usd = 50000.0
    mock_pool.volume_5m = 1000.0
    mock_pool.volume_1h = 5000.0
    mock_pool.volume_24h = 25000.0
    mock_pool.buys_5m = 20
    mock_pool.sells_5m = 5
    mock_pool.price_change_5m = 5.0
    mock_pool.price_change_1h = 10.0
    mock_pool.pair_created_at = 1700000000
    mock_pool.observed_at = datetime.now(timezone.utc)

    # Set up session execute returns
    execute_calls = 0

    async def mock_execute(stmt):
        nonlocal execute_calls
        execute_calls += 1
        res = MagicMock()
        if execute_calls == 1:
            # Token
            res.scalar_one_or_none.return_value = mock_token
        elif execute_calls == 2:
            # DiscoveryEvent
            res.scalars.return_value.all.return_value = []
        elif execute_calls == 3:
            # TokenSecurityProfile
            res.scalars.return_value.first.return_value = mock_sec
        elif execute_calls == 4:
            # TokenHolderSnapshot
            res.scalars.return_value.first.return_value = None
        elif execute_calls == 5:
            # MarketPairObservation
            res.scalars.return_value.first.return_value = mock_pool
        elif execute_calls == 6:
            # MarketObservation
            res.scalars.return_value.all.return_value = []
        elif execute_calls == 7:
            # SocialMetricsSnapshot
            res.scalars.return_value.first.return_value = None
        elif execute_calls == 8:
            # TokenInvestigation
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = mock_execute

    inp = await build_decision_input_from_db(session, "BridgeMint11111111111111111111111111")
    assert inp.mint_address == "BridgeMint11111111111111111111111111"
    assert inp.canonical_token["symbol"] == "BRG"
    assert inp.security_findings["lp_burned_percentage"] == 100.0
    assert inp.liquidity_pool["liquidity_usd"] == 50000.0
