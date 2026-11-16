"""Cleaning + validation: URL normalisation, de-duplication, status/timestamp fixes."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit

import numpy as np
import pandas as pd

TRACKING_PREFIXES = ("utm_", "mc_")
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "igshid"}
MULTI_PART_TLDS = {"co.in", "org.in", "co.uk", "org.uk", "com.au", "co.za", "com.br"}
HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
VALID_STATUSES = {"pending", "reported", "taken_down"}


def normalize_url(raw) -> str | None:
    """Return 'host/path?sorted_query' (no scheme, no www, no tracking) or None if invalid."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    url = str(raw).strip()
    if not url or " " in url:
        return None
    if not SCHEME_RE.match(url):
        url = "http://" + url
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not host:
        return None
    host = host.lower().removeprefix("www.")
    if not HOST_RE.match(host):
        return None
    if port and port not in (80, 443):
        host = f"{host}:{port}"

    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_KEYS and not k.lower().startswith(TRACKING_PREFIXES)]
    path = parts.path.lower().rstrip("/")
    out = f"{host}{path}"
    if query:
        out += "?" + urlencode(sorted(query))
    return out


def extract_domain(normalized: str | None) -> str | None:
    """Registrable domain from a normalized URL (handles co.in-style TLDs)."""
    if not normalized:
        return None
    host = normalized.split("/")[0].split("?")[0].split(":")[0]
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_PART_TLDS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean raw case data. Returns (clean_df, report) where report counts every drop/fix."""
    df = raw.copy()
    report = {"input_rows": int(len(df))}

    # 1. URLs: normalise + validate
    df["url_raw"] = df["url"]
    df["url_normalized"] = df["url"].map(normalize_url)
    report["invalid_urls_dropped"] = int(df["url_normalized"].isna().sum())
    df = df.dropna(subset=["url_normalized"]).copy()
    df["domain"] = df["url_normalized"].map(extract_domain)

    # 2. Timestamps
    for col in ["detected_at", "reported_at", "takedown_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    report["bad_timestamp_dropped"] = int(df["detected_at"].isna().sum())
    df = df.dropna(subset=["detected_at"]).copy()

    # 3. Standardise categorical columns
    df["status"] = (df["status"].astype(str).str.strip().str.lower()
                    .str.replace(r"[\s\-]+", "_", regex=True))
    unknown = ~df["status"].isin(VALID_STATUSES)
    report["unknown_status_set_pending"] = int(unknown.sum())
    df.loc[unknown, "status"] = "pending"

    df["platform"] = df["platform"].fillna("Unknown").astype(str).str.strip()
    report["missing_platform_filled"] = int((df["platform"] == "Unknown").sum())

    # 4. Logical consistency: takedown_at only valid for taken_down cases
    inconsistent = (df["status"] == "taken_down") & df["takedown_at"].isna()
    df.loc[inconsistent, "status"] = "reported"
    df.loc[df["status"] != "taken_down", "takedown_at"] = pd.NaT
    report["status_fixed_missing_takedown_time"] = int(inconsistent.sum())

    # 5. De-duplicate: same match + same normalized URL = same case (keep earliest)
    before = len(df)
    df = df.sort_values("detected_at").drop_duplicates(["match_id", "url_normalized"], keep="first")
    report["duplicates_removed"] = int(before - len(df))

    # 6. Derived fields
    df["time_to_takedown_hrs"] = (df["takedown_at"] - df["reported_at"]).dt.total_seconds() / 3600
    df["detected_date"] = df["detected_at"].dt.date

    df = df.reset_index(drop=True)
    report["output_rows"] = int(len(df))
    report["rows_removed_pct"] = round(100 * (1 - len(df) / max(report["input_rows"], 1)), 2)
    return df, report
