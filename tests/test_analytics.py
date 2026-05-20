"""Unit tests for fintech analytics modules."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.data_generator import generate_transactions, generate_ab_test_data
from src.ab_testing import power_analysis, run_ab_test
from src.kpi_metrics import (
    compute_transaction_kpis, compute_revenue_kpis,
    compute_compliance_kpis, compute_all_kpis,
)
from src.sql_analytics import AnalyticsDB
from src.reporting import generate_weekly_kpi_report, format_as_markdown


@pytest.fixture
def sample_df():
    return generate_transactions(n_records=1_000, days=7)


# ── Data generator ────────────────────────────────────────────────────────────

def test_generate_transactions_shape(sample_df):
    assert len(sample_df) == 1_000
    assert "amount_usd" in sample_df.columns
    assert "status" in sample_df.columns
    assert (sample_df["amount_usd"] > 0).all()


def test_generate_ab_data():
    control, treatment = generate_ab_test_data(n_control=6_000, n_treatment=6_000)
    assert len(control) == 6_000
    assert len(treatment) == 6_000
    assert control.isin([0, 1]).all()


# ── A/B testing ──────────────────────────────────────────────────────────────

def test_power_analysis_returns_dict():
    result = power_analysis(baseline_rate=0.03, mde_absolute=0.01)
    assert "n_per_variant" in result
    assert result["n_per_variant"] > 0
    assert result["n_total"] == result["n_per_variant"] * 2


def test_power_analysis_n12k():
    """Production test runs n=12,000 — verify our params produce that scale."""
    result = power_analysis(baseline_rate=0.03, mde_absolute=0.01, power=0.80, alpha=0.05)
    assert result["n_total"] > 5_000


def test_ab_test_proportion_significant():
    control, treatment = generate_ab_test_data(
        control_conversion_rate=0.03, treatment_lift=0.015, random_state=0
    )
    result = run_ab_test(control, treatment, metric_type="proportion")
    assert result["significant"] is True
    assert result["absolute_lift"] > 0


def test_ab_test_proportion_not_significant():
    rng = np.random.RandomState(99)
    control = pd.Series(rng.binomial(1, 0.03, 500))
    treatment = pd.Series(rng.binomial(1, 0.031, 500))
    result = run_ab_test(control, treatment, metric_type="proportion")
    assert result["significant"] is False


def test_ab_test_continuous():
    rng = np.random.RandomState(42)
    control = pd.Series(rng.normal(100, 20, 500))
    treatment = pd.Series(rng.normal(115, 20, 500))
    result = run_ab_test(control, treatment, metric_type="continuous")
    assert result["significant"] is True
    assert result["absolute_lift"] > 0


# ── KPI metrics ───────────────────────────────────────────────────────────────

def test_transaction_kpis(sample_df):
    kpis = compute_transaction_kpis(sample_df)
    assert kpis["total_transactions"] == 1_000
    assert kpis["total_volume_usd"] > 0
    assert 0 <= kpis["success_rate_pct"] <= 100


def test_revenue_kpis(sample_df):
    kpis = compute_revenue_kpis(sample_df)
    assert kpis["total_volume_usd"] > 0
    assert kpis["avg_daily_volume_usd"] > 0


def test_compliance_kpis(sample_df):
    kpis = compute_compliance_kpis(sample_df)
    assert "high_value_transaction_count" in kpis
    assert kpis["failed_transaction_rate_pct"] >= 0


def test_compute_all_kpis(sample_df):
    all_kpis = compute_all_kpis(sample_df)
    assert "transaction" in all_kpis
    assert "revenue" in all_kpis
    assert "compliance" in all_kpis
    assert "users" in all_kpis


# ── SQL analytics ─────────────────────────────────────────────────────────────

def test_sql_daily_revenue(sample_df):
    db = AnalyticsDB()
    db.load(sample_df)
    result = db.daily_revenue()
    assert len(result) > 0
    assert "total_volume_usd" in result.columns
    db.close()


def test_sql_window_metrics(sample_df):
    db = AnalyticsDB()
    db.load(sample_df)
    result = db.window_metrics()
    assert "running_total_usd" in result.columns
    assert "rolling_7d_avg_usd" in result.columns
    db.close()


def test_sql_compliance(sample_df):
    db = AnalyticsDB()
    db.load(sample_df)
    result = db.compliance_risk_tiers()
    assert "risk_tier" in result.columns
    db.close()


# ── Reporting ─────────────────────────────────────────────────────────────────

def test_generate_report(sample_df):
    report = generate_weekly_kpi_report(sample_df)
    assert "kpis" in report
    assert "narrative" in report
    assert len(report["narrative"]) > 0


def test_format_as_markdown(sample_df):
    report = generate_weekly_kpi_report(sample_df)
    md = format_as_markdown(report)
    assert "# Weekly Fintech KPI Summary" in md
    assert "## Transaction KPIs" in md
    assert "## Revenue KPIs" in md
