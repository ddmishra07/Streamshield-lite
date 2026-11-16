"""Static EDA charts (Matplotlib) -> docs/images/. Run after the pipeline."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import analyze

IMG = Path("docs/images")


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv("data/processed/cases_clean.csv", parse_dates=["detected_at", "reported_at", "takedown_at"])
    df["detected_date"] = df["detected_at"].dt.date
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 120})

    # 1. Detections per day
    daily = df.groupby("detected_date").size()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(pd.to_datetime(daily.index), daily.values, color="#1f77b4")
    ax.set(title="Detections per day (spikes = match days)", ylabel="URLs detected")
    fig.tight_layout(); fig.savefig(IMG / "daily_detections.png"); plt.close(fig)

    # 2. Takedown rate by platform
    ps = analyze.platform_summary(df).sort_values("takedown_rate_pct")
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(ps["platform"], ps["takedown_rate_pct"], color="#2ca02c")
    for y, v in enumerate(ps["takedown_rate_pct"]):
        ax.text(v + 1, y, f"{v}%", va="center")
    ax.set(title="Takedown rate by platform", xlim=(0, 105), xlabel="% of cases taken down")
    fig.tight_layout(); fig.savefig(IMG / "platform_takedown_rate.png"); plt.close(fig)

    # 3. Top 10 repeat offenders
    off = analyze.offender_table(df).head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(off["domain"], off["risk_score"], color="#d62728")
    ax.set(title="Top 10 repeat-offender domains by risk score", xlabel="Risk score (0-100)")
    fig.tight_layout(); fig.savefig(IMG / "top_offenders.png"); plt.close(fig)

    # 4. Time to takedown distribution
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for plat, grp in df.groupby("platform"):
        vals = grp["time_to_takedown_hrs"].dropna()
        if len(vals) > 30:
            ax.hist(vals.clip(upper=100), bins=40, alpha=0.5, label=plat)
    ax.set(title="Hours from report to takedown (clipped at 100h)", xlabel="hours", ylabel="cases")
    ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(IMG / "time_to_takedown.png"); plt.close(fig)
    print(f"Saved 4 charts to {IMG}/")


if __name__ == "__main__":
    main()
