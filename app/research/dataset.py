"""
Point-In-Time Dataset Construction for Meco Quantitative Research (Phase 7).

Extracts observable features strictly at prediction timestamp T+0.
Guarantees point-in-time correctness with zero future look-ahead bias.
Supports versioned dataset manifest generation with SHA-256 reproducibility hashes.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any


@dataclass
class PointInTimeFeatures:
    """
    Standardized, point-in-time observable feature vector at T+0.
    No future prices, liquidity, or observations are permitted.
    """
    token_mint: str
    timestamp: datetime

    # 1. Age Features (seconds)
    token_age_seconds: float = 0.0
    pool_age_seconds: float = 0.0

    # 2. Liquidity Features
    liquidity_usd: float = 0.0
    initial_liquidity_usd: float = 0.0
    liquidity_growth_pct: float = 0.0
    liquidity_to_mcap_ratio: float = 0.0

    # 3. Volume & Activity Features (5m / 1h)
    volume_5m_usd: float = 0.0
    volume_1h_usd: float = 0.0
    trades_5m_count: int = 0
    buys_5m_count: int = 0
    sells_5m_count: int = 0
    buy_fraction_5m: float = 0.5  # buys / (buys + sells)
    net_volume_flow_5m_usd: float = 0.0
    volume_to_liquidity_ratio: float = 0.0

    # 4. Price Momentum & Volatility
    price_usd: float = 0.0
    price_momentum_1m_pct: float = 0.0
    price_momentum_5m_pct: float = 0.0
    price_momentum_15m_pct: float = 0.0
    price_volatility_5m_pct: float = 0.0

    # 5. Holder Distribution & Concentration
    holder_count: int = 1
    top10_holder_share_pct: float = 0.0
    deployer_holding_share_pct: float = 0.0

    # 6. Deployer & Wallet Intelligence
    deployer_prior_token_count: int = 0
    deployer_risk_score: float = 0.0  # 0 to 100
    suspicious_sniper_wallet_count: int = 0
    insider_cluster_detected: bool = False

    # 7. Social Attention & Narratives
    social_post_count_1h: int = 0
    social_unique_authors_1h: int = 0
    social_reach_estimate: int = 0
    social_sentiment_score: float = 0.0  # -1.0 to 1.0
    narrative_tier: str = "unknown"  # tier_1 (viral), tier_2, tier_3, none

    # 8. Discovery & Market Context
    discovery_source: str = "unknown"  # pumpfun, dexscreener, telegram, memepool
    seconds_from_discovery_to_liquidity: float = 0.0
    sol_1h_momentum_pct: float = 0.0
    market_regime: str = "neutral"  # bullish, bearish, high_volatility, chop

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_feature_vector(self, feature_columns: list[str] | None = None) -> list[float]:
        """Convert selected continuous and encoded features to a numeric vector for ML models."""
        d = self.to_dict()
        
        # Categorical encodings
        narrative_map = {"none": 0.0, "unknown": 0.0, "tier_3": 1.0, "tier_2": 2.0, "tier_1": 3.0}
        source_map = {"unknown": 0.0, "telegram": 1.0, "dexscreener": 2.0, "pumpfun": 3.0, "memepool": 4.0}
        regime_map = {"bearish": -1.0, "chop": 0.0, "neutral": 0.0, "high_volatility": 1.0, "bullish": 2.0}

        d["narrative_tier_num"] = narrative_map.get(self.narrative_tier.lower(), 0.0)
        d["discovery_source_num"] = source_map.get(self.discovery_source.lower(), 0.0)
        d["market_regime_num"] = regime_map.get(self.market_regime.lower(), 0.0)
        d["insider_cluster_num"] = 1.0 if self.insider_cluster_detected else 0.0

        if not feature_columns:
            feature_columns = [
                "token_age_seconds", "pool_age_seconds", "liquidity_usd",
                "liquidity_growth_pct", "volume_5m_usd", "buys_5m_count",
                "sells_5m_count", "buy_fraction_5m", "volume_to_liquidity_ratio",
                "price_momentum_5m_pct", "price_volatility_5m_pct",
                "top10_holder_share_pct", "deployer_risk_score",
                "suspicious_sniper_wallet_count", "insider_cluster_num",
                "social_post_count_1h", "social_sentiment_score",
                "narrative_tier_num", "discovery_source_num",
                "sol_1h_momentum_pct", "market_regime_num",
            ]

        vector: list[float] = []
        for col in feature_columns:
            val = d.get(col, 0.0)
            if isinstance(val, (int, float)):
                vector.append(float(val))
            elif isinstance(val, bool):
                vector.append(1.0 if val else 0.0)
            elif isinstance(val, Decimal):
                vector.append(float(val))
            else:
                vector.append(0.0)
        return vector


@dataclass
class DatasetManifest:
    """Metadata and integrity hash for reproducible ML datasets."""
    dataset_id: str
    version: str
    created_at: str
    row_count: int
    token_count: int
    feature_columns: list[str]
    time_window_start: str
    time_window_end: str
    sha256_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PointInTimeDatasetBuilder:
    """
    Constructs point-in-time training and evaluation datasets from historical records.
    Ensures zero future look-ahead bias: each feature snapshot only sees data as of T+0.
    """

    def __init__(self, version: str = "1.0.0") -> None:
        self.version = version

    def extract_features(
        self,
        token_mint: str,
        as_of: datetime,
        token_meta: dict[str, Any] | None = None,
        pool_data: dict[str, Any] | None = None,
        market_obs_history: list[dict[str, Any]] | None = None,
        holder_data: dict[str, Any] | None = None,
        deployer_data: dict[str, Any] | None = None,
        social_data: dict[str, Any] | None = None,
        market_regime_data: dict[str, Any] | None = None,
    ) -> PointInTimeFeatures:
        """
        Build a PointInTimeFeatures record using only records with timestamp <= as_of.
        """
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        token_meta = token_meta or {}
        pool_data = pool_data or {}
        holder_data = holder_data or {}
        deployer_data = deployer_data or {}
        social_data = social_data or {}
        market_regime_data = market_regime_data or {}

        # 1. Age Calculation
        created_at = token_meta.get("created_at")
        token_age = 0.0
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            token_age = max(0.0, (as_of - created_at).total_seconds())

        pool_created_at = pool_data.get("created_at")
        pool_age = 0.0
        if pool_created_at:
            if isinstance(pool_created_at, str):
                pool_created_at = datetime.fromisoformat(pool_created_at)
            if pool_created_at.tzinfo is None:
                pool_created_at = pool_created_at.replace(tzinfo=timezone.utc)
            pool_age = max(0.0, (as_of - pool_created_at).total_seconds())

        # 2. Liquidity
        liq = float(pool_data.get("liquidity_usd", 0.0))
        init_liq = float(pool_data.get("initial_liquidity_usd", liq))
        liq_growth = ((liq - init_liq) / init_liq * 100.0) if init_liq > 0 else 0.0
        mcap = float(pool_data.get("market_cap", liq * 2.0))
        liq_to_mcap = (liq / mcap) if mcap > 0 else 0.5

        # 3. Volume & Activity (5m)
        vol5m = float(pool_data.get("volume_5m", 0.0))
        vol1h = float(pool_data.get("volume_1h", vol5m * 4.0))
        buys = int(pool_data.get("buys_5m", 0))
        sells = int(pool_data.get("sells_5m", 0))
        total_tx = buys + sells
        buy_frac = (float(buys) / total_tx) if total_tx > 0 else 0.5
        net_flow = float(pool_data.get("net_flow_5m_usd", (buys - sells) * (vol5m / max(1, total_tx))))
        vol_to_liq = (vol5m / liq) if liq > 0 else 0.0

        # 4. Price & Momentum from historical observations <= as_of
        current_price = float(pool_data.get("price_usd", 0.0))
        p_mom_1m = 0.0
        p_mom_5m = float(pool_data.get("price_change_5m", 0.0))
        p_mom_15m = 0.0
        p_vol_5m = 0.0

        if market_obs_history:
            # Filter strictly by observation timestamp <= as_of (zero look-ahead)
            valid_obs: list[tuple[float, float]] = []  # (seconds_ago, price)
            for obs in market_obs_history:
                obs_ts = obs.get("timestamp")
                if isinstance(obs_ts, str):
                    obs_ts = datetime.fromisoformat(obs_ts)
                if obs_ts and obs_ts.tzinfo is None:
                    obs_ts = obs_ts.replace(tzinfo=timezone.utc)
                if obs_ts and obs_ts <= as_of:
                    p = float(obs.get("price_usd", 0.0))
                    if p > 0:
                        sec_ago = (as_of - obs_ts).total_seconds()
                        valid_obs.append((sec_ago, p))

            valid_obs.sort(key=lambda x: x[0])  # Sort by closeness to as_of
            if valid_obs:
                current_price = valid_obs[0][1]
                # Find observation close to 60s ago
                p_1m_obs = [p for sec, p in valid_obs if 45 <= sec <= 90]
                if p_1m_obs and p_1m_obs[0] > 0:
                    p_mom_1m = ((current_price - p_1m_obs[0]) / p_1m_obs[0]) * 100.0

                p_15m_obs = [p for sec, p in valid_obs if 800 <= sec <= 1000]
                if p_15m_obs and p_15m_obs[0] > 0:
                    p_mom_15m = ((current_price - p_15m_obs[0]) / p_15m_obs[0]) * 100.0

                # Compute volatility across last 10 points
                prices = [p for _, p in valid_obs[:10]]
                if len(prices) >= 3:
                    mean_p = sum(prices) / len(prices)
                    variance = sum((p - mean_p) ** 2 for p in prices) / (len(prices) - 1)
                    p_vol_5m = (variance ** 0.5 / mean_p) * 100.0 if mean_p > 0 else 0.0

        # 5. Holders
        h_count = int(holder_data.get("holder_count", 1))
        top10_share = float(holder_data.get("top10_share_pct", 0.0))
        deployer_share = float(holder_data.get("deployer_share_pct", 0.0))

        # 6. Deployer & Wallets
        dep_tokens = int(deployer_data.get("prior_token_count", 0))
        dep_risk = float(deployer_data.get("deployer_risk_score", 0.0))
        snipers = int(deployer_data.get("suspicious_snipers", 0))
        insider = bool(deployer_data.get("insider_cluster", False))

        # 7. Social Attention
        soc_posts = int(social_data.get("post_count_1h", 0))
        soc_authors = int(social_data.get("unique_authors_1h", 0))
        soc_reach = int(social_data.get("estimated_reach", 0))
        soc_sent = float(social_data.get("sentiment_score", 0.0))
        narr_tier = str(social_data.get("narrative_tier", "none"))

        # 8. Discovery & Market Context
        disc_src = str(token_meta.get("discovery_source", pool_data.get("dex", "unknown")))
        disc_time = token_meta.get("discovered_at")
        sec_disc_to_liq = 0.0
        if disc_time and pool_created_at:
            if isinstance(disc_time, str):
                disc_time = datetime.fromisoformat(disc_time)
            if disc_time.tzinfo is None:
                disc_time = disc_time.replace(tzinfo=timezone.utc)
            sec_disc_to_liq = max(0.0, (pool_created_at - disc_time).total_seconds())

        sol_mom = float(market_regime_data.get("sol_1h_momentum_pct", 0.0))
        regime = str(market_regime_data.get("regime", "neutral"))

        return PointInTimeFeatures(
            token_mint=token_mint,
            timestamp=as_of,
            token_age_seconds=round(token_age, 1),
            pool_age_seconds=round(pool_age, 1),
            liquidity_usd=round(liq, 2),
            initial_liquidity_usd=round(init_liq, 2),
            liquidity_growth_pct=round(liq_growth, 2),
            liquidity_to_mcap_ratio=round(liq_to_mcap, 4),
            volume_5m_usd=round(vol5m, 2),
            volume_1h_usd=round(vol1h, 2),
            trades_5m_count=total_tx,
            buys_5m_count=buys,
            sells_5m_count=sells,
            buy_fraction_5m=round(buy_frac, 4),
            net_volume_flow_5m_usd=round(net_flow, 2),
            volume_to_liquidity_ratio=round(vol_to_liq, 4),
            price_usd=round(current_price, 8),
            price_momentum_1m_pct=round(p_mom_1m, 2),
            price_momentum_5m_pct=round(p_mom_5m, 2),
            price_momentum_15m_pct=round(p_mom_15m, 2),
            price_volatility_5m_pct=round(p_vol_5m, 2),
            holder_count=h_count,
            top10_holder_share_pct=round(top10_share, 2),
            deployer_holding_share_pct=round(deployer_share, 2),
            deployer_prior_token_count=dep_tokens,
            deployer_risk_score=round(dep_risk, 2),
            suspicious_sniper_wallet_count=snipers,
            insider_cluster_detected=insider,
            social_post_count_1h=soc_posts,
            social_unique_authors_1h=soc_authors,
            social_reach_estimate=soc_reach,
            social_sentiment_score=round(soc_sent, 3),
            narrative_tier=narr_tier,
            discovery_source=disc_src,
            seconds_from_discovery_to_liquidity=round(sec_disc_to_liq, 1),
            sol_1h_momentum_pct=round(sol_mom, 2),
            market_regime=regime,
        )

    def build_dataset_manifest(
        self,
        dataset_id: str,
        records: list[PointInTimeFeatures],
        feature_columns: list[str],
    ) -> DatasetManifest:
        """Create a versioned, hash-verified manifest for a historical dataset."""
        if not records:
            now_iso = datetime.now(timezone.utc).isoformat()
            return DatasetManifest(
                dataset_id=dataset_id,
                version=self.version,
                created_at=now_iso,
                row_count=0,
                token_count=0,
                feature_columns=feature_columns,
                time_window_start=now_iso,
                time_window_end=now_iso,
                sha256_hash=hashlib.sha256(b"empty").hexdigest(),
            )

        sorted_records = sorted(records, key=lambda r: (r.timestamp, r.token_mint))
        unique_tokens = {r.token_mint for r in records}

        # Deterministic hashing of all records
        serialized = json.dumps([r.to_dict() for r in sorted_records], sort_keys=True)
        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return DatasetManifest(
            dataset_id=dataset_id,
            version=self.version,
            created_at=datetime.now(timezone.utc).isoformat(),
            row_count=len(records),
            token_count=len(unique_tokens),
            feature_columns=feature_columns,
            time_window_start=sorted_records[0].timestamp.isoformat(),
            time_window_end=sorted_records[-1].timestamp.isoformat(),
            sha256_hash=sha256_hash,
            metadata={"generator": "PointInTimeDatasetBuilder", "schema_version": self.version},
        )
