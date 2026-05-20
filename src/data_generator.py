from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate_transactions(n_records: int = 50_000, days: int = 30, random_state: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(random_state)
    end = datetime.utcnow()
    timestamps = pd.date_range(end - timedelta(days=days), end, periods=n_records)

    df = pd.DataFrame({
        "transaction_hash": [f"0x{''.join(rng.choice(list('abcdef0123456789'), 8))}" for _ in range(n_records)],
        "from_address": [f"0x{rng.randint(1000, 9999):04d}{rng.randint(1000, 9999):04d}" for _ in range(n_records)],
        "to_address":   [f"0x{rng.randint(1000, 9999):04d}{rng.randint(1000, 9999):04d}" for _ in range(n_records)],
        "timestamp":    timestamps,
        "chain":        rng.choice(["ethereum", "bitcoin", "polygon", "solana"], n_records, p=[0.35, 0.25, 0.25, 0.15]),
        "token_symbol": rng.choice(["ETH", "BTC", "USDT", "USDC", "MATIC"], n_records, p=[0.3, 0.2, 0.25, 0.15, 0.1]),
        "amount_usd":   np.abs(rng.lognormal(4.5, 2.0, n_records)).clip(1, 500_000),
        "gas_fee_usd":  np.abs(rng.lognormal(1.5, 0.8, n_records)).clip(0.01, 500),
        "tx_type":      rng.choice(["transfer", "swap", "mint", "burn", "stake"], n_records, p=[0.5, 0.25, 0.1, 0.05, 0.1]),
        "status":       rng.choice(["confirmed", "failed", "pending"], n_records, p=[0.93, 0.05, 0.02]),
    })

    df["year"]  = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["day"]   = df["timestamp"].dt.day

    return df.sort_values("timestamp").reset_index(drop=True)


def generate_ab_test_data(
    n_control: int = 6_000,
    n_treatment: int = 6_000,
    control_conversion_rate: float = 0.03,
    treatment_lift: float = 0.01,
    random_state: int = 42,
):
    rng = np.random.RandomState(random_state)
    control   = pd.Series(rng.binomial(1, control_conversion_rate, n_control))
    treatment = pd.Series(rng.binomial(1, control_conversion_rate + treatment_lift, n_treatment))
    return control, treatment
