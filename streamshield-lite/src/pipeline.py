"""One-command pipeline: generate -> clean -> analyze -> save (CSV + SQLite + JSON).

    python -m src.pipeline                  # full run with fresh synthetic data
    python -m src.pipeline --skip-generate  # reuse existing data/raw/cases_raw.csv
    python -m src.pipeline --upload         # also push outputs to S3
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src import analyze, clean, generate_data

RAW = Path("data/raw/cases_raw.csv")
OUT = Path("data/processed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("streamshield")


def run(rows: int = 12_000, seed: int = 42, skip_generate: bool = False, upload: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)

    if skip_generate and RAW.exists():
        log.info("Using existing raw data: %s", RAW)
        raw = pd.read_csv(RAW)
    else:
        log.info("Generating %s synthetic rows (seed=%s)", f"{rows:,}", seed)
        raw = generate_data.generate(rows, seed)
        RAW.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(RAW, index=False)

    log.info("Cleaning %s raw rows", f"{len(raw):,}")
    df, report = clean.clean(raw)
    for k, v in report.items():
        log.info("  cleaning | %-36s %s", k, v)

    log.info("Analyzing")
    kpi = analyze.kpis(df)
    platforms = analyze.platform_summary(df)
    offenders = analyze.offender_table(df)

    df.to_csv(OUT / "cases_clean.csv", index=False)
    platforms.to_csv(OUT / "platform_summary.csv", index=False)
    offenders.to_csv(OUT / "offenders.csv", index=False)
    (OUT / "kpis.json").write_text(json.dumps(kpi, indent=2))
    (OUT / "cleaning_report.json").write_text(json.dumps(report, indent=2))

    with sqlite3.connect(OUT / "streamshield.db") as con:
        df.drop(columns=["detected_date"]).astype({"detected_at": str, "reported_at": str, "takedown_at": str}) \
          .to_sql("cases", con, if_exists="replace", index=False)
        offenders.astype({"first_seen": str, "last_seen": str, "risk_band": str}) \
                 .to_sql("offenders", con, if_exists="replace", index=False)
        platforms.to_sql("platform_summary", con, if_exists="replace", index=False)

    log.info("KPIs: %s", kpi)
    if upload:
        from src.upload_s3 import upload_processed
        for path in upload_processed(str(OUT)):
            log.info("Uploaded %s", path)
    log.info("Done. Outputs in %s/", OUT)
    return {"kpis": kpi, "cleaning": report}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=12_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-generate", action="store_true")
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    run(a.rows, a.seed, a.skip_generate, a.upload)
