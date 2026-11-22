"""
Timestamp validation and data freshness evaluator for Meco Decision Engine.
Ensures zero temporal leakage and rejects stale or incomplete critical information.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import EvidenceItem
from app.decision.config import FreshnessConfig
from app.decision.models import TokenDecisionInput


class FreshnessValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_valid: bool = True
    has_stale_critical_data: bool = False
    has_missing_critical_data: bool = False
    stale_fields: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    staleness_durations_seconds: dict[str, float] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


def evaluate_input_freshness(
    input_data: TokenDecisionInput,
    config: FreshnessConfig,
    as_of: datetime | None = None,
) -> FreshnessValidationResult:
    """
    Validate all timestamped inputs against configured staleness thresholds and completeness requirements.
    Rejects evaluations with missing critical data or outdated market/security snapshots.
    """
    eval_time = as_of or input_data.as_of or datetime.now(timezone.utc)
    # Ensure eval_time is timezone-aware
    if eval_time.tzinfo is None:
        eval_time = eval_time.replace(tzinfo=timezone.utc)

    result = FreshnessValidationResult()

    # 1. Check Missing Critical Information
    # Mint address is strictly required
    if not input_data.mint_address:
        result.missing_critical_fields.append("mint_address")
        result.rejection_reasons.append("Missing mint address in input.")

    # Canonical token info
    if not input_data.canonical_token:
        result.missing_critical_fields.append("canonical_token")
        result.rejection_reasons.append("Missing canonical token record.")

    # Security findings are critical to prevent trading unvetted contracts
    if input_data.security_findings is None:
        result.missing_critical_fields.append("security_findings")
        result.rejection_reasons.append("Missing security and authority findings (TokenSecurityProfile).")

    # Liquidity pool is required to evaluate tradeability
    if input_data.liquidity_pool is None:
        result.missing_critical_fields.append("liquidity_pool")
        result.rejection_reasons.append("Missing liquidity pool information.")

    if result.missing_critical_fields:
        result.has_missing_critical_data = True
        result.is_valid = False

    # 2. Check Input Timestamps for Staleness
    timestamps = input_data.input_timestamps or {}

    # Check Price Staleness
    price_ts = timestamps.get("price") or timestamps.get("market_observations")
    if price_ts:
        if price_ts.tzinfo is None:
            price_ts = price_ts.replace(tzinfo=timezone.utc)
        age = (eval_time - price_ts).total_seconds()
        result.staleness_durations_seconds["price"] = age
        if age > config.max_price_staleness_seconds:
            result.stale_fields.append("price")
            msg = f"Price data is stale ({age:.1f}s old > max {config.max_price_staleness_seconds}s allowed)."
            result.rejection_reasons.append(msg)
            result.evidence.append(
                EvidenceItem(
                    source="freshness_evaluator",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"field": "price", "age_seconds": age, "max_allowed": config.max_price_staleness_seconds},
                )
            )

    # Check Liquidity Staleness
    liq_ts = timestamps.get("liquidity_pool") or timestamps.get("liquidity")
    if liq_ts:
        if liq_ts.tzinfo is None:
            liq_ts = liq_ts.replace(tzinfo=timezone.utc)
        age = (eval_time - liq_ts).total_seconds()
        result.staleness_durations_seconds["liquidity_pool"] = age
        if age > config.max_liquidity_staleness_seconds:
            result.stale_fields.append("liquidity_pool")
            msg = f"Liquidity data is stale ({age:.1f}s old > max {config.max_liquidity_staleness_seconds}s allowed)."
            result.rejection_reasons.append(msg)
            result.evidence.append(
                EvidenceItem(
                    source="freshness_evaluator",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"field": "liquidity_pool", "age_seconds": age, "max_allowed": config.max_liquidity_staleness_seconds},
                )
            )

    # Check Security Staleness
    sec_ts = timestamps.get("security_findings") or timestamps.get("security")
    if sec_ts:
        if sec_ts.tzinfo is None:
            sec_ts = sec_ts.replace(tzinfo=timezone.utc)
        age = (eval_time - sec_ts).total_seconds()
        result.staleness_durations_seconds["security_findings"] = age
        if age > config.max_security_staleness_seconds:
            result.stale_fields.append("security_findings")
            msg = f"Security data is stale ({age:.1f}s old > max {config.max_security_staleness_seconds}s allowed)."
            result.rejection_reasons.append(msg)
            result.evidence.append(
                EvidenceItem(
                    source="freshness_evaluator",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"field": "security_findings", "age_seconds": age, "max_allowed": config.max_security_staleness_seconds},
                )
            )

    # Check Social Staleness (soft warning or rejection if strictly configured)
    soc_ts = timestamps.get("social_intelligence") or timestamps.get("social")
    if soc_ts:
        if soc_ts.tzinfo is None:
            soc_ts = soc_ts.replace(tzinfo=timezone.utc)
        age = (eval_time - soc_ts).total_seconds()
        result.staleness_durations_seconds["social_intelligence"] = age
        if age > config.max_social_staleness_seconds:
            result.stale_fields.append("social_intelligence")

    # If critical stale fields found and reject_stale_critical_data is True
    critical_stale = [f for f in result.stale_fields if f in ("price", "liquidity_pool", "security_findings")]
    if critical_stale and config.reject_stale_critical_data:
        result.has_stale_critical_data = True
        result.is_valid = False

    return result
