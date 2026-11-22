"""
Deterministic hard risk constraints for Meco Decision Engine.
Evaluates binary, non-negotiable safety guardrails that immediately reject tokens
regardless of high social hype or strong short-term price momentum.
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import HardRiskRuleConfig
from app.decision.models import HardRiskViolation, TokenDecisionInput


def evaluate_hard_risk_rules(
    input_data: TokenDecisionInput,
    config: HardRiskRuleConfig,
    as_of: datetime | None = None,
) -> list[HardRiskViolation]:
    """
    Evaluate deterministic hard risk constraints against canonical token intelligence,
    security profiles, holder distributions, and specialist risk agent findings.
    Returns a list of violations. If non-empty, the token MUST be rejected.
    """
    eval_time = as_of or input_data.as_of or datetime.now(timezone.utc)
    violations: list[HardRiskViolation] = []
    sec = input_data.security_findings or {}
    holders = input_data.holder_distribution or {}
    deployer = input_data.deployer_intelligence or {}
    pool = input_data.liquidity_pool or {}

    # 1. Mint Authority Check
    if config.reject_if_mint_authority_enabled:
        # Check both boolean flag and presence of non-null mint_authority address
        mint_auth = sec.get("mint_authority")
        has_mint_auth = sec.get("has_mint_authority", False) or (mint_auth is not None and str(mint_auth).strip() != "")
        if has_mint_auth:
            violations.append(
                HardRiskViolation(
                    rule_code="HR-MINT-AUTH-ACTIVE",
                    description=f"Mint authority is active ({mint_auth}); creator can arbitrarily inflate supply.",
                    severity="critical",
                    evidence=EvidenceItem(
                        source="security_profile",
                        timestamp=eval_time,
                        reference=f"mint:{input_data.mint_address}",
                        details={"mint_authority": mint_auth},
                    ),
                    details={"mint_authority": mint_auth},
                )
            )

    # 2. Freeze Authority Check
    if config.reject_if_freeze_authority_enabled:
        freeze_auth = sec.get("freeze_authority")
        has_freeze_auth = sec.get("has_freeze_authority", False) or (freeze_auth is not None and str(freeze_auth).strip() != "")
        if has_freeze_auth:
            violations.append(
                HardRiskViolation(
                    rule_code="HR-FREEZE-AUTH-ACTIVE",
                    description=f"Freeze authority is active ({freeze_auth}); holder balances can be frozen.",
                    severity="critical",
                    evidence=EvidenceItem(
                        source="security_profile",
                        timestamp=eval_time,
                        reference=f"mint:{input_data.mint_address}",
                        details={"freeze_authority": freeze_auth},
                    ),
                    details={"freeze_authority": freeze_auth},
                )
            )

    # 3. Honeypot / Transfer Restrictions
    if config.reject_if_honeypot:
        is_honeypot = bool(sec.get("is_honeypot") or sec.get("honeypot_risk"))
        if is_honeypot:
            violations.append(
                HardRiskViolation(
                    rule_code="HR-HONEYPOT-DETECTED",
                    description="Token is flagged as an active honeypot or transfer-restricted scam.",
                    severity="critical",
                    evidence=EvidenceItem(
                        source="security_profile",
                        timestamp=eval_time,
                        reference=f"mint:{input_data.mint_address}",
                        details={"is_honeypot": True},
                    ),
                    details={"is_honeypot": True},
                )
            )

    # 4. Minimum Liquidity Check
    liq_usd = float(pool.get("liquidity_usd") or 0.0)
    if liq_usd < config.min_liquidity_usd:
        violations.append(
            HardRiskViolation(
                rule_code="HR-INSUFFICIENT-LIQUIDITY",
                description=f"Pool liquidity (${liq_usd:.2f}) is below minimum viable threshold (${config.min_liquidity_usd:.2f}).",
                severity="critical",
                evidence=EvidenceItem(
                    source="liquidity_pool",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"liquidity_usd": liq_usd, "min_required": config.min_liquidity_usd},
                ),
                details={"liquidity_usd": liq_usd, "min_required": config.min_liquidity_usd},
            )
        )

    # 5. Top 10 Holder Concentration Check
    top_10_pct = float(holders.get("top_10_percentage") or sec.get("top_10_holder_percent") or 0.0)
    if top_10_pct > config.max_top_10_holder_percent:
        violations.append(
            HardRiskViolation(
                rule_code="HR-TOP10-CONCENTRATION-EXCESSIVE",
                description=f"Top 10 holders control {top_10_pct:.1f}% of supply (ceiling is {config.max_top_10_holder_percent:.1f}%).",
                severity="critical",
                evidence=EvidenceItem(
                    source="holder_distribution",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"top_10_percentage": top_10_pct, "max_allowed": config.max_top_10_holder_percent},
                ),
                details={"top_10_percentage": top_10_pct, "max_allowed": config.max_top_10_holder_percent},
            )
        )

    # 6. Single Largest Holder Concentration Check
    single_max_pct = float(holders.get("max_single_holder_pct") or 0.0)
    if single_max_pct > config.max_single_holder_percent:
        violations.append(
            HardRiskViolation(
                rule_code="HR-WHALE-DOMINANCE-EXCESSIVE",
                description=f"Single largest non-pool holder owns {single_max_pct:.1f}% of supply (ceiling {config.max_single_holder_percent:.1f}%).",
                severity="critical",
                evidence=EvidenceItem(
                    source="holder_distribution",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"max_single_holder_pct": single_max_pct, "max_allowed": config.max_single_holder_percent},
                ),
                details={"max_single_holder_pct": single_max_pct, "max_allowed": config.max_single_holder_percent},
            )
        )

    # 7. Deployer Holding Check
    deployer_holding = float(deployer.get("deployer_holding_pct") or holders.get("deployer_holding_pct") or 0.0)
    if deployer_holding > config.max_deployer_holding_percent:
        violations.append(
            HardRiskViolation(
                rule_code="HR-DEPLOYER-HOLDING-EXCESSIVE",
                description=f"Deployer retains {deployer_holding:.1f}% of token supply (ceiling {config.max_deployer_holding_percent:.1f}%).",
                severity="critical",
                evidence=EvidenceItem(
                    source="deployer_intelligence",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"deployer_holding_pct": deployer_holding, "max_allowed": config.max_deployer_holding_percent},
                ),
                details={"deployer_holding_pct": deployer_holding, "max_allowed": config.max_deployer_holding_percent},
            )
        )

    # 8. Malicious Deployer Check
    if config.reject_if_known_malicious_deployer:
        rug_count = int(deployer.get("known_rug_count") or deployer.get("prior_rugs", 0))
        is_blacklisted = bool(deployer.get("is_blacklisted", False))
        if rug_count > 0 or is_blacklisted:
            violations.append(
                HardRiskViolation(
                    rule_code="HR-MALICIOUS-DEPLOYER",
                    description=f"Deployer wallet has {rug_count} confirmed rug pulls or is on fraud blacklist.",
                    severity="critical",
                    evidence=EvidenceItem(
                        source="deployer_intelligence",
                        timestamp=eval_time,
                        reference=f"deployer:{deployer.get('address')}",
                        details={"rug_count": rug_count, "blacklisted": is_blacklisted},
                    ),
                    details={"rug_count": rug_count, "blacklisted": is_blacklisted},
                )
            )

    # 9. Minimum Unique Holders Check
    holder_count = int(holders.get("unique_holders_count") or holders.get("holder_count") or 0)
    if 0 < holder_count < config.min_unique_holders:
        violations.append(
            HardRiskViolation(
                rule_code="HR-TOO-FEW-HOLDERS",
                description=f"Token has only {holder_count} unique holders (minimum required is {config.min_unique_holders}).",
                severity="critical",
                evidence=EvidenceItem(
                    source="holder_distribution",
                    timestamp=eval_time,
                    reference=f"mint:{input_data.mint_address}",
                    details={"holder_count": holder_count, "min_required": config.min_unique_holders},
                ),
                details={"holder_count": holder_count, "min_required": config.min_unique_holders},
            )
        )

    # 10. Direct Risk Agent Hard Risks Ingestion
    if input_data.risk_agent_output and input_data.risk_agent_output.hard_risks:
        for hr in input_data.risk_agent_output.hard_risks:
            violations.append(
                HardRiskViolation(
                    rule_code=f"AGENT-{hr.code}",
                    description=f"Risk Agent: {hr.description}",
                    severity="critical",
                    evidence=hr.evidence,
                    details={"agent": "risk", "code": hr.code},
                )
            )

    return violations
