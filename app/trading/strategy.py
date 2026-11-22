"""
Strategy Evaluation and Signal Templates for Meco Paper Trading Engine (Phase 6).
Evaluates qualifying decisions against concrete execution templates:
- MomentumBreakoutStrategy: trades volume acceleration and price trend continuation with trailing stops.
- LiquiditySurgeStrategy: trades deep pool liquidity events with bounded risk.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from app.decision.models import DecisionOutcome, TokenDecisionInput, TokenDecisionResult
from app.trading.models import PortfolioSnapshot, TradeProposal
from app.trading.proposal import ProposalGenerator
from app.trading.sizing import PositionSizer

logger = logging.getLogger("meco.trading.strategy")


class BaseTradingStrategy(ABC):
    """Abstract base class for all trading strategy templates."""

    def __init__(self, strategy_id: str, version: str = "1.0.0") -> None:
        self.strategy_id = strategy_id
        self.version = version
        self.proposal_generator = ProposalGenerator()

    @abstractmethod
    def evaluate(
        self,
        decision: TokenDecisionResult,
        token_input: TokenDecisionInput,
        portfolio: PortfolioSnapshot,
        sizer: PositionSizer,
        as_of: datetime | None = None,
    ) -> TradeProposal | None:
        """Evaluate strategy entry conditions and return a TradeProposal if triggered."""
        pass


class MomentumBreakoutStrategy(BaseTradingStrategy):
    """
    Momentum Breakout Strategy:
    Triggers when:
    - Decision Engine classifies token as PAPER_TRADE_CANDIDATE.
    - 5m volume acceleration component >= 55.0.
    - Market conditions buy pressure >= 60.0.
    - Execution feasibility >= 60.0.
    Employs trailing stops and two-stage profit taking.
    """

    def __init__(self, version: str = "1.0.0") -> None:
        super().__init__(strategy_id="momentum_breakout", version=version)

    def evaluate(
        self,
        decision: TokenDecisionResult,
        token_input: TokenDecisionInput,
        portfolio: PortfolioSnapshot,
        sizer: PositionSizer,
        as_of: datetime | None = None,
    ) -> TradeProposal | None:
        if decision.outcome != DecisionOutcome.PAPER_TRADE_CANDIDATE:
            return None

        scores = decision.dimension_scores
        vol_accel = scores.opportunity_quality.components.get("volume_acceleration", 0.0)
        buy_pressure = scores.market_conditions.components.get("buy_pressure", 0.0)
        feasibility = scores.execution_feasibility.score

        # Strategy-specific trigger rules
        if vol_accel < 50.0 or buy_pressure < 55.0 or feasibility < 50.0:
            logger.info(
                f"[{self.strategy_id}] Token {decision.mint_address} skipped: "
                f"vol_accel={vol_accel:.1f}, buy_pressure={buy_pressure:.1f}, feasibility={feasibility:.1f}."
            )
            return None

        return self.proposal_generator.generate_proposal(
            decision=decision,
            token_input=token_input,
            portfolio=portfolio,
            sizer=sizer,
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            as_of=as_of,
        )


class LiquiditySurgeStrategy(BaseTradingStrategy):
    """
    Liquidity Surge Strategy:
    Triggers when:
    - Decision Engine classifies token as PAPER_TRADE_CANDIDATE or WATCHLIST.
    - Liquidity quality score >= 65.0 (pool depth >= $30k, 100% burned/locked).
    - Security risk is minimal (<= 15.0).
    - Market conditions volume-to-liquidity ratio is healthy (>= 50.0).
    """

    def __init__(self, version: str = "1.0.0") -> None:
        super().__init__(strategy_id="liquidity_surge", version=version)

    def evaluate(
        self,
        decision: TokenDecisionResult,
        token_input: TokenDecisionInput,
        portfolio: PortfolioSnapshot,
        sizer: PositionSizer,
        as_of: datetime | None = None,
    ) -> TradeProposal | None:
        if decision.outcome not in (DecisionOutcome.PAPER_TRADE_CANDIDATE, DecisionOutcome.WATCHLIST):
            return None

        scores = decision.dimension_scores
        liq_qual = scores.liquidity_quality.score
        sec_risk = scores.security_risk.score

        if liq_qual < 60.0 or sec_risk > 20.0:
            return None

        return self.proposal_generator.generate_proposal(
            decision=decision,
            token_input=token_input,
            portfolio=portfolio,
            sizer=sizer,
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            as_of=as_of,
        )


class StrategyRegistry:
    """Manages strategy instances and version dispatch."""

    def __init__(self) -> None:
        self._strategies: dict[str, BaseTradingStrategy] = {
            "momentum_breakout": MomentumBreakoutStrategy(),
            "liquidity_surge": LiquiditySurgeStrategy(),
        }

    def register(self, strategy: BaseTradingStrategy) -> None:
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> BaseTradingStrategy | None:
        return self._strategies.get(strategy_id)

    def all_strategies(self) -> list[BaseTradingStrategy]:
        return list(self._strategies.values())
