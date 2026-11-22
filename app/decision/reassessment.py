"""
Event-Driven Reassessment Manager for Meco Decision Engine (Phase 5).
Detects meaningful market, security, and lifecycle shifts to trigger timely re-evaluations
while enforcing deduplication and cooldowns to prevent thrashing.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.decision.config import DecisionEngineConfig, ReassessmentConfig, get_decision_config
from app.decision.models import (
    ReassessmentTriggerEvent,
    ReassessmentTriggerType,
    TokenDecisionResult,
)


class ReassessmentDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    should_reassess: bool
    trigger_type: ReassessmentTriggerType
    reason: str
    is_emergency: bool = False
    cooldown_active: bool = False
    seconds_until_cooldown_expires: float = 0.0
    deduplicated: bool = False


class ReassessmentManager:
    """
    Manages decision invalidation, triggers, deduplication, and cooldowns.
    Prevents infinite re-investigation loops while ensuring rapid response to critical risk events.
    """

    def __init__(self, config: DecisionEngineConfig | None = None) -> None:
        self.config = config or get_decision_config()
        self.reassessment_cfg: ReassessmentConfig = self.config.reassessment

        # In-memory tracking (can be backed by DB/Redis)
        self._last_reassessment: dict[str, datetime] = {}
        self._recent_event_hashes: set[str] = set()

    def _event_signature(self, event: ReassessmentTriggerEvent) -> str:
        """Create a deterministic hash signature of an event for deduplication."""
        payload = {
            "mint": event.mint_address,
            "type": event.trigger_type.value,
            "metrics": event.delta_metrics,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def record_reassessment(self, mint_address: str, as_of: datetime | None = None) -> None:
        """Mark a completed reassessment timestamp for cooldown tracking."""
        ts = as_of or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self._last_reassessment[mint_address] = ts

    def evaluate_event(
        self,
        event: ReassessmentTriggerEvent,
        current_decision: TokenDecisionResult | None = None,
        as_of: datetime | None = None,
    ) -> ReassessmentDecision:
        """
        Evaluate whether an incoming event should trigger a decision reassessment.
        """
        now = as_of or event.detected_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # 1. Check Decision Expiration
        if current_decision and current_decision.is_expired(at_time=now):
            return ReassessmentDecision(
                should_reassess=True,
                trigger_type=ReassessmentTriggerType.DECISION_EXPIRED,
                reason=f"Current decision expired at {current_decision.expiration_time.isoformat()}.",
                is_emergency=False,
            )

        # 2. Event Deduplication
        sig = self._event_signature(event)
        if sig in self._recent_event_hashes:
            return ReassessmentDecision(
                should_reassess=False,
                trigger_type=event.trigger_type,
                reason=f"Duplicate event signature {sig[:8]} already processed.",
                deduplicated=True,
            )

        # 3. Check Cooldowns
        is_emergency = event.is_emergency or event.trigger_type in (
            ReassessmentTriggerType.AUTHORITY_CHANGE,
            ReassessmentTriggerType.NEW_RISK_FINDINGS,
        )

        cooldown_limit = (
            self.reassessment_cfg.emergency_cooldown_seconds
            if is_emergency
            else self.reassessment_cfg.cooldown_seconds
        )

        last_time = self._last_reassessment.get(event.mint_address)
        if last_time:
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            elapsed = (now - last_time).total_seconds()
            if elapsed < cooldown_limit:
                rem = cooldown_limit - elapsed
                return ReassessmentDecision(
                    should_reassess=False,
                    trigger_type=event.trigger_type,
                    reason=f"Cooldown active ({elapsed:.1f}s elapsed < {cooldown_limit}s limit). Try again in {rem:.1f}s.",
                    is_emergency=is_emergency,
                    cooldown_active=True,
                    seconds_until_cooldown_expires=round(rem, 1),
                )

        # 4. Check Meaningful Change Thresholds
        metrics = event.delta_metrics or {}
        should_trigger = False
        reason = ""

        if event.trigger_type == ReassessmentTriggerType.LIQUIDITY_CHANGE:
            liq_pct = abs(float(metrics.get("liquidity_delta_pct") or 0.0))
            if liq_pct >= self.reassessment_cfg.liquidity_change_reassessment_pct:
                should_trigger = True
                reason = f"Liquidity shifted by {liq_pct:.1f}% (threshold: {self.reassessment_cfg.liquidity_change_reassessment_pct:.1f}%)."
            else:
                reason = f"Liquidity change {liq_pct:.1f}% below trigger threshold."

        elif event.trigger_type == ReassessmentTriggerType.SIGNIFICANT_PRICE_MOVEMENT:
            price_pct = abs(float(metrics.get("price_delta_pct") or 0.0))
            if price_pct >= self.reassessment_cfg.price_change_reassessment_pct:
                should_trigger = True
                reason = f"Price moved by {price_pct:.1f}% (threshold: {self.reassessment_cfg.price_change_reassessment_pct:.1f}%)."
            else:
                reason = f"Price movement {price_pct:.1f}% below trigger threshold."

        elif event.trigger_type == ReassessmentTriggerType.HOLDER_CHANGE:
            holder_delta = abs(float(metrics.get("top10_delta_pct") or 0.0))
            whale_sold = bool(metrics.get("top_holder_dumped", False))
            if holder_delta >= self.reassessment_cfg.holder_concentration_change_pct or whale_sold:
                should_trigger = True
                reason = f"Holder concentration shifted by {holder_delta:.1f}% (whale dump={whale_sold})."
            else:
                reason = f"Holder shift {holder_delta:.1f}% below threshold."

        elif event.trigger_type == ReassessmentTriggerType.AUTHORITY_CHANGE:
            should_trigger = True
            is_emergency = True
            reason = f"Token authority updated: {metrics.get('details', 'mint or freeze authority change')}."

        elif event.trigger_type == ReassessmentTriggerType.NEW_RISK_FINDINGS:
            should_trigger = True
            is_emergency = True
            reason = f"New specialist risk agent finding: {metrics.get('finding_code', 'risk alert')}."

        elif event.trigger_type == ReassessmentTriggerType.NEW_SOCIAL_ACTIVITY:
            velocity_mult = float(metrics.get("velocity_multiplier") or 1.0)
            if velocity_mult >= 2.5:
                should_trigger = True
                reason = f"Social velocity jumped {velocity_mult:.1f}x baseline."
            else:
                reason = f"Social velocity change {velocity_mult:.1f}x below 2.5x threshold."

        elif event.trigger_type == ReassessmentTriggerType.MARKET_DETERIORATION:
            should_trigger = True
            reason = f"Market deterioration detected: {metrics.get('reason', 'order flow collapse')}."

        elif event.trigger_type == ReassessmentTriggerType.MANUAL_REQUEST:
            should_trigger = True
            reason = "Manual reassessment request."

        else:
            reason = f"Unrecognized trigger type {event.trigger_type}."

        if should_trigger:
            # Register event signature to prevent instant duplicate trigger
            self._recent_event_hashes.add(sig)

        return ReassessmentDecision(
            should_reassess=should_trigger,
            trigger_type=event.trigger_type,
            reason=reason,
            is_emergency=is_emergency,
            cooldown_active=False,
            deduplicated=False,
        )
