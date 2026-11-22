"""
State Persistence and Restart Recovery Manager for Meco Paper Trading Engine (Phase 6).
Saves positions, orders, proposals, and portfolio snapshots to the database
and restores complete in-memory engine state upon process restarts.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    PaperOrderRecord,
    PaperPositionRecord,
    PaperProposalRecord,
    PortfolioSnapshotRecord,
)
from app.trading.accounting import quantize_usd
from app.trading.engine import PaperTradingEngine
from app.trading.models import (
    ExitConditions,
    ExitReason,
    OrderSide,
    OrderType,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
    PositionStatus,
    ProposalStatus,
    StopLossConfig,
    TakeProfitConfig,
    TradeProposal,
)

logger = logging.getLogger("meco.trading.persistence")


class PersistenceManager:
    """
    Handles database persistence and restart recovery for PaperTradingEngine.
    """

    @classmethod
    async def save_position(cls, session: AsyncSession, position: PaperPosition) -> None:
        """Upsert a PaperPositionRecord in the database."""
        stmt = select(PaperPositionRecord).where(PaperPositionRecord.id == position.position_id)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            record = PaperPositionRecord(
                id=position.position_id,
                proposal_id=position.proposal_id,
                mint_address=position.mint_address,
                token_id=position.token_id,
                strategy_id=position.strategy_id,
                status=position.status.value,
                entry_time=position.entry_time,
                entry_price=float(position.entry_price),
                quantity=float(position.quantity),
                capital_committed=float(position.capital_committed),
                current_mark_price=float(position.current_mark_price),
                unrealised_pnl_usd=float(position.unrealised_pnl_usd),
                realised_pnl_usd=float(position.realised_pnl_usd),
                total_fees_paid_usd=float(position.total_fees_paid_usd),
                exit_conditions=position.exit_conditions.model_dump(mode="json"),
                peak_price=float(position.peak_price),
                max_favourable_excursion_usd=float(position.max_favourable_excursion_usd),
                max_adverse_excursion_usd=float(position.max_adverse_excursion_usd),
                exit_reason=position.exit_reason.value if position.exit_reason else None,
                closed_at=position.closed_at,
            )
            session.add(record)
        else:
            record.status = position.status.value
            record.current_mark_price = float(position.current_mark_price)
            record.quantity = float(position.quantity)
            record.capital_committed = float(position.capital_committed)
            record.unrealised_pnl_usd = float(position.unrealised_pnl_usd)
            record.realised_pnl_usd = float(position.realised_pnl_usd)
            record.total_fees_paid_usd = float(position.total_fees_paid_usd)
            record.peak_price = float(position.peak_price)
            record.max_favourable_excursion_usd = float(position.max_favourable_excursion_usd)
            record.max_adverse_excursion_usd = float(position.max_adverse_excursion_usd)
            record.exit_reason = position.exit_reason.value if position.exit_reason else None
            record.closed_at = position.closed_at
            record.updated_at = datetime.now(timezone.utc)

        await session.commit()

    @classmethod
    async def save_order(cls, session: AsyncSession, order: PaperOrder) -> None:
        """Persist a PaperOrderRecord."""
        record = PaperOrderRecord(
            id=order.order_id,
            position_id=order.position_id,
            mint_address=order.mint_address,
            side=order.side.value,
            order_type=order.order_type.value,
            requested_size_usd=float(order.requested_size_usd),
            executed_size_usd=float(order.executed_size_usd),
            executed_price=float(order.executed_price),
            executed_quantity=float(order.executed_quantity),
            total_fees_usd=float(order.total_fees_usd),
            status=order.status,
            created_at=order.created_at,
            executed_at=order.executed_at,
            details=order.details,
        )
        session.add(record)
        await session.commit()

    @classmethod
    async def save_proposal(cls, session: AsyncSession, proposal: TradeProposal) -> None:
        """Persist a TradeProposalRecord."""
        record = PaperProposalRecord(
            id=proposal.proposal_id,
            mint_address=proposal.mint_address,
            token_id=proposal.token_id,
            strategy_id=proposal.strategy_id,
            strategy_version=proposal.strategy_version,
            decision_id=proposal.decision_id,
            proposed_entry_price=float(proposal.proposed_entry_price),
            proposed_position_size_usd=float(proposal.proposed_position_size_usd),
            expected_slippage_pct=float(proposal.expected_slippage_pct),
            max_acceptable_price_impact_pct=float(proposal.max_acceptable_price_impact_pct),
            exit_conditions=proposal.exit_conditions.model_dump(mode="json"),
            risk_assessment=proposal.risk_assessment,
            status=proposal.status.value,
            rejection_reason=proposal.rejection_reason,
            proposal_timestamp=proposal.proposal_timestamp,
            proposal_expiration=proposal.proposal_expiration,
        )
        session.add(record)
        await session.commit()

    @classmethod
    async def save_portfolio_snapshot(cls, session: AsyncSession, snapshot: PortfolioSnapshot) -> None:
        """Persist a PortfolioSnapshotRecord."""
        record = PortfolioSnapshotRecord(
            id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            starting_capital=float(snapshot.starting_capital),
            available_capital=float(snapshot.available_capital),
            reserved_capital=float(snapshot.reserved_capital),
            open_positions_value=float(snapshot.open_positions_value),
            realised_pnl=float(snapshot.realised_pnl),
            unrealised_pnl=float(snapshot.unrealised_pnl),
            total_fees=float(snapshot.total_fees),
            net_equity=float(snapshot.net_equity),
            peak_equity=float(snapshot.peak_equity),
            current_drawdown_pct=float(snapshot.current_drawdown_pct),
            open_positions_count=snapshot.open_positions_count,
            exposure_by_token={k: float(v) for k, v in snapshot.exposure_by_token.items()},
            exposure_by_strategy={k: float(v) for k, v in snapshot.exposure_by_strategy.items()},
        )
        session.add(record)
        await session.commit()

    @classmethod
    async def recover_engine_state(
        cls,
        session: AsyncSession,
        engine: PaperTradingEngine,
    ) -> int:
        """
        Recover active positions and portfolio accounting balances after a crash or restart.
        Returns the number of active positions successfully restored.
        """
        # 1. Restore latest Portfolio Snapshot if available
        snap_stmt = select(PortfolioSnapshotRecord).order_by(PortfolioSnapshotRecord.timestamp.desc()).limit(1)
        snap_res = await session.execute(snap_stmt)
        latest_snap = snap_res.scalar_one_or_none()

        if latest_snap:
            engine.account.starting_capital = quantize_usd(Decimal(str(latest_snap.starting_capital)))
            engine.account.available_capital = quantize_usd(Decimal(str(latest_snap.available_capital)))
            engine.account.reserved_capital = quantize_usd(Decimal(str(latest_snap.reserved_capital)))
            engine.account.realised_pnl = quantize_usd(Decimal(str(latest_snap.realised_pnl)))
            engine.account.total_fees_paid = quantize_usd(Decimal(str(latest_snap.total_fees)))
            engine.account.peak_equity = quantize_usd(Decimal(str(latest_snap.peak_equity)))
            logger.info(
                f"Restored portfolio state: equity=${latest_snap.net_equity}, "
                f"available=${latest_snap.available_capital}, realised_pnl=${latest_snap.realised_pnl}."
            )

        # 2. Restore all active open positions
        pos_stmt = select(PaperPositionRecord).where(
            PaperPositionRecord.status.in_([PositionStatus.OPEN.value, PositionStatus.PARTIALLY_EXITED.value])
        )
        pos_res = await session.execute(pos_stmt)
        active_records = pos_res.scalars().all()

        engine.position_manager.open_positions.clear()
        restored_count = 0

        for rec in active_records:
            # Load exit orders for this position
            orders_stmt = select(PaperOrderRecord).where(PaperOrderRecord.position_id == rec.id)
            orders_res = await session.execute(orders_stmt)
            order_records = orders_res.scalars().all()

            exit_orders = [
                PaperOrder(
                    order_id=o.id,
                    position_id=o.position_id,
                    mint_address=o.mint_address,
                    side=OrderSide(o.side),
                    order_type=OrderType(o.order_type),
                    requested_size_usd=quantize_usd(Decimal(str(o.requested_size_usd))),
                    executed_size_usd=quantize_usd(Decimal(str(o.executed_size_usd))),
                    executed_price=Decimal(str(o.executed_price)),
                    executed_quantity=Decimal(str(o.executed_quantity)),
                    total_fees_usd=quantize_usd(Decimal(str(o.total_fees_usd))),
                    status=o.status,
                    created_at=o.created_at,
                    executed_at=o.executed_at,
                    details=o.details or {},
                )
                for o in order_records
            ]

            pos = PaperPosition(
                position_id=rec.id,
                proposal_id=rec.proposal_id,
                mint_address=rec.mint_address,
                token_id=rec.token_id,
                strategy_id=rec.strategy_id,
                status=PositionStatus(rec.status),
                entry_time=rec.entry_time,
                entry_price=Decimal(str(rec.entry_price)),
                quantity=Decimal(str(rec.quantity)),
                capital_committed=quantize_usd(Decimal(str(rec.capital_committed))),
                current_mark_price=Decimal(str(rec.current_mark_price)),
                unrealised_pnl_usd=quantize_usd(Decimal(str(rec.unrealised_pnl_usd))),
                realised_pnl_usd=quantize_usd(Decimal(str(rec.realised_pnl_usd))),
                total_fees_paid_usd=quantize_usd(Decimal(str(rec.total_fees_paid_usd))),
                exit_history=exit_orders,
                exit_conditions=ExitConditions(**(rec.exit_conditions or {})),
                peak_price=Decimal(str(rec.peak_price)),
                max_favourable_excursion_usd=quantize_usd(Decimal(str(rec.max_favourable_excursion_usd))),
                max_adverse_excursion_usd=quantize_usd(Decimal(str(rec.max_adverse_excursion_usd))),
                exit_reason=ExitReason(rec.exit_reason) if rec.exit_reason else None,
                closed_at=rec.closed_at,
                updated_at=rec.updated_at,
            )
            engine.position_manager.open_positions[pos.position_id] = pos
            restored_count += 1

        logger.info(f"Restart recovery complete: restored {restored_count} active positions.")
        return restored_count
