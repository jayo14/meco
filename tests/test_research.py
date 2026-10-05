from datetime import datetime, timezone
import pytest

from app.database.models import MarketObservation, MarketPairObservation, Signal
from app.research.anomalies import detect_all_anomalies, filter_usable_signals
from app.research.audit import (
    build_audit_report,
    calculate_mean,
    calculate_median,
)
from app.research.features import (
    extract_signal_features,
    pearson_correlation,
    spearman_rank_correlation,
)
from app.research.hypotheses import chronological_split
from app.research.loader import (
    group_observations_by_signal,
    group_pairs_by_signal,
)
from app.research.models import ExclusionCriteria
from app.research.outcomes import aggregate_outcomes, calculate_signal_outcome
from app.research.simulation import ExecutionConfig, simulate_paper_trade


def create_mock_signal(
    id: int,
    token_address: str = "TestMint11111111111111111111111111111111111",
    price_usd: float = 0.001,
    liquidity_usd: float = 25000.0,
    volume_5m: float = 10000.0,
    buys_5m: int = 150,
    sells_5m: int = 100,
    source_name: str | None = "Bullish Calls - Solana",
    market_status: str = "available",
    validation_status: str = "valid",
    message_created_at: datetime | None = None,
    received_at: datetime | None = None,
    dex_id: str = "pumpswap",
) -> Signal:
    dt = message_created_at or datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    rec = received_at or datetime(2026, 10, 2, 12, 0, 2, tzinfo=timezone.utc)
    s = Signal(
        id=id,
        chat_id=-100123456,
        message_id=id * 10,
        message_text="Test call",
        message_created_at=dt,
        received_at=rec,
        source_name=source_name,
        source_username="test_channel",
        token_address=token_address,
        slippage=15.0,
        decimals=6,
        supply=1000000000,
        pair_address=f"pair_{id}",
        dex_id=dex_id,
        price_usd=price_usd,
        liquidity_usd=liquidity_usd,
        volume_5m=volume_5m,
        buys_5m=buys_5m,
        sells_5m=sells_5m,
        market_status=market_status,
        validation_status=validation_status,
    )
    return s


def create_mock_observation(
    signal_id: int,
    target_seconds: int,
    seconds_since_signal: int,
    price_usd: float,
    liquidity_usd: float = 25000.0,
    status: str = "success",
    pair_address: str = "pair_1",
) -> MarketObservation:
    from datetime import timedelta
    base_dt = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    obs = MarketObservation(
        id=signal_id * 100 + target_seconds,
        signal_id=signal_id,
        token_address="TestMint11111111111111111111111111111111111",
        pair_address=pair_address,
        dex_id="pumpswap",
        observation_status=status,
        observed_at=base_dt + timedelta(seconds=seconds_since_signal),
        target_seconds=target_seconds,
        seconds_since_signal=seconds_since_signal,
        price_usd=price_usd,
        liquidity_usd=liquidity_usd,
        volume_5m=5000.0,
        buys_5m=50,
        sells_5m=30,
    )
    return obs


def test_audit_calculations():
    s1 = create_mock_signal(1, token_address="MintA")
    s2 = create_mock_signal(2, token_address="MintB")
    s3 = create_mock_signal(3, token_address="MintA")  # repeated mint
    s4 = create_mock_signal(4, token_address="MintC", source_name=None)

    obs = [
        create_mock_observation(1, 10, 11, 0.0011),
        create_mock_observation(1, 30, 31, 0.0012),
        create_mock_observation(2, 10, 11, 0.0009),
    ]

    report = build_audit_report(
        [s1, s2, s3, s4],
        obs,
        [],
        now=datetime(2026, 10, 2, 13, 0, 0, tzinfo=timezone.utc),
    )

    assert report.total_signals == 4
    assert report.unique_signals == 4
    assert report.unique_tokens == 3
    assert report.duplicate_rate == 25.0
    assert report.source_distribution["Bullish Calls - Solana"] == 3
    assert report.source_distribution["Unknown/Test"] == 1


def test_outcome_calculations():
    s = create_mock_signal(1, price_usd=0.0010)
    obs = [
        create_mock_observation(1, 10, 11, 0.0011),  # +10%
        create_mock_observation(1, 30, 31, 0.0013),  # +30% (peak)
        create_mock_observation(1, 60, 61, 0.0008),  # -20%
        create_mock_observation(1, 300, 301, 0.0004),  # -60% (trough)
    ]

    res = calculate_signal_outcome(s, obs)

    assert res.signal_id == 1
    assert res.returns_by_target[10] == pytest.approx(10.0)
    assert res.returns_by_target[30] == pytest.approx(30.0)
    assert res.returns_by_target[60] == pytest.approx(-20.0)
    assert res.returns_by_target[300] == pytest.approx(-60.0)

    assert res.max_favorable_excursion == pytest.approx(30.0)
    assert res.time_to_mfe == 31
    assert res.max_adverse_excursion == pytest.approx(-60.0)
    assert res.time_to_mae == 301

    assert res.hit_plus_20 is True
    assert res.hit_plus_50 is False
    assert res.hit_minus_20 is True
    assert res.hit_minus_50 is True
    assert res.hit_minus_80 is False

    # Drawdown after peak: from 0.0013 to 0.0004 = -69.23%
    assert res.drawdown_after_peak is not None
    assert res.drawdown_after_peak == pytest.approx(
        (0.0004 - 0.0013) / 0.0013 * 100
    )


def test_outcome_excludes_delayed_observations():
    s = create_mock_signal(1, price_usd=0.0010)
    obs = [
        create_mock_observation(1, 30, 31, 0.0011),
        # Severe catch-up delay: target 60s but captured at 56,000s
        create_mock_observation(1, 60, 56000, 0.0001),
    ]

    res = calculate_signal_outcome(s, obs, max_delay_seconds=60.0)

    assert 30 in res.returns_by_target
    assert 60 not in res.returns_by_target  # Excluded due to excessive delay
    assert res.max_adverse_excursion == 0.0  # Delayed price does not contaminate MAE


def test_anomaly_detection():
    # Signal #103 anomaly
    s103 = create_mock_signal(
        103,
        token_address="ETXqxfVoPN9f1qX1EV9qPWNqYuu5TUUUXMUM4SsniJga",
        liquidity_usd=345863635.0,
        price_usd=0.3146,
    )
    # Test signal with source=None
    s_test = create_mock_signal(1, source_name=None)
    # Market status no_liquid_pair
    s_nolq = create_mock_signal(2, market_status="no_liquid_pair")
    # RPC failure
    s_rpc = create_mock_signal(3, validation_status="rpc_failed")

    obs = [
        create_mock_observation(1, 999, 999, 0.001),  # non-standard target
        create_mock_observation(1, 60, 1000, 0.001),  # severe delay (>300s)
        # Pair switch on signal 2
        create_mock_observation(2, 30, 31, 0.001, pair_address="pair_A"),
        create_mock_observation(2, 60, 61, 0.001, pair_address="pair_B"),
    ]

    anomalies = detect_all_anomalies([s103, s_test, s_nolq, s_rpc], obs)
    types = {a.anomaly_type for a in anomalies}

    assert "extreme_liquidity_drop" in types
    assert "test_signal" in types
    assert "no_liquid_pair_at_signal" in types
    assert "solana_rpc_failed" in types
    assert "non_standard_target" in types
    assert "severe_observation_delay" in types
    assert "primary_pair_switched" in types


def test_exclusion_filtering():
    s_good = create_mock_signal(10, liquidity_usd=20000.0, price_usd=0.001)
    s_103 = create_mock_signal(103)
    s_test = create_mock_signal(1, source_name=None)
    s_nolq = create_mock_signal(2, market_status="no_liquid_pair")

    usable, excluded = filter_usable_signals(
        [s_good, s_103, s_test, s_nolq],
        ExclusionCriteria(),
    )

    assert len(usable) == 1
    assert usable[0].id == 10
    assert len(excluded) == 3


def test_feature_extraction_zero_lookahead():
    s = create_mock_signal(
        1,
        price_usd=0.005,
        liquidity_usd=50000.0,
        volume_5m=25000.0,
        buys_5m=200,
        sells_5m=100,
    )
    feat = extract_signal_features(s)

    assert feat.signal_id == 1
    assert feat.price_usd == 0.005
    assert feat.liquidity_usd == 50000.0
    assert feat.volume_5m == 25000.0
    assert feat.total_txns_5m == 300
    assert feat.buy_sell_ratio == pytest.approx(2.0)
    assert feat.buy_fraction == pytest.approx(200.0 / 300.0)
    assert feat.volume_to_liquidity == pytest.approx(0.5)


def test_correlations():
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    assert pearson_correlation(x, y) == pytest.approx(1.0)
    assert spearman_rank_correlation(x, y) == pytest.approx(1.0)

    y_inv = [12.0, 10.0, 8.0, 6.0, 4.0, 2.0]
    assert pearson_correlation(x, y_inv) == pytest.approx(-1.0)
    assert spearman_rank_correlation(x, y_inv) == pytest.approx(-1.0)


def test_paper_trade_simulation():
    s = create_mock_signal(1, price_usd=0.0010, liquidity_usd=25000.0)
    config = ExecutionConfig(
        position_size_usd=100.0,
        base_slippage_pct=1.5,
        price_impact_factor=2.0,
        dex_fee_pct=0.25,
        solana_tx_fee_usd=0.01,
    )

    # Take profit scenario: price rises to 0.0015 (+50%)
    obs_win = [
        create_mock_observation(1, 30, 31, 0.0015),
    ]
    res_win = simulate_paper_trade(
        s,
        obs_win,
        take_profit_pct=20.0,
        stop_loss_pct=-15.0,
        max_holding_seconds=120,
        config=config,
    )
    assert res_win is not None
    assert res_win.exit_reason == "take_profit"
    assert res_win.net_pnl_usd > 0

    # Stop loss scenario: price drops to 0.0007 (-30%)
    obs_loss = [
        create_mock_observation(1, 30, 31, 0.0007),
    ]
    res_loss = simulate_paper_trade(
        s,
        obs_loss,
        take_profit_pct=20.0,
        stop_loss_pct=-15.0,
        max_holding_seconds=120,
        config=config,
    )
    assert res_loss is not None
    assert res_loss.exit_reason == "stop_loss"
    assert res_loss.net_pnl_usd < 0


def test_chronological_split():
    signals = [create_mock_signal(i) for i in range(1, 101)]
    train, test = chronological_split(signals, train_fraction=0.7)

    assert len(train) == 70
    assert len(test) == 30
    assert max(s.id for s in train) < min(s.id for s in test)


@pytest.mark.asyncio
async def test_wait_and_capture_guards_expired_target(monkeypatch):
    from unittest.mock import AsyncMock
    from datetime import timedelta
    from app.market.observer import wait_and_capture

    # Signal created 2 hours ago
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    s = create_mock_signal(1, message_created_at=old_time, received_at=old_time)

    mock_save = AsyncMock()
    mock_capture = AsyncMock()

    monkeypatch.setattr("app.market.observer.save_market_observation", mock_save)
    monkeypatch.setattr("app.market.observer.capture_observation", mock_capture)

    # For a 60s target on a 2-hour old signal, it should trigger the guard
    await wait_and_capture(s, target_seconds=60)

    # capture_observation should NOT have been called
    mock_capture.assert_not_called()
    # save_market_observation should have been called with missed_offline
    assert mock_save.await_count == 1
    call_kwargs = mock_save.call_args.kwargs
    assert call_kwargs["observation_status"] == "missed_offline"
    assert call_kwargs["target_seconds"] == 60
    assert call_kwargs["snapshot"] is None


def test_chronological_split_strict_timestamps():
    from datetime import timedelta
    base_time = datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc)

    # Intentionally shuffle IDs relative to creation timestamps
    s1 = create_mock_signal(10, message_created_at=base_time + timedelta(minutes=1))
    s2 = create_mock_signal(2, message_created_at=base_time + timedelta(minutes=2))
    s3 = create_mock_signal(15, message_created_at=base_time + timedelta(minutes=3))
    s4 = create_mock_signal(1, message_created_at=base_time + timedelta(minutes=4))

    train, test = chronological_split([s1, s2, s3, s4], train_fraction=0.5)

    assert len(train) == 2
    assert len(test) == 2
    # Ensure train timestamps strictly precede test timestamps regardless of IDs
    assert max(s.message_created_at for s in train) <= min(s.message_created_at for s in test)
    assert train[0].id == 10
    assert train[1].id == 2
    assert test[0].id == 15
    assert test[1].id == 1


def test_no_lookahead_leakage_in_features():
    s = create_mock_signal(1)
    feat = extract_signal_features(s)

    # Verify no outcome or future checkpoint attributes exist on FeatureRecord
    assert not hasattr(feat, "ret_60")
    assert not hasattr(feat, "ret_300")
    assert not hasattr(feat, "mfe")
    assert not hasattr(feat, "mae")
    assert not hasattr(feat, "hit_plus_20")
    assert not hasattr(feat, "future_price")


def test_friction_sensitivity_monotonicity():
    from app.research.simulation import run_friction_sensitivity_grid
    s = create_mock_signal(1, price_usd=0.001, liquidity_usd=25000.0)
    obs = [
        create_mock_observation(1, 30, 31, 0.0011),
        create_mock_observation(1, 60, 61, 0.0009),
    ]

    grid = run_friction_sensitivity_grid([s], {1: obs})

    # Net PnL must strictly decrease as friction increases: zero >= low >= baseline >= high
    assert grid["zero_friction"]["total_pnl_usd"] >= grid["low_friction"]["total_pnl_usd"]
    assert grid["low_friction"]["total_pnl_usd"] >= grid["baseline_friction"]["total_pnl_usd"]
    assert grid["baseline_friction"]["total_pnl_usd"] >= grid["high_friction"]["total_pnl_usd"]


def test_cohort_classification_and_partition():
    from app.research.cohorts import (
        HISTORICAL_RESEARCH_MAX_SIGNAL_ID,
        SignalCohort,
        classify_signal_cohort,
        partition_by_cohort,
    )

    s_hist = create_mock_signal(HISTORICAL_RESEARCH_MAX_SIGNAL_ID)
    s_fwd = create_mock_signal(HISTORICAL_RESEARCH_MAX_SIGNAL_ID + 1)

    assert classify_signal_cohort(s_hist) == SignalCohort.HISTORICAL_RESEARCH
    assert classify_signal_cohort(s_fwd) == SignalCohort.FORWARD_TESTING

    parts = partition_by_cohort([s_hist, s_fwd])
    assert len(parts[SignalCohort.HISTORICAL_RESEARCH]) == 1
    assert len(parts[SignalCohort.FORWARD_TESTING]) == 1



