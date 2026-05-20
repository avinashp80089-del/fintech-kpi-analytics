"""
KPI computation for fintech analytics.
Tracks transaction trends, revenue, billing accuracy, and compliance metrics
across 10M daily blockchain transactions.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def compute_transaction_kpis(
    df: pd.DataFrame,
    amount_col: str = "amount_usd",
    timestamp_col: str = "timestamp",
    status_col: str = "status",
) -> Dict[str, Any]:
    """Compute core transaction volume and value KPIs."""
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    confirmed = df[df[status_col] == "confirmed"] if status_col in df.columns else df

    return {
        "total_transactions": len(df),
        "confirmed_transactions": len(confirmed),
        "success_rate_pct": round(100 * len(confirmed) / max(len(df), 1), 2),
        "total_volume_usd": round(confirmed[amount_col].sum(), 2),
        "avg_transaction_usd": round(confirmed[amount_col].mean(), 2),
        "median_transaction_usd": round(confirmed[amount_col].median(), 2),
        "p95_transaction_usd": round(confirmed[amount_col].quantile(0.95), 2),
        "p99_transaction_usd": round(confirmed[amount_col].quantile(0.99), 2),
        "computed_at": datetime.utcnow().isoformat(),
    }


def compute_revenue_kpis(
    df: pd.DataFrame,
    fee_col: str = "gas_fee_usd",
    amount_col: str = "amount_usd",
    timestamp_col: str = "timestamp",
) -> Dict[str, Any]:
    """Revenue and fee analytics — presented directly to CFO in weekly summaries."""
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    total_fees = df[fee_col].sum() if fee_col in df.columns else 0
    total_volume = df[amount_col].sum()
    fee_ratio = total_fees / max(total_volume, 1)

    daily = df.set_index(timestamp_col).resample("D")[amount_col].sum()
    wow_growth = (daily.iloc[-1] / daily.iloc[-8] - 1) * 100 if len(daily) >= 8 else None

    return {
        "total_fee_revenue_usd": round(total_fees, 2),
        "total_volume_usd": round(total_volume, 2),
        "fee_revenue_pct": round(fee_ratio * 100, 4),
        "avg_daily_volume_usd": round(daily.mean(), 2),
        "peak_daily_volume_usd": round(daily.max(), 2),
        "wow_volume_growth_pct": round(wow_growth, 2) if wow_growth is not None else None,
        "days_analyzed": len(daily),
    }


def compute_compliance_kpis(
    df: pd.DataFrame,
    amount_col: str = "amount_usd",
    status_col: str = "status",
    high_value_threshold: float = 10_000.0,
) -> Dict[str, Any]:
    """
    Compliance monitoring KPIs — flagging patterns for risk team.
    Drove the $500K compliance tooling investment at Rockwallet.
    """
    high_value = df[df[amount_col] >= high_value_threshold]
    failed = df[df[status_col] == "failed"] if status_col in df.columns else pd.DataFrame()

    return {
        "high_value_transaction_count": len(high_value),
        "high_value_volume_usd": round(high_value[amount_col].sum(), 2),
        "high_value_pct_of_total": round(100 * len(high_value) / max(len(df), 1), 3),
        "failed_transaction_count": len(failed),
        "failed_transaction_rate_pct": round(100 * len(failed) / max(len(df), 1), 3),
        "flagged_for_review": len(high_value[high_value[amount_col] >= high_value_threshold * 5]),
    }


def compute_user_kpis(
    df: pd.DataFrame,
    user_col: str = "from_address",
    amount_col: str = "amount_usd",
    timestamp_col: str = "timestamp",
) -> Dict[str, Any]:
    """User-level activity KPIs for product and growth analytics."""
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    user_stats = df.groupby(user_col).agg(
        txn_count=(amount_col, "count"),
        total_volume=(amount_col, "sum"),
        first_seen=(timestamp_col, "min"),
        last_seen=(timestamp_col, "max"),
    ).reset_index()

    dau = df.groupby(df[timestamp_col].dt.date)[user_col].nunique()

    return {
        "total_unique_users": len(user_stats),
        "avg_txn_per_user": round(user_stats["txn_count"].mean(), 2),
        "median_txn_per_user": round(user_stats["txn_count"].median(), 2),
        "avg_volume_per_user_usd": round(user_stats["total_volume"].mean(), 2),
        "avg_dau": round(dau.mean(), 0),
        "peak_dau": int(dau.max()),
        "power_users_top_10pct_volume_pct": round(
            100 * user_stats.nlargest(int(len(user_stats) * 0.1), "total_volume")["total_volume"].sum()
            / max(user_stats["total_volume"].sum(), 1), 2
        ),
    }


def compute_all_kpis(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Master KPI report — all sections combined for executive dashboard."""
    return {
        "transaction": compute_transaction_kpis(df),
        "revenue": compute_revenue_kpis(df),
        "compliance": compute_compliance_kpis(df),
        "users": compute_user_kpis(df),
        "report_generated_at": datetime.utcnow().isoformat(),
    }


def compute_period_over_period(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
    amount_col: str = "amount_usd",
) -> Dict[str, Any]:
    """Week-over-week and month-over-month KPI deltas for executive summaries."""
    cur = compute_transaction_kpis(current_df, amount_col)
    pri = compute_transaction_kpis(prior_df, amount_col)

    def pct_change(a, b):
        return round(100 * (a - b) / max(abs(b), 1), 2)

    return {
        "volume_delta_usd": round(cur["total_volume_usd"] - pri["total_volume_usd"], 2),
        "volume_growth_pct": pct_change(cur["total_volume_usd"], pri["total_volume_usd"]),
        "transaction_count_delta": cur["total_transactions"] - pri["total_transactions"],
        "transaction_count_growth_pct": pct_change(cur["total_transactions"], pri["total_transactions"]),
        "success_rate_delta_pp": round(cur["success_rate_pct"] - pri["success_rate_pct"], 2),
        "current_period": cur,
        "prior_period": pri,
    }
