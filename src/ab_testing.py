"""
Statistical A/B testing framework — mirrors the structured experiments
(n=12,000, 80% power, α=0.05) run in production at Rockwallet and Erasmus.AI.
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json

import numpy as np
import pandas as pd
from scipy import stats


def power_analysis(
    baseline_rate: float,
    mde_absolute: float,
    power: float = 0.80,
    alpha: float = 0.05,
    two_tailed: bool = True,
) -> Dict[str, Any]:
    """
    Compute required sample size per variant.
    Returns the full power analysis report used to justify experiment scope to stakeholders.
    """
    z_alpha = stats.norm.ppf(1 - alpha / (2 if two_tailed else 1))
    z_beta = stats.norm.ppf(power)

    p1 = baseline_rate
    p2 = baseline_rate + mde_absolute
    p_avg = (p1 + p2) / 2

    numerator = (z_alpha * np.sqrt(2 * p_avg * (1 - p_avg)) + z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    n = int(np.ceil(numerator / (mde_absolute ** 2)))

    return {
        "n_per_variant": n,
        "n_total": n * 2,
        "baseline_rate": baseline_rate,
        "mde_absolute": mde_absolute,
        "expected_treatment_rate": round(p2, 6),
        "power": power,
        "alpha": alpha,
        "two_tailed": two_tailed,
    }


def run_ab_test(
    control: pd.Series,
    treatment: pd.Series,
    metric_type: str = "proportion",
    alpha: float = 0.05,
    experiment_name: str = "ab_test",
) -> Dict[str, Any]:
    """
    Run a complete A/B test.
    metric_type: 'proportion' (binary outcomes) or 'continuous' (revenue, latency).
    Returns a report suitable for executive presentation.
    """
    if metric_type == "proportion":
        return _proportion_test(control, treatment, alpha, experiment_name)
    return _continuous_test(control, treatment, alpha, experiment_name)


def _proportion_test(
    control: pd.Series,
    treatment: pd.Series,
    alpha: float,
    experiment_name: str,
) -> Dict[str, Any]:
    n_c, n_t = len(control), len(treatment)
    conv_c = int(control.sum())
    conv_t = int(treatment.sum())
    p_c = conv_c / n_c
    p_t = conv_t / n_t

    p_pooled = (conv_c + conv_t) / (n_c + n_t)
    se = np.sqrt(p_pooled * (1 - p_pooled) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se if se > 0 else 0.0
    p_value = float(2 * (1 - stats.norm.cdf(abs(z))))

    delta = p_t - p_c
    ci_margin = 1.96 * np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)

    return _build_report(
        experiment_name=experiment_name,
        metric_type="proportion",
        control_stat=round(p_c, 5),
        treatment_stat=round(p_t, 5),
        delta=round(delta, 5),
        relative_lift_pct=round(100 * delta / p_c, 2) if p_c > 0 else 0,
        z_or_t=round(z, 4),
        p_value=round(p_value, 6),
        ci=(round(delta - ci_margin, 5), round(delta + ci_margin, 5)),
        n_control=n_c,
        n_treatment=n_t,
        alpha=alpha,
    )


def _continuous_test(
    control: pd.Series,
    treatment: pd.Series,
    alpha: float,
    experiment_name: str,
) -> Dict[str, Any]:
    t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
    delta = float(treatment.mean() - control.mean())
    n_c, n_t = len(control), len(treatment)
    se = np.sqrt(treatment.var() / n_t + control.var() / n_c)
    ci_margin = stats.t.ppf(0.975, df=n_c + n_t - 2) * se

    return _build_report(
        experiment_name=experiment_name,
        metric_type="continuous",
        control_stat=round(float(control.mean()), 4),
        treatment_stat=round(float(treatment.mean()), 4),
        delta=round(delta, 4),
        relative_lift_pct=round(100 * delta / control.mean(), 2) if control.mean() != 0 else 0,
        z_or_t=round(float(t_stat), 4),
        p_value=round(float(p_value), 6),
        ci=(round(delta - ci_margin, 4), round(delta + ci_margin, 4)),
        n_control=n_c,
        n_treatment=n_t,
        alpha=alpha,
    )


def _build_report(
    experiment_name, metric_type, control_stat, treatment_stat,
    delta, relative_lift_pct, z_or_t, p_value, ci, n_control, n_treatment, alpha,
) -> Dict[str, Any]:
    significant = p_value < alpha
    report = {
        "experiment": experiment_name,
        "timestamp": datetime.utcnow().isoformat(),
        "metric_type": metric_type,
        "n_control": n_control,
        "n_treatment": n_treatment,
        "control_metric": control_stat,
        "treatment_metric": treatment_stat,
        "absolute_lift": delta,
        "relative_lift_pct": relative_lift_pct,
        "statistic": z_or_t,
        "p_value": p_value,
        "alpha": alpha,
        "significant": significant,
        "confidence_interval_95": ci,
        "recommendation": (
            "DEPLOY treatment variant" if (significant and delta > 0)
            else "HOLD — no statistically significant improvement" if not significant
            else "REJECT — treatment is significantly worse"
        ),
    }
    print(json.dumps(report, indent=2))
    return report


def sequential_test(
    observations: List[Tuple[int, int, int, int]],
    alpha: float = 0.05,
    power: float = 0.80,
) -> List[Dict[str, Any]]:
    """
    Sequential A/B test — allows peeking at intermediate results without inflating α.
    Each observation: (control_conversions, control_n, treatment_conversions, treatment_n).
    """
    results = []
    for i, (cc, cn, tc, tn) in enumerate(observations):
        control = pd.Series([1] * cc + [0] * (cn - cc))
        treatment = pd.Series([1] * tc + [0] * (tn - tc))
        result = run_ab_test(control, treatment, metric_type="proportion", alpha=alpha / len(observations))
        result["observation"] = i + 1
        result["alpha_corrected"] = round(alpha / len(observations), 6)
        results.append(result)
    return results
