import sqlite3
import pandas as pd


TRANSACTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    transaction_hash TEXT PRIMARY KEY,
    from_address     TEXT,
    to_address       TEXT,
    chain            TEXT,
    token_symbol     TEXT,
    amount_usd       REAL,
    gas_fee_usd      REAL,
    tx_type          TEXT,
    status           TEXT,
    timestamp        TEXT,
    year             INTEGER,
    month            INTEGER,
    day              INTEGER
);
"""

# ── CTEs & window function queries ────────────────────────────────────────────

DAILY_REVENUE_CTE = """
WITH daily_volume AS (
    SELECT
        date(timestamp)         AS trade_date,
        chain,
        COUNT(*)                AS txn_count,
        SUM(amount_usd)         AS total_volume_usd,
        SUM(gas_fee_usd)        AS total_fees_usd,
        AVG(amount_usd)         AS avg_txn_usd
    FROM transactions
    WHERE status = 'confirmed'
    GROUP BY date(timestamp), chain
),
rolling_7d AS (
    SELECT
        trade_date,
        chain,
        txn_count,
        total_volume_usd,
        total_fees_usd,
        SUM(total_volume_usd) OVER (
            PARTITION BY chain
            ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_volume_usd,
        AVG(total_volume_usd) OVER (
            PARTITION BY chain
            ORDER BY trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg_daily_usd
    FROM daily_volume
)
SELECT
    trade_date,
    chain,
    txn_count,
    total_volume_usd,
    total_fees_usd,
    rolling_7d_volume_usd,
    rolling_7d_avg_daily_usd,
    ROUND(total_fees_usd / NULLIF(total_volume_usd, 0) * 100, 4) AS fee_rate_pct
FROM rolling_7d
ORDER BY trade_date DESC, total_volume_usd DESC;
"""

USER_COHORT_CTE = """
WITH user_first_txn AS (
    SELECT
        from_address,
        MIN(date(timestamp))    AS cohort_date,
        COUNT(*)                AS total_txns,
        SUM(amount_usd)         AS lifetime_volume_usd
    FROM transactions
    WHERE status = 'confirmed'
    GROUP BY from_address
),
cohort_summary AS (
    SELECT
        cohort_date,
        COUNT(*)                    AS new_users,
        AVG(total_txns)             AS avg_txns_per_user,
        AVG(lifetime_volume_usd)    AS avg_ltv_usd,
        SUM(lifetime_volume_usd)    AS cohort_total_volume_usd
    FROM user_first_txn
    GROUP BY cohort_date
)
SELECT
    cohort_date,
    new_users,
    ROUND(avg_txns_per_user, 2)       AS avg_txns,
    ROUND(avg_ltv_usd, 2)             AS avg_ltv_usd,
    ROUND(cohort_total_volume_usd, 2) AS cohort_volume_usd,
    SUM(new_users) OVER (
        ORDER BY cohort_date
        ROWS UNBOUNDED PRECEDING
    )                                 AS cumulative_users
FROM cohort_summary
ORDER BY cohort_date;
"""

HIGH_VALUE_COMPLIANCE_CTE = """
WITH high_value_txns AS (
    SELECT * FROM transactions
    WHERE amount_usd >= 10000 AND status = 'confirmed'
),
address_risk AS (
    SELECT
        from_address,
        COUNT(*)                AS high_value_count,
        SUM(amount_usd)         AS high_value_volume,
        MAX(amount_usd)         AS max_single_txn,
        COUNT(DISTINCT chain)   AS chains_used,
        RANK() OVER (ORDER BY SUM(amount_usd) DESC) AS volume_rank
    FROM high_value_txns
    GROUP BY from_address
)
SELECT
    from_address,
    high_value_count,
    ROUND(high_value_volume, 2) AS high_value_volume_usd,
    ROUND(max_single_txn, 2)    AS max_single_txn_usd,
    chains_used,
    volume_rank,
    CASE
        WHEN high_value_count > 10 AND chains_used > 2 THEN 'HIGH'
        WHEN high_value_count > 5                      THEN 'MEDIUM'
        ELSE                                                'LOW'
    END AS risk_tier
FROM address_risk
ORDER BY high_value_volume DESC
LIMIT 100;
"""

WINDOW_FUNCTION_METRICS = """
SELECT
    from_address,
    date(timestamp)                                              AS trade_date,
    amount_usd,
    SUM(amount_usd)   OVER (PARTITION BY from_address ORDER BY timestamp ROWS UNBOUNDED PRECEDING) AS running_total_usd,
    AVG(amount_usd)   OVER (PARTITION BY from_address ORDER BY date(timestamp) ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d_avg_usd,
    ROW_NUMBER()      OVER (PARTITION BY from_address ORDER BY amount_usd DESC) AS txn_rank_by_amount,
    LAG(amount_usd,1) OVER (PARTITION BY from_address ORDER BY timestamp)       AS prev_txn_usd,
    amount_usd - LAG(amount_usd,1) OVER (PARTITION BY from_address ORDER BY timestamp) AS amount_delta_usd,
    NTILE(4)          OVER (ORDER BY amount_usd)                                AS amount_quartile
FROM transactions
WHERE status = 'confirmed'
ORDER BY from_address, timestamp;
"""


class AnalyticsDB:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(TRANSACTION_SCHEMA)
        self.conn.commit()

    def load(self, df: pd.DataFrame):
        cols = [c for c in [
            "transaction_hash", "from_address", "to_address", "chain",
            "token_symbol", "amount_usd", "gas_fee_usd", "tx_type",
            "status", "timestamp", "year", "month", "day",
        ] if c in df.columns]
        df[cols].to_sql("transactions", self.conn, if_exists="replace", index=False)

    def query(self, sql: str) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.conn)

    def daily_revenue(self):      return self.query(DAILY_REVENUE_CTE)
    def user_cohorts(self):       return self.query(USER_COHORT_CTE)
    def compliance_risk_tiers(self): return self.query(HIGH_VALUE_COMPLIANCE_CTE)
    def window_metrics(self):     return self.query(WINDOW_FUNCTION_METRICS)

    def close(self):
        self.conn.close()
