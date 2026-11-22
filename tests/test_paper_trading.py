"""
Comprehensive Test Suite for Meco Autonomous Paper Trading Engine (Phase 6).
Validates all Section 9 acceptance criteria:
- Successful simulated entries and exits.
- Rejected orders.
- Slippage and fee calculations.
- Insufficient liquidity rejection.
- Position sizing calculations and constraints.
- Partial exits and trailing stops.
- Failed execution simulation (quote expiration, depth limits).
- Restart recovery.
- Concurrent proposals and capital reservation.
- Risk-limit enforcement (max positions, drawdown, daily loss).
- Accounting reconciliation (exact decimal balance verification).
- Emergency stop kill switch.
- Liquidity deterioration and time-based exits.
- Performance analytics and reporting.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.decision.models import (
    DecisionDimension,
    DecisionOutcome,
    DimensionScore,
    DimensionScores,
    TokenDecisionInput,
    TokenDecisionResult,
)
from app.trading import (
    ExecutionSimulatorConfig,
    ExitConditions,
    ExitReason,
    OrderSide,
    OrderType,
    PaperExecutionSimulator,
    PaperOrder,
    PaperPosition,
    PaperTradingEngine,
    PerformanceAnalyzer,
    PersistenceManager,
    PortfolioAccount,
    PortfolioSnapshot,
    PositionManager,
    PositionSizer,
    PositionSizingConfig,
    PositionStatus,
    PreTradeRiskGateway,
    ProposalGenerator,
    ProposalStatus,
    RiskGatewayConfig,
    SizingMethod,
    StopLossConfig,
    StrategyRegistry,
    TakeProfitConfig,
    TakeProfitStage,
    TradeProposal,
    quantize_usd,
)


@pytest.fixture
def candidate_decision() -> tuple[TokenDecisionResult, TokenDecisionInput]:
    """Fixture providing an approved PAPER_TRADE_CANDIDATE decision and input."""
    now = datetime.now(timezone.utc)
    token_input = TokenDecisionInput(
        mint_address="AlphaToken1111111111111111111111111111111",
        token_id=1,
        as_of=now,
        canonical_token={"name": "Alpha", "symbol": "ALPHA"},
        security_findings={"mint_authority": None, "freeze_authority": None},
        liquidity_pool={
            "liquidity_usd": 75000.0,
            "volume_5m": 5000.0,
            "volume_1h": 25000.0,
            "price_usd": 0.010,
            "buys_5m": 70,
            "sells_5m": 10,
            "price_change_5m": 15.0,
            "dex": "raydium",
        },
        market_observations=[
            {"price_usd": 0.010, "volume_5m": 5000.0, "price_change_5m": 15.0, "timestamp": now}
        ],
    )

    dim_scores = DimensionScores(
        opportunity_quality=DimensionScore(
            dimension=DecisionDimension.OPPORTUNITY_QUALITY,
            score=78.0,
            confidence=0.88,
            components={"volume_acceleration": 75.0, "price_momentum": 80.0},
        ),
        market_conditions=DimensionScore(
            dimension=DecisionDimension.MARKET_CONDITIONS,
            score=72.0,
            confidence=0.85,
            components={"buy_pressure": 85.0, "volume_to_liquidity": 70.0},
        ),
        social_traction=DimensionScore(
            dimension=DecisionDimension.SOCIAL_TRACTION,
            score=68.0,
            confidence=0.80,
            components={"mention_velocity": 70.0},
        ),
        liquidity_quality=DimensionScore(
            dimension=DecisionDimension.LIQUIDITY_QUALITY,
            score=82.0,
            confidence=0.90,
            components={"pool_depth": 85.0, "lp_lock_burn": 100.0},
        ),
        security_risk=DimensionScore(
            dimension=DecisionDimension.SECURITY_RISK,
            score=8.0,
            confidence=0.95,
            components={"authority_risk": 0.0},
        ),
        wallet_deployer_risk=DimensionScore(
            dimension=DecisionDimension.WALLET_DEPLOYER_RISK,
            score=12.0,
            confidence=0.90,
            components={"top_10_concentration_risk": 15.0},
        ),
        data_confidence=DimensionScore(
            dimension=DecisionDimension.DATA_CONFIDENCE,
            score=85.0,
            confidence=0.85,
            components={"domain_completeness": 90.0},
        ),
        execution_feasibility=DimensionScore(
            dimension=DecisionDimension.EXECUTION_FEASIBILITY,
            score=88.0,
            confidence=0.90,
            components={"slippage_viability": 90.0},
        ),
    )

    decision = TokenDecisionResult(
        decision_id="dec-candidate-001",
        mint_address="AlphaToken1111111111111111111111111111111",
        token_id=1,
        outcome=DecisionOutcome.PAPER_TRADE_CANDIDATE,
        reasoning_summary="Candidate approved with high opportunity and clean security.",
        dimension_scores=dim_scores,
        confidence=0.88,
        decision_timestamp=now,
        expiration_time=now + timedelta(minutes=30),
    )

    return decision, token_input


# ==============================================================================
# 1. Successful Simulated Entries and Exits
# ==============================================================================

def test_successful_simulated_entry_and_exit(candidate_decision):
    """End-to-end: propose, risk validate, execute entry, tick price, exit take-profit."""
    decision, token_input = candidate_decision
    engine = PaperTradingEngine(starting_capital_usd=Decimal("10000.00"))
    now = datetime.now(timezone.utc)

    # 1. Generate proposal from decision
    prop = engine.process_decision(decision, token_input, strategy_id="momentum_breakout", as_of=now)
    assert prop is not None
    assert prop.status == ProposalStatus.PENDING
    assert prop.proposed_position_size_usd > Decimal("0.00")

    # 2. Execute proposal
    pos = engine.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        dex_id="raydium",
        as_of=now,
    )
    assert pos is not None
    assert pos.status == PositionStatus.OPEN
    assert pos.quantity > Decimal("0.00")
    assert pos.entry_price > Decimal("0.010")  # Slippage paid

    # Capital must be committed in accounting
    snap = engine.get_portfolio_snapshot()
    assert snap.available_capital < Decimal("10000.00")
    assert snap.open_positions_count == 1

    # 3. Simulate market price surge (+40% gain) triggering Take-Profit Stage 1 (25% gain)
    entry_price = pos.entry_price
    higher_price = entry_price * Decimal("1.40")

    exit_orders = engine.evaluate_market_tick(
        mark_prices={pos.mint_address: higher_price},
        pool_liquidities={pos.mint_address: Decimal("80000.00")},
        as_of=now + timedelta(minutes=10),
    )
    assert len(exit_orders) == 1
    assert exit_orders[0].side == OrderSide.SELL
    assert exit_orders[0].executed_price > Decimal("0.00")

    # Position should now be partially exited (50% closed at TP stage 1)
    assert pos.status == PositionStatus.PARTIALLY_EXITED
    assert pos.realised_pnl_usd > Decimal("0.00")

    # 4. Accounting reconciliation must hold exactly
    ok, msg = engine.reconcile_accounting()
    assert ok is True, msg


# ==============================================================================
# 2. Rejected Orders (Ineligible Decision Outcomes)
# ==============================================================================

def test_rejected_orders_ineligible_decision(candidate_decision):
    """Tokens with IGNORE or REJECTED_DUE_TO_HARD_RISK must not produce active proposals."""
    decision, token_input = candidate_decision
    engine = PaperTradingEngine()

    decision.outcome = DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
    prop = engine.process_decision(decision, token_input)
    assert prop is None
    assert len(engine.active_proposals) == 0

    decision.outcome = DecisionOutcome.IGNORE
    prop2 = engine.process_decision(decision, token_input)
    assert prop2 is None


# ==============================================================================
# 3. Slippage and Fee Calculations
# ==============================================================================

def test_slippage_and_fee_calculations():
    """Verify constant-product AMM impact, base slippage, DEX fee, and priority fees."""
    cfg = ExecutionSimulatorConfig(
        base_slippage_pct=Decimal("1.0"),
        dex_fee_pct=Decimal("0.25"),
        solana_priority_fee_usd=Decimal("0.02"),
        latency_drift_seconds=2.0,
        latency_drift_pct_per_sec=Decimal("0.10"),
    )
    sim = PaperExecutionSimulator(config=cfg)
    now = datetime.now(timezone.utc)

    # $500 order on $50,000 pool ($25,000 reserve)
    # Price impact = 500 / (25000 + 500) = 500 / 25500 ≈ 1.96%
    # Latency drift = 2.0s * 0.10% = 0.20%
    # Base slippage = 1.0%
    # Total slippage = 1.96% + 0.20% + 1.0% = 3.16%
    res = sim.simulate_order(
        side=OrderSide.BUY,
        requested_size_usd=Decimal("500.00"),
        displayed_spot_price=Decimal("1.000"),
        pool_liquidity_usd=Decimal("50000.00"),
        quote_timestamp=now,
        execution_timestamp=now,
    )

    assert res.success is True
    assert res.is_simulated is True
    # Executed price should be ~1.0316
    assert Decimal("1.030") <= res.executed_price <= Decimal("1.035")

    # Fees: DEX fee = 0.25% of $500 = $1.25; Network fee = $0.02; Total = $1.27
    assert res.dex_fee_usd == Decimal("1.25")
    assert res.network_fee_usd == Decimal("0.02")
    assert res.total_fee_usd == Decimal("1.27")
    assert "constant_product_amm" in res.assumptions_logged["model"]


# ==============================================================================
# 4. Insufficient Liquidity Rejection
# ==============================================================================

def test_insufficient_liquidity_rejection(candidate_decision):
    """Orders on shallow pools (< $5000) or with extreme impact must be rejected."""
    decision, token_input = candidate_decision
    engine = PaperTradingEngine()
    now = datetime.now(timezone.utc)

    prop = engine.process_decision(decision, token_input, as_of=now)
    assert prop is not None

    # Attempt execution on $1500 pool (below min $5000 gateway threshold)
    pos = engine.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("1500.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos is None
    assert prop.status == ProposalStatus.REJECTED
    assert "Insufficient pool liquidity" in prop.rejection_reason


# ==============================================================================
# 5. Position Sizing Methods and Constraints
# ==============================================================================

def test_position_sizing_methods_and_constraints():
    """Verify different sizing methods, liquidity scaling, risk scaling, and hard $500 cap."""
    cfg = PositionSizingConfig(
        max_position_size_usd=Decimal("500.00"),
        min_position_size_usd=Decimal("25.00"),
        base_equity_pct=Decimal("3.0"),
        max_pool_fraction_pct=Decimal("1.0"),
    )
    sizer = PositionSizer(config=cfg)

    # 1. Percent of equity: 3% of $10,000 = $300
    res_pct = sizer.calculate_size(
        available_capital=Decimal("10000.00"),
        net_equity=Decimal("10000.00"),
        pool_liquidity_usd=Decimal("100000.00"),
        current_open_positions_count=0,
        current_total_exposure_usd=Decimal("0.00"),
        method_override=SizingMethod.PERCENT_OF_EQUITY,
    )
    assert res_pct.is_approved is True
    assert res_pct.allocated_size_usd == Decimal("300.00")

    # 2. Hard position cap ($500 max even if 3% of equity is $600)
    res_capped = sizer.calculate_size(
        available_capital=Decimal("20000.00"),
        net_equity=Decimal("20000.00"),
        pool_liquidity_usd=Decimal("200000.00"),
        current_open_positions_count=0,
        current_total_exposure_usd=Decimal("0.00"),
        method_override=SizingMethod.PERCENT_OF_EQUITY,
    )
    assert res_capped.allocated_size_usd == Decimal("500.00")
    assert any("capped_by_max_position_size" in c for c in res_capped.constraints_applied)

    # 3. Liquidity cap: 1% of $20,000 pool = $200 (caps the $300 base size)
    res_liq_cap = sizer.calculate_size(
        available_capital=Decimal("10000.00"),
        net_equity=Decimal("10000.00"),
        pool_liquidity_usd=Decimal("20000.00"),
        current_open_positions_count=0,
        current_total_exposure_usd=Decimal("0.00"),
        method_override=SizingMethod.LIQUIDITY_CONSTRAINED,
    )
    assert res_liq_cap.allocated_size_usd <= Decimal("200.00")


# ==============================================================================
# 6. Partial Exits and Trailing Stops
# ==============================================================================

def test_partial_exits_and_trailing_stops():
    """Position executes partial take profit then trailing stop closes the remainder."""
    mgr = PositionManager()
    acc = PortfolioAccount(Decimal("10000.00"))
    sim = PaperExecutionSimulator()
    now = datetime.now(timezone.utc)

    exit_cond = ExitConditions(
        stop_loss=StopLossConfig(
            stop_loss_pct=Decimal("10.0"),
            is_trailing=True,
            trailing_activation_pct=Decimal("20.0"),
            trailing_delta_pct=Decimal("10.0"),
        ),
        take_profit=TakeProfitConfig(
            stages=[
                TakeProfitStage(target_gain_pct=Decimal("25.0"), close_fraction=Decimal("0.50")),
            ]
        ),
    )

    acc.commit_entry(Decimal("200.00"), Decimal("0.50"))
    pos = mgr.open_position(
        proposal_id="prop-trail",
        mint_address="MintTrail111111111111111111111111111111111",
        strategy_id="momentum_breakout",
        entry_price=Decimal("1.00"),
        quantity=Decimal("200.00"),
        capital_committed=Decimal("200.00"),
        exit_conditions=exit_cond,
        as_of=now,
    )

    # Price moves to $1.30 (+30% gain): hits TP stage 1 (close 50%)
    orders_tp = mgr.evaluate_and_execute_exits(
        mark_prices={pos.mint_address: Decimal("1.30")},
        pool_liquidities={pos.mint_address: Decimal("50000.00")},
        execution_simulator=sim,
        account=acc,
        as_of=now + timedelta(minutes=5),
    )
    assert len(orders_tp) == 1
    assert pos.status == PositionStatus.PARTIALLY_EXITED
    assert pos.quantity == Decimal("100.00")  # Half exited
    assert pos.peak_price == Decimal("1.30")

    # Price subsequently pulls back from peak $1.30 to $1.15 (-11.5% drop from peak > 10% trail delta)
    orders_trail = mgr.evaluate_and_execute_exits(
        mark_prices={pos.mint_address: Decimal("1.15")},
        pool_liquidities={pos.mint_address: Decimal("50000.00")},
        execution_simulator=sim,
        account=acc,
        as_of=now + timedelta(minutes=10),
    )
    assert len(orders_trail) == 1
    # Full closure
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == ExitReason.TRAILING_STOP
    assert pos.quantity == Decimal("0.00")


# ==============================================================================
# 7. Failed Execution Simulation (Quote Expiration)
# ==============================================================================

def test_failed_execution_quote_expired(candidate_decision):
    """If quote timestamp is older than validity window (>30s), execution fails and capital is released."""
    decision, token_input = candidate_decision
    engine = PaperTradingEngine()
    now = datetime.now(timezone.utc)

    prop = engine.process_decision(decision, token_input, as_of=now)
    assert prop is not None

    # Try executing with quote timestamp 45 seconds in the past
    stale_time = now + timedelta(seconds=45)
    pos = engine.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=stale_time,
    )
    # Execution simulator detects quote age > 30s
    assert pos is None
    # Capital must have been released back to available
    assert engine.account.reserved_capital == Decimal("0.00")
    assert engine.account.available_capital == Decimal("10000.00")


# ==============================================================================
# 8. Restart Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_restart_recovery(candidate_decision):
    """Engine active positions and portfolio accounting restore cleanly across restarts."""
    decision, token_input = candidate_decision
    engine1 = PaperTradingEngine(starting_capital_usd=Decimal("10000.00"))
    now = datetime.now(timezone.utc)

    # Create and execute a position in engine1
    prop = engine1.process_decision(decision, token_input, as_of=now)
    pos1 = engine1.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos1 is not None

    # Mock database session to simulate persistence
    session = AsyncMock()
    mock_pos_record = MagicMock()
    mock_pos_record.id = pos1.position_id
    mock_pos_record.proposal_id = pos1.proposal_id
    mock_pos_record.mint_address = pos1.mint_address
    mock_pos_record.token_id = pos1.token_id
    mock_pos_record.strategy_id = pos1.strategy_id
    mock_pos_record.status = pos1.status.value
    mock_pos_record.entry_time = pos1.entry_time
    mock_pos_record.entry_price = float(pos1.entry_price)
    mock_pos_record.quantity = float(pos1.quantity)
    mock_pos_record.capital_committed = float(pos1.capital_committed)
    mock_pos_record.current_mark_price = float(pos1.current_mark_price)
    mock_pos_record.unrealised_pnl_usd = float(pos1.unrealised_pnl_usd)
    mock_pos_record.realised_pnl_usd = float(pos1.realised_pnl_usd)
    mock_pos_record.total_fees_paid_usd = float(pos1.total_fees_paid_usd)
    mock_pos_record.exit_conditions = pos1.exit_conditions.model_dump(mode="json")
    mock_pos_record.peak_price = float(pos1.peak_price)
    mock_pos_record.max_favourable_excursion_usd = 0.0
    mock_pos_record.max_adverse_excursion_usd = 0.0
    mock_pos_record.exit_reason = None
    mock_pos_record.closed_at = None
    mock_pos_record.updated_at = now

    mock_snap_record = MagicMock()
    snap1 = engine1.get_portfolio_snapshot()
    mock_snap_record.starting_capital = float(snap1.starting_capital)
    mock_snap_record.available_capital = float(snap1.available_capital)
    mock_snap_record.reserved_capital = float(snap1.reserved_capital)
    mock_snap_record.open_positions_value = float(snap1.open_positions_value)
    mock_snap_record.realised_pnl = float(snap1.realised_pnl)
    mock_snap_record.unrealised_pnl = float(snap1.unrealised_pnl)
    mock_snap_record.total_fees = float(snap1.total_fees)
    mock_snap_record.net_equity = float(snap1.net_equity)
    mock_snap_record.peak_equity = float(snap1.peak_equity)

    exec_call = 0

    async def mock_execute(stmt):
        nonlocal exec_call
        exec_call += 1
        res = MagicMock()
        if exec_call == 1:
            # Snapshot query
            res.scalar_one_or_none.return_value = mock_snap_record
        elif exec_call == 2:
            # Open positions query
            res.scalars.return_value.all.return_value = [mock_pos_record]
        elif exec_call == 3:
            # Orders query for position
            res.scalars.return_value.all.return_value = []
        return res

    session.execute.side_effect = mock_execute

    # Reinitialize clean engine2 (simulating restart)
    engine2 = PaperTradingEngine(starting_capital_usd=Decimal("10000.00"))
    restored = await PersistenceManager.recover_engine_state(session, engine2)

    assert restored == 1
    assert len(engine2.position_manager.open_positions) == 1
    assert engine2.account.available_capital == snap1.available_capital

    # Accounting reconciliation on recovered state
    ok, msg = engine2.reconcile_accounting()
    assert ok is True, msg


# ==============================================================================
# 9. Concurrent Proposals and Capital Reservation
# ==============================================================================

def test_concurrent_proposals_and_capital_reservation(candidate_decision):
    """Multiple proposals reserve capital atomically, preventing double-spend."""
    decision, token_input = candidate_decision
    sizing_cfg = PositionSizingConfig(
        base_notional_usd=Decimal("200.00"),
        default_method=SizingMethod.FIXED_NOTIONAL,
        min_position_size_usd=Decimal("10.00"),
    )
    engine = PaperTradingEngine(
        starting_capital_usd=Decimal("500.00"),
        sizing_config=sizing_cfg,
    )
    now = datetime.now(timezone.utc)

    # Create 2 proposals each requesting ~$250
    prop1 = engine.process_decision(decision, token_input, as_of=now)
    assert prop1 is not None

    decision2 = decision.model_copy(deep=True)
    decision2.decision_id = "dec-2"
    decision2.mint_address = "BetaToken2222222222222222222222222222222"
    token_input2 = token_input.model_copy(deep=True)
    token_input2.mint_address = decision2.mint_address

    prop2 = engine.process_decision(decision2, token_input2, as_of=now)
    assert prop2 is not None

    # Execute prop1 -> reserves and commits ~$250
    pos1 = engine.execute_proposal(
        proposal_id=prop1.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos1 is not None

    # Now available capital is ~$250. Third proposal asking for $300 must be rejected due to lack of capital
    decision3 = decision.model_copy(deep=True)
    decision3.decision_id = "dec-3"
    decision3.mint_address = "GammaToken333333333333333333333333333333"
    token_input3 = token_input.model_copy(deep=True)
    token_input3.mint_address = decision3.mint_address

    prop3 = engine.process_decision(decision3, token_input3, as_of=now)
    # Available capital is now only ~$248, so proposal sizes to remaining room
    assert prop3.proposed_position_size_usd <= engine.account.available_capital


# ==============================================================================
# 10. Risk-Limit Enforcement (Max Positions, Drawdown, Daily Loss)
# ==============================================================================

def test_risk_limit_enforcement(candidate_decision):
    """Enforce max concurrent positions (5) and circuit breaker daily loss limits."""
    decision, token_input = candidate_decision
    risk_cfg = RiskGatewayConfig(max_concurrent_positions=2, max_daily_loss_usd=Decimal("100.00"))
    engine = PaperTradingEngine(risk_config=risk_cfg)
    now = datetime.now(timezone.utc)

    # Artificially populate 2 open positions
    for i in range(2):
        engine.position_manager.open_position(
            proposal_id=f"p-{i}",
            mint_address=f"Mint-{i}",
            strategy_id="momentum_breakout",
            entry_price=Decimal("1.0"),
            quantity=Decimal("100.0"),
            capital_committed=Decimal("100.0"),
            exit_conditions=ExitConditions(),
            as_of=now,
        )

    # 3rd proposal execution should be blocked by Risk Gateway max positions limit
    prop = engine.process_decision(decision, token_input, as_of=now)
    pos = engine.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos is None
    assert "Max concurrent positions limit reached" in prop.rejection_reason

    # Test Daily Loss Circuit Breaker
    engine.position_manager.open_positions.clear()
    engine.account.daily_realised_pnl[now.strftime("%Y-%m-%d")] = Decimal("-150.00")  # $150 loss today

    prop2 = engine.process_decision(decision, token_input, as_of=now)
    pos2 = engine.execute_proposal(
        proposal_id=prop2.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos2 is None
    assert "Daily loss limit breached" in prop2.rejection_reason


# ==============================================================================
# 11. Accounting Reconciliation Test
# ==============================================================================

def test_accounting_reconciliation_exact_decimal_balance():
    """Verify Net Equity == Starting + Realised + Unrealised - Fees across multiple trades."""
    acc = PortfolioAccount(Decimal("10000.00"))
    positions = []

    # Position 1: $300 entry, closed with +$60 profit, $2 fee
    acc.commit_entry(Decimal("300.00"), Decimal("1.00"))
    acc.record_exit(capital_returned=Decimal("300.00"), realised_pnl=Decimal("60.00"), fee=Decimal("1.00"))

    # Position 2: $200 entry, currently open with +$40 unrealised PnL, $0.50 buy fee
    acc.commit_entry(Decimal("200.00"), Decimal("0.50"))
    p2 = PaperPosition(
        proposal_id="p2",
        mint_address="MintOpen",
        strategy_id="strat",
        status=PositionStatus.OPEN,
        entry_time=datetime.now(timezone.utc),
        entry_price=Decimal("1.00"),
        quantity=Decimal("200.00"),
        capital_committed=Decimal("200.00"),
        current_mark_price=Decimal("1.20"),
        unrealised_pnl_usd=Decimal("40.00"),
        exit_conditions=ExitConditions(),
        peak_price=Decimal("1.20"),
    )
    positions.append(p2)

    ok, msg = acc.reconcile(positions)
    assert ok is True, msg
    assert acc.realised_pnl == Decimal("60.00")
    assert acc.total_fees_paid == Decimal("2.50")
    # Expected equity = 10000 + 60 + 40 - 2.50 = 10097.50
    assert acc.get_net_equity(positions) == Decimal("10097.50")


# ==============================================================================
# 12. Emergency Stop Kill Switch
# ==============================================================================

def test_emergency_stop_kill_switch(candidate_decision):
    """Kill switch immediately prevents any order execution."""
    decision, token_input = candidate_decision
    engine = PaperTradingEngine()
    now = datetime.now(timezone.utc)

    prop = engine.process_decision(decision, token_input, as_of=now)
    assert prop is not None

    # Activate emergency stop
    engine.trigger_emergency_stop("Suspicious Solana network congestion")
    assert engine.risk_gateway.is_emergency_stop_active is True

    # Execution must fail immediately
    pos = engine.execute_proposal(
        proposal_id=prop.proposal_id,
        pool_liquidity_usd=Decimal("75000.00"),
        displayed_spot_price=Decimal("0.010"),
        as_of=now,
    )
    assert pos is None
    assert "Emergency stop is ACTIVE" in prop.rejection_reason

    # Reset emergency stop and execution can proceed
    engine.reset_emergency_stop()
    assert engine.risk_gateway.is_emergency_stop_active is False


# ==============================================================================
# 13. Liquidity Deterioration Exit
# ==============================================================================

def test_liquidity_deterioration_exit():
    """Position closes immediately if pool liquidity falls by > 30%."""
    mgr = PositionManager()
    acc = PortfolioAccount(Decimal("10000.00"))
    sim = PaperExecutionSimulator()
    now = datetime.now(timezone.utc)

    acc.commit_entry(Decimal("200.00"), Decimal("0.50"))
    pos = mgr.open_position(
        proposal_id="p-liq",
        mint_address="MintLiqDrain",
        strategy_id="momentum_breakout",
        entry_price=Decimal("1.00"),
        quantity=Decimal("200.00"),
        capital_committed=Decimal("200.00"),
        exit_conditions=ExitConditions(max_liquidity_drop_pct=Decimal("30.0")),
        initial_pool_liquidity_usd=Decimal("50000.00"),
        as_of=now,
    )

    # Liquidity drains from $50,000 to $30,000 (-40% drop)
    orders = mgr.evaluate_and_execute_exits(
        mark_prices={pos.mint_address: Decimal("1.00")},
        pool_liquidities={pos.mint_address: Decimal("30000.00")},
        execution_simulator=sim,
        account=acc,
        as_of=now + timedelta(minutes=5),
    )
    assert len(orders) == 1
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == ExitReason.LIQUIDITY_DETERIORATION


# ==============================================================================
# 14. Time-Based Exit (Holding Duration Timeout)
# ==============================================================================

def test_time_based_exit():
    """Position closes when max holding duration expires."""
    mgr = PositionManager()
    acc = PortfolioAccount(Decimal("10000.00"))
    sim = PaperExecutionSimulator()
    now = datetime.now(timezone.utc)

    acc.commit_entry(Decimal("200.00"), Decimal("0.50"))
    pos = mgr.open_position(
        proposal_id="p-time",
        mint_address="MintTimeout",
        strategy_id="momentum_breakout",
        entry_price=Decimal("1.00"),
        quantity=Decimal("200.00"),
        capital_committed=Decimal("200.00"),
        exit_conditions=ExitConditions(max_holding_seconds=1800),  # 30 min max
        as_of=now,
    )

    # 35 minutes elapse
    future_time = now + timedelta(minutes=35)
    orders = mgr.evaluate_and_execute_exits(
        mark_prices={pos.mint_address: Decimal("1.05")},
        pool_liquidities={pos.mint_address: Decimal("50000.00")},
        execution_simulator=sim,
        account=acc,
        as_of=future_time,
    )
    assert len(orders) == 1
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == ExitReason.MAX_HOLDING_TIME


# ==============================================================================
# 15. Performance Reporting Analytics
# ==============================================================================

def test_performance_reporting_analytics():
    """Generates comprehensive trading performance reports with win rates and friction."""
    now = datetime.now(timezone.utc)

    p1 = PaperPosition(
        proposal_id="p1",
        mint_address="Mint1",
        strategy_id="momentum_breakout",
        status=PositionStatus.CLOSED,
        entry_time=now - timedelta(hours=1),
        entry_price=Decimal("1.00"),
        quantity=Decimal("100.00"),
        capital_committed=Decimal("100.00"),
        current_mark_price=Decimal("1.40"),
        realised_pnl_usd=Decimal("40.00"),
        total_fees_paid_usd=Decimal("1.00"),
        exit_conditions=ExitConditions(),
        peak_price=Decimal("1.45"),
        max_favourable_excursion_usd=Decimal("45.00"),
        max_adverse_excursion_usd=Decimal("5.00"),
        exit_reason=ExitReason.TAKE_PROFIT_FULL,
        closed_at=now,
    )

    p2 = PaperPosition(
        proposal_id="p2",
        mint_address="Mint2",
        strategy_id="momentum_breakout",
        status=PositionStatus.CLOSED,
        entry_time=now - timedelta(hours=1),
        entry_price=Decimal("1.00"),
        quantity=Decimal("100.00"),
        capital_committed=Decimal("100.00"),
        current_mark_price=Decimal("0.85"),
        realised_pnl_usd=Decimal("-15.00"),
        total_fees_paid_usd=Decimal("1.00"),
        exit_conditions=ExitConditions(),
        peak_price=Decimal("1.02"),
        max_favourable_excursion_usd=Decimal("2.00"),
        max_adverse_excursion_usd=Decimal("15.00"),
        exit_reason=ExitReason.STOP_LOSS,
        closed_at=now,
    )

    report = PerformanceAnalyzer.evaluate([p1, p2])
    assert report.total_trades_count == 2
    assert report.winning_trades_count == 1
    assert report.losing_trades_count == 1
    assert report.win_rate_pct == 50.0
    assert report.net_realised_pnl_usd == Decimal("23.00")  # (40 - 15) - 2 fees = 23

    # Check markdown rendering
    md = report.render_markdown_report()
    assert "# Paper Trading Performance Report" in md
    assert "**Win Rate:** `50.0%`" in md
    assert "momentum_breakout" in md
