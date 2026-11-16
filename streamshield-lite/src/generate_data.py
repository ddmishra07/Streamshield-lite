"""Generate a SYNTHETIC OTT piracy-monitoring dataset.

Everything here is fake: teams, matches, domains and URLs are randomly
generated. The data is deliberately messy (duplicates, tracking params,
bad URLs, inconsistent status labels) so the cleaning step has real work to do.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PLATFORMS = {
    # name: (share of cases, takedown success probability, median hours to takedown)
    "Streaming Website": (0.40, 0.55, 18),
    "Social Video Platform": (0.20, 0.88, 3),
    "Messaging Channel": (0.20, 0.65, 8),
    "Mobile App": (0.10, 0.45, 36),
    "File Hosting": (0.10, 0.75, 12),
}
TEAMS = ["Falcons", "Titans", "Strikers", "Royals", "Panthers", "Warriors",
         "Knights", "Rangers", "Comets", "Vikings", "Sharks", "Dragons"]
PREFIXES = ["live", "hd", "free", "stream", "watch", "match", "sport", "play",
            "goal", "cast", "tv", "net", "zone", "max", "pro"]
SUFFIXES = ["hub", "online", "zone", "world", "box", "plus", "now", "arena",
            "central", "direct", "go", "flix", "go24", "fan"]
TLDS = [".xyz", ".live", ".to", ".cc", ".site", ".online", ".top", ".club", ".co.in", ".net"]
TRACKING = ["utm_source=tg", "utm_campaign=live", "fbclid=abc123", "ref=home", "gclid=xyz789"]
BAD_URLS = ["not a url", "http://", "ftp://files.example", "htp:/broken-link", "", "www", "http://.com"]


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def build_domain_pool(rng: np.random.Generator, n_domains: int = 400):
    domains = set()
    while len(domains) < n_domains:
        domains.add(str(rng.choice(PREFIXES)) + str(rng.choice(SUFFIXES))
                    + str(rng.integers(1, 99)) + str(rng.choice(TLDS)))
    domains = sorted(domains)
    # Zipf-like weights -> a few domains are heavy repeat offenders
    weights = 1 / np.arange(1, len(domains) + 1) ** 0.9
    return domains, weights / weights.sum()


def generate(n_rows: int = 12_000, seed: int = 42, end_date: datetime | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end_date = end_date or datetime(2026, 4, 30)
    start_date = end_date - timedelta(days=90)

    # --- matches -----------------------------------------------------------
    n_matches = 45
    match_days = sorted(start_date + timedelta(days=int(d)) for d in rng.integers(0, 90, n_matches))
    matches = []
    for i, day in enumerate(match_days, start=1):
        a, b = rng.choice(TEAMS, 2, replace=False)
        kickoff = day.replace(hour=int(rng.choice([14, 16, 19, 20])), minute=0, second=0)
        matches.append((f"M{i:03d}", f"{a} vs {b}", kickoff))
    match_weights = rng.dirichlet(np.ones(n_matches) * 2)

    # --- base rows ---------------------------------------------------------
    domains, d_weights = build_domain_pool(rng)
    plat_names = list(PLATFORMS)
    plat_probs = [PLATFORMS[p][0] for p in plat_names]

    rows = []
    for case_no in range(1, n_rows + 1):
        m_id, m_name, kickoff = matches[rng.choice(n_matches, p=match_weights)]
        platform = str(rng.choice(plat_names, p=plat_probs))
        _, p_success, median_hrs = PLATFORMS[platform]
        domain = str(rng.choice(domains, p=d_weights))
        sub = str(rng.choice(["", "www.", "live.", "s2.", "cdn."], p=[0.4, 0.3, 0.15, 0.1, 0.05]))
        path = f"/live/{_slug(m_name)}/{rng.integers(1, 2500)}"
        url = f"https://{sub}{domain}{path}"

        detected = kickoff + timedelta(minutes=int(rng.integers(-30, 180)))
        reported = detected + timedelta(minutes=int(rng.integers(5, 180)))

        roll = rng.random()
        if roll < p_success:
            status = "taken_down"
            hrs = float(rng.lognormal(mean=np.log(median_hrs), sigma=0.6))
            takedown = reported + timedelta(hours=hrs)
        elif roll < p_success + (1 - p_success) * 0.6:
            status, takedown = "reported", pd.NaT
        else:
            status, takedown, reported = "pending", pd.NaT, pd.NaT

        rows.append([f"C{case_no:06d}", m_id, m_name, platform, url, detected, reported, status, takedown])

    df = pd.DataFrame(rows, columns=["case_id", "match_id", "match_name", "platform", "url",
                                     "detected_at", "reported_at", "status", "takedown_at"])

    # --- inject realistic mess ---------------------------------------------
    next_id = n_rows + 1

    # 1) duplicates: same URL written differently
    dups = df.sample(frac=0.10, random_state=seed).copy()

    def mutate(u: str) -> str:
        style = int(rng.integers(0, 4))
        if style == 0:
            return u.upper().replace("HTTPS://", "https://")
        if style == 1:
            return u + "?" + str(rng.choice(TRACKING))
        if style == 2:
            return u + "/"
        return u.replace("https://", "http://www.", 1)

    dups["url"] = dups["url"].map(mutate)
    dups["detected_at"] = dups["detected_at"] + pd.to_timedelta(rng.integers(1, 90, len(dups)), unit="m")
    dups["case_id"] = [f"C{next_id + i:06d}" for i in range(len(dups))]
    df = pd.concat([df, dups], ignore_index=True)

    # 2) invalid URLs
    bad_idx = df.sample(frac=0.02, random_state=seed + 1).index
    df.loc[bad_idx, "url"] = rng.choice(BAD_URLS, len(bad_idx))

    # 3) missing platforms
    df.loc[df.sample(frac=0.01, random_state=seed + 2).index, "platform"] = np.nan

    # 4) inconsistent status labels
    variants = {"taken_down": ["Taken Down", "TAKEN_DOWN", "taken down", "taken_down"],
                "reported": ["Reported", "REPORTED", "reported"],
                "pending": ["Pending", "PENDING ", "pending"]}
    df["status"] = df["status"].map(lambda s: str(rng.choice(variants[s])))

    # 5) timestamps as strings (+ a few unparsable ones)
    for col in ["detected_at", "reported_at", "takedown_at"]:
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df.loc[df.sample(frac=0.005, random_state=seed + 3).index, "detected_at"] = "N/A"

    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic piracy-monitoring data")
    p.add_argument("--rows", type=int, default=12_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/raw/cases_raw.csv")
    args = p.parse_args()
    df = generate(args.rows, args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} raw rows -> {args.out}")


if __name__ == "__main__":
    main()
