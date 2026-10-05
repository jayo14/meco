# Graph Report - meco  (2026-10-05)

## Corpus Check
- 78 files · ~57,994 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 3, .example 1, .ini 1)

## Summary
- 422 nodes · 1114 edges · 29 communities (18 shown, 11 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 73 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `763937ae`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generate_research_report.py
- test_research.py
- detector.py
- Signal
- analyze_signals.py
- parser.py
- 1. Quantitative Features vs Outcomes
- 1. High-Level Signal Summary
- Detailed Hypotheses Documentation
- Meco 📡
- Critical & High Severity Details
- Meco Quantitative Research Report: Executive Summary
- Meco Outcome & Path Analysis Report
- dataclasses
- Meco Pre-Signal On-Chain Research Plan & Experimental Design
- Meco Execution Model Audit & Sensitivity Analysis
- Meco Forward-Testing Baseline & Cohort Specification
- Meco On-Chain Data Source Review & Feasibility Analysis

## God Nodes (most connected - your core abstractions)
1. `Signal` - 51 edges
2. `run_full_research_pipeline()` - 32 edges
3. `MarketObservation` - 27 edges
4. `filter_usable_signals()` - 20 edges
5. `load_all_signals()` - 20 edges
6. `create_mock_signal()` - 17 edges
7. `build_audit_report()` - 16 edges
8. `load_all_observations()` - 16 edges
9. `calculate_signal_outcome()` - 14 edges
10. `run_friction_sensitivity_grid()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `build_outcomes()` --uses--> `Signal`  [INFERRED]
  scripts/analyze_signals.py → app/database/models.py
- `get_buy_sell_ratio()` --uses--> `Signal`  [INFERRED]
  scripts/analyze_signals.py → app/database/models.py
- `load_data()` --uses--> `Signal`  [INFERRED]
  scripts/analyze_signals.py → app/database/models.py
- `SignalOutcome` --uses--> `Signal`  [INFERRED]
  scripts/analyze_signals.py → app/database/models.py
- `build_outcomes()` --uses--> `MarketObservation`  [INFERRED]
  scripts/analyze_signals.py → app/database/models.py

## Import Cycles
- None detected.

## Communities (29 total, 11 thin omitted)

### Community 0 - "generate_research_report.py"
Cohesion: 0.10
Nodes (28): detect_all_anomalies(), filter_usable_signals(), format_anomaly_markdown(), format_audit_markdown(), analyze_categorical_feature(), analyze_feature_vs_outcomes(), format_features_markdown(), format_hypotheses_markdown() (+20 more)

### Community 1 - "test_research.py"
Cohesion: 0.07
Nodes (45): init_db(), Base, MarketObservation, MarketPairObservation, build_audit_report(), calculate_mean(), calculate_median(), extract_signal_features() (+37 more)

### Community 2 - "detector.py"
Cohesion: 0.09
Nodes (18): derive_pump_bonding_curve(), inspect_bonding_curve_state(), OnChainSourceReview, BondingCurveMetrics, build_pump_logs_subscription_request(), decode_bonding_curve_data(), inspect_token_curve(), parse_pump_instruction_logs() (+10 more)

### Community 3 - "Signal"
Cohesion: 0.08
Nodes (31): get_settings(), Settings, Signal, save_market_observation(), save_market_pair_observations(), create_signal(), update_signal_market(), update_signal_market_status() (+23 more)

### Community 4 - "analyze_signals.py"
Cohesion: 0.31
Nodes (17): average(), build_outcomes(), classify_outcome(), feature_values(), get_buy_sell_ratio(), get_latency(), load_data(), main() (+9 more)

### Community 5 - "parser.py"
Cohesion: 0.29
Nodes (9): extract_slippage(), extract_solana_addresses(), extract_token_address(), extract_token_signal(), TokenSignal, test_extract_token_signal(), test_extracts_address_after_ca(), test_extracts_address_after_contract_address() (+1 more)

### Community 6 - "1. Quantitative Features vs Outcomes"
Cohesion: 0.15
Nodes (12): 1. Quantitative Features vs Outcomes, 2. Categorical Features vs Outcomes, 3. Evidence vs Exploration Assessment, Breakdown by `dex_id`, Feature: `buy_fraction` (Samples: 301), Feature: `buy_sell_ratio` (Samples: 299), Feature: `liquidity_usd` (Samples: 311), Feature: `telegram_latency` (Samples: 287) (+4 more)

### Community 7 - "1. High-Level Signal Summary"
Cohesion: 0.17
Nodes (11): 1. High-Level Signal Summary, 2. Observation Coverage by Target Checkpoint, 3. Pair-Level Observation Coverage, 4. Key Audit Findings & Structural Realities, Date Distribution, DEX Breakdown Across All Stored Pairs, Market Availability Status, Meco Dataset Audit Report (+3 more)

### Community 8 - "Detailed Hypotheses Documentation"
Cohesion: 0.17
Nodes (11): Detailed Hypotheses Documentation, H0: Baseline Naive Follow (All Signals), H1: Anti-Climax Filter (Low Volume/Liquidity), H2: Buy-Pressure Momentum Scalp, H3: Trailing Stop Momentum Rider, Meco Strategy Hypotheses & Paper Trading Evaluation, Performance Breakdown, Performance Breakdown (+3 more)

### Community 9 - "Meco 📡"
Cohesion: 0.18
Nodes (10): Architecture & Tech Stack, Features, License, Meco 📡, Option 1: Docker Deployment (Recommended), Option 2: Local Development, Production VPS Operation, Research & Analytics Suite (+2 more)

### Community 10 - "Critical & High Severity Details"
Cohesion: 0.22
Nodes (8): 1. Signal #103 Liquidity Anomaly, 2. Severe Observation Delays (Catch-up Gaps), 3. Primary Pair Switches Across Checkpoints, 4. Market Availability Failures, Breakdown by Anomaly Category, Critical & High Severity Details, Meco Anomaly & Data Quality Report, Summary of Detected Anomalies

### Community 11 - "Meco Quantitative Research Report: Executive Summary"
Cohesion: 0.22
Nodes (8): 1. Core Mission Question & Empirical Verdict, 2. Quantitative Summary of Market Behavior, 3. Data Quality & Historical Artifacts, 4. Hypothesis Testing & Paper Trading Results, 5. Recommended Strategic Next Steps, Empirical Verdict: **NO EXECUTABLE EDGE FOUND (NEGATIVE EXPECTED VALUE)**, Meco Quantitative Research Report: Executive Summary, Why Did All Hypotheses Fail?

### Community 12 - "Meco Outcome & Path Analysis Report"
Cohesion: 0.22
Nodes (8): 1. Checkpoint Return Distributions, 2. Excursion (MFE / MAE) & Path Dynamics, 3. Threshold Reachability Matrix, 4. Key Quantitative Insights, Maximum Adverse Excursion (MAE - Worst Drawdown), Maximum Favorable Excursion (MFE - Peak Upside), Meco Outcome & Path Analysis Report, Peak-to-Trough Collapse

### Community 13 - "dataclasses"
Cohesion: 0.20
Nodes (10): classify_signal_cohort(), CohortSummary, format_baseline_cohort_markdown(), partition_by_cohort(), SignalCohort, summarize_cohort(), main(), format_onchain_source_review_markdown() (+2 more)

### Community 25 - "Meco Pre-Signal On-Chain Research Plan & Experimental Design"
Cohesion: 0.20
Nodes (9): 1. Core Hypothesis & Empirical Motivation, 2. Experimental Design: Two-System Comparison, 3. Control Group Architecture (Eliminating Survivorship Bias), 4. Candidate Pre-Signal Features (T - Minutes), 5. Latency as a First-Class Metric, Empirical Finding from Historical Reconstruction:, Meco Pre-Signal On-Chain Research Plan & Experimental Design, Strategy A: Telegram-Triggered (Control Baseline) (+1 more)

### Community 26 - "Meco Execution Model Audit & Sensitivity Analysis"
Cohesion: 0.33
Nodes (5): 1. Parameter Classification & Methodology, 2. Friction Sensitivity Grid Analysis, 3. Robustness Verdict, Interpretation of Parameter Biases:, Meco Execution Model Audit & Sensitivity Analysis

### Community 27 - "Meco Forward-Testing Baseline & Cohort Specification"
Cohesion: 0.40
Nodes (4): 1. Dataset Partition Boundary, 2. Historical Research Baseline Metrics (Cohort 1), 3. Forward Collection Protocol & Integrity Rules, Meco Forward-Testing Baseline & Cohort Specification

### Community 28 - "Meco On-Chain Data Source Review & Feasibility Analysis"
Cohesion: 0.40
Nodes (4): 1. Executive Evaluation Matrix, 2. Empirical Findings from Live Solana RPC Audit, 3. Recommended Technical Architecture for Pre-Signal Detection, Meco On-Chain Data Source Review & Feasibility Analysis

## Knowledge Gaps
- **62 isolated node(s):** `OnChainSourceReview`, `Features`, `Architecture & Tech Stack`, `Option 1: Docker Deployment (Recommended)`, `Option 2: Local Development` (+57 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 156 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Signal` connect `Signal` to `generate_research_report.py`, `test_research.py`, `analyze_signals.py`, `dataclasses`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `MarketObservation` connect `test_research.py` to `generate_research_report.py`, `Signal`, `analyze_signals.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `run_full_research_pipeline()` connect `generate_research_report.py` to `test_research.py`, `dataclasses`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `Signal` (e.g. with `save_market_observation()` and `save_market_pair_observations()`) actually correct?**
  _`Signal` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `MarketObservation` (e.g. with `detect_all_anomalies()` and `build_audit_report()`) actually correct?**
  _`MarketObservation` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `OnChainSourceReview`, `Features`, `Architecture & Tech Stack` to the rest of the system?**
  _62 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `generate_research_report.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0992063492063492 - nodes in this community are weakly interconnected._