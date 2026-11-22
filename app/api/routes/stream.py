"""
Real-Time Server-Sent Events (SSE) Streaming Route for Meco Dashboard (Phase 8).

Streams live discovery ticks, paper position mark prices, and system status updates.
"""
import asyncio
from datetime import datetime, timezone
import json
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.state import system_state

router = APIRouter(prefix="/stream", tags=["Real-Time Stream"])


async def event_generator(limit: Optional[int] = None):
    """Generates periodic real-time state telemetry chunks for the dashboard."""
    # Send initial connected handshake event
    yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
    count = 1
    if limit is not None and count >= limit:
        return

    while True:
        now = datetime.now(timezone.utc)
        open_positions = list(system_state.paper_engine.position_manager.open_positions.values())
        open_pos_count = len(open_positions)
        emergency_stop = system_state.paper_engine.risk_gateway.is_emergency_stop_active
        snap = system_state.paper_engine.account.get_snapshot(open_positions)

        payload = {
            "timestamp": now.isoformat(),
            "emergency_stop": emergency_stop,
            "is_discovery_paused": system_state.is_discovery_paused,
            "open_positions_count": open_pos_count,
            "portfolio_equity": float(snap.net_equity),
            "latest_log": system_state.recent_system_logs[0] if system_state.recent_system_logs else None,
        }

        yield f"data: {json.dumps(payload)}\n\n"
        count += 1
        if limit is not None and count >= limit:
            break
        await asyncio.sleep(2.0)


@router.get("/events")
async def stream_live_events(limit: Optional[int] = Query(None, description="Optional max events before terminating stream")):
    """SSE endpoint consumed by the frontend dashboard TanStack query / event listener."""
    return StreamingResponse(event_generator(limit=limit), media_type="text/event-stream")
