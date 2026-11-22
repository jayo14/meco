"""
Target Labels & Executable Exit Modeling for Meco Quantitative Research (Phase 7).

Computes forward path-dependent target variables, excursions, and executable
exit classifications. Avoids treating temporary illiquid spikes as successful trades.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass
class TargetLabels:
    """
    Complete forward label suite for a prediction point at T+0.
    """
    token_mint: str
    prediction_timestamp: datetime
    initial_price_usd: float
    initial_liquidity_usd: float

    # 1. Forward Returns at Fixed Horizons (%)
    return_1m_pct: float | None = None
    return_5m_pct: float | None = None
    return_15m_pct: float | None = None
    return_30m_pct: float | None = None
    return_60m_pct: float | None = None

    # 2. Maximum Excursions over Horizon (up to 60m)
    max_favourable_excursion_pct: float = 0.0  # MFE
    max_adverse_excursion_pct: float = 0.0     # MAE
    seconds_to_mfe: int = 0
    seconds_to_mae: int = 0

    # 3. Time to Target Milestones (seconds, 0 if not reached)
    seconds_to_plus_20pct: int | None = None
    seconds_to_plus_50pct: int | None = None
    seconds_to_minus_20pct: int | None = None
    seconds_to_minus_50pct: int | None = None

    # 4. Liquidity & Deterioration
    min_forward_liquidity_usd: float = 0.0
    liquidity_deterioration_detected: bool = False  # True if forward liquidity drops > 30%
    max_liquidity_drop_pct: float = 0.0

    # 5. Executable Exit & Net Friction Outcomes
    # Realistic exit check: must have enough liquidity to absorb exit without exceeding max price impact
    is_executable_exit_possible: bool = True
    estimated_roundtrip_friction_pct: float = 2.0  # Slippage + Impact + Fees
    net_return_5m_pct: float | None = None
    net_return_15m_pct: float | None = None
    net_return_60m_pct: float | None = None

    # 6. Discrete Classification Labels
    # Binary classification target: Did token achieve >= +25% net gain with executable liquidity before -15% stop loss?
    binary_profit_target_hit: bool = False
    is_liquidity_trap: bool = False  # Price spiked but liquidity collapsed or was too shallow to exit

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["prediction_timestamp"] = self.prediction_timestamp.isoformat()
        return data


class TargetLabelComputer:
    """
    Computes path-dependent forward labels from future market checkpoints (T > T_pred).
    Enforces realistic exit feasibility checks to filter out phantom liquidity spikes.
    """

    def __init__(
        self,
        nominal_exit_size_usd: float = 100.0,
        base_slippage_pct: float = 1.5,
        dex_fee_pct: float = 0.50,  # 0.25% x 2 roundtrip
        solana_fee_usd: float = 0.01,
        max_acceptable_exit_impact_pct: float = 5.0,
        liquidity_drop_threshold_pct: float = 30.0,
    ) -> None:
        self.nominal_exit_size_usd = nominal_exit_size_usd
        self.base_slippage_pct = base_slippage_pct
        self.dex_fee_pct = dex_fee_pct
        self.solana_fee_usd = solana_fee_usd
        self.max_acceptable_exit_impact_pct = max_acceptable_exit_impact_pct
        self.liquidity_drop_threshold_pct = liquidity_drop_threshold_pct

    def compute_labels(
        self,
        token_mint: str,
        prediction_timestamp: datetime,
        initial_price_usd: float,
        initial_liquidity_usd: float,
        forward_checkpoints: list[dict[str, Any]],
        horizon_seconds: int = 3600,
    ) -> TargetLabels:
        """
        Evaluate forward checkpoints strictly occurring after prediction_timestamp.
        Each checkpoint: {"timestamp": datetime, "price_usd": float, "liquidity_usd": float}
        """
        if prediction_timestamp.tzinfo is None:
            prediction_timestamp = prediction_timestamp.replace(tzinfo=timezone.utc)

        labels = TargetLabels(
            token_mint=token_mint,
            prediction_timestamp=prediction_timestamp,
            initial_price_usd=initial_price_usd,
            initial_liquidity_usd=initial_liquidity_usd,
            min_forward_liquidity_usd=initial_liquidity_usd,
        )

        if initial_price_usd <= 0.0 or not forward_checkpoints:
            return labels

        # Filter strictly future checkpoints up to horizon_seconds
        future_obs: list[tuple[float, float, float]] = []  # (elapsed_seconds, price, liquidity)
        for cp in forward_checkpoints:
            ts = cp.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts <= prediction_timestamp:
                continue

            elapsed = (ts - prediction_timestamp).total_seconds()
            if 0 < elapsed <= horizon_seconds:
                p = float(cp.get("price_usd", 0.0))
                l = float(cp.get("liquidity_usd", initial_liquidity_usd))
                if p > 0:
                    future_obs.append((elapsed, p, l))

        if not future_obs:
            return labels

        future_obs.sort(key=lambda x: x[0])

        best_ret = 0.0
        worst_ret = 0.0
        sec_mfe = 0
        sec_mae = 0
        min_liq = initial_liquidity_usd

        # Track targets
        sec_p20 = None
        sec_p50 = None
        sec_m20 = None
        sec_m50 = None

        hit_tp25_before_sl15 = False
        sl15_hit = False

        for elapsed, price, liq in future_obs:
            ret_pct = ((price - initial_price_usd) / initial_price_usd) * 100.0

            if ret_pct > best_ret:
                best_ret = ret_pct
                sec_mfe = int(elapsed)

            if ret_pct < worst_ret:
                worst_ret = ret_pct
                sec_mae = int(elapsed)

            if liq < min_liq:
                min_liq = liq

            # Milestones
            if ret_pct >= 20.0 and sec_p20 is None:
                sec_p20 = int(elapsed)
            if ret_pct >= 50.0 and sec_p50 is None:
                sec_p50 = int(elapsed)
            if ret_pct <= -20.0 and sec_m20 is None:
                sec_m20 = int(elapsed)
            if ret_pct <= -50.0 and sec_m50 is None:
                sec_m50 = int(elapsed)

            # Path-dependent strategy hit
            if not sl15_hit and not hit_tp25_before_sl15:
                if ret_pct <= -15.0:
                    sl15_hit = True
                elif ret_pct >= 25.0:
                    hit_tp25_before_sl15 = True

        labels.max_favourable_excursion_pct = round(best_ret, 2)
        labels.max_adverse_excursion_pct = round(worst_ret, 2)
        labels.seconds_to_mfe = sec_mfe
        labels.seconds_to_mae = sec_mae
        labels.seconds_to_plus_20pct = sec_p20
        labels.seconds_to_plus_50pct = sec_p50
        labels.seconds_to_minus_20pct = sec_m20
        labels.seconds_to_minus_50pct = sec_m50
        labels.min_forward_liquidity_usd = round(min_liq, 2)

        # Liquidity deterioration check
        if initial_liquidity_usd > 0:
            liq_drop = ((initial_liquidity_usd - min_liq) / initial_liquidity_usd) * 100.0
            labels.max_liquidity_drop_pct = round(max(0.0, liq_drop), 2)
            if labels.max_liquidity_drop_pct >= self.liquidity_drop_threshold_pct:
                labels.liquidity_deterioration_detected = True

        # Extract fixed horizon returns (closest observation within tolerance)
        def find_horizon_return(target_secs: int, tolerance_secs: int = 45) -> tuple[float | None, float]:
            candidates = [
                (abs(el - target_secs), p, l)
                for el, p, l in future_obs
                if abs(el - target_secs) <= tolerance_secs
            ]
            if not candidates:
                return None, initial_liquidity_usd
            candidates.sort(key=lambda c: c[0])
            chosen_price = candidates[0][1]
            chosen_liq = candidates[0][2]
            ret = ((chosen_price - initial_price_usd) / initial_price_usd) * 100.0
            return round(ret, 2), chosen_liq

        r1, _ = find_horizon_return(60, tolerance_secs=30)
        r5, l5 = find_horizon_return(300, tolerance_secs=60)
        r15, l15 = find_horizon_return(900, tolerance_secs=180)
        r30, _ = find_horizon_return(1800, tolerance_secs=300)
        r60, l60 = find_horizon_return(3600, tolerance_secs=600)

        labels.return_1m_pct = r1
        labels.return_5m_pct = r5
        labels.return_15m_pct = r15
        labels.return_30m_pct = r30
        labels.return_60m_pct = r60

        # Calculate estimated roundtrip friction and net returns
        # AMM Price Impact at exit: size / (pool / 2)
        exit_pool_liq = max(100.0, l15 if l15 else initial_liquidity_usd)
        reserve_side = exit_pool_liq / 2.0
        exit_impact_pct = (self.nominal_exit_size_usd / reserve_side) * 100.0
        entry_impact_pct = (self.nominal_exit_size_usd / (initial_liquidity_usd / 2.0)) * 100.0 if initial_liquidity_usd > 0 else 5.0
        
        gas_burden_pct = (self.solana_fee_usd * 2.0 / self.nominal_exit_size_usd) * 100.0
        total_friction_pct = self.base_slippage_pct * 2.0 + self.dex_fee_pct + entry_impact_pct + exit_impact_pct + gas_burden_pct
        labels.estimated_roundtrip_friction_pct = round(total_friction_pct, 2)

        # Net outcomes
        if r5 is not None:
            labels.net_return_5m_pct = round(r5 - total_friction_pct, 2)
        if r15 is not None:
            labels.net_return_15m_pct = round(r15 - total_friction_pct, 2)
        if r60 is not None:
            labels.net_return_60m_pct = round(r60 - total_friction_pct, 2)

        # Exit Feasibility Validation (Anti-Phantom Spike Guard)
        # If pool liquidity is so small that selling $100 causes > max_acceptable_exit_impact_pct, exit fails
        if exit_impact_pct > self.max_acceptable_exit_impact_pct or exit_pool_liq < 1000.0:
            labels.is_executable_exit_possible = False
            if best_ret >= 50.0:
                # High spike with no exit liquidity = liquidity trap
                labels.is_liquidity_trap = True

        # Binary label: hit +25% net gain executable before stop loss
        if hit_tp25_before_sl15 and labels.is_executable_exit_possible and not labels.liquidity_deterioration_detected:
            labels.binary_profit_target_hit = True
        else:
            labels.binary_profit_target_hit = False

        return labels
