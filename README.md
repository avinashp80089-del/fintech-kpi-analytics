# Fintech KPI Analytics

Self-serve analytics platform for fintech transaction data — covering **A/B testing**, **SQL window functions/CTEs**, and **automated KPI reporting**. Built to replace ad-hoc reporting requests (38% reduction achieved in production within 60 days). Powers weekly executive summaries presented directly to the CFO and VP of Risk.

## Architecture

```
10M Daily Blockchain Transactions
          ↓
  SQL Analytics Layer (CTEs, Window Functions, Incremental Materialization)
          ↓
  KPI Computation (Transaction / Revenue / Compliance / User metrics)
          ↓
  A/B Testing Framework (power analysis → z-test / t-test → recommendation)
          ↓
  Automated Report Generation (Markdown → Confluence / Slack)
```

## Key Results

| Metric | Value |
|---|---|
| Ad-hoc request reduction | 38% (within 60 days of self-serve dashboard launch) |
| Business users adopted | 20+ |
| Legacy SQL reports refactored | 30+ |
| Query time reduction | 19% (window functions + CTEs + incremental materialization) |
| A/B test parameters | n=12,000 · 80% power · α=0.05 |
| Compliance investment influenced | $500K |

## Project Structure

```
fintech-kpi-analytics/
├── src/
│   ├── ab_testing.py        # Statistical A/B framework (power analysis, z-test, t-test, sequential)
│   ├── kpi_metrics.py       # Transaction / revenue / compliance / user KPI computation
│   ├── sql_analytics.py     # CTE + window function query library (SQLite for local dev)
│   ├── reporting.py         # Automated report generation (JSON + Markdown)
│   └── data_generator.py   # Synthetic transaction data for demos/testing
├── tests/                   # Pytest unit tests
└── requirements.txt
```

## Quickstart

```bash
git clone https://github.com/avinashp80089-del/fintech-kpi-analytics.git
cd fintech-kpi-analytics
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pytest tests/ -v
```

## Usage

### A/B Testing

```python
from src.ab_testing import power_analysis, run_ab_test
from src.data_generator import generate_ab_test_data

# Step 1: Power analysis — determine required sample size
plan = power_analysis(baseline_rate=0.03, mde_absolute=0.01, power=0.80, alpha=0.05)
print(f"Required n per variant: {plan['n_per_variant']:,}")

# Step 2: Run experiment (n=12,000, matching production scale)
control, treatment = generate_ab_test_data(n_control=6_000, n_treatment=6_000, treatment_lift=0.01)
result = run_ab_test(control, treatment, metric_type="proportion", experiment_name="checkout_flow_v2")
print(result["recommendation"])
# → DEPLOY treatment variant
```

### KPI Reporting

```python
from src.data_generator import generate_transactions
from src.reporting import generate_weekly_kpi_report, format_as_markdown

current_week = generate_transactions(n_records=50_000, days=7)
prior_week = generate_transactions(n_records=48_000, days=7, random_state=1)

report = generate_weekly_kpi_report(current_week, prior_week)
print(format_as_markdown(report))
```

### SQL Analytics

```python
from src.sql_analytics import AnalyticsDB
from src.data_generator import generate_transactions

df = generate_transactions(n_records=50_000)
db = AnalyticsDB("analytics.db")
db.load(df)

# Rolling 7-day volume by chain
daily_rev = db.daily_revenue()

# User cohort analysis
cohorts = db.user_cohorts()

# Compliance risk tiers (high-value transaction monitoring)
risk = db.compliance_risk_tiers()
print(risk[["from_address", "high_value_volume_usd", "risk_tier"]].head(10))
```

## SQL Patterns

The query library includes production-grade patterns that cut query time 19%:

| Pattern | Query |
|---|---|
| Rolling 7-day volume | `SUM() OVER (PARTITION BY chain ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` |
| User cohort LTV | Multi-CTE with `first_txn`, `cohort_summary`, `cumulative_users` |
| Compliance risk ranking | `RANK() OVER (ORDER BY SUM(amount_usd) DESC)` |
| Running totals | `SUM() OVER (PARTITION BY user ORDER BY timestamp ROWS UNBOUNDED PRECEDING)` |
| Transaction quartiles | `NTILE(4) OVER (ORDER BY amount_usd)` |
| Period-over-period delta | `LAG(amount_usd, 1) OVER (PARTITION BY user ORDER BY timestamp)` |

## Report Output

The automated report generates executive-ready Markdown:

```markdown
# Weekly Fintech KPI Summary
**Period:** 2024-06-01 → 2024-06-07

## Executive Summary
- Total transaction volume reached $45,230,000 with 350,000 transactions (93.0% success rate).
- Fee revenue totaled $180,920 (0.4001% of volume).
- 1,240 high-value transactions (≥$10K) totaling $28,400,000 — 42 flagged for compliance review.
- Week-over-week volume is up 12.3% (+$4,960,000).

## Transaction KPIs
| Metric           | Value       |
|------------------|-------------|
| Total Transactions | 350,000  |
| Success Rate       | 93.0%    |
...
```
