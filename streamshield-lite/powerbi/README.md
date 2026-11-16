# Power BI version (optional)

Build the same dashboard in Power BI Desktop on top of the pipeline outputs.

## 1. Load data
**Get Data → Text/CSV** and load from `data/processed/`:
`cases_clean.csv`, `offenders.csv`, `platform_summary.csv`.
(Or **Get Data → ODBC/SQLite** and connect to `streamshield.db`.)

In **Power Query**: set `detected_at`, `reported_at`, `takedown_at` to *Date/Time*, `risk_score` to *Decimal*.

## 2. Model
- Create a **Date** table: `Date = CALENDAR(MIN(cases_clean[detected_at]), MAX(cases_clean[detected_at]))`
- Relate `Date[Date]` → `cases_clean[detected_date]` (1:many).
- Relate `offenders[domain]` → `cases_clean[domain]` (1:many, single direction).

## 3. DAX measures
```DAX
Total Cases = COUNTROWS(cases_clean)

Taken Down = CALCULATE([Total Cases], cases_clean[status] = "taken_down")

Pending = CALCULATE([Total Cases], cases_clean[status] = "pending")

Takedown Rate % = DIVIDE([Taken Down], [Total Cases], 0)

Avg Hours to Takedown = AVERAGE(cases_clean[time_to_takedown_hrs])

Unique Domains = DISTINCTCOUNT(cases_clean[domain])

Cases Last 7 Days =
CALCULATE([Total Cases], DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -7, DAY))

Cases Prev 7 Days =
CALCULATE([Total Cases], DATESINPERIOD('Date'[Date], MAX('Date'[Date]) - 7, -7, DAY))

WoW Change % = DIVIDE([Cases Last 7 Days] - [Cases Prev 7 Days], [Cases Prev 7 Days])

High Risk Domains = CALCULATE(DISTINCTCOUNT(offenders[domain]), offenders[risk_band] = "High")
```

## 4. Report pages
1. **Overview**: KPI cards (Total Cases, Takedown Rate %, Pending, Avg Hours), line chart of cases by date, slicers for Platform / Match / Date.
2. **Platforms**: bar chart of Takedown Rate % by platform, table of cases + avg hours.
3. **Repeat offenders**: top-10 bar by `risk_score`, table with conditional formatting on `risk_band`.

## 5. Ship it
Save the `.pbix` in this folder and add 2–3 screenshots to `docs/images/` for the README.
