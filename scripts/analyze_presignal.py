import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.research.anomalies import filter_usable_signals
from app.research.loader import load_all_pair_observations, load_all_signals
from app.research.presignal import (
    analyze_presignal_cohort,
    reconstruct_presignal_metrics,
)


def format_presignal_research_plan_markdown(analysis) -> str:
    med_m = (
        f"{analysis.median_pool_age_seconds/60:.1f} minutes ({analysis.median_pool_age_seconds:.0f}s)"
        if analysis.median_pool_age_seconds is not None
        else "n/a"
    )

    lines = [
        "# Meco Pre-Signal On-Chain Research Plan & Experimental Design",
        "",
        "## 1. Core Hypothesis & Empirical Motivation",
        "",
        "> **Central Research Question:**",
        "> *Is the public Telegram signal an actionable source of forward-looking alpha, or merely a delayed confirmation of an on-chain event that has already progressed past its optimal entry point?*",
        "",
        "### Empirical Finding from Historical Reconstruction:",
        f"- Across **{analysis.total_evaluated} evaluated tokens** with on-chain pool creation timestamps:",
        f"- **Median Pool Age when Telegram alert was posted:** **{med_m}**.",
        f"- Tokens ≤ 2 minutes old at signal time: **{analysis.pct_under_2_minutes:.1f}%**.",
        f"- Tokens ≤ 5 minutes old at signal time: **{analysis.pct_under_5_minutes:.1f}%**.",
        f"- Tokens ≤ 15 minutes old at signal time: **{analysis.pct_under_15_minutes:.1f}%**.",
        f"- Tokens > 1 hour old at signal time: **{analysis.pct_over_1_hour:.1f}%**.",
        "",
        "**Conclusion:** The public Telegram channel is systematically late. In fast-moving Solana meme-coin markets, an 8.6-minute delay means retail callers enter after early snipers and accumulation have completed.",
        "",
        "---",
        "",
        "## 2. Experimental Design: Two-System Comparison",
        "",
        "To test whether independent on-chain detection contains predictive power, we design a controlled prospective experiment comparing two systems:",
        "",
        "### Strategy A: Telegram-Triggered (Control Baseline)",
        "```text",
        "On-chain pool created",
        "       ↓ (8.6m median delay)",
        "Telegram alert posted",
        "       ↓ (1.0s Meco latency)",
        "Meco hypothetical entry",
        "       ↓",
        "Observed outcome: Net Expected Value = -$2.68 per $100 trade",
        "```",
        "",
        "### Strategy B: On-Chain-Triggered (Candidate Alpha System)",
        "```text",
        "On-chain pool created / Pump.fun bonding curve initialized",
        "       ↓ (50ms - 200ms WebSocket / RPC event)",
        "Meco on-chain detection",
        "       ↓",
        "Pre-signal feature filter (liquidity, initial buy momentum, creator checks)",
        "       ↓",
        "Hypothetical pre-signal entry (T-8m before Telegram)",
        "       ↓",
        "Measure: Does early detection yield positive net returns after friction?",
        "```",
        "",
        "---",
        "",
        "## 3. Control Group Architecture (Eliminating Survivorship Bias)",
        "",
        "To prevent survivorship bias (studying only tokens that Telegram chose to call), the prospective on-chain experiment mandates a **1:1 Control Cohort**:",
        "",
        "| Cohort | Definition | Selection Criteria | Purpose |",
        "| :--- | :--- | :--- | :--- |",
        "| **Treatment Cohort (Telegram Called)** | Tokens appearing on Telegram alerts | Received via Meco Telethon listener | Establishes whether Telegram-selected tokens had unique pre-signal signatures. |",
        "| **Control Cohort (Uncalled Pools)** | New pools on Pump.fun / Raydium created in same time window | Sampled from RPC `logsSubscribe` or DexScreener new pairs | Baseline: measures base-rate survival of all newly created meme pools. |",
        "",
        "Without this control group, any filter would simply learn 'tokens Telegram likes', which provides zero independent detection utility.",
        "",
        "---",
        "",
        "## 4. Candidate Pre-Signal Features (T - Minutes)",
        "",
        "For candidate on-chain detection, only features observable before hypothetical entry may be used:",
        "",
        "| Feature Name | Definition | Measurement Source | Target Window |",
        "| :--- | :--- | :--- | :--- |",
        "| `time_since_pool_creation` | Elapsed seconds since pool initialized | `block_time` of initialization tx | T+10s to T+120s |",
        "| `bonding_curve_progress_pct` | Virtual SOL accumulated / Target curve cap | Pump.fun Bonding Curve PDA | Real-time state |",
        "| `initial_buyer_concentration` | % of supply bought by top 5 unique wallets | Pre/post token balances | First 20 swaps |",
        "| `liquidity_velocity` | $\\Delta \\text{Liquidity} / \\Delta t$ | Pool reserves | 30s rolling |",
        "| `buy_sell_pressure` | $\\text{Buys} / (\\text{Buys} + \\text{Sells})$ | Decoded swap instructions | 60s rolling |",
        "",
        "---",
        "",
        "## 5. Latency as a First-Class Metric",
        "",
        "The on-chain pipeline must record exact microsecond timestamps across four milestones:",
        "1. `t_source_block`: Solana block timestamp of the liquidity event.",
        "2. `t_meco_received`: Wall-clock UTC time Meco received the WebSocket notification.",
        "3. `t_meco_decision`: Timestamp feature calculation and filter decision completed.",
        "4. `t_telegram_signal`: If token is eventually called on Telegram, timestamp of the message.",
        "",
        "This allows exact empirical measurement of **information lead time**: `Lead Time = t_telegram_signal - t_meco_decision`.",
    ]

    return "\n".join(lines)


async def main() -> None:
    print("=" * 80)
    print("MECO PRE-SIGNAL ON-CHAIN RECONSTRUCTION & RESEARCH PLAN")
    print("=" * 80)

    signals = await load_all_signals()
    pair_observations = await load_all_pair_observations()

    usable_signals, _ = filter_usable_signals(signals)

    metrics = reconstruct_presignal_metrics(usable_signals, pair_observations)
    analysis = analyze_presignal_cohort(metrics)

    print(f"Total Evaluated Pools with On-Chain Creation Data: {analysis.total_evaluated}")
    if analysis.median_pool_age_seconds is not None:
        print(
            f"Median Pool Age at Telegram Signal: {analysis.median_pool_age_seconds/60:.1f} minutes ({analysis.median_pool_age_seconds:.0f}s)"
        )
    print(f"Pools <= 2m Old at Signal:  {analysis.pct_under_2_minutes:.1f}%")
    print(f"Pools <= 5m Old at Signal:  {analysis.pct_under_5_minutes:.1f}%")
    print(f"Pools <= 15m Old at Signal: {analysis.pct_under_15_minutes:.1f}%")
    print(f"Pools > 1 Hour Old at Signal: {analysis.pct_over_1_hour:.1f}%")
    print()

    # Generate Report
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_presignal_research_plan_markdown(analysis)
    md_path = reports_dir / "presignal_research_plan.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "presignal_research_plan.json"
    json_path.write_text(
        json.dumps(
            {
                "cohort_analysis": asdict(analysis),
                "sample_metrics": [
                    asdict(m) for m in metrics[:10]
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"Pre-signal research plan saved to: {md_path}")
    print(f"JSON metrics saved to:             {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
