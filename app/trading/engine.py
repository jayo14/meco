"""
Autonomous Paper Trading Engine for Meco (Phase 6).
Coordinates strategy evaluation, trade proposal generation, position sizing,
independent pre-trade risk validation, paper order execution, position lifecycle management,
and portfolio accounting.
Does not enable live trading or wallet signing.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from app.decision.models import DecisionOutcome, TokenDecisionInput, TokenDecisionResult
from app.trading.accounting import PortfolioAccount, quantize_usd
from app.trading.execution import ExecutionSimulatorConfig, PaperExecutionSimulator
from app.trading.models import (
    OrderSide,
    OrderType,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
    PositionStatus,
    ProposalStatus,
    SimulatedExecutionResult,
    TradeProposal,
)
from app.trading.performance import PerformanceAnalyzer, TradingPerformanceReport
from app.trading.position_manager import PositionManager
from app.trading.risk_gateway import PreTradeRiskGateway, RiskGatewayConfig
from app.trading.sizing import PositionSizer, PositionSizingConfig
from app.trading.strategy import BaseTradingStrategy, StrategyRegistry

logger = logging.getLogger("meco.trading.engine")


class PaperTradingEngine:
    """
    Main Autonomous Paper Trading Engine.
    Enforces strict architectural boundaries: Decision Engine never directly executes orders;
    every trade must be proposed, sized, validated through the Risk Gateway,
    executed via the simulated DEX environment, and managed until closed.
    """

    def __init__(
        self,
        starting_capital_usd: Decimal | str = Decimal("10000.00"),
        sizing_config: PositionSizingConfig | None = None,
        risk_config: RiskGatewayConfig | None = None,
        execution_config: ExecutionSimulatorConfig | None = None,
        strategy_registry: StrategyRegistry | None = None,
    ) -> None:
        self.account = PortfolioAccount(starting_capital_usd=starting_capital_usd)
        self.sizer = PositionSizer(config=sizing_config)
        self.risk_gateway = PreTradeRiskGateway(config=risk_config)
        self.execution_simulator = PaperExecutionSimulator(config=execution_config)
        self.position_manager = PositionManager()
        self.strategy_registry = strategy_registry or StrategyRegistry()

        # In-flight proposals
        self.active_proposals: dict[str, TradeProposal] = {}
        self.rejected_proposals: list[TradeProposal] = []

    def get_portfolio_snapshot(self, as_of: datetime | None = None) -> PortfolioSnapshot:
        """Produce point-in-time portfolio balance and risk snapshot."""
        open_positions = self.position_manager.all_active_positions()
        return self.account.get_snapshot(open_positions, as_of=as_of)

    def process_decision(
        self,
        decision: TokenDecisionResult,
        token_input: TokenDecisionInput,
        strategy_id: str = "momentum_breakout",
        as_of: datetime | None = None,
    ) -> TradeProposal | None:
        """
        Step 1: Strategy Evaluation & Proposal Generation.
        Translates candidate decision into a structured TradeProposal.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # Retrieve selected strategy
        strat = self.strategy_registry.get(strategy_id)
        if not strat:
            logger.error(f"Strategy {strategy_id} not found in registry.")
            return None

        portfolio_snapshot = self.get_portfolio_snapshot(as_of=eval_time)

        proposal = strat.evaluate(
            decision=decision,
            token_input=token_input,
            portfolio=portfolio_snapshot,
            sizer=self.sizer,
            as_of=eval_time,
        )

        if proposal:
            if proposal.status == ProposalStatus.PENDING:
                self.active_proposals[proposal.proposal_id] = proposal
            else:
                self.rejected_proposals.append(proposal)

        return proposal

    def execute_proposal(
        self,
        proposal_id: str,
        pool_liquidity_usd: Decimal,
        displayed_spot_price: Decimal,
        dex_id: str = "raydium",
        transfer_fee_bps: int = 0,
        as_of: datetime | None = None,
    ) -> PaperPosition | None:
        """
        Step 2: Pre-Trade Risk Validation & Simulated Execution.
        Processes proposal through the Independent Risk Gateway and simulated DEX execution.
        """
        eval_time = as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        proposal = self.active_proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"Proposal {proposal_id} not found in active proposals.")
            return None

        # 1. Proposal Expiration Check
        if proposal.is_expired(at_time=eval_time):
            proposal.status = ProposalStatus.EXPIRED
            proposal.rejection_reason = "Proposal expired before execution arrival."
            self.active_proposals.pop(proposal_id, None)
            self.rejected_proposals.append(proposal)
            logger.info(f"Proposal {proposal_id} expired.")
            return None

        # 2. Capital Reservation
        size_to_reserve = proposal.proposed_position_size_usd
        reserved = self.account.reserve_capital(size_to_reserve)
        if not reserved:
            proposal.status = ProposalStatus.REJECTED
            proposal.rejection_reason = f"Insufficient available capital to reserve ${size_to_reserve}."
            self.active_proposals.pop(proposal_id, None)
            self.rejected_proposals.append(proposal)
            logger.warning(f"Failed to reserve capital for proposal {proposal_id}.")
            return None

        # 3. Independent Pre-Trade Risk Gateway Validation
        portfolio_snapshot = self.get_portfolio_snapshot(as_of=eval_time)
        reserve_side = pool_liquidity_usd / Decimal("2.0") if pool_liquidity_usd > Decimal("0.0") else Decimal("1.0")
        est_price_impact = (size_to_reserve / (reserve_side + size_to_reserve)) * Decimal("100.0")

        daily_loss = self.account.get_daily_loss_today(as_of=eval_time)

        risk_decision = self.risk_gateway.validate_proposal(
            proposal=proposal,
            portfolio=portfolio_snapshot,
            pool_liquidity_usd=pool_liquidity_usd,
            estimated_price_impact_pct=est_price_impact,
            daily_loss_today_usd=daily_loss,
            as_of=eval_time,
        )

        if not risk_decision.approved:
            # Release reserved funds
            self.account.release_capital(size_to_reserve)
            proposal.status = ProposalStatus.REJECTED
            proposal.rejection_reason = f"Risk Gateway rejection: {'; '.join(risk_decision.rejection_reasons)}"
            self.active_proposals.pop(proposal_id, None)
            self.rejected_proposals.append(proposal)
            logger.warning(f"Proposal {proposal_id} rejected by Risk Gateway: {proposal.rejection_reason}")
            return None

        # 4. Realistic Simulated Execution
        exec_res = self.execution_simulator.simulate_order(
            side=OrderSide.BUY,
            requested_size_usd=size_to_reserve,
            displayed_spot_price=displayed_spot_price,
            pool_liquidity_usd=pool_liquidity_usd,
            quote_timestamp=proposal.proposal_timestamp,
            execution_timestamp=eval_time,
            dex_id=dex_id,
            transfer_fee_bps=transfer_fee_bps,
            max_slippage_override_pct=proposal.max_acceptable_price_impact_pct,
        )

        if not exec_res.success:
            # Release reserved funds
            self.account.release_capital(size_to_reserve)
            proposal.status = ProposalStatus.FAILED
            proposal.rejection_reason = f"Execution simulation failed: {exec_res.failure_reason}"
            self.active_proposals.pop(proposal_id, None)
            self.rejected_proposals.append(proposal)
            logger.error(f"Simulated execution failed for {proposal_id}: {exec_res.failure_reason}")
            return None

        # 5. Commit Entry in Portfolio Accounting
        # If partial fill occurred, release un-filled remainder of reservation
        if exec_res.executed_size_usd < size_to_reserve:
            unfilled_diff = size_to_reserve - exec_res.executed_size_usd
            self.account.release_capital(unfilled_diff)

        self.account.commit_entry(
            amount_committed=exec_res.executed_size_usd,
            fee=exec_res.total_fee_usd,
        )

        # 6. Initialize Position in Position Manager
        pos = self.position_manager.open_position(
            proposal_id=proposal.proposal_id,
            mint_address=proposal.mint_address,
            strategy_id=proposal.strategy_id,
            entry_price=exec_res.executed_price,
            quantity=exec_res.executed_quantity,
            capital_committed=exec_res.executed_size_usd,
            exit_conditions=proposal.exit_conditions,
            token_id=proposal.token_id,
            initial_pool_liquidity_usd=pool_liquidity_usd,
            as_of=eval_time,
        )

        # Mark proposal executed
        proposal.status = ProposalStatus.EXECUTED
        self.active_proposals.pop(proposal_id, None)

        logger.info(
            f"Successfully entered paper position {pos.position_id} on {pos.mint_address}: "
            f"size=${exec_res.executed_size_usd}, price={exec_res.executed_price}, qty={exec_res.executed_quantity}."
        )

        return pos

    def evaluate_market_tick(
        self,
        mark_prices: dict[str, Decimal],
        pool_liquidities: dict[str, Decimal],
        risk_flags: dict[str, bool] | None = None,
        as_of: datetime | None = None,
    ) -> list[PaperOrder]:
        """
        Step 3: Autonomous Position Lifecycle & Exit Management.
        Evaluates stop losses, take profits, timeouts, and liquidity shifts across open positions.
        """
        return self.position_manager.evaluate_and_execute_exits(
            mark_prices=mark_prices,
            pool_liquidities=pool_liquidities,
            execution_simulator=self.execution_simulator,
            account=self.account,
            risk_flags=risk_flags,
            as_of=as_of,
        )

    def trigger_emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        """Halt all new entries immediately."""
        self.risk_gateway.trigger_emergency_stop(reason)

    def reset_emergency_stop(self) -> None:
        """Clear the emergency kill switch."""
        self.risk_gateway.reset_emergency_stop()

    def get_performance_report(self, as_of: datetime | None = None) -> TradingPerformanceReport:
        """Generate comprehensive performance analytics across closed positions."""
        closed = self.position_manager.all_closed_positions()
        snapshot = self.get_portfolio_snapshot(as_of=as_of)
        return PerformanceAnalyzer.evaluate(closed_positions=closed, portfolio=snapshot, as_of=as_of)

    def reconcile_accounting(self) -> tuple[bool, str]:
        """Verify double-entry portfolio balance integrity."""
        open_positions = self.position_manager.all_active_positions()
        return self.account.reconcile(open_positions)
