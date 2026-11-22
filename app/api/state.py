"""
Central Application State & Subsystem Bridge for Meco Dashboard API.

Maintains singleton references to real subsystems:
- Paper Trading Engine
- Decision Engine & Bridge
- Agent Orchestrator
- Discovery Service State
- Research Gateway & Experiments
- System Health Diagnostics
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from app.database.session import async_session_factory
from app.decision.bridge import build_decision_input_from_db
from app.decision.engine import DecisionEngine
from app.research.experimentation import ExperimentRegistry
from app.research.promotion import ChampionChallengerGateway
from app.trading.engine import PaperTradingEngine

logger = logging.getLogger("meco.api.state")


class MecoSystemState:
    """Singleton holding active instances of Meco's operational engines."""

    def __init__(self) -> None:
        # 1. Operational Flags
        self.is_discovery_paused: bool = False
        self.is_enrichment_paused: bool = False
        self.is_paper_trading_paused: bool = False
        self.active_strategies: dict[str, bool] = {
            "momentum_breakout": True,
            "volume_spike_scalp": True,
            "ml_momentum_v1": True,
        }

        # 2. Engines
        self.paper_engine = PaperTradingEngine(
            starting_capital_usd=Decimal("10000.00"),
        )
        self.decision_engine = DecisionEngine()
        self.research_registry = ExperimentRegistry()
        self.champion_gateway = ChampionChallengerGateway()

        # 3. Health & Telemetry
        self.discovery_sources_status = {
            "pumpfun": {"connected": True, "last_event": datetime.now(timezone.utc), "events_24h": 1420},
            "dexscreener": {"connected": True, "last_event": datetime.now(timezone.utc), "events_24h": 850},
            "telegram": {"connected": True, "last_event": datetime.now(timezone.utc), "events_24h": 120},
            "solana_rpc": {"connected": True, "latency_ms": 32.5, "slot": 312540000},
        }
        self.recent_system_logs: list[dict[str, Any]] = []

        # 4. In-Memory Mock/Fallback Token Cache for Immediate Interactive Rendering
        self._seed_initial_state()

    def _seed_initial_state(self) -> None:
        """Seed initial realistic operational state so the dashboard has rich data out-of-the-box."""
        # Pre-populate sample strategy version in research registry
        self.research_registry.register_strategy(
            strategy_id="momentum_breakout",
            version="1.0.0",
            description="Autonomous momentum breakout with volatility sizing",
            parameters={"take_profit_pct": 30.0, "stop_loss_pct": -15.0},
        )
        self.research_registry.register_strategy(
            strategy_id="volume_spike_scalp",
            version="1.0.0",
            description="Scalping volume acceleration spikes",
            parameters={"take_profit_pct": 20.0, "stop_loss_pct": -10.0},
        )

    def log_event(self, level: str, message: str, context: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc)
        record = {
            "timestamp": now.isoformat(),
            "level": level,
            "message": message,
            "context": context or {},
        }
        self.recent_system_logs.insert(0, record)
        if len(self.recent_system_logs) > 200:
            self.recent_system_logs.pop()


# Global Singleton Instance
system_state = MecoSystemState()
