"""
Real-Time Server-Sent Events (SSE) Streaming Route for Meco Dashboard (Phase 8).

Streams live discovery ticks, paper position mark prices, and system status updates.
"""
import asyncio
from datetime import datetime, timezone
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.state import system_state

router = APIRouter(prefix="/stream", tags=["Real-Time Stream"])


async def event_generator():
    """Generates periodic real-time state telemetry chunks for the dashboard."""
    while True:
        now = datetime.now(timezone.utc)
        open_pos_count = len(system_state.paper_engine.position_manager.open_positions)
        emergency_stop = system_state.paper_engine.risk_gateway.is_emergency_stopped

        payload = {
            "timestamp": now.isoformat(),
            "emergency_stop": emergency_stop,
            "is_discovery_paused": system_state.is_discovery_paused,
            "open_positions_count": open_pos_count,
            "portfolio_equity": float(system_state.paper_engine.account.net_equity),
            "latest_log": system_state.recent_system_logs[0] if system_state.recent_system_logs else None,
        }

        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(2.0)


@router.get("/events")
async def stream_live_events():
    """SSE endpoint consumed by the frontend dashboard TanStack query / event listener."""
    return StreamingResponse(event_generator(), media_type="text/event-stream")
