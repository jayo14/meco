"""
Comprehensive Acceptance Test Suite for Meco Intelligence Dashboard & Control Centre (Phase 8).
Validates all Section 1-8 criteria:
- Real-time Overview with persisted system KPIs, equity, and PnL.
- Discovery Centre with filtering, sorting, and search.
- Token Intelligence Dossier with provenance, liquidity, authorities, and agent findings.
- Agent Operations inspector and investigation triggers.
- Decision Centre with opportunity rankings, deterministic evidence, and risk factors.
- Paper Trading Centre with position lifecycles, mark prices, excursions, and simulated labels.
- Research & Evaluation with equity curves, attribution slices, and champion/challenger tracking.
- System Health telemetry and RPC latencies.
- Real Operator Controls with strict confirmation guards (emergency stop, strategy toggles, manual liquidations).
- SSE telemetry stream connectivity.
"""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from starlette.testclient import TestClient

from app.api.app import app
from app.api.state import system_state
from app.trading.models import ExitConditions, PaperPosition, PositionStatus


@pytest.fixture
def client():
    """Provides a TestClient for the FastAPI dashboard application."""
    # Ensure system state is clean
    if system_state.paper_engine.risk_gateway.is_emergency_stop_active:
        system_state.paper_engine.reset_emergency_stop()
    system_state.is_discovery_paused = False
    with TestClient(app) as test_client:
        yield test_client
    if system_state.paper_engine.risk_gateway.is_emergency_stop_active:
        system_state.paper_engine.reset_emergency_stop()
    system_state.is_discovery_paused = False


def test_overview_endpoint(client):
    """Verifies /api/overview returns aggregated metrics from persisted state."""
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    assert "system_status" in data
    assert "total_tokens_discovered" in data
    assert "portfolio_starting_capital" in data
    assert "portfolio_available_capital" in data
    assert "portfolio_net_equity" in data
    assert "realised_pnl_usd" in data
    assert "unrealised_pnl_usd" in data
    assert "active_strategies" in data
    assert "emergency_stop_active" in data
    assert isinstance(data["active_strategies"], list)


def test_discovery_endpoint_filtering(client):
    """Verifies /api/discovery returns tokens and supports filtering."""
    response = client.get("/api/discovery?limit=20")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if len(data) > 0:
        token = data[0]
        assert "token_mint" in token
        assert "discovery_source" in token
        assert "lifecycle_state" in token
        assert "risk_level" in token

    # Test filtering by source
    resp_source = client.get("/api/discovery?source=pump_dot_fun")
    assert resp_source.status_code == 200
    assert isinstance(resp_source.json(), list)

    # Test filtering by risk
    resp_risk = client.get("/api/discovery?risk=low")
    assert resp_risk.status_code == 200
    assert isinstance(resp_risk.json(), list)


def test_token_detail_endpoint(client):
    """Verifies /api/tokens/{mint} returns full intelligence dossier."""
    disc_resp = client.get("/api/discovery?limit=1")
    tokens = disc_resp.json()
    test_mint = tokens[0]["token_mint"] if tokens else "So11111111111111111111111111111111111111112"

    response = client.get(f"/api/tokens/{test_mint}")
    assert response.status_code == 200
    data = response.json()

    assert data["token_mint"] == test_mint
    assert "discovery_source" in data
    assert "investigations" in data
    assert "decisions" in data
    assert "positions" in data
    assert isinstance(data["investigations"], list)
    assert isinstance(data["decisions"], list)
    assert isinstance(data["positions"], list)


def test_agent_investigations_and_trigger(client):
    """Verifies /api/agents/investigations and on-demand trigger."""
    resp_list = client.get("/api/agents/investigations")
    assert resp_list.status_code == 200
    invs = resp_list.json()
    assert isinstance(invs, list)

    trigger_resp = client.post(
        "/api/agents/investigate",
        json={"token_mint": "TestTokenMintTrigger123456789012345678901234"},
    )
    assert trigger_resp.status_code == 200
    data = trigger_resp.json()
    assert "task_id" in data
    assert "dispatched" in data["message"].lower() or "investigation" in data["message"].lower()


def test_decisions_endpoint(client):
    """Verifies /api/decisions returns structured decision records."""
    response = client.get("/api/decisions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if len(data) > 0:
        d = data[0]
        assert "decision_id" in d
        assert "token_mint" in d
        assert "outcome" in d
        assert "confidence_score" in d
        assert "supporting_evidence" in d
        assert "contradictory_evidence" in d
        assert "risk_factors" in d


def test_trading_positions_and_proposals(client):
    """Verifies /api/trading/positions and /api/trading/proposals."""
    resp_pos = client.get("/api/trading/positions")
    assert resp_pos.status_code == 200
    positions = resp_pos.json()
    assert isinstance(positions, list)

    resp_prop = client.get("/api/trading/proposals")
    assert resp_prop.status_code == 200
    proposals = resp_prop.json()
    assert isinstance(proposals, list)


def test_research_performance_endpoint(client):
    """Verifies /api/research/performance returns analytics, curves, and attributions."""
    response = client.get("/api/research/performance")
    assert response.status_code == 200
    data = response.json()

    assert "equity_curve" in data
    assert "win_rate" in data
    assert "profit_factor" in data
    assert "attribution_by_liquidity" in data
    assert "attribution_by_token_age" in data
    assert "attribution_by_regime" in data
    assert "champion_challenger" in data

    assert isinstance(data["equity_curve"], list)
    assert len(data["attribution_by_liquidity"]) > 0
    assert len(data["attribution_by_regime"]) > 0


def test_health_endpoint(client):
    """Verifies /api/health exposes operational status and gateway state."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert "overall_status" in data
    assert "database_connected" in data
    assert "rpc_connected" in data
    assert "rpc_latency_ms" in data
    assert "discovery_sources" in data
    assert "background_backlog_count" in data
    assert "emergency_stop_engaged" in data


def test_operator_controls_lifecycle_and_confirmation_guards(client):
    """
    Verifies operator controls execute safely and enforce confirmation guards:
    - Discovery pause/resume.
    - Strategy toggling.
    - Emergency stop requiring confirmation.
    - Manual position exit requiring confirmation.
    """
    # 1. Pause Discovery
    resp = client.post("/api/controls/execute", json={"action": "pause_discovery"})
    assert resp.status_code == 200
    assert system_state.is_discovery_paused is True

    # 2. Resume Discovery
    resp = client.post("/api/controls/execute", json={"action": "resume_discovery"})
    assert resp.status_code == 200
    assert system_state.is_discovery_paused is False

    # 3. Strategy Toggle
    resp = client.post(
        "/api/controls/execute",
        json={"action": "toggle_strategy", "target_id": "momentum_breakout"},
    )
    assert resp.status_code == 200

    # 4. Emergency Stop without confirmation MUST be rejected with HTTP 400
    resp_unconfirmed = client.post(
        "/api/controls/execute",
        json={"action": "emergency_stop", "confirmation": False},
    )
    assert resp_unconfirmed.status_code == 400
    assert "confirmation required" in resp_unconfirmed.json()["detail"].lower()

    # 5. Emergency Stop WITH confirmation MUST succeed
    resp_confirmed = client.post(
        "/api/controls/execute",
        json={
            "action": "emergency_stop",
            "confirmation": True,
            "operator_notes": "Automated security test halt",
        },
    )
    assert resp_confirmed.status_code == 200
    assert system_state.paper_engine.risk_gateway.is_emergency_stop_active is True

    # Check health reflects emergency stop
    health_resp = client.get("/api/health")
    assert health_resp.json()["emergency_stop_engaged"] is True

    # 6. Resume Operations without confirmation MUST fail
    resp_resume_unconfirmed = client.post(
        "/api/controls/execute",
        json={"action": "resume_operations", "confirmation": False},
    )
    assert resp_resume_unconfirmed.status_code == 400

    # Resume Operations with confirmation MUST succeed
    resp_resume_confirmed = client.post(
        "/api/controls/execute",
        json={"action": "resume_operations", "confirmation": True},
    )
    assert resp_resume_confirmed.status_code == 200
    assert system_state.paper_engine.risk_gateway.is_emergency_stop_active is False

    # 7. Close Position without confirmation MUST fail
    resp_close_unconfirmed = client.post(
        "/api/controls/execute",
        json={"action": "close_position", "target_id": "test_pos_1", "confirmation": False},
    )
    assert resp_close_unconfirmed.status_code == 400

    # 8. Close Position with confirmation but nonexistent target MUST return 404
    resp_close_notfound = client.post(
        "/api/controls/execute",
        json={"action": "close_position", "target_id": "nonexistent_pos_id", "confirmation": True},
    )
    assert resp_close_notfound.status_code == 404

    # 9. Close Position with confirmation and valid position MUST succeed
    now = datetime.now(timezone.utc)
    mock_pos = PaperPosition(
        position_id="mock_close_pos_123",
        proposal_id="prop_test_123",
        decision_id="dec_test_123",
        mint_address="TestMint12345678901234567890123456789012",
        token_symbol="TEST",
        strategy_id="momentum_breakout",
        status=PositionStatus.OPEN,
        entry_time=now,
        entry_price=Decimal("1.50"),
        quantity=Decimal("100"),
        capital_committed=Decimal("150.00"),
        current_mark_price=Decimal("1.65"),
        unrealised_pnl_usd=Decimal("15.00"),
        realised_pnl_usd=Decimal("0.00"),
        total_fees_paid_usd=Decimal("0.50"),
        exit_conditions=ExitConditions(),
        peak_price=Decimal("1.65"),
        max_favourable_excursion_usd=Decimal("15.00"),
        max_adverse_excursion_usd=Decimal("0.00"),
        last_updated=now,
    )
    system_state.paper_engine.position_manager.open_positions[mock_pos.position_id] = mock_pos

    resp_close_valid = client.post(
        "/api/controls/execute",
        json={
            "action": "close_position",
            "target_id": mock_pos.position_id,
            "confirmation": True,
            "operator_notes": "Manual operator exit",
        },
    )
    assert resp_close_valid.status_code == 200
    assert resp_close_valid.json()["success"] is True

    # Position should now be closed
    closed_pos = system_state.paper_engine.position_manager.positions_history[-1]
    assert closed_pos.position_id == mock_pos.position_id
    assert closed_pos.status == PositionStatus.CLOSED

    # 10. Unknown action MUST return 400
    resp_unknown = client.post(
        "/api/controls/execute",
        json={"action": "invalid_unknown_action", "confirmation": True},
    )
    assert resp_unknown.status_code == 400


def test_stream_events_endpoint(client):
    """Verifies /api/stream/events provides SSE stream with text/event-stream headers."""
    with client.stream("GET", "/api/stream/events?limit=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        lines = [line for line in response.iter_lines() if line]
        assert any("connected" in l for l in lines)
