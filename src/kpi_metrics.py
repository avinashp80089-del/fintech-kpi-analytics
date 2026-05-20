from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


def compute_transaction_kpis(
    df: pd.DataFrame,
    amount_col: str = "amount_usd",
    timestamp_col: str = "timestamp",
    status_col: str = "status",
) -> Dict[str, Any]:
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
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    total_fees = df[fee_col].sum() if fee_col in df.columns else 0
    total_vol = df[amount_col].sum()

    daily = df.set_index(timestamp_col).resample("D")[amount_col].sum()
    wow = (daily.iloc[-1] / daily.iloc[-8] - 1) * 100 if len(daily) >= 8 else None

    return {
        "total_fee_revenue_usd": round(total_fees, 2),
        "total_volume_usd": round(total_vol, 2),
        "fee_revenue_pct": round(total_fees / max(total_vol, 1) * 100, 4),
        "avg_daily_volume_usd": round(daily.mean(), 2),
        "peak_daily_volume_usd": round(daily.max(), 2),
        "wow_volume_growth_pct": round(wow, 2) if wow is not None else None,
        "days_analyzed": len(daily),
    }


def compute_compliance_kpis(
    df: pd.DataFrame,
    amount_col: str = "amount_usd",
    status_col: str = "status",
    high_value_threshold: float = 10_000.0,
) -> Dict[str, Any]:
    hv = df[df[amount_col] >= high_value_threshold]
    failed = df[df[status_col] == "failed"] if status_col in df.columns else pd.DataFrame()

    return {
        "high_value_transaction_count": len(hv),
        "high_value_volume_usd": round(hv[amount_col].sum(), 2),
        "high_value_pct_of_total": round(100 * len(hv) / max(len(df), 1), 3),
        "failed_transaction_count": len(failed),
        "failed_transaction_rate_pct": round(100 * len(failed) / max(len(df), 1), 3),
        "flagged_for_review": len(hv[hv[amount_col] >= high_value_threshold * 5]),
    }


def compute_user_kpis(
    df: pd.DataFrame,
    user_col: str = "from_address",
    amount_col: str = "amount_usd",
    timestamp_col: str = "timestamp",
) -> Dict[str, Any]:
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    stats = df.groupby(user_col).agg(
        txn_count=(amount_col, "count"),
        total_volume=(amount_col, "sum"),
    ).reset_index()

    dau = df.groupby(df[timestamp_col].dt.date)[user_col].nunique()
    top10_vol = stats.nlargest(int(len(stats) * 0.1) or 1, "total_volume")["total_volume"].sum()

    return {
        "total_unique_users": len(stats),
        "avg_txn_per_user": round(stats["txn_count"].mean(), 2),
        "median_txn_per_user": round(stats["txn_count"].median(), 2),
        "avg_volume_per_user_usd": round(stats["total_volume"].mean(), 2),
        "avg_dau": round(dau.mean(), 0),
        "peak_dau": int(dau.max()),
        "power_users_top_10pct_volume_pct": round(100 * top10_vol / max(stats["total_volume"].sum(), 1), 2),
    }


def compute_all_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "transaction": compute_transaction_kpis(df),
        "revenue": compute_revenue_kpis(df),
        "compliance": compute_compliance_kpis(df),
        "users": compute_user_kpis(df),
        "report_generated_at": datetime.utcnow().isoformat(),
    }


def compute_period_over_period(current_df: pd.DataFrame, prior_df: pd.DataFrame, amount_col: str = "amount_usd") -> Dict[str, Any]:
    cur = compute_transaction_kpis(current_df, amount_col)
    pri = compute_transaction_kpis(prior_df, amount_col)

    def pct(a, b):
        return round(100 * (a - b) / max(abs(b), 1), 2)

    return {
        "volume_delta_usd": round(cur["total_volume_usd"] - pri["total_volume_usd"], 2),
        "volume_growth_pct": pct(cur["total_volume_usd"], pri["total_volume_usd"]),
        "transaction_count_delta": cur["total_transactions"] - pri["total_transactions"],
        "transaction_count_growth_pct": pct(cur["total_transactions"], pri["total_transactions"]),
        "success_rate_delta_pp": round(cur["success_rate_pct"] - pri["success_rate_pct"], 2),
        "current_period": cur,
        "prior_period": pri,
    }
