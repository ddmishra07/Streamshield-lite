"""KPIs, platform summaries and repeat-offender risk scoring."""
from __future__ import annotations

import numpy as np
import pandas as pd

# Risk score weights (sum to 1). Tune these to change what "high risk" means.
W_FREQUENCY, W_RECENCY, W_FAILURE = 0.40, 0.30, 0.30
RECENCY_HALF_LIFE_DAYS = 14


def kpis(df: pd.DataFrame) -> dict:
    total = len(df)
    taken = int((df["status"] == "taken_down").sum())
    ttt = df["time_to_takedown_hrs"].dropna()
    return {
        "total_cases": int(total),
        "unique_domains": int(df["domain"].nunique()),
        "matches_monitored": int(df["match_id"].nunique()),
        "taken_down": taken,
        "reported": int((df["status"] == "reported").sum()),
        "pending": int((df["status"] == "pending").sum()),
        "takedown_rate_pct": round(100 * taken / total, 1) if total else 0.0,
        "avg_hours_to_takedown": round(float(ttt.mean()), 1) if len(ttt) else None,
        "median_hours_to_takedown": round(float(ttt.median()), 1) if len(ttt) else None,
    }


def platform_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("platform")
    out = pd.DataFrame({
        "cases": g.size(),
        "taken_down": g["status"].apply(lambda s: (s == "taken_down").sum()),
        "avg_hours_to_takedown": g["time_to_takedown_hrs"].mean().round(1),
    })
    out["takedown_rate_pct"] = (100 * out["taken_down"] / out["cases"]).round(1)
    return out.sort_values("cases", ascending=False).reset_index()


def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby(["detected_date", "platform"]).size()
              .rename("cases").reset_index())


def offender_table(df: pd.DataFrame, ref_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Domain-level repeat-offender table with a 0-100 risk score.

    risk = 100 * (0.40 * frequency + 0.30 * recency + 0.30 * failure_rate)
      frequency    : appearances on a log scale, scaled 0-1 (so one giant domain doesn't flatten the rest)
      recency      : exponential decay since last detection (half-life 14 days)
      failure_rate : share of the domain's cases that were NOT taken down
    """
    ref_date = ref_date or df["detected_at"].max()
    g = df.groupby("domain")
    t = pd.DataFrame({
        "appearances": g.size(),
        "matches_hit": g["match_id"].nunique(),
        "platforms": g["platform"].nunique(),
        "first_seen": g["detected_at"].min(),
        "last_seen": g["detected_at"].max(),
        "taken_down": g["status"].apply(lambda s: (s == "taken_down").sum()),
    })
    t["failure_rate"] = 1 - t["taken_down"] / t["appearances"]
    days_since = (ref_date - t["last_seen"]).dt.total_seconds() / 86400
    t["recency"] = np.power(0.5, days_since / RECENCY_HALF_LIFE_DAYS)
    freq = np.log1p(t["appearances"])
    t["frequency"] = freq / freq.max()

    t["risk_score"] = (100 * (W_FREQUENCY * t["frequency"] + W_RECENCY * t["recency"]
                              + W_FAILURE * t["failure_rate"])).round(1)
    t["risk_band"] = pd.cut(t["risk_score"], [-1, 45, 65, 101], labels=["Low", "Medium", "High"])
    t["failure_rate"] = t["failure_rate"].round(3)
    cols = ["appearances", "matches_hit", "platforms", "taken_down", "failure_rate",
            "first_seen", "last_seen", "risk_score", "risk_band"]
    return t[cols].sort_values("risk_score", ascending=False).reset_index()
