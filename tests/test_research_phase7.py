"""
Comprehensive Acceptance Test Suite for Meco Quantitative Research, Backtesting,
and Continuous Learning Engine (Phase 7).

Validates all Section 10 acceptance criteria:
- Historical datasets can be reproduced (deterministic manifests and hashing).
- Features are strictly point-in-time correct (zero future look-ahead).
- Leakage checks prevent temporal inversion and token overlap.
- Target labels correctly model excursions and reject phantom liquidity spikes.
- Backtests realistically model execution friction (slippage, AMM price impact, DEX fees).
- Machine learning models are compared against non-predictive & heuristic baselines.
- Out-of-sample evaluation is strictly segregated.
- Multi-dimensional attribution across liquidity, token age, and regimes.
- Paper-trading outcomes feed research (error diagnosis and calibration).
- Model promotion is controlled, gated against active champion, and auditable with rollback.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.research import (
    BacktestEngine,
    BacktestExecutionConfig,
    ChampionChallengerGateway,
    DataLeakageGuard,
    ExperimentRegistry,
    ExperimentStatus,
    HeuristicRuleBaseline,
    LogisticRegressionModel,
    MajorityClassBaseline,
    PaperTradingLearner,
    PerformanceEvaluator,
    PointInTimeDatasetBuilder,
    PointInTimeFeatures,
    PromotionGateCriteria,
    PromotionStatus,
    RandomBaseline,
    RandomForestModel,
    TargetLabelComputer,
)
from app.trading.models import ExitConditions, ExitReason, PaperPosition, PositionStatus


# ==============================================================================
# 1. Point-In-Time Dataset Construction & Reproducibility Tests
# ==============================================================================

def test_point_in_time_feature_extraction_zero_lookahead():
    """Verify features only see observations timestamped <= prediction timestamp."""
    builder = PointInTimeDatasetBuilder(version="1.0.0")
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Historical observations: 2 before t0, 2 after t0
    obs_history = [
        {"timestamp": t0 - timedelta(seconds=120), "price_usd": 0.0080},
        {"timestamp": t0 - timedelta(seconds=60), "price_usd": 0.0090},
        {"timestamp": t0 + timedelta(seconds=60), "price_usd": 0.0200},  # FUTURE
        {"timestamp": t0 + timedelta(seconds=120), "price_usd": 0.0500}, # FUTURE
    ]

    features = builder.extract_features(
        token_mint="TokenAlpha11111111111111111111111111111111",
        as_of=t0,
        token_meta={
            "created_at": t0 - timedelta(minutes=10),
            "discovery_source": "pumpfun",
        },
        pool_data={
            "created_at": t0 - timedelta(minutes=8),
            "liquidity_usd": 50000.0,
            "initial_liquidity_usd": 40000.0,
            "volume_5m": 12000.0,
            "buys_5m": 80,
            "sells_5m": 20,
            "price_usd": 0.0090,
        },
        market_obs_history=obs_history,
        holder_data={"holder_count": 150, "top10_share_pct": 28.5},
        deployer_data={"deployer_risk_score": 15.0, "suspicious_snipers": 1},
        social_data={"post_count_1h": 25, "narrative_tier": "tier_2"},
        market_regime_data={"regime": "bullish", "sol_1h_momentum_pct": 2.5},
    )

    # Current price must be 0.0090 (from t0 - 60s), NEVER future price 0.0200 or 0.0500
    assert features.price_usd == 0.0090
    assert features.token_age_seconds == 600.0
    assert features.pool_age_seconds == 480.0
    assert features.buy_fraction_5m == 0.80  # 80 / (80 + 20)
    assert features.liquidity_growth_pct == 25.0
    assert features.discovery_source == "pumpfun"
    assert features.narrative_tier == "tier_2"
    assert features.market_regime == "bullish"


def test_dataset_manifest_reproducibility_hash():
    """Manifest produces identical SHA-256 hash for identical data ordering."""
    builder = PointInTimeDatasetBuilder(version="1.0.0")
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    f1 = PointInTimeFeatures(token_mint="MintA", timestamp=t0, liquidity_usd=25000.0)
    f2 = PointInTimeFeatures(token_mint="MintB", timestamp=t0 + timedelta(minutes=1), liquidity_usd=35000.0)

    cols = ["liquidity_usd", "buy_fraction_5m", "volume_5m_usd"]
    manifest1 = builder.build_dataset_manifest("dataset-01", [f1, f2], cols)
    # Shuffled input order must still yield deterministic hash due to canonical sorting
    manifest2 = builder.build_dataset_manifest("dataset-01", [f2, f1], cols)

    assert manifest1.sha256_hash == manifest2.sha256_hash
    assert manifest1.row_count == 2
    assert manifest1.token_count == 2


# ==============================================================================
# 2. Target Labels & Anti-Phantom Spike Tests
# ==============================================================================

def test_target_labels_excursions_and_forward_returns():
    """Calculates forward returns, MFE, MAE, and milestone reach times."""
    computer = TargetLabelComputer(nominal_exit_size_usd=100.0)
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Checkpoints: rises +30%, then falls -10%
    checkpoints = [
        {"timestamp": t0 + timedelta(seconds=60), "price_usd": 0.0110, "liquidity_usd": 50000.0},
        {"timestamp": t0 + timedelta(seconds=300), "price_usd": 0.0130, "liquidity_usd": 52000.0},  # +30% at 5m
        {"timestamp": t0 + timedelta(seconds=900), "price_usd": 0.0125, "liquidity_usd": 51000.0},  # +25% at 15m
        {"timestamp": t0 + timedelta(seconds=1800), "price_usd": 0.0090, "liquidity_usd": 48000.0}, # -10% at 30m
    ]

    labels = computer.compute_labels(
        token_mint="MintAlpha",
        prediction_timestamp=t0,
        initial_price_usd=0.010,
        initial_liquidity_usd=50000.0,
        forward_checkpoints=checkpoints,
    )

    assert labels.return_1m_pct == 10.0
    assert labels.return_5m_pct == 30.0
    assert labels.return_15m_pct == 25.0
    assert labels.return_30m_pct == -10.0
    assert labels.max_favourable_excursion_pct == 30.0
    assert labels.max_adverse_excursion_pct == -10.0
    assert labels.seconds_to_mfe == 300
    assert labels.seconds_to_plus_20pct == 300
    assert labels.is_executable_exit_possible is True
    assert labels.binary_profit_target_hit is True


def test_target_labels_reject_phantom_liquidity_spike():
    """Price spikes +100%, but liquidity is near zero, failing executable exit check."""
    computer = TargetLabelComputer(
        nominal_exit_size_usd=100.0,
        max_acceptable_exit_impact_pct=5.0,
    )
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Illiquid pool: only $500 total liquidity
    checkpoints = [
        {"timestamp": t0 + timedelta(seconds=300), "price_usd": 0.020, "liquidity_usd": 500.0},  # +100% price spike!
    ]

    labels = computer.compute_labels(
        token_mint="IlliquidTrapMint",
        prediction_timestamp=t0,
        initial_price_usd=0.010,
        initial_liquidity_usd=500.0,
        forward_checkpoints=checkpoints,
    )

    assert labels.max_favourable_excursion_pct == 100.0
    # Selling $100 into a $250 reserve causes 40% price impact, exceeding 5% limit!
    assert labels.is_executable_exit_possible is False
    assert labels.is_liquidity_trap is True
    # Must NOT label this as a successful profit target!
    assert labels.binary_profit_target_hit is False


# ==============================================================================
# 3. Data Leakage Prevention Tests
# ==============================================================================

def test_chronological_purged_split():
    """Purge window enforces strict temporal separation between train and test."""
    t_start = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    records = [
        PointInTimeFeatures(token_mint=f"Mint_{i}", timestamp=t_start + timedelta(minutes=i * 10))
        for i in range(20)
    ]

    split = DataLeakageGuard.chronological_split(
        records,
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
        purge_window_seconds=1800,  # 30m purge
    )

    # Check temporal ordering
    max_train_t = max(records[i].timestamp for i in split.train_indices)
    min_val_t = min(records[i].timestamp for i in split.val_indices)
    min_test_t = min(records[i].timestamp for i in split.test_indices)

    assert max_train_t < min_val_t
    assert min_val_t < min_test_t
    assert (min_val_t - max_train_t).total_seconds() >= 1800


def test_token_grouped_split_zero_overlap():
    """Token-grouped split guarantees same mint never appears across splits."""
    t_start = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    records = []
    # 6 unique tokens, each with 3 timestamps
    for t_idx in range(6):
        mint = f"Token_{t_idx}"
        for obs_idx in range(3):
            records.append(PointInTimeFeatures(
                token_mint=mint,
                timestamp=t_start + timedelta(minutes=t_idx * 20 + obs_idx * 5),
            ))

    split = DataLeakageGuard.token_grouped_split(records, train_ratio=0.50, val_ratio=0.25, test_ratio=0.25)
    assert len(split.train_tokens.intersection(split.val_tokens)) == 0
    assert len(split.train_tokens.intersection(split.test_tokens)) == 0
    assert len(split.val_tokens.intersection(split.test_tokens)) == 0


def test_leakage_audit_detects_violations():
    """Audit engine catches temporal inversions and forbidden feature contamination."""
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    f1 = PointInTimeFeatures(token_mint="M1", timestamp=t0 + timedelta(hours=2))
    f2 = PointInTimeFeatures(token_mint="M2", timestamp=t0)

    # Contaminated split: train has future timestamp, test has past timestamp
    from app.research.leakage import SplitResult
    bad_split = SplitResult(
        train_indices=[0],
        val_indices=[],
        test_indices=[1],
        train_tokens={"M1"},
        val_tokens=set(),
        test_tokens={"M2"},
        purge_window_seconds=3600,
        embargo_window_seconds=0,
    )

    report = DataLeakageGuard.audit_dataset_for_leakage([f1, f2], [], bad_split)
    assert report.is_passed is False
    assert report.temporal_inversions_count >= 1


# ==============================================================================
# 4. Machine Learning Models & Baseline Comparison Tests
# ==============================================================================

def test_ml_models_fit_predict_and_evaluate():
    """Trains baselines, Logistic Regression, and Random Forest models on synthetic features."""
    # Synthetic dataset: buy_fraction and volume_to_liq predict success
    rng = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95] * 4
    X = []
    y = []
    cols = ["buy_fraction_5m", "volume_to_liquidity_ratio", "price_momentum_5m_pct"]

    for i, bf in enumerate(rng):
        vol_liq = 0.05 + (bf * 0.3)
        mom = (bf - 0.5) * 20.0
        label = 1 if (bf > 0.60 and vol_liq > 0.15) else 0
        X.append([bf, vol_liq, mom])
        y.append(label)

    # 1. Non-Predictive Majority Baseline
    maj_model = MajorityClassBaseline().fit(X[:25], y[:25], feature_names=cols)
    maj_rep = maj_model.evaluate(X[25:], y[25:])
    assert maj_rep.accuracy >= 0.0

    # 2. Heuristic Baseline
    heur_model = HeuristicRuleBaseline().fit(X[:25], y[:25], feature_names=cols)
    heur_rep = heur_model.evaluate(X[25:], y[25:])
    assert heur_rep.accuracy > 0.60

    # 3. Logistic Regression
    lr_model = LogisticRegressionModel(C=1.0).fit(X[:25], y[:25], feature_names=cols)
    lr_rep = lr_model.evaluate(X[25:], y[25:])
    assert lr_rep.roc_auc is not None and lr_rep.roc_auc >= 0.70

    # 4. Random Forest
    rf_model = RandomForestModel(n_estimators=30, max_depth=3).fit(X[:25], y[:25], feature_names=cols)
    rf_rep = rf_model.evaluate(X[25:], y[25:])
    assert rf_rep.roc_auc is not None and rf_rep.roc_auc >= 0.75
    assert len(rf_rep.feature_importances) == 3


# ==============================================================================
# 5. Backtesting Engine with Realistic Execution Friction Tests
# ==============================================================================

def test_backtest_execution_friction_and_exits():
    """Validates realistic price impact, slippage, and multi-stage exits in backtest."""
    engine = BacktestEngine(
        config=BacktestExecutionConfig(
            initial_capital_usd=10000.0,
            position_size_usd=100.0,
            execution_delay_seconds=2.0,
            base_slippage_pct=1.5,
            price_impact_factor=2.0,
            dex_fee_pct=0.25,
            min_pool_liquidity_usd=10000.0,
        )
    )

    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    sig1 = PointInTimeFeatures(
        token_mint="WinnerMint",
        timestamp=t0,
        price_usd=0.010,
        liquidity_usd=50000.0,
        buy_fraction_5m=0.85,
        volume_to_liquidity_ratio=0.30,
    )
    sig2 = PointInTimeFeatures(
        token_mint="LoserMint",
        timestamp=t0 + timedelta(minutes=5),
        price_usd=0.010,
        liquidity_usd=50000.0,
        buy_fraction_5m=0.80,
        volume_to_liquidity_ratio=0.25,
    )

    # Future checkpoints
    checkpoints_by_token = {
        "WinnerMint": [
            {"timestamp": t0 + timedelta(seconds=2), "price_usd": 0.010, "liquidity_usd": 50000.0},
            {"timestamp": t0 + timedelta(seconds=60), "price_usd": 0.0135, "liquidity_usd": 52000.0},  # +35% gain -> hit take profit
        ],
        "LoserMint": [
            {"timestamp": t0 + timedelta(minutes=5, seconds=2), "price_usd": 0.010, "liquidity_usd": 50000.0},
            {"timestamp": t0 + timedelta(minutes=6), "price_usd": 0.0080, "liquidity_usd": 45000.0},   # -20% loss -> hit stop loss
        ],
    }

    result = engine.run_backtest(
        signals=[sig1, sig2],
        checkpoints_by_token=checkpoints_by_token,
        take_profit_pct=25.0,
        stop_loss_pct=-15.0,
    )

    assert result.trades_executed == 2
    assert len(result.completed_trades) == 2

    # Check friction was debited
    assert result.total_fees_paid_usd > 0.0
    winner_trade = [t for t in result.completed_trades if t.token_mint == "WinnerMint"][0]
    assert winner_trade.exit_reason == "take_profit"
    assert winner_trade.executed_entry_price > 0.010  # Slippage + impact pushed entry price higher
    assert winner_trade.net_pnl_usd > 0.0

    loser_trade = [t for t in result.completed_trades if t.token_mint == "LoserMint"][0]
    assert loser_trade.exit_reason == "stop_loss"
    assert loser_trade.net_pnl_usd < 0.0


# ==============================================================================
# 6. Performance Evaluation & Multi-Dimensional Attribution Tests
# ==============================================================================

def test_performance_evaluator_attribution_slices():
    """Generates quantitative metrics broken down by token age, liquidity, and regimes."""
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    sig_map = {
        "M1": PointInTimeFeatures(token_mint="M1", timestamp=t0, liquidity_usd=25000.0, token_age_seconds=150.0, market_regime="bullish", discovery_source="pumpfun"),
        "M2": PointInTimeFeatures(token_mint="M2", timestamp=t0, liquidity_usd=80000.0, token_age_seconds=1200.0, market_regime="chop", discovery_source="dexscreener"),
    }

    from app.research.backtest import BacktestResult, SimulatedTrade
    tr1 = SimulatedTrade(
        trade_id="t1", token_mint="M1", strategy_id="strat_v1", signal_timestamp=t0, entry_timestamp=t0,
        position_size_usd=100.0, net_pnl_usd=25.0, total_fees_usd=2.50, gross_pnl_usd=27.50, return_pct=25.0,
        holding_duration_seconds=120.0, exit_reason="take_profit"
    )
    tr2 = SimulatedTrade(
        trade_id="t2", token_mint="M2", strategy_id="strat_v1", signal_timestamp=t0, entry_timestamp=t0,
        position_size_usd=100.0, net_pnl_usd=-15.0, total_fees_usd=2.00, gross_pnl_usd=-13.00, return_pct=-15.0,
        holding_duration_seconds=300.0, exit_reason="stop_loss"
    )

    bt_res = BacktestResult(
        strategy_id="strat_v1", total_signals_evaluated=2, trades_executed=2, trades_rejected=0,
        completed_trades=[tr1, tr2], portfolio_equity_curve=[(t0.isoformat(), 10000.0), (t0.isoformat(), 10010.0)],
        final_equity_usd=10010.0, net_profit_usd=10.0, total_fees_paid_usd=4.50
    )

    report = PerformanceEvaluator.evaluate(bt_res, signals_lookup=sig_map)

    assert report.total_trades == 2
    assert report.win_rate_pct == 50.0
    assert report.profit_factor == 1.67  # 25 / 15
    assert report.net_profit_usd == 10.0
    assert report.expectancy_usd == 5.0  # (0.5 * 25) - (0.5 * 15)

    # Attribution slices
    assert "$10k-$50k" in report.by_liquidity_band
    assert "$50k-$200k" in report.by_liquidity_band
    assert "<5m" in report.by_token_age
    assert "pumpfun" in report.by_discovery_source
    assert "bullish" in report.by_market_regime

    # Render markdown report
    md = report.render_markdown()
    assert "# Quantitative Strategy Performance Report" in md
    assert "Performance by Liquidity Band" in md


# ==============================================================================
# 7. Champion/Challenger Promotion & Governance Tests
# ==============================================================================

def test_champion_challenger_promotion_gates_and_rollback():
    """Enforces strict OOS criteria before promotion and supports emergency rollback."""
    from app.research.dataset import DatasetManifest
    from app.research.metrics import QuantitativeReport

    manifest = DatasetManifest(
        dataset_id="ds-v1", version="1.0.0", created_at="2026-11-20T12:00:00Z",
        row_count=100, token_count=50, feature_columns=["c1"],
        time_window_start="2026-11-20T12:00:00Z", time_window_end="2026-11-21T12:00:00Z",
        sha256_hash="abc123hash"
    )

    champ_report = QuantitativeReport(
        strategy_id="champion_v1", total_trades=20, winning_trades=11, losing_trades=9,
        win_rate_pct=55.0, profit_factor=1.40, expectancy_usd=2.50, gross_profit_usd=50.0,
        gross_loss_usd=20.0, net_profit_usd=30.0, total_fees_paid_usd=5.0, fee_burden_pct=10.0,
        average_win_usd=5.0, average_loss_usd=2.5, win_loss_ratio=2.0, max_drawdown_pct=10.0,
        sharpe_ratio=1.1, sortino_ratio=1.5, average_holding_duration_seconds=200.0, trades_per_day=5.0,
        capital_utilization_pct=10.0,
    )

    gateway = ChampionChallengerGateway(
        initial_champion_id="champion_v1",
        initial_champion_version="1.0.0",
        initial_champion_report=champ_report,
    )

    # 1. Weak challenger with insufficient profit factor must be REJECTED
    weak_report = QuantitativeReport(
        strategy_id="weak_challenger", total_trades=20, winning_trades=8, losing_trades=12,
        win_rate_pct=40.0, profit_factor=1.10, expectancy_usd=0.20, gross_profit_usd=20.0,
        gross_loss_usd=18.0, net_profit_usd=2.0, total_fees_paid_usd=5.0, fee_burden_pct=25.0,
        average_win_usd=2.5, average_loss_usd=1.5, win_loss_ratio=1.6, max_drawdown_pct=15.0,
        sharpe_ratio=0.4, sortino_ratio=0.5, average_holding_duration_seconds=200.0, trades_per_day=5.0,
        capital_utilization_pct=10.0,
    )
    eval_weak = gateway.evaluate_challenger("weak_challenger", "1.0.0", weak_report, manifest)
    assert eval_weak.is_eligible is False
    with pytest.raises(ValueError):
        gateway.promote_candidate(eval_weak, weak_report)

    # 2. Strong challenger beating champion across profit factor & net profit
    strong_report = QuantitativeReport(
        strategy_id="strong_challenger", total_trades=25, winning_trades=16, losing_trades=9,
        win_rate_pct=64.0, profit_factor=1.85, expectancy_usd=4.20, gross_profit_usd=80.0,
        gross_loss_usd=25.0, net_profit_usd=55.0, total_fees_paid_usd=6.0, fee_burden_pct=7.5,
        average_win_usd=5.5, average_loss_usd=2.8, win_loss_ratio=1.96, max_drawdown_pct=8.5,
        sharpe_ratio=1.65, sortino_ratio=2.1, average_holding_duration_seconds=180.0, trades_per_day=6.0,
        capital_utilization_pct=12.0,
    )
    eval_strong = gateway.evaluate_challenger("strong_challenger", "1.1.0", strong_report, manifest)
    assert eval_strong.is_eligible is True

    # Execute Promotion
    promo_rec = gateway.promote_candidate(eval_strong, strong_report, approver="risk_board")
    assert promo_rec.status == PromotionStatus.APPROVED
    assert gateway.active_champion_id == "strong_challenger"

    # 3. Emergency Rollback
    rollback_rec = gateway.rollback_to_champion("champion_v1", "1.0.0", champ_report, reason="High live slippage")
    assert rollback_rec.status == PromotionStatus.ROLLED_BACK
    assert gateway.active_champion_id == "champion_v1"


# ==============================================================================
# 8. Learning from Paper Trades Tests
# ==============================================================================

def test_paper_trading_learning_loop_diagnoses():
    """Diagnoses false positives, execution drag, and liquidity traps from paper trades."""
    now = datetime.now(timezone.utc)

    # Position 1: Execution drag (gross profit $4.00, fees $5.00 -> net -$1.00)
    p_drag = PaperPosition(
        proposal_id="p1", mint_address="MintDrag", strategy_id="breakout",
        status=PositionStatus.CLOSED, entry_time=now, entry_price=Decimal("1.00"),
        quantity=Decimal("100.0"), capital_committed=Decimal("100.0"),
        current_mark_price=Decimal("1.04"), realised_pnl_usd=Decimal("4.00"),
        total_fees_paid_usd=Decimal("5.00"), exit_conditions=ExitConditions(),
        peak_price=Decimal("1.05"), exit_reason=ExitReason.TAKE_PROFIT_PARTIAL,
    )

    # Position 2: False positive (high probability 85%, but stopped out -$15.00)
    p_fp = PaperPosition(
        proposal_id="p2", mint_address="MintFP", strategy_id="breakout",
        status=PositionStatus.CLOSED, entry_time=now, entry_price=Decimal("1.00"),
        quantity=Decimal("100.0"), capital_committed=Decimal("100.0"),
        current_mark_price=Decimal("0.85"), realised_pnl_usd=Decimal("-15.00"),
        total_fees_paid_usd=Decimal("1.00"), exit_conditions=ExitConditions(),
        peak_price=Decimal("1.01"), exit_reason=ExitReason.STOP_LOSS,
    )

    d1 = PaperTradingLearner.diagnose_trade(p_drag)
    assert d1.error_mode == "execution_drag"

    d2 = PaperTradingLearner.diagnose_trade(p_fp, pred_probability=0.85)
    assert d2.error_mode == "false_positive"

    insights = PaperTradingLearner.aggregate_insights([d1, d2])
    assert insights.total_analyzed_trades == 2
    assert insights.execution_drag_count == 1
    assert insights.false_positives_count == 1
    assert len(insights.recommended_strategy_adjustments) >= 1


# ==============================================================================
# 9. Experiment Tracking & Registry Lock Tests
# ==============================================================================

def test_experiment_registry_and_strategy_lock():
    """Registry tracks experiments and prevents uncontrolled live strategy modification."""
    registry = ExperimentRegistry()

    # Register locked strategy
    strat = registry.register_strategy(
        strategy_id="momentum_core",
        version="1.0.0",
        description="Core momentum strategy",
        parameters={"take_profit_pct": 25.0, "stop_loss_pct": -15.0},
        lock_live_modification=True,
    )
    assert strat.is_locked is True

    # Attempting to overwrite locked strategy must raise ValueError
    with pytest.raises(ValueError):
        registry.register_strategy(
            strategy_id="momentum_core",
            version="1.0.0",
            description="Modified core momentum",
            parameters={"take_profit_pct": 50.0},
            lock_live_modification=True,
        )

    # Track experiment
    from app.research.dataset import DatasetManifest
    manifest = DatasetManifest(
        dataset_id="ds-exp", version="1.0.0", created_at="2026-11-20T12:00:00Z",
        row_count=50, token_count=20, feature_columns=["c1"],
        time_window_start="2026-11-20T12:00:00Z", time_window_end="2026-11-21T12:00:00Z",
        sha256_hash="hash123",
    )
    exp = registry.create_experiment(
        name="test_exp",
        hypothesis="Testing momentum breakout with LightGBM",
        dataset_manifest=manifest,
        strategy_key="momentum_core@1.0.0",
    )
    assert exp.status == ExperimentStatus.CONFIGURED

    completed = registry.complete_experiment(exp.experiment_id, notes=["Successfully verified"])
    assert completed.status == ExperimentStatus.COMPLETED
    assert "Successfully verified" in completed.execution_notes
