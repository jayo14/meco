import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Token, TokenLifecycleEvent

logger = logging.getLogger("meco.intelligence.lifecycle")


class TokenLifecycleState(str, Enum):
    DISCOVERED = "discovered"
    METADATA_ENRICHED = "metadata_enriched"
    SECURITY_EVALUATED = "security_evaluated"
    POOL_NOT_FOUND = "pool_not_found"
    LIQUIDITY_DETECTED = "liquidity_detected"
    TRADING_ACTIVE = "trading_active"
    LIQUIDITY_DETERIORATING = "liquidity_deteriorating"
    INACTIVE = "inactive"
    SUSPICIOUS = "suspicious"
    ENRICHMENT_FAILED = "enrichment_failed"


async def transition_lifecycle(
    session: AsyncSession,
    *,
    token: Token,
    to_state: TokenLifecycleState | str,
    reason: str | None = None,
    event_metadata: dict[str, Any] | None = None,
) -> TokenLifecycleEvent:
    """
    Transition a token to a new lifecycle state.
    Records a point-in-time lifecycle event and updates the token's current state.
    Transitions are non-linear to accommodate multi-pool dynamics and changing conditions.
    """
    state_str = to_state.value if isinstance(to_state, TokenLifecycleState) else str(to_state)
    from_state = token.lifecycle_state

    event = TokenLifecycleEvent(
        token_id=token.id,
        mint_address=token.mint_address,
        from_state=from_state,
        to_state=state_str,
        reason=reason,
        event_metadata=event_metadata,
        occurred_at=datetime.now(timezone.utc),
    )
    session.add(event)

    token.lifecycle_state = state_str
    token.updated_at = datetime.now(timezone.utc)

    await session.flush()
    await session.refresh(event)

    logger.info(
        "TOKEN LIFECYCLE TRANSITION | mint=%s | from=%s | to=%s | reason=%s",
        token.mint_address,
        from_state,
        state_str,
        reason or "unspecified",
    )
    return event
