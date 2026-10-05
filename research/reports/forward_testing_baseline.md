# Meco Forward-Testing Baseline & Cohort Specification

## 1. Dataset Partition Boundary

To prevent historical contamination and establish a scientific boundary between retrospective exploration and prospective forward evaluation, the dataset is split into two immutable cohorts:

| Cohort | Signal ID Range | Timestamp Range | Status | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`HISTORICAL_RESEARCH`** | `1` to `387` | `2026-10-02` to `2026-10-05` | **FROZEN** | Initial data audit, anomaly detection, feature exploration, and initial hypothesis falsification. |
| **`FORWARD_TESTING`** | `388+` | Ongoing | **ACTIVE** | Uninterrupted 24/7 VPS forward collection. Tests whether future signals exhibit different dynamics. |

---

## 2. Historical Research Baseline Metrics (Cohort 1)

- **Total Captured Signals:** 387
- **Clean Usable Signals for Research:** 306
- **Excluded Signals:** 81 (test calls, unliquid pools, anomaly #103)
- **Identified Phenomena:**
  - Median time to peak: **121 seconds** (~2.0 minutes)
  - Median peak upside (MFE): **+12.9%**
  - Median post-peak collapse: **-72.0%**
  - Falsified hypotheses: All 4 tested strategies produced negative net EV after realistic friction.

---

## 3. Forward Collection Protocol & Integrity Rules

1. **Never Backfill or Mutate Historical Cohort:** Historical signals (1 to 387) are immutable baseline ground truth.
2. **Stale Target Protection:** The active listener enforces `max_tolerance = 60s` (300s for >=1h targets). If the collector is delayed or offline, expired checkpoints are logged as `missed_offline` rather than recording stale prices.
3. **Complete Observation Schedule:** The continuous VPS deployment will capture uninterrupted observations across all 12 targets:
   - `T+10s, T+30s, T+60s, T+120s, T+180s, T+300s, T+600s, T+900s, T+1800s, T+3600s, T+21600s, T+86400s`
4. **Prospective Forward Testing:** Any future hypothesis must be frozen before evaluating on the `FORWARD_TESTING` cohort to guarantee zero data snooping.