"""
utils/dates.py
==============
Canonical date and time utilities for the news-article scraper toolkit.

Consolidates all date-related helpers that were duplicated or re-implemented
across the original per-site scraper notebooks.

Public API
----------
    utc_now_iso()                        – current UTC timestamp as ISO-8601 string
    parse_iso_date(value)                – parse ISO-8601 / sitemap lastmod → datetime
    to_date_string(value)                – extract YYYY-MM-DD from any ISO string
    parse_human_date(text, formats)      – strptime loop over a list of format strings
    parse_us_datetime(text)              – parse US news timestamps with timezone abbr
    is_after_cutoff(date_str, cutoff)    – date-range guard used by crawlers
"""

import re
from datetime import date, datetime, timezone
from typing import Optional

import pytz

# ---------------------------------------------------------------------------
# Internal timezone map
# ---------------------------------------------------------------------------

_US_TIMEZONES: dict[str, str] = {
    "EST": "US/Eastern",
    "EDT": "US/Eastern",
    "CST": "US/Central",
    "CDT": "US/Central",
    "MST": "US/Mountain",
    "MDT": "US/Mountain",
    "PST": "US/Pacific",
    "PDT": "US/Pacific",
    "ET":  "US/Eastern",   # Daily Caller uses bare "ET"
    "CT":  "US/Central",
    "MT":  "US/Mountain",
    "PT":  "US/Pacific",
}

# Format strings tried by parse_us_datetime, in priority order.
# Covers every real format observed across the scraper notebooks:
#
#   Daily Beast  – "Feb. 9 2026 4:34PM EST"  / "Feb. 9 20265:37PM EST"
#   Daily Caller – "January 14, 2026 4:47 PM ET"
#   Fox News     – "March 28, 2026 6:49pm EDT"   (produced raw; not parsed here)
#
_US_DATETIME_FORMATS: list[str] = [
    # Daily Caller: full month name, 12-h with space before AM/PM
    "%B %d, %Y %I:%M %p",       # "January 14, 2026 4:47 PM"
    "%B %d, %Y %I:%M:%S %p",    # "January 14, 2026 4:47:00 PM"
    # Daily Beast: abbreviated month with period, no space before AM/PM
    "%b. %d %Y %I:%M%p",        # "Feb. 9 2026 4:34PM"
    "%b. %d %Y %I:%M:%S%p",     # "Feb. 9 2026 4:34:00PM"
    # Daily Beast edge case: year runs into time (no space after year)
    "%b. %d %Y%I:%M%p",         # "Feb. 9 20264:34PM"
    "%b. %d %Y%I:%M:%S%p",      # "Feb. 9 20264:34:00PM"
    # American Conservative byline: full month, date-only
    "%B %d, %Y",                 # "February 3, 2026"
    "%b %d, %Y",                 # "Feb 3, 2026"
    "%m/%d/%Y",                  # "02/03/2026"
    "%Y-%m-%d",                  # "2026-02-03"
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """
    Return the current UTC time as an ISO-8601 string with second precision
    and a trailing 'Z' suffix.

    Example: "2026-04-10T14:23:05Z"

    Sources: CounterPunch, Mother Jones, Salon, American Spectator
    (all had identical one-liner implementations).
    """
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_iso_date(value: str) -> datetime:
    """
    Parse an ISO-8601 datetime string — including the 'Z' suffix used by
    XML sitemaps — into an aware datetime object (UTC).

    Returns ``datetime.min`` (naive) on failure so callers can safely use
    it as a sort key without branching.

    Example inputs:
        "2026-04-10T14:23:05Z"           → datetime(2026, 4, 10, 14, 23, 5, tzinfo=UTC)
        "2026-04-10T14:23:05+00:00"      → same
        "2026-04-10"                     → datetime(2026, 4, 10, 0, 0, tzinfo=UTC)

    Sources: Daily Beast (parse_lastmod), Daily Caller (parse_lastmod) —
    byte-identical implementations in both scrapers.
    """
    if not value:
        return datetime.min

    try:
        normalized = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return datetime.min


def to_date_string(value: str) -> Optional[str]:
    """
    Extract a ``YYYY-MM-DD`` date string from any ISO-8601 value.

    Handles:
        "2026-04-10T14:23:05+00:00"  → "2026-04-10"
        "2026-04-10"                 → "2026-04-10"
        "2026-04-10Z"                → "2026-04-10"

    Returns None if the string is empty or cannot be interpreted.

    Sources: American Conservative (content.split("T")[0] / content[:10]),
             Free Beacon (parsed_meta.date().isoformat()).
    """
    if not value:
        return None

    stripped = value.strip()

    # Full ISO datetime — take the date part
    if "T" in stripped:
        return stripped.split("T")[0]

    # Plain date or date with Z
    candidate = stripped[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return candidate

    return None


def parse_human_date(
    text: str,
    formats: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Try to parse a human-readable date string into ``YYYY-MM-DD`` using a
    list of ``strptime`` format strings.

    Falls back to the built-in ``_US_DATETIME_FORMATS`` list if no formats
    are supplied.  Returns ``None`` if no format matches.

    Example:
        parse_human_date("February 3, 2026")   → "2026-02-03"
        parse_human_date("Feb 3, 2026")         → "2026-02-03"
        parse_human_date("02/03/2026")          → "2026-02-03"

    Parameters
    ----------
    text : str
        Raw date string from a page.
    formats : list[str], optional
        strptime format strings to try in order.  If omitted the default
        US news format list is used.

    Sources: American Conservative (extract_publication_date date_formats loop),
             Free Beacon (datetime.strptime(raw_date, "%B %d, %Y")).
    """
    if not text:
        return None

    fmt_list = formats if formats is not None else _US_DATETIME_FORMATS

    cleaned = text.strip()

    for fmt in fmt_list:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue

    return None


def parse_us_datetime(text: str) -> Optional[str]:
    """
    Parse a US news publication timestamp that includes a timezone
    abbreviation, and return an ISO-8601 UTC string.

    Handles the two distinct formats found in the scraper notebooks:

        Daily Beast  – "Feb. 9 2026 4:34PM EST"
        Daily Caller – "January 14, 2026 4:47 PM ET"

    Timezone abbreviations supported: EST/EDT, CST/CDT, MST/MDT, PST/PDT,
    and the bare forms ET/CT/MT/PT.  Defaults to US/Eastern when no
    timezone abbreviation is found (matching original Daily Beast behaviour).

    Returns None on any parse failure so callers can store None rather than
    crash.

    Sources: Daily Beast (normalize_published), Daily Caller (normalize_published)
    — near-identical functions, merged here with the Daily Caller format added.
    """
    if not text:
        return None

    try:
        cleaned = text.strip()

        # Extract trailing timezone abbreviation
        tz_match = re.search(
            r"\s+(" + "|".join(_US_TIMEZONES) + r")\s*$",
            cleaned,
            re.IGNORECASE,
        )
        tz_abbr = tz_match.group(1).upper() if tz_match else None

        # Remove the timezone suffix before parsing
        if tz_abbr:
            cleaned = cleaned[: tz_match.start()].strip()

        dt: Optional[datetime] = None
        for fmt in _US_DATETIME_FORMATS:
            try:
                dt = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue

        if dt is None:
            return None

        # Localise and convert to UTC
        tz_name = _US_TIMEZONES.get(tz_abbr, "US/Eastern") if tz_abbr else "US/Eastern"
        local_tz = pytz.timezone(tz_name)
        dt_aware = local_tz.localize(dt)
        return dt_aware.astimezone(pytz.UTC).isoformat()

    except Exception:
        return None


def is_after_cutoff(date_str: str, cutoff: date) -> bool:
    """
    Return True if ``date_str`` represents a date on or after ``cutoff``.

    ``date_str`` must be in ``YYYY-MM-DD`` format (or a longer ISO string
    from which the date portion can be extracted via ``to_date_string``).
    Returns False for empty or unparseable strings — callers use this as a
    skip signal.

    Example:
        is_after_cutoff("2026-02-03", date(2025, 1, 20))  → True
        is_after_cutoff("2024-12-31", date(2025, 1, 20))  → False
        is_after_cutoff("",           date(2025, 1, 20))  → False

    Source: American Conservative (is_recent_enough).
    """
    if not date_str:
        return False

    candidate = to_date_string(date_str) or date_str[:10]

    try:
        pub_date = datetime.strptime(candidate, "%Y-%m-%d").date()
        return pub_date >= cutoff
    except Exception:
        return False