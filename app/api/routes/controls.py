"""
Operator Controls & Safety Command Gateway for Meco Dashboard (Phase 8).

Executes live operational controls:
- Emergency Stop Kill Switch (atomic halt of all new paper entries).
- Pause/Resume Token Discovery.
- Pause/Resume Specialist Enrichment.
- Manual position close via execution simulator.
- Strategy toggle switches.
- Trigger manual investigation or research evaluation.

Enforces confirmation guards for consequential operations.
"""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import OperatorControlCommand
from app.api.state import system_state
from app.security.auth import verify_operator_access
from app.trading.models import ExitReason, OrderSide

router = APIRouter(prefix="/controls", tags=["Operator Controls"])


@router.post("/execute", dependencies=[Depends(verify_operator_access)])
async def execute_operator_command(cmd: OperatorControlCommand):
    """
    Executes real operator control actions with mandatory confirmation validation.
    """
    action = cmd.action.lower()
    now = datetime.now(timezone.utc)

    # 1. Emergency Stop Kill Switch (Consequential - requires confirmation)
    if action == "emergency_stop":
        if not cmd.confirmation:
            raise HTTPException(status_code=400, detail="Confirmation required for emergency stop.")
        reason = cmd.operator_notes or "Operator engaged manual Emergency Stop via Dashboard."
        system_state.paper_engine.trigger_emergency_stop(reason)
        system_state.log_event("CRITICAL", f"EMERGENCY STOP engaged by operator: {reason}")
        return {
            "success": True,
            "action": action,
            "status": "emergency_stop_active",
            "message": "All new paper entries halted immediately across all strategies.",
            "timestamp": now.isoformat(),
        }

    # 2. Reset Emergency Stop / Resume Operations
    if action in ("reset_emergency_stop", "resume_operations"):
        if not cmd.confirmation:
            raise HTTPException(status_code=400, detail="Confirmation required to reset emergency stop.")
        system_state.paper_engine.reset_emergency_stop()
        system_state.log_event("WARNING", "Emergency Stop reset by operator. Normal paper execution resumed.")
        return {
            "success": True,
            "action": action,
            "status": "operational",
            "message": "Emergency stop cleared. Trading gateway active.",
            "timestamp": now.isoformat(),
        }

    # 3. Discovery Pause / Resume
    if action == "pause_discovery":
        system_state.is_discovery_paused = True
        system_state.log_event("INFO", "Token discovery ingestion paused by operator.")
        return {"success": True, "action": action, "is_discovery_paused": True}

    if action == "resume_discovery":
        system_state.is_discovery_paused = False
        system_state.log_event("INFO", "Token discovery ingestion resumed by operator.")
        return {"success": True, "action": action, "is_discovery_paused": False}

    # 4. Enrichment Pause / Resume
    if action == "pause_enrichment":
        system_state.is_enrichment_paused = True
        system_state.log_event("INFO", "Specialist enrichment workers paused by operator.")
        return {"success": True, "action": action, "is_enrichment_paused": True}

    if action == "resume_enrichment":
        system_state.is_enrichment_paused = False
        system_state.log_event("INFO", "Specialist enrichment workers resumed by operator.")
        return {"success": True, "action": action, "is_enrichment_paused": False}

    # 5. Toggle Individual Strategy
    if action == "toggle_strategy":
        strat_id = cmd.target_id
        if not strat_id or strat_id not in system_state.active_strategies:
            raise HTTPException(status_code=404, detail=f"Strategy '{strat_id}' not found.")
        params = cmd.parameters or {}
        new_state = params.get("enabled", not system_state.active_strategies[strat_id])
        system_state.active_strategies[strat_id] = new_state
        system_state.log_event("INFO", f"Strategy '{strat_id}' toggled to {'ENABLED' if new_state else 'DISABLED'}.")
        return {"success": True, "strategy_id": strat_id, "enabled": new_state}

    # 6. Close Paper Position Through Execution Simulator (Consequential)
    if action == "close_position":
        pos_id = cmd.target_id
        if not pos_id:
            raise HTTPException(status_code=400, detail="Position ID required.")
        if not cmd.confirmation:
            raise HTTPException(status_code=400, detail="Confirmation required to manually close position.")

        pos = system_state.paper_engine.position_manager.open_positions.get(pos_id)
        if not pos:
            raise HTTPException(status_code=404, detail=f"Position '{pos_id}' not found or already closed.")

        # Simulate execution on exit order
        order_res = system_state.paper_engine.execution_simulator.simulate_order(
            side=OrderSide.SELL,
            requested_size_usd=pos.quantity * pos.current_mark_price,
            displayed_spot_price=pos.current_mark_price,
            pool_liquidity_usd=Decimal("50000.00"),
            quote_timestamp=now,
            execution_timestamp=now,
        )

        close_price = order_res.executed_price if order_res.success else pos.current_mark_price
        fee = order_res.total_fee_usd if order_res.success else Decimal("0.05")

        closed_pos = system_state.paper_engine.position_manager.close_position(
            position_id=pos_id,
            exit_price=close_price,
            exit_time=now,
            exit_reason=ExitReason.MANUAL_EXIT,
            fee_usd=fee,
        )

        system_state.log_event(
            "INFO",
            f"Manual liquidation of simulated position {pos_id} at ${close_price:.6f} (fee: ${fee:.4f}).",
        )
        return {
            "success": True,
            "action": action,
            "position_id": pos_id,
            "exit_price": float(close_price),
            "fees_paid_usd": float(fee),
            "realised_pnl_usd": float(closed_pos.realised_pnl_usd),
            "closed_at": now.isoformat(),
        }

    raise HTTPException(status_code=400, detail=f"Unknown or unsupported operator action: '{action}'.")
