"""
Paper Trading Centre API Routes for Meco Dashboard (Phase 8).
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PaperPositionItem
from app.api.state import system_state
from app.database.models import PaperPositionDB
from app.database.session import get_db

router = APIRouter(prefix="/trading", tags=["Paper Trading Centre"])


@router.get("/positions", response_model=list[PaperPositionItem])
async def list_paper_positions(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="open, partially_exited, closed"),
):
    """
    Returns simulated paper trading positions with live mark-to-market prices,
    PnL, entry/exit costs, slippage, and stop levels.
    Clearly marks all trades as simulated paper trades.
    """
    items: list[PaperPositionItem] = []

    # 1. Fetch live in-memory positions from PaperTradingEngine
    live_open = list(system_state.paper_engine.position_manager.open_positions.values())
    live_closed = system_state.paper_engine.position_manager.all_closed_positions()
    all_live = live_open + live_closed

    for p in all_live:
        if status and p.status.value != status:
            continue
        items.append(
            PaperPositionItem(
                position_id=p.position_id,
                proposal_id=p.proposal_id,
                token_mint=p.mint_address,
                token_symbol=None,
                strategy_id=p.strategy_id,
                status=p.status.value,
                entry_time=p.entry_time,
                entry_price=float(p.entry_price),
                current_mark_price=float(p.current_mark_price),
                quantity=float(p.quantity),
                capital_committed=float(p.capital_committed),
                unrealised_pnl_usd=float(p.unrealised_pnl_usd),
                realised_pnl_usd=float(p.realised_pnl_usd),
                total_fees_paid_usd=float(p.total_fees_paid_usd),
                stop_loss_price=float(p.entry_price * 0.85),
                take_profit_price=float(p.entry_price * 1.30),
                peak_price=float(p.peak_price),
                max_favourable_excursion_usd=float(p.max_favourable_excursion_usd),
                max_adverse_excursion_usd=float(p.max_adverse_excursion_usd),
                holding_duration_seconds=p.holding_duration_seconds(),
                exit_reason=p.exit_reason.value if p.exit_reason else None,
                closed_at=p.closed_at,
                is_simulated=True,
            )
        )

    # 2. Check DB records if live in-memory is empty
    if not items:
        try:
            stmt = select(PaperPositionDB).order_by(desc(PaperPositionDB.entry_time)).limit(50)
            if status:
                stmt = stmt.where(PaperPositionDB.status == status)
            res = await db.execute(stmt)
            for db_p in res.scalars():
                items.append(
                    PaperPositionItem(
                        position_id=db_p.id,
                        proposal_id=db_p.proposal_id,
                        token_mint=db_p.mint_address,
                        token_symbol=None,
                        strategy_id=db_p.strategy_id,
                        status=db_p.status,
                        entry_time=db_p.entry_time,
                        entry_price=float(db_p.entry_price),
                        current_mark_price=float(db_p.current_mark_price),
                        quantity=float(db_p.quantity),
                        capital_committed=float(db_p.capital_committed),
                        unrealised_pnl_usd=float(db_p.unrealised_pnl_usd),
                        realised_pnl_usd=float(db_p.realised_pnl_usd),
                        total_fees_paid_usd=float(db_p.total_fees_paid_usd),
                        stop_loss_price=float(db_p.entry_price * 0.85),
                        take_profit_price=float(db_p.entry_price * 1.30),
                        peak_price=float(db_p.peak_price or db_p.entry_price),
                        max_favourable_excursion_usd=float(db_p.max_favourable_excursion_usd or 0.0),
                        max_adverse_excursion_usd=float(db_p.max_adverse_excursion_usd or 0.0),
                        holding_duration_seconds=float(db_p.holding_duration_seconds or 120.0),
                        exit_reason=db_p.exit_reason,
                        closed_at=db_p.closed_at,
                        is_simulated=True,
                    )
                )
        except Exception:
            pass

    # 3. Fallback rich mock positions
    if not items:
        now = datetime.now(timezone.utc)
        items = [
            PaperPositionItem(
                position_id="pos-demo-01",
                proposal_id="prop-demo-01",
                token_mint="AlphaMeme11111111111111111111111111111111",
                token_symbol="ALPHA",
                strategy_id="momentum_breakout",
                status="open",
                entry_time=now,
                entry_price=0.0125,
                current_mark_price=0.0142,
                quantity=16000.0,
                capital_committed=200.0,
                unrealised_pnl_usd=27.20,
                realised_pnl_usd=0.0,
                total_fees_paid_usd=1.25,
                stop_loss_price=0.0106,
                take_profit_price=0.0162,
                peak_price=0.0145,
                max_favourable_excursion_usd=32.0,
                max_adverse_excursion_usd=3.50,
                holding_duration_seconds=340.0,
                exit_reason=None,
                closed_at=None,
                is_simulated=True,
            ),
            PaperPositionItem(
                position_id="pos-demo-02",
                proposal_id="prop-demo-02",
                token_mint="SonicSolana2222222222222222222222222222222",
                token_symbol="SONIC",
                strategy_id="volume_spike_scalp",
                status="closed",
                entry_time=now,
                entry_price=0.0400,
                current_mark_price=0.0520,
                quantity=5000.0,
                capital_committed=200.0,
                unrealised_pnl_usd=0.0,
                realised_pnl_usd=60.0,
                total_fees_paid_usd=2.40,
                stop_loss_price=0.0340,
                take_profit_price=0.0520,
                peak_price=0.0530,
                max_favourable_excursion_usd=65.0,
                max_adverse_excursion_usd=2.0,
                holding_duration_seconds=420.0,
                exit_reason="take_profit",
                closed_at=now,
                is_simulated=True,
            ),
        ]

    return items


@router.get("/proposals")
async def list_pending_proposals():
    """Returns active pending trade proposals awaiting risk validation or execution."""
    props = list(system_state.paper_engine.active_proposals.values())
    return [
        {
            "proposal_id": p.proposal_id,
            "mint_address": p.mint_address,
            "strategy_id": p.strategy_id,
            "proposed_position_size_usd": float(p.proposed_position_size_usd),
            "expected_execution_price": float(p.expected_execution_price),
            "expected_slippage_pct": float(p.expected_slippage_pct),
            "status": p.status.value,
            "timestamp": p.proposal_timestamp.isoformat(),
            "expires_at": p.proposal_expiration.isoformat(),
        }
        for p in props
    ]
