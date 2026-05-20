import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.kpi_metrics import compute_all_kpis, compute_period_over_period


def generate_weekly_kpi_report(
    current_df: pd.DataFrame,
    prior_df: Optional[pd.DataFrame] = None,
    report_title: str = "Weekly Fintech KPI Summary",
    author: str = "Analytics Team",
) -> Dict[str, Any]:
    kpis = compute_all_kpis(current_df)
    report: Dict[str, Any] = {
        "title": report_title,
        "author": author,
        "generated_at": datetime.utcnow().isoformat(),
        "period": {
            "start": str(pd.to_datetime(current_df["timestamp"]).min().date()),
            "end": str(pd.to_datetime(current_df["timestamp"]).max().date()),
        },
        "kpis": kpis,
    }

    if prior_df is not None:
        report["period_over_period"] = compute_period_over_period(current_df, prior_df)

    report["narrative"] = _build_narrative(kpis, report.get("period_over_period"))
    return report


def _build_narrative(kpis: Dict, pop: Optional[Dict]) -> List[str]:
    txn = kpis.get("transaction", {})
    rev = kpis.get("revenue", {})
    comp = kpis.get("compliance", {})
    bullets = []

    bullets.append(
        f"Total transaction volume reached ${rev.get('total_volume_usd', 0):,.0f} with "
        f"{txn.get('total_transactions', 0):,} transactions "
        f"({txn.get('success_rate_pct', 0):.1f}% success rate)."
    )
    bullets.append(
        f"Fee revenue totaled ${rev.get('total_fee_revenue_usd', 0):,.0f} "
        f"({rev.get('fee_revenue_pct', 0):.3f}% of volume)."
    )

    hv = comp.get("high_value_transaction_count", 0)
    if hv > 0:
        bullets.append(
            f"{hv:,} high-value transactions (≥$10K) totaling "
            f"${comp.get('high_value_volume_usd', 0):,.0f} — "
            f"{comp.get('flagged_for_review', 0)} flagged for compliance review."
        )

    if pop:
        growth = pop.get("volume_growth_pct", 0)
        direction = "up" if growth >= 0 else "down"
        bullets.append(f"WoW volume {direction} {abs(growth):.1f}% (${pop.get('volume_delta_usd', 0):+,.0f}).")

    return bullets


def format_as_markdown(report: Dict[str, Any]) -> str:
    txn = report["kpis"].get("transaction", {})
    rev = report["kpis"].get("revenue", {})
    comp = report["kpis"].get("compliance", {})

    lines = [
        f"# {report['title']}",
        f"**Generated:** {report['generated_at']}  |  **Author:** {report['author']}",
        f"**Period:** {report['period']['start']} → {report['period']['end']}",
        "",
        "## Executive Summary",
        *[f"- {b}" for b in report.get("narrative", [])],
        "",
        "## Transaction KPIs",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Transactions | {txn.get('total_transactions', 0):,} |",
        f"| Success Rate | {txn.get('success_rate_pct', 0):.1f}% |",
        f"| Total Volume (USD) | ${txn.get('total_volume_usd', 0):,.2f} |",
        f"| Avg Transaction (USD) | ${txn.get('avg_transaction_usd', 0):,.2f} |",
        f"| P99 Transaction (USD) | ${txn.get('p99_transaction_usd', 0):,.2f} |",
        "",
        "## Revenue KPIs",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Fee Revenue (USD) | ${rev.get('total_fee_revenue_usd', 0):,.2f} |",
        f"| Fee Rate | {rev.get('fee_revenue_pct', 0):.4f}% |",
        f"| Avg Daily Volume (USD) | ${rev.get('avg_daily_volume_usd', 0):,.2f} |",
        f"| WoW Volume Growth | {rev.get('wow_volume_growth_pct', 'N/A')}% |",
        "",
        "## Compliance KPIs",
        "| Metric | Value |",
        "|--------|-------|",
        f"| High-Value Txns (≥$10K) | {comp.get('high_value_transaction_count', 0):,} |",
        f"| High-Value Volume (USD) | ${comp.get('high_value_volume_usd', 0):,.2f} |",
        f"| Flagged for Review | {comp.get('flagged_for_review', 0):,} |",
        f"| Failed Tx Rate | {comp.get('failed_transaction_rate_pct', 0):.3f}% |",
    ]

    if "period_over_period" in report:
        pop = report["period_over_period"]
        lines += [
            "",
            "## Period-over-Period",
            "| Metric | Delta |",
            "|--------|-------|",
            f"| Volume | ${pop.get('volume_delta_usd', 0):+,.2f} ({pop.get('volume_growth_pct', 0):+.1f}%) |",
            f"| Transaction Count | {pop.get('transaction_count_delta', 0):+,} ({pop.get('transaction_count_growth_pct', 0):+.1f}%) |",
            f"| Success Rate | {pop.get('success_rate_delta_pp', 0):+.2f} pp |",
        ]

    return "\n".join(lines)


def save_report(report: Dict[str, Any], output_path: str):
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"saved → {output_path}")
