"""
Versioned, deterministic scoring and engine configuration for Meco Decision Engine.
Allows transparent parameter versioning and historical reproducibility.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FreshnessConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_price_staleness_seconds: int = Field(default=600, description="Max acceptable age for price observations (10m)")
    max_liquidity_staleness_seconds: int = Field(default=900, description="Max acceptable age for pool liquidity data (15m)")
    max_security_staleness_seconds: int = Field(default=3600, description="Max acceptable age for security profile (1h)")
    max_social_staleness_seconds: int = Field(default=1800, description="Max acceptable age for social metrics (30m)")
    max_agent_findings_staleness_seconds: int = Field(default=1800, description="Max acceptable age for specialist agent outputs (30m)")
    reject_stale_critical_data: bool = Field(default=True, description="Strictly reject if critical security or liquidity is stale")


class HardRiskRuleConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reject_if_mint_authority_enabled: bool = Field(
        default=True,
        description="Reject if token mint authority is retained (arbitrary supply inflation risk)",
    )
    reject_if_freeze_authority_enabled: bool = Field(
        default=True,
        description="Reject if freeze authority is retained (funds can be frozen)",
    )
    reject_if_honeypot: bool = Field(
        default=True,
        description="Reject if token is identified as a honeypot or transfer-tax blacklist",
    )
    min_liquidity_usd: float = Field(
        default=500.0,
        description="Hard minimum liquidity in USD to even consider monitoring or trading",
    )
    max_top_10_holder_percent: float = Field(
        default=85.0,
        description="Hard ceiling for top 10 non-pool holder concentration",
    )
    max_single_holder_percent: float = Field(
        default=40.0,
        description="Hard ceiling for a single non-pool holder concentration",
    )
    max_deployer_holding_percent: float = Field(
        default=30.0,
        description="Hard ceiling for deployer remaining wallet holding",
    )
    reject_if_known_malicious_deployer: bool = Field(
        default=True,
        description="Reject if deployer has confirmed previous rug pulls or wash trading records",
    )
    min_unique_holders: int = Field(
        default=10,
        description="Minimum unique holder count for liquidity and holder distribution sanity",
    )


class OpportunityWeightsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Transparent baseline component weights - summing to 1.0
    volume_growth_weight: float = Field(
        default=0.25,
        description="Weight for 5m/1h volume acceleration (trading velocity)",
    )
    price_momentum_weight: float = Field(
        default=0.25,
        description="Weight for positive price action and buy/sell ratio dominance",
    )
    social_traction_weight: float = Field(
        default=0.25,
        description="Weight for organic social mention velocity and engagement without spam",
    )
    statistical_edge_weight: float = Field(
        default=0.25,
        description="Weight for historical cohort pattern match and validated win-rate edge",
    )
    rationale: str = (
        "Equal baseline weighting across four distinct opportunity vectors (volume, price momentum, "
        "social traction, and statistical cohort models) to avoid overfitting or claiming false predictive precision."
    )


class OutcomeThresholdsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Paper trade qualification
    paper_trade_min_opportunity: float = 65.0
    paper_trade_max_security_risk: float = 20.0
    paper_trade_max_wallet_risk: float = 25.0
    paper_trade_min_liquidity_quality: float = 50.0
    paper_trade_min_confidence: float = 0.70
    paper_trade_min_feasibility: float = 60.0

    # Watchlist qualification
    watchlist_min_opportunity: float = 50.0
    watchlist_max_security_risk: float = 35.0
    watchlist_max_wallet_risk: float = 40.0
    watchlist_min_confidence: float = 0.55

    # Investigate further qualification (strong indicators but missing/moderate confidence)
    investigate_min_opportunity: float = 45.0
    investigate_max_confidence: float = 0.65

    # Monitor qualification (early signs or low liquidity but clean security)
    monitor_min_opportunity: float = 30.0
    monitor_max_security_risk: float = 50.0


class ReassessmentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision_validity_seconds: int = Field(
        default=1800,
        description="Default expiration time for a decision (30 minutes)",
    )
    cooldown_seconds: int = Field(
        default=300,
        description="Minimum cooldown between reassessments under normal circumstances (5 minutes)",
    )
    emergency_cooldown_seconds: int = Field(
        default=30,
        description="Cooldown for emergency security or critical risk events (30 seconds)",
    )
    price_change_reassessment_pct: float = Field(
        default=20.0,
        description="Price change percentage (up or down) that triggers mandatory decision reassessment",
    )
    liquidity_change_reassessment_pct: float = Field(
        default=15.0,
        description="Liquidity drop or addition percentage that triggers mandatory reassessment",
    )
    holder_concentration_change_pct: float = Field(
        default=10.0,
        description="Top holder concentration shift triggering reassessment",
    )


class DecisionEngineConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = "1.0.0"
    name: str = "baseline_deterministic_v1"
    description: str = "Deterministic evidence-based baseline decision engine configuration."
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    freshness: FreshnessConfig = Field(default_factory=FreshnessConfig)
    hard_rules: HardRiskRuleConfig = Field(default_factory=HardRiskRuleConfig)
    weights: OpportunityWeightsConfig = Field(default_factory=OpportunityWeightsConfig)
    thresholds: OutcomeThresholdsConfig = Field(default_factory=OutcomeThresholdsConfig)
    reassessment: ReassessmentConfig = Field(default_factory=ReassessmentConfig)

    def hash_signature(self) -> str:
        """Deterministic sha256 hash of configuration parameters for tamper detection."""
        dumped = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


# Version registry for persisted configurations
_CONFIG_REGISTRY: dict[str, DecisionEngineConfig] = {}


def register_decision_config(config: DecisionEngineConfig) -> None:
    """Register a versioned configuration."""
    _CONFIG_REGISTRY[config.version] = config


def get_decision_config(version: str | None = None) -> DecisionEngineConfig:
    """Retrieve decision engine configuration by version, or return default v1.0.0."""
    if not _CONFIG_REGISTRY:
        default_cfg = DecisionEngineConfig()
        register_decision_config(default_cfg)

    if version and version in _CONFIG_REGISTRY:
        return _CONFIG_REGISTRY[version]

    # Return default or latest
    return _CONFIG_REGISTRY.get("1.0.0", DecisionEngineConfig())
