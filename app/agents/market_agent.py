from datetime import datetime, timezone
import logging
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import (
    AgentConfig,
    AgentFinding,
    AgentOutput,
    AgentStatus,
    BaseAgent,
    EvidenceItem,
    FindingType,
    InvestigationContext,
)
from app.agents.llm.client import LLMClient
from app.agents.llm.prompts import MARKET_AGENT_PROMPT_V1, MARKET_SYSTEM_PROMPT

logger = logging.getLogger("meco.agents.market")


class MarketAnalysisOutput(AgentOutput):
    model_config = ConfigDict(extra="ignore")

    agent_name: str = "market_analysis"
    market_metrics: dict[str, Any] = Field(default_factory=dict)
    price_impact: dict[str, float] = Field(default_factory=dict)
    volatility: float = 0.0
    momentum_verdict: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL, EXHAUSTED


class LLMMarketSynthesis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    market_regime: str = "UNKNOWN"
    inferences: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)


def calculate_amm_price_impact(trade_size_usd: float, total_liquidity_usd: float) -> float:
    """
    Deterministic constant-product AMM price impact calculation.
    Assuming standard 50/50 liquidity pool where quote reserve x = total_liquidity_usd / 2.
    Price impact = trade_size / (x + trade_size).
    """
    if total_liquidity_usd <= 0 or trade_size_usd <= 0:
        return 100.0
    quote_reserve = total_liquidity_usd / 2.0
    impact = (trade_size_usd / (quote_reserve + trade_size_usd)) * 100.0
    return min(round(impact, 2), 100.0)


def calculate_snapshot_volatility(snapshots: list[dict[str, Any]]) -> float:
    """
    Deterministic coefficient of variation (normalized volatility)
    across a series of recent market price snapshots.
    """
    prices = [
        float(s.get("price_usd") or 0.0)
        for s in snapshots
        if s.get("price_usd") and float(s.get("price_usd") or 0.0) > 0
    ]
    if len(prices) < 2:
        return 0.0

    mean_price = sum(prices) / len(prices)
    if mean_price <= 0:
        return 0.0

    variance = sum((p - mean_price) ** 2 for p in prices) / (len(prices) - 1)
    std_dev = math.sqrt(variance)
    return round((std_dev / mean_price) * 100.0, 2)


class MarketAnalysisAgent(BaseAgent):
    """
    Market Analysis Specialist Agent.
    Evaluates price velocity, volume, volatility, liquidity resilience,
    order depth, and slippage using deterministic mathematical models.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm_client or LLMClient()

    @property
    def name(self) -> str:
        return "market_analysis"

    @property
    def responsibility(self) -> str:
        return (
            "Analyze market behavior, price momentum, trading volume velocity, liquidity depth changes, "
            "pool age, buy/sell pressure, volatility, and deterministic price impact."
        )

    @property
    def required_input(self) -> list[str]:
        return ["mint_address"]

    @property
    def available_tools(self) -> list[str]:
        return [
            "deterministic_feature_calculator",
            "market_depth_analyzer",
            "slippage_impact_model",
            "dexscreener_history_reader",
        ]

    @property
    def expected_output_schema(self) -> type[MarketAnalysisOutput]:
        return MarketAnalysisOutput

    @property
    def evidence_requirements(self) -> list[str]:
        return [
            "market_snapshot_series",
            "pair_liquidity_depth",
            "dex_trade_activity",
        ]

    async def investigate(self, context: InvestigationContext) -> MarketAnalysisOutput:
        now_utc = datetime.now(timezone.utc)
        mint_address = context.mint_address
        profile = context.profile

        if profile is None:
            return MarketAnalysisOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                confidence=0.0,
                insufficient_evidence=True,
                insufficient_evidence_reason="No profile or market snapshots available for token.",
                unanswered_questions=["Market pair data has not been observed."],
            )

        profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else dict(profile)
        liquidity = profile_dict.get("liquidity") or {}
        recent_snapshots = profile_dict.get("recent_market_snapshots") or []

        # If zero liquidity exists or primary pair is missing, report insufficient evidence
        liquidity_usd = float(liquidity.get("liquidity_usd") or 0.0)
        pair_address = liquidity.get("primary_pair_address")

        if liquidity_usd <= 0.0 and not recent_snapshots:
            return MarketAnalysisOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                confidence=0.5,
                insufficient_evidence=True,
                insufficient_evidence_reason="Token has no initialized market liquidity pool.",
                unanswered_questions=["Token not yet paired with liquidity or DEX pool."],
            )

        findings: list[AgentFinding] = []
        evidence_references: list[EvidenceItem] = []
        unanswered_questions: list[str] = []

        mkt_ev = EvidenceItem(
            source="market_snapshot_observer",
            timestamp=now_utc,
            reference=f"pair:{pair_address or 'none'}",
            details=liquidity,
        )
        evidence_references.append(mkt_ev)

        # 1. Deterministic Market Metrics Extraction
        price_usd = float(liquidity.get("price_usd") or 0.0)
        volume_5m = float(liquidity.get("volume_5m") or 0.0)
        buys_5m = int(liquidity.get("buys_5m") or 0)
        sells_5m = int(liquidity.get("sells_5m") or 0)
        total_txs_5m = buys_5m + sells_5m
        buy_sell_ratio = round(buys_5m / max(1, sells_5m), 2)
        pool_age_seconds = float(liquidity.get("pool_age_seconds") or 0.0)
        market_cap = float(liquidity.get("market_cap") or 0.0)
        fdv = float(liquidity.get("fdv") or 0.0)

        # 2. Historical Delta Calculations from Snapshots
        liquidity_change_pct = 0.0
        price_change_recent_pct = 0.0
        if len(recent_snapshots) >= 2:
            earliest = recent_snapshots[0]
            latest = recent_snapshots[-1]

            earliest_liq = float(earliest.get("liquidity_usd") or 0.0)
            latest_liq = float(latest.get("liquidity_usd") or 0.0)
            if earliest_liq > 0:
                liquidity_change_pct = round(((latest_liq - earliest_liq) / earliest_liq) * 100.0, 2)

            earliest_px = float(earliest.get("price_usd") or 0.0)
            latest_px = float(latest.get("price_usd") or 0.0)
            if earliest_px > 0:
                price_change_recent_pct = round(((latest_px - earliest_px) / earliest_px) * 100.0, 2)

        volatility = calculate_snapshot_volatility(recent_snapshots)

        # 3. Deterministic Price Impact Model ($100, $500, $1,000, $5,000 orders)
        price_impact = {
            "100_usd": calculate_amm_price_impact(100.0, liquidity_usd),
            "500_usd": calculate_amm_price_impact(500.0, liquidity_usd),
            "1000_usd": calculate_amm_price_impact(1000.0, liquidity_usd),
            "5000_usd": calculate_amm_price_impact(5000.0, liquidity_usd),
        }

        # 4. Momentum Classification
        if buy_sell_ratio > 1.8 and price_change_recent_pct > 5.0:
            momentum_verdict = "BULLISH"
        elif buy_sell_ratio < 0.6 or price_change_recent_pct < -10.0:
            momentum_verdict = "BEARISH"
        elif volume_5m > 0 and abs(price_change_recent_pct) <= 5.0:
            momentum_verdict = "NEUTRAL"
        else:
            momentum_verdict = "EXHAUSTED"

        market_metrics = {
            "price_usd": price_usd,
            "liquidity_usd": liquidity_usd,
            "volume_5m": volume_5m,
            "buys_5m": buys_5m,
            "sells_5m": sells_5m,
            "total_txs_5m": total_txs_5m,
            "buy_sell_ratio": buy_sell_ratio,
            "pool_age_seconds": pool_age_seconds,
            "market_cap": market_cap,
            "fdv": fdv,
            "volatility_pct": volatility,
            "liquidity_change_pct": liquidity_change_pct,
            "price_change_recent_pct": price_change_recent_pct,
            "momentum_verdict": momentum_verdict,
        }

        # 5. Verified Facts
        findings.append(
            AgentFinding(
                type=FindingType.VERIFIED_FACT,
                title="Current Market State Observed",
                statement=(
                    f"Price: ${price_usd:.8f}, Liquidity: ${liquidity_usd:,.2f}, "
                    f"5m Volume: ${volume_5m:,.2f} across {total_txs_5m} trades."
                ),
                confidence=1.0,
                evidence_sources=[mkt_ev],
                metadata=market_metrics,
            )
        )

        findings.append(
            AgentFinding(
                type=FindingType.STATISTICAL_OBSERVATION,
                title="Order Impact and Slippage Profile",
                statement=(
                    f"Estimated constant-product AMM slippage: $100 -> {price_impact['100_usd']}%, "
                    f"$500 -> {price_impact['500_usd']}%, $1,000 -> {price_impact['1000_usd']}%. "
                    f"Historical snapshot volatility is {volatility}%."
                ),
                confidence=0.95,
                evidence_sources=[mkt_ev],
                metadata={"price_impact": price_impact, "volatility": volatility},
            )
        )

        if buy_sell_ratio >= 1.5:
            findings.append(
                AgentFinding(
                    type=FindingType.INFERENCE,
                    title="Net Inflow Buy Pressure",
                    statement=f"Buy count outpaces sells with a ratio of {buy_sell_ratio} ({buys_5m} buys vs {sells_5m} sells).",
                    confidence=0.85,
                    evidence_sources=[mkt_ev],
                )
            )
        elif buy_sell_ratio <= 0.6 and total_txs_5m > 5:
            findings.append(
                AgentFinding(
                    type=FindingType.INFERENCE,
                    title="Heavy Sell-Side Pressure",
                    statement=f"Selling outpaces buying ({sells_5m} sells vs {buys_5m} buys, ratio {buy_sell_ratio}).",
                    confidence=0.85,
                    evidence_sources=[mkt_ev],
                )
            )

        if liquidity_change_pct < -25.0:
            findings.append(
                AgentFinding(
                    type=FindingType.STATISTICAL_OBSERVATION,
                    title="Rapid Liquidity Outflow",
                    statement=f"Liquidity decreased by {abs(liquidity_change_pct)}% across recorded snapshots.",
                    confidence=0.9,
                    evidence_sources=[mkt_ev],
                )
            )

        # 6. LLM Qualitative Synthesis (Optional, over pre-computed metrics ONLY)
        model_name = None
        provider = None
        tokens_used = None

        if self.config.allow_llm:
            prompt_input = (
                f"Token: {profile_dict.get('name')} ({profile_dict.get('symbol')})\n"
                f"Mint: {mint_address}\n"
                f"Calculated Metrics (DO NOT RECALCULATE):\n"
                f"- Price: ${price_usd}\n"
                f"- Liquidity USD: ${liquidity_usd}\n"
                f"- 5m Volume: ${volume_5m}\n"
                f"- Buy/Sell Ratio: {buy_sell_ratio} ({buys_5m} buys, {sells_5m} sells)\n"
                f"- Volatility: {volatility}%\n"
                f"- Price Impact ($500): {price_impact['500_usd']}%\n"
                f"- Price Impact ($1000): {price_impact['1000_usd']}%\n"
                f"- Pool Age: {int(pool_age_seconds)}s\n"
                f"- Momentum: {momentum_verdict}\n"
            )

            llm_resp = await self.llm.generate_structured(
                system_prompt=MARKET_SYSTEM_PROMPT,
                user_prompt=prompt_input,
                response_schema=LLMMarketSynthesis,
                prompt_version=MARKET_AGENT_PROMPT_V1,
                model_override=self.config.model_name,
            )

            if llm_resp.parsed:
                model_name = llm_resp.model
                provider = llm_resp.provider
                tokens_used = llm_resp.usage.total_tokens

                for inf in llm_resp.parsed.inferences:
                    findings.append(
                        AgentFinding(
                            type=FindingType.INFERENCE,
                            title="Market Behavior Synthesis",
                            statement=inf,
                            confidence=0.8,
                            evidence_sources=[mkt_ev],
                        )
                    )
                for hyp in llm_resp.parsed.hypotheses:
                    findings.append(
                        AgentFinding(
                            type=FindingType.HYPOTHESIS,
                            title="Market Trajectory Hypothesis",
                            statement=hyp,
                            confidence=0.6,
                            evidence_sources=[mkt_ev],
                        )
                    )
                unanswered_questions.extend(llm_resp.parsed.unanswered_questions)

        confidence = 0.9 if total_txs_5m > 0 and liquidity_usd > 1000 else 0.7

        return MarketAnalysisOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            confidence=confidence,
            insufficient_evidence=False,
            findings=findings,
            evidence_references=evidence_references,
            unanswered_questions=list(dict.fromkeys(unanswered_questions)),
            metrics=market_metrics,
            market_metrics=market_metrics,
            price_impact=price_impact,
            volatility=volatility,
            momentum_verdict=momentum_verdict,
            model_provider=provider,
            model_name=model_name,
            prompt_version=MARKET_AGENT_PROMPT_V1,
            tokens_used=tokens_used,
        )
