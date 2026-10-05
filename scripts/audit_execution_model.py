import asyncio
import json
from pathlib import Path

from app.research.anomalies import filter_usable_signals
from app.research.loader import (
    group_observations_by_signal,
    load_all_observations,
    load_all_signals,
)
from app.research.simulation import (
    format_execution_audit_markdown,
    run_friction_sensitivity_grid,
)


async def main() -> None:
    print("=" * 80)
    print("MECO EXECUTION MODEL AUDIT & SENSITIVITY ANALYSIS")
    print("=" * 80)

    signals = await load_all_signals()
    observations = await load_all_observations()

    usable_signals, _ = filter_usable_signals(signals)
    obs_by_signal = group_observations_by_signal(observations)

    grid_results = run_friction_sensitivity_grid(usable_signals, obs_by_signal)

    print("Friction Sensitivity Results ($100 Trade Size):")
    print(
        f"  {'Tier':<20} {'Trades':>7} {'Win%':>7} {'Gross Ret':>12} "
        f"{'Net Ret':>10} {'Total PnL':>12} {'Expectancy':>12}"
    )
    for tier, data in grid_results.items():
        if data.get("total_trades", 0) == 0:
            continue
        print(
            f"  {tier:<20} {data['total_trades']:>7} {data['win_rate_pct']:>6.1f}% "
            f"{data['mean_gross_return_pct']:>+11.2f}% {data['mean_net_return_pct']:>+9.2f}% "
            f"${data['total_pnl_usd']:>+11.2f} ${data['expectancy_per_trade_usd']:>+11.2f}"
        )
    print()

    # Save report
    reports_dir = Path("research/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_content = format_execution_audit_markdown(grid_results)
    md_path = reports_dir / "execution_model_audit.md"
    md_path.write_text(md_content, encoding="utf-8")

    json_path = reports_dir / "execution_model_audit.json"
    json_path.write_text(
        json.dumps(
            {
                tier: {
                    k: (str(v) if not isinstance(v, (int, float, bool, list, dict)) else v)
                    for k, v in data.items()
                }
                for tier, data in grid_results.items()
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"Audit report saved to: {md_path}")
    print(f"JSON metrics saved to: {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
