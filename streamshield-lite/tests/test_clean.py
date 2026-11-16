import numpy as np
import pandas as pd
import pytest

from src.clean import clean, extract_domain, normalize_url
from src.analyze import offender_table


@pytest.mark.parametrize("raw, expected", [
    ("https://WWW.Example.COM/Live/Match1/", "example.com/live/match1"),
    ("http://example.com/live?utm_source=tg&id=5", "example.com/live?id=5"),
    ("example.com/watch", "example.com/watch"),
    ("https://example.com/a?fbclid=123", "example.com/a"),
    ("https://example.com:8080/x", "example.com:8080/x"),
])
def test_normalize_valid(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "not a url", "http://", "ftp://files.example.com", "htp:/broken", "www", None, np.nan])
def test_normalize_invalid(raw):
    assert normalize_url(raw) is None


def test_extract_domain_handles_multipart_tld():
    assert extract_domain("live.stream.example.co.in/x") == "example.co.in"
    assert extract_domain("cdn.example.com/x") == "example.com"


def _raw(**over):
    base = dict(case_id="C1", match_id="M1", match_name="A vs B", platform="Mobile App",
                url="https://site.com/live/1", detected_at="2026-01-01 10:00:00",
                reported_at="2026-01-01 11:00:00", status="Taken Down", takedown_at="2026-01-01 13:00:00")
    base.update(over)
    return base


def test_clean_dedupes_and_validates():
    raw = pd.DataFrame([
        _raw(case_id="C1"),
        _raw(case_id="C2", url="HTTPS://WWW.SITE.COM/live/1/?utm_source=x", detected_at="2026-01-01 10:30:00"),  # dup
        _raw(case_id="C3", url="not a url"),                                                                      # invalid
        _raw(case_id="C4", detected_at="N/A"),                                                                    # bad ts
        _raw(case_id="C5", match_id="M2"),                                                                        # same URL, other match -> kept
    ])
    df, report = clean(raw)
    assert len(df) == 2
    assert set(df["match_id"]) == {"M1", "M2"}
    assert report["duplicates_removed"] == 1
    assert report["invalid_urls_dropped"] == 1
    assert report["bad_timestamp_dropped"] == 1
    assert df["status"].eq("taken_down").all()
    assert df["time_to_takedown_hrs"].iloc[0] == pytest.approx(2.0)


def test_clean_fixes_status_without_takedown_time():
    df, report = clean(pd.DataFrame([_raw(takedown_at=None)]))
    assert df.loc[0, "status"] == "reported"
    assert report["status_fixed_missing_takedown_time"] == 1


def test_risk_score_bounds_and_ordering():
    rows = []
    for i in range(30):   # heavy, recent, never taken down
        rows.append(_raw(case_id=f"A{i}", url=f"https://bad.com/{i}", status="pending", takedown_at=None,
                         detected_at="2026-01-10 10:00:00"))
    rows.append(_raw(case_id="B1", url="https://ok.com/1"))  # single, old, taken down
    df, _ = clean(pd.DataFrame(rows))
    t = offender_table(df)
    assert t["risk_score"].between(0, 100).all()
    assert t.iloc[0]["domain"] == "bad.com"
