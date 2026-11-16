"""StreamShield-Lite dashboard.   Run:  streamlit run dashboard/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import analyze, pipeline  # noqa: E402

DATA = ROOT / "data" / "processed" / "cases_clean.csv"

st.set_page_config(page_title="StreamShield-Lite", page_icon="🛡️", layout="wide")


@st.cache_data(show_spinner="Loading data...")
def load() -> pd.DataFrame:
    if not DATA.exists():  # first run (e.g. on Streamlit Cloud): build the synthetic dataset
        import os
        os.chdir(ROOT)
        pipeline.run()
    return pd.read_csv(DATA, parse_dates=["detected_at", "reported_at", "takedown_at"])


df = load()
df["detected_date"] = df["detected_at"].dt.date

# ---------------- sidebar filters ----------------
st.sidebar.title("🛡️ StreamShield-Lite")
st.sidebar.caption("Synthetic OTT piracy monitoring demo. No real data.")
platforms = st.sidebar.multiselect("Platform", sorted(df["platform"].unique()),
                                   default=sorted(df["platform"].unique()))
matches = st.sidebar.multiselect("Match", sorted(df["match_name"].unique()))
d_min, d_max = df["detected_date"].min(), df["detected_date"].max()
date_range = st.sidebar.date_input("Detection date", (d_min, d_max), min_value=d_min, max_value=d_max)
statuses = st.sidebar.multiselect("Status", ["taken_down", "reported", "pending"],
                                  default=["taken_down", "reported", "pending"])

f = df[df["platform"].isin(platforms) & df["status"].isin(statuses)]
if matches:
    f = f[f["match_name"].isin(matches)]
if isinstance(date_range, tuple) and len(date_range) == 2:
    f = f[(f["detected_date"] >= date_range[0]) & (f["detected_date"] <= date_range[1])]

st.title("OTT Piracy Monitoring Dashboard")
if f.empty:
    st.warning("No cases match the current filters.")
    st.stop()

# ---------------- KPI cards ----------------
k = analyze.kpis(f)
c = st.columns(5)
c[0].metric("Total cases", f"{k['total_cases']:,}")
c[1].metric("Takedown rate", f"{k['takedown_rate_pct']}%")
c[2].metric("Pending", f"{k['pending']:,}")
c[3].metric("Avg hrs to takedown", k["avg_hours_to_takedown"] or "n/a")
c[4].metric("Unique domains", f"{k['unique_domains']:,}")

tab1, tab2, tab3, tab4 = st.tabs(["📈 Trends", "🌐 Platforms", "🚨 Repeat offenders", "🗂️ Data"])

with tab1:
    daily = f.groupby(["detected_date", "platform"]).size().unstack(fill_value=0)
    st.subheader("Detections per day by platform")
    st.line_chart(daily)
    st.subheader("Cases per match")
    st.bar_chart(f.groupby("match_name").size().sort_values(ascending=False).head(15))

with tab2:
    ps = analyze.platform_summary(f)
    a, b = st.columns(2)
    a.subheader("Takedown rate (%)")
    a.bar_chart(ps.set_index("platform")["takedown_rate_pct"])
    b.subheader("Avg hours from report to takedown")
    b.bar_chart(ps.set_index("platform")["avg_hours_to_takedown"])
    st.dataframe(ps, width="stretch", hide_index=True)

with tab3:
    off = analyze.offender_table(f)
    st.caption("Risk score = 40% frequency + 30% recency + 30% takedown failure rate (see src/analyze.py).")
    band = st.multiselect("Risk band", ["High", "Medium", "Low"], default=["High", "Medium"])
    shown = off[off["risk_band"].astype(str).isin(band)]
    st.subheader(f"Top 10 domains by risk score ({len(shown)} in selected bands)")
    st.bar_chart(shown.head(10).set_index("domain")["risk_score"])
    st.dataframe(shown, width="stretch", hide_index=True)

with tab4:
    st.dataframe(f.drop(columns=["detected_date"]).head(1000), width="stretch", hide_index=True)
    st.download_button("⬇️ Download filtered data (CSV)", f.to_csv(index=False).encode(),
                       "streamshield_filtered.csv", "text/csv")
