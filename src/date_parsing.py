"""
date_parsing.py — pluggable date-string → datetime.date converter.

Priority
--------
1. ``dateparser`` (pip install dateparser) — handles virtually any locale,
   ordinal words ("thirty-first"), fuzzy natural language, etc.
2. ``dateutil.parser`` — solid fallback for standard formats when dateparser
   is not installed.

Both are tried automatically; callers just use ``parse_date_string()``.
"""

from __future__ import annotations
from datetime import date, datetime
from typing   import Optional
import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import the best available backend
# ---------------------------------------------------------------------------

try:
    import dateparser as _dateparser  # type: ignore
    _HAS_DATEPARSER = True
    log.debug("date_parsing: using dateparser backend")
except ImportError:
    _HAS_DATEPARSER = False
    log.debug("date_parsing: dateparser not found, falling back to dateutil")

try:
    from dateutil import parser as _dateutil_parser  # type: ignore
    _HAS_DATEUTIL = True
except ImportError:
    _HAS_DATEUTIL = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Settings passed to dateparser.parse() when available.
# PREFER_DAY_OF_MONTH_FIRST keeps EU-style dd/mm/yyyy as the default
# interpretation (change to False for US-style mm/dd/yyyy documents).
DATEPARSER_SETTINGS: dict = {
    "PREFER_DAY_OF_MONTH_FIRST": True,
    "RETURN_AS_TIMEZONE_AWARE":  False,
    "PREFER_LOCALE_DATE_ORDER":  True,
}


def parse_date_string(text: str, dayfirst: bool = True) -> Optional[date]:
    """
    Convert an arbitrary date string to a ``datetime.date``.

    Parameters
    ----------
    text:
        Raw date text, e.g. ``"31 January 2025"``, ``"Jan 31st, 2025"``,
        ``"31/01/2025"``, ``"the thirty-first of January, two-thousand and
        twenty-five"``.
    dayfirst:
        Hint for ambiguous formats like ``01/02/2025``.
        ``True`` → dd/mm/yyyy (European, default).
        ``False`` → mm/dd/yyyy (American).

    Returns
    -------
    ``datetime.date`` on success, ``None`` if the string could not be parsed.
    """
    text = text.strip()
    if not text:
        return None

    # ---- 1. dateparser (preferred) ----------------------------------------
    if _HAS_DATEPARSER:
        settings = {**DATEPARSER_SETTINGS, "PREFER_DAY_OF_MONTH_FIRST": dayfirst}
        try:
            result: Optional[datetime] = _dateparser.parse(text, settings=settings)
            if result is not None:
                return result.date()
        except Exception as exc:  # pragma: no cover
            log.debug("dateparser raised %s for %r", exc, text)

    # ---- 2. dateutil (fallback) --------------------------------------------
    if _HAS_DATEUTIL:
        try:
            return _dateutil_parser.parse(text, dayfirst=dayfirst, fuzzy=True).date()
        except Exception as exc:
            log.debug("dateutil raised %s for %r", exc, text)

    return None


def backend_name() -> str:
    """Return the name of the active date-parsing backend."""
    if _HAS_DATEPARSER:
        return "dateparser"
    if _HAS_DATEUTIL:
        return "dateutil"
    return "none"
