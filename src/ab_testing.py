import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

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
    z_alpha = stats.norm.ppf(1 - alpha / (2 if two_tailed else 1))
    z_beta = stats.norm.ppf(power)

    p1 = baseline_rate
    p2 = baseline_rate + mde_absolute
    p_avg = (p1 + p2) / 2

    numer = (z_alpha * np.sqrt(2 * p_avg * (1 - p_avg)) + z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    n = int(np.ceil(numer / mde_absolute ** 2))

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
    if metric_type == "proportion":
        return _proportion_test(control, treatment, alpha, experiment_name)
    return _continuous_test(control, treatment, alpha, experiment_name)


def _proportion_test(control, treatment, alpha, experiment_name):
    n_c, n_t = len(control), len(treatment)
    conv_c, conv_t = int(control.sum()), int(treatment.sum())
    p_c, p_t = conv_c / n_c, conv_t / n_t

    p_pooled = (conv_c + conv_t) / (n_c + n_t)
    se = np.sqrt(p_pooled * (1 - p_pooled) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se if se > 0 else 0.0
    p_value = float(2 * (1 - stats.norm.cdf(abs(z))))

    delta = p_t - p_c
    ci = 1.96 * np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)

    return _build_report(
        experiment_name, "proportion",
        round(p_c, 5), round(p_t, 5), round(delta, 5),
        round(100 * delta / p_c, 2) if p_c > 0 else 0,
        round(z, 4), round(p_value, 6),
        (round(delta - ci, 5), round(delta + ci, 5)),
        n_c, n_t, alpha,
    )


def _continuous_test(control, treatment, alpha, experiment_name):
    t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
    delta = float(treatment.mean() - control.mean())
    n_c, n_t = len(control), len(treatment)
    se = np.sqrt(treatment.var() / n_t + control.var() / n_c)
    ci = stats.t.ppf(0.975, df=n_c + n_t - 2) * se

    return _build_report(
        experiment_name, "continuous",
        round(float(control.mean()), 4), round(float(treatment.mean()), 4),
        round(delta, 4),
        round(100 * delta / control.mean(), 2) if control.mean() != 0 else 0,
        round(float(t_stat), 4), round(float(p_value), 6),
        (round(delta - ci, 4), round(delta + ci, 4)),
        n_c, n_t, alpha,
    )


def _build_report(
    name, metric_type, ctrl, trt, delta, lift_pct,
    stat, p_value, ci, n_c, n_t, alpha
) -> Dict[str, Any]:
    sig = p_value < alpha
    report = {
        "experiment": name,
        "timestamp": datetime.utcnow().isoformat(),
        "metric_type": metric_type,
        "n_control": n_c,
        "n_treatment": n_t,
        "control_metric": ctrl,
        "treatment_metric": trt,
        "absolute_lift": delta,
        "relative_lift_pct": lift_pct,
        "statistic": stat,
        "p_value": p_value,
        "alpha": alpha,
        "significant": sig,
        "confidence_interval_95": ci,
        "recommendation": (
            "DEPLOY treatment variant"  if (sig and delta > 0) else
            "REJECT — treatment is worse" if (sig and delta <= 0) else
            "HOLD — not significant"
        ),
    }
    print(json.dumps(report, indent=2))
    return report


def sequential_test(
    observations: List[Tuple[int, int, int, int]],
    alpha: float = 0.05,
) -> List[Dict[str, Any]]:
    """Bonferroni-corrected sequential peek — doesn't inflate alpha."""
    results = []
    adj_alpha = alpha / len(observations)
    for i, (cc, cn, tc, tn) in enumerate(observations):
        ctrl = pd.Series([1] * cc + [0] * (cn - cc))
        trt  = pd.Series([1] * tc + [0] * (tn - tc))
        r = run_ab_test(ctrl, trt, metric_type="proportion", alpha=adj_alpha)
        r["observation"] = i + 1
        r["alpha_corrected"] = round(adj_alpha, 6)
        results.append(r)
    return results
