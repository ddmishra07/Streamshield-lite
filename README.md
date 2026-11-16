# 🛡️ StreamShield-Lite

An end-to-end **OTT piracy monitoring pipeline + dashboard**: automated data ingestion, URL cleaning and validation, KPI reporting, repeat-offender risk scoring, and an interactive Streamlit dashboard (with a Power BI build guide).

> **Note:** This is a portfolio project inspired by real-world piracy-investigation workflows. It runs entirely on **synthetic data** (fake teams, matches, domains and URLs). No real or confidential data is used.



## The problem
During live sports matches, investigation teams must track thousands of pirate streaming URLs. Raw URL lists are messy (duplicates, tracking parameters, malformed links), so analysts waste time on bad data and lack visibility into takedown progress and repeat offenders.

## What this project does
| Stage | What happens | Code |
|---|---|---|
| **Ingest** | Generates ~13k messy raw records across 45 matches and 5 platforms | `src/generate_data.py` |
| **Clean & validate** | Normalizes URLs, strips tracking params, validates hosts, fixes statuses/timestamps, de-duplicates, logs every drop | `src/clean.py` |
| **Analyze** | KPIs, platform takedown rates, time-to-takedown, repeat-offender risk score | `src/analyze.py` |
| **Store** | CSV + SQLite + JSON; optional S3 upload | `src/pipeline.py`, `src/upload_s3.py` |
| **Visualize** | Streamlit dashboard + Matplotlib EDA charts + Power BI guide | `dashboard/`, `src/eda.py`, `powerbi/` |
| **Automate** | GitHub Actions: tests + daily pipeline run | `.github/workflows/pipeline.yml` |

## Architecture
```
Synthetic source → generate_data.py → clean.py → analyze.py → CSV / SQLite / JSON ──┬→ Streamlit dashboard
 (messy raw CSV)    (ingestion)      (Pandas)    (KPIs + risk)   (data/processed)    ├→ Power BI (DAX)
                                                                                      └→ S3 (optional, boto3)
                                   GitHub Actions: pytest + scheduled daily run
```

## Quick start
```bash
git clone https://github.com/<your-username>/streamshield-lite.git
cd streamshield-lite
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.pipeline            # generate → clean → analyze → save
python -m src.eda                 # (optional) regenerate charts in docs/images
streamlit run dashboard/app.py    # open the dashboard
pytest -q                         # run the tests
```

## Data cleaning results (seed 42)
From 13,200 raw rows → **11,807 clean rows** (10.5% removed):
- 264 invalid or malformed URLs dropped
- 65 rows dropped for unparsable timestamps
- 1,064 duplicates removed (same match + same normalized URL, e.g. `HTTPS://WWW.SITE.COM/x/?utm_source=tg` and `site.com/x`)
- 127 missing platforms labelled `Unknown`; status labels standardized (`Taken Down`, `TAKEN_DOWN` → `taken_down`)

## Key findings (synthetic data)
- **64.4%** of cases were taken down, with a **median of 10 hours** from report to takedown.
- **Social video platforms** have the best takedown performance (89% taken down, ~3.7 hrs on average). **Mobile apps** are the weakest (43% taken down, ~43 hrs on average).
- Piracy is highly concentrated: the top offender domain alone accounts for **1,360 cases** (about 11.5% of all cases) and appeared in every monitored match.
- 22 domains fall in the **High** risk band, and they should get investigator attention first.



## Risk score
```
risk = 100 × (0.40 × frequency + 0.30 × recency + 0.30 × failure_rate)
```
- **frequency**: appearances (log-scaled, 0-1)
- **recency**: exponential decay since last detection (14-day half-life)
- **failure_rate**: share of the domain's cases not taken down

Bands: Low ≤ 45 < Medium ≤ 65 < High. Weights live at the top of `src/analyze.py`.

## Project structure
```
streamshield-lite/
├── src/                 generate_data.py · clean.py · analyze.py · pipeline.py · upload_s3.py · eda.py
├── dashboard/app.py     Streamlit app
├── powerbi/README.md    Power BI model, DAX measures and page layout
├── tests/               pytest unit tests for cleaning and risk scoring
├── data/                raw/ and processed/ (generated, git-ignored)
├── docs/images/         EDA charts used in this README
└── .github/workflows/   CI + scheduled run
```

## Optional: AWS S3
```bash
export S3_BUCKET=my-bucket   # plus AWS credentials
python -m src.pipeline --upload
```

## Deploy the dashboard (free)
Push to GitHub → [share.streamlit.io](https://share.streamlit.io) → select `dashboard/app.py`. On first launch the app builds its own synthetic dataset, so no data files are needed.

## Tech stack
Python · Pandas · NumPy · Matplotlib · Streamlit · SQLite · Power BI/DAX · pytest · GitHub Actions · AWS S3 (boto3)

## Ideas for next steps
- Add an ML model (scikit-learn) to predict high-risk domains from domain features
- Add domain-age/WHOIS enrichment
- Replace SQLite with PostgreSQL and schedule with Airflow
