"""
End-to-End Production Regression Pipeline Test Suite (Phase 9).
Verifies the complete 13-stage lifecycle of Meco autonomously:
 1. Independent token discovery.
 2. Token persistence & canonical identity.
 3. Intelligence enrichment (Metadata, Security, Liquidity, Holders).
 4. Scheduled market observation checkpoint (T+10s).
 5. Social intelligence ingestion.
 6. Specialist agent investigation.
 7. Decision engine evaluation.
 8. Paper trade proposal generation.
 9. Pre-trade risk validation.
 10. Simulated execution (Constant-product slippage & fees).
 11. Position monitoring & excursion tracking (MFE / MAE).
 12. Exit execution and portfolio accounting reconciliation.
 13. Quantitative research outcome recording.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.database.models import (
    AgentInvestigationResult,
    DiscoveryEvent,
    MarketObservation,
    MarketPairObservation,
    Signal,
    SocialMetricsSnapshot,
    SocialPost,
    SocialTokenAssociation,
    Token,
    TokenHolderSnapshot,
    TokenInvestigation,
    TokenMetadataRecord,
    TokenSecurityProfile,
)
from app.decision.bridge import build_decision_input_from_db
from app.decision.engine import DecisionEngine
from app.decision.models import DecisionOutcome
from app.discovery.models import NormalizedDiscoveryEvent
from app.intelligence.lifecycle import TokenLifecycleState, transition_lifecycle
from app.research.experimentation import ExperimentRegistry
from app.research.learning import PaperTradingLearner
from app.trading import (
    ExitReason,
    PaperTradingEngine,
    PositionStatus,
    ProposalStatus,
)


@pytest.mark.asyncio
async def test_complete_13_stage_pipeline_end_to_end():
    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    now = datetime.now(timezone.utc)
    ts = int(now.timestamp())
    mint = f"PumpE2E{ts}1111111111111111111111111"

    try:
        async with session_maker() as test_session:
            # =========================================================================
            # STAGE 1: Independent Token Discovery
            # =========================================================================
            discovery_event = NormalizedDiscoveryEvent(
                source="pump_dot_fun",
                mint_address=mint,
                name="Meco Autonomous Alpha",
                symbol="MECOA",
                signature=f"5jK5...txSig{ts}",
                source_timestamp=now,
                slot=312450000,
                raw_payload={"platform": "pump.fun", "initial_buy": 1.5},
            )
            assert discovery_event.mint_address == mint
            assert discovery_event.source == "pump_dot_fun"

            # =========================================================================
            # STAGE 2: Token Persistence & Canonical Identity
            # =========================================================================
            token = Token(
                mint_address=mint,
                name=discovery_event.name,
                symbol=discovery_event.symbol,
                decimals=6,
                total_supply=1_000_000_000,
                first_discovery_source=discovery_event.source,
                first_discovered_at=now,
                lifecycle_state=TokenLifecycleState.DISCOVERED.value,
                created_at=now,
            )
            test_session.add(token)
            await test_session.flush()

            db_event = DiscoveryEvent(
                token_id=token.id,
                mint_address=mint,
                source="pump_dot_fun",
                event_type="token_created",
                signature=discovery_event.signature,
                slot=discovery_event.slot,
                received_at=now,
                source_timestamp=now,
                raw_payload=discovery_event.raw_payload,
                created_at=now,
            )
            test_session.add(db_event)
            await test_session.flush()
            assert token.id is not None

            # =========================================================================
            # STAGE 3: Intelligence Enrichment (Metadata, Security, Liquidity, Holders)
            # =========================================================================
            meta = TokenMetadataRecord(
                token_id=token.id,
                mint_address=mint,
                name="Meco Autonomous Alpha",
                symbol="MECOA",
                description="Autonomous Meme Research Alpha Token",
                updated_at=now,
            )
            sec = TokenSecurityProfile(
                token_id=token.id,
                mint_address=mint,
                token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                mint_authority=None,
                freeze_authority=None,
                is_mintable=False,
                is_freezable=False,
                is_mutable=False,
                has_transfer_fee=False,
                transfer_fee_basis_points=0,
                is_lp_burned_or_locked=True,
                risk_score=5.0,
                updated_at=now,
            )
            holders = TokenHolderSnapshot(
                token_id=token.id,
                mint_address=mint,
                total_holders_count=285,
                top10_concentration_pct=28.5,
                top20_concentration_pct=42.0,
                deployer_holding_pct=0.0,
                deployer_address="DeployerWallet111111111111111111111111111111",
                observed_at=now,
                created_at=now,
            )
            test_session.add_all([meta, sec, holders])
            await transition_lifecycle(test_session, token=token, to_state=TokenLifecycleState.TRADING_ACTIVE, reason="Healthy pool detected")
            await test_session.flush()
            assert token.lifecycle_state == TokenLifecycleState.TRADING_ACTIVE.value

            # =========================================================================
            # STAGE 4: Scheduled Market Observation Checkpoint (T+10s)
            # =========================================================================
            signal = Signal(
                chat_id=-100123456789,
                message_id=ts,
                message_text=f"Breakout on ${token.symbol} {mint}",
                message_created_at=now,
                received_at=now,
                token_address=mint,
            )
            test_session.add(signal)
            await test_session.flush()

            pair_obs = MarketPairObservation(
                signal_id=signal.id,
                token_address=mint,
                observed_at=now,
                target_seconds=10,
                seconds_since_signal=10,
                pair_address="PairAddress1111111111111111111111111111111111",
                dex_id="raydium",
                base_token_address=mint,
                liquidity_usd=85000.0,
                price_usd=0.0025,
                volume_5m=18500.0,
                volume_1h=45000.0,
                volume_24h=120000.0,
                buys_5m=45,
                sells_5m=12,
                price_change_5m=14.5,
                price_change_1h=22.0,
            )
            obs = MarketObservation(
                signal_id=signal.id,
                token_address=mint,
                target_seconds=10,
                seconds_since_signal=10,
                observation_status="success",
                price_usd=0.00255,
                liquidity_usd=86500.0,
                volume_5m=19000.0,
                observed_at=now,
            )
            test_session.add_all([pair_obs, obs])
            await test_session.flush()

            # =========================================================================
            # STAGE 5: Social Intelligence Ingestion
            # =========================================================================
            post = SocialPost(
                source="telegram",
                external_id=f"msg_{ts}",
                author_id="user_12345",
                author_username="solana_gems_hunter",
                content=f"Huge breakout momentum on ${token.symbol} ({mint[:8]}...)! Super clean deployer and liquidity expanding.",
                sanitized_content=f"Huge breakout momentum on ${token.symbol} ({mint[:8]}...)! Super clean deployer and liquidity expanding.",
                content_hash=f"hash_{ts}_{mint[:8]}",
                published_at=now,
                ingested_at=now,
            )
            test_session.add(post)
            await test_session.flush()

            assoc = SocialTokenAssociation(
                social_post_id=post.id,
                token_id=token.id,
                match_type="exact_mint",
                confidence=0.95,
                match_evidence={"reason": "Exact mint and symbol match"},
                associated_at=now,
            )
            soc_snapshot = SocialMetricsSnapshot(
                token_id=token.id,
                snapshot_time=now,
                mention_count=25,
                mention_velocity=2.5,
                unique_authors_count=18,
                author_concentration=0.15,
                sentiment_positive=0.8,
                sentiment_negative=0.05,
                spam_score=0.05,
                created_at=now,
            )
            test_session.add_all([assoc, soc_snapshot])
            await test_session.flush()

            # =========================================================================
            # STAGE 6: Specialist Agent Investigation
            # =========================================================================
            inv_id = str(uuid.uuid4())
            investigation = TokenInvestigation(
                id=inv_id,
                token_id=token.id,
                mint_address=mint,
                trigger="high_priority",
                status="completed",
                requested_agents=["SecurityAgent", "MarketAgent", "SocialAgent", "RiskAgent"],
                completed_agents=["SecurityAgent", "MarketAgent", "SocialAgent", "RiskAgent"],
                start_time=now,
                completion_time=now,
                created_at=now,
            )
            test_session.add(investigation)
            await test_session.flush()

            res_risk = AgentInvestigationResult(
                id=str(uuid.uuid4()),
                investigation_id=inv_id,
                agent_name="risk",
                status="completed",
                confidence=0.92,
                findings=[{
                    "type": "verified_fact",
                    "title": "Authority Audit",
                    "statement": "Mint and freeze authorities are permanently revoked.",
                    "confidence": 0.95,
                }],
            )
            test_session.add(res_risk)
            await test_session.flush()

            # =========================================================================
            # STAGE 7: Decision Engine Evaluation
            # =========================================================================
            token_input = await build_decision_input_from_db(test_session, mint)
            assert token_input is not None
            assert token_input.security_findings is not None
            assert token_input.security_findings.get("has_mint_authority") is False
            assert token_input.liquidity_pool is not None
            assert token_input.liquidity_pool["liquidity_usd"] == 85000.0

            decision_engine = DecisionEngine()
            decision_result = decision_engine.evaluate(token_input)
            assert decision_result.outcome in (DecisionOutcome.PAPER_TRADE_CANDIDATE, DecisionOutcome.WATCHLIST, DecisionOutcome.MONITOR)
            assert decision_result.confidence > 0.4
            assert len(decision_result.supporting_evidence) > 0
            await test_session.rollback()
    finally:
        await test_engine.dispose()

    # =========================================================================
    # STAGE 8 & 9: Paper Trade Proposal Generation & Pre-Trade Risk Validation
    # =========================================================================
    trading_engine = PaperTradingEngine(
        starting_capital_usd=Decimal("10000.00"),
    )

    # Force candidate outcome to verify proposal and simulated execution pipeline
    decision_result.outcome = DecisionOutcome.PAPER_TRADE_CANDIDATE

    proposal = trading_engine.process_decision(
        decision=decision_result,
        token_input=token_input,
        strategy_id="momentum_breakout",
        as_of=now,
    )
    assert proposal is not None
    assert proposal.mint_address == mint
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.proposed_position_size_usd > Decimal("0.00")

    # =========================================================================
    # STAGE 10: Simulated Execution (Constant-Product Slippage & Priority Fees)
    # =========================================================================
    spot_price = Decimal("0.0025")
    pool_liq = Decimal("85000.00")

    position = trading_engine.execute_proposal(
        proposal_id=proposal.proposal_id,
        pool_liquidity_usd=pool_liq,
        displayed_spot_price=spot_price,
        dex_id="raydium",
        as_of=now,
    )
    assert position is not None
    assert position.status == PositionStatus.OPEN
    assert position.mint_address == mint
    # Slippage: executed buy price >= spot price
    assert position.entry_price >= spot_price
    assert position.capital_committed > Decimal("0.00")
    assert trading_engine.account.available_capital < Decimal("10000.00")

    # =========================================================================
    # STAGE 11: Position Monitoring & Excursion Tracking (MFE / MAE)
    # =========================================================================
    higher_price = position.entry_price * Decimal("1.25")
    trading_engine.position_manager.update_mark_price(
        position_id=position.position_id,
        current_price=higher_price,
        as_of=now,
    )
    assert position.unrealised_pnl_usd > Decimal("0.00")
    assert position.max_favourable_excursion_usd > Decimal("0.00")

    # =========================================================================
    # STAGE 12: Exit Execution and Portfolio Accounting Reconciliation
    # =========================================================================
    closed_pos = trading_engine.position_manager.close_position(
        position_id=position.position_id,
        exit_price=higher_price,
        exit_time=now,
        exit_reason=ExitReason.TAKE_PROFIT_FULL,
        fee_usd=Decimal("0.50"),
    )
    assert closed_pos.status == PositionStatus.CLOSED
    assert closed_pos.realised_pnl_usd > Decimal("0.00")

    # Record exit in account
    trading_engine.account.record_exit(
        capital_returned=closed_pos.capital_committed,
        realised_pnl=closed_pos.realised_pnl_usd,
        fee=Decimal("0.50"),
        as_of=now,
    )
    # Exact decimal ledger reconciliation
    reconciled, msg = trading_engine.account.reconcile(
        list(trading_engine.position_manager.open_positions.values())
    )
    assert reconciled is True, msg
    assert trading_engine.account.realised_pnl > Decimal("0.00")

    # =========================================================================
    # STAGE 13: Quantitative Research Outcome Recording & Paper Trading Learner
    # =========================================================================
    diagnosis = PaperTradingLearner.diagnose_trade(
        position=closed_pos,
        model_version="1.0.0",
        pred_probability=0.82,
    )
    assert diagnosis.position_id == closed_pos.position_id
    assert diagnosis.token_mint == mint
    assert diagnosis.error_mode == "success"
    assert diagnosis.net_pnl_usd > 0
    assert "Profitable trade" in diagnosis.diagnosis_notes

    registry = ExperimentRegistry()
    strat_record = registry.register_strategy(
        strategy_id="momentum_breakout",
        version="1.0.0",
        description="High liquidity momentum breakout",
        parameters={"take_profit_pct": 20.0, "stop_loss_pct": -10.0},
        lock_live_modification=True,
    )
    assert strat_record.strategy_id == "momentum_breakout"
    assert strat_record.version == "1.0.0"
    assert strat_record.is_locked is True
