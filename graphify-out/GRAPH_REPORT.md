# Graph Report - meco  (2026-10-05)

## Corpus Check
- 60 files · ~48,276 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .ini 1)

## Summary
- 313 nodes · 815 edges · 25 communities (14 shown, 11 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 60 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `03227917`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generate_research_report.py
- test_research.py
- Signal
- client.py
- analyze_signals.py
- parser.py
- 1. Quantitative Features vs Outcomes
- 1. High-Level Signal Summary
- Detailed Hypotheses Documentation
- Meco 📡
- Critical & High Severity Details
- Meco Quantitative Research Report: Executive Summary
- Meco Outcome & Path Analysis Report
- spearman_rank_correlation

## God Nodes (most connected - your core abstractions)
1. `Signal` - 42 edges
2. `MarketObservation` - 24 edges
3. `run_full_research_pipeline()` - 23 edges
4. `build_audit_report()` - 16 edges
5. `filter_usable_signals()` - 14 edges
6. `load_all_signals()` - 14 edges
7. `load_all_observations()` - 14 edges
8. `calculate_signal_outcome()` - 14 edges
9. `process_new_message()` - 14 edges
10. `create_market_snapshot()` - 12 edges

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

## Communities (25 total, 11 thin omitted)

### Community 0 - "generate_research_report.py"
Cohesion: 0.11
Nodes (24): detect_all_anomalies(), filter_usable_signals(), format_anomaly_markdown(), format_audit_markdown(), analyze_categorical_feature(), analyze_feature_vs_outcomes(), extract_signal_features(), format_features_markdown() (+16 more)

### Community 1 - "test_research.py"
Cohesion: 0.11
Nodes (28): MarketObservation, build_audit_report(), calculate_mean(), calculate_median(), chronological_split(), evaluate_hypothesis_on_set(), format_hypotheses_markdown(), run_hypotheses_evaluation() (+20 more)

### Community 2 - "Signal"
Cohesion: 0.12
Nodes (18): init_db(), Base, MarketPairObservation, Signal, save_market_observation(), save_market_pair_observations(), get_token_pairs(), MarketPair (+10 more)

### Community 3 - "client.py"
Cohesion: 0.11
Nodes (14): get_settings(), Settings, create_signal(), update_signal_market(), update_signal_market_status(), update_signal_validation(), get_mint_info(), MintInfo (+6 more)

### Community 4 - "analyze_signals.py"
Cohesion: 0.31
Nodes (17): average(), build_outcomes(), classify_outcome(), feature_values(), get_buy_sell_ratio(), get_latency(), load_data(), main() (+9 more)

### Community 5 - "parser.py"
Cohesion: 0.29
Nodes (9): extract_slippage(), extract_solana_addresses(), extract_token_address(), extract_token_signal(), TokenSignal, test_extract_token_signal(), test_extracts_address_after_ca(), test_extracts_address_after_contract_address() (+1 more)

### Community 6 - "1. Quantitative Features vs Outcomes"
Cohesion: 0.15
Nodes (12): 1. Quantitative Features vs Outcomes, 2. Categorical Features vs Outcomes, 3. Evidence vs Exploration Assessment, Breakdown by `dex_id`, Feature: `buy_fraction` (Samples: 294), Feature: `buy_sell_ratio` (Samples: 292), Feature: `liquidity_usd` (Samples: 304), Feature: `telegram_latency` (Samples: 280) (+4 more)

### Community 7 - "1. High-Level Signal Summary"
Cohesion: 0.17
Nodes (11): 1. High-Level Signal Summary, 2. Observation Coverage by Target Checkpoint, 3. Pair-Level Observation Coverage, 4. Key Audit Findings & Structural Realities, Date Distribution, DEX Breakdown Across All Stored Pairs, Market Availability Status, Meco Dataset Audit Report (+3 more)

### Community 8 - "Detailed Hypotheses Documentation"
Cohesion: 0.17
Nodes (11): Detailed Hypotheses Documentation, H0: Baseline Naive Follow (All Signals), H1: Anti-Climax Filter (Low Volume/Liquidity), H2: Buy-Pressure Momentum Scalp, H3: Trailing Stop Momentum Rider, Meco Strategy Hypotheses & Paper Trading Evaluation, Performance Breakdown, Performance Breakdown (+3 more)

### Community 9 - "Meco 📡"
Cohesion: 0.20
Nodes (9): Analytics, Architecture & Tech Stack, Features, License, Meco 📡, Option 1: Docker Deployment (Recommended), Option 2: Local Development, Setup & Installation (+1 more)

### Community 10 - "Critical & High Severity Details"
Cohesion: 0.22
Nodes (8): 1. Signal #103 Liquidity Anomaly, 2. Severe Observation Delays (Catch-up Gaps), 3. Primary Pair Switches Across Checkpoints, 4. Market Availability Failures, Breakdown by Anomaly Category, Critical & High Severity Details, Meco Anomaly & Data Quality Report, Summary of Detected Anomalies

### Community 11 - "Meco Quantitative Research Report: Executive Summary"
Cohesion: 0.22
Nodes (8): 1. Core Mission Question & Empirical Verdict, 2. Quantitative Summary of Market Behavior, 3. Data Quality & Historical Artifacts, 4. Hypothesis Testing & Paper Trading Results, 5. Recommended Strategic Next Steps, Empirical Verdict: **NO EXECUTABLE EDGE FOUND (NEGATIVE EXPECTED VALUE)**, Meco Quantitative Research Report: Executive Summary, Why Did All Hypotheses Fail?

### Community 12 - "Meco Outcome & Path Analysis Report"
Cohesion: 0.22
Nodes (8): 1. Checkpoint Return Distributions, 2. Excursion (MFE / MAE) & Path Dynamics, 3. Threshold Reachability Matrix, 4. Key Quantitative Insights, Maximum Adverse Excursion (MAE - Worst Drawdown), Maximum Favorable Excursion (MFE - Peak Upside), Meco Outcome & Path Analysis Report, Peak-to-Trough Collapse

### Community 13 - "spearman_rank_correlation"
Cohesion: 0.25
Nodes (4): pearson_correlation(), spearman_rank_correlation(), group_pairs_by_signal(), test_correlations()

## Knowledge Gaps
- **45 isolated node(s):** `Features`, `Architecture & Tech Stack`, `Option 1: Docker Deployment (Recommended)`, `Option 2: Local Development`, `Analytics` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 117 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Signal` connect `Signal` to `generate_research_report.py`, `test_research.py`, `client.py`, `analyze_signals.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `MarketObservation` connect `test_research.py` to `generate_research_report.py`, `Signal`, `analyze_signals.py`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `run_full_research_pipeline()` connect `generate_research_report.py` to `test_research.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `Signal` (e.g. with `save_market_observation()` and `save_market_pair_observations()`) actually correct?**
  _`Signal` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MarketObservation` (e.g. with `detect_all_anomalies()` and `build_audit_report()`) actually correct?**
  _`MarketObservation` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `build_audit_report()` (e.g. with `MarketObservation` and `MarketPairObservation`) actually correct?**
  _`build_audit_report()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Features`, `Architecture & Tech Stack`, `Option 1: Docker Deployment (Recommended)` to the rest of the system?**
  _45 weakly-connected nodes found - possible documentation gaps or missing edges._