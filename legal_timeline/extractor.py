"""
extractor.py — extract AbsoluteDate and RelativeDate entries from plain text.

Strategy
--------
* Split text into sentences.
* For each sentence run two passes:
  1. **Relative-date pass** — look for patterns like "within N days of …",
     "N months after …", "no later than N days from …".  These are captured
     *before* the absolute pass so the trailing anchor phrase is not mistakenly
     parsed as a standalone date.
  2. **Absolute-date pass** — scan for date-like tokens and hand them to the
     date_parsing layer (dateparser → dateutil).

The regex patterns are intentionally broad; false positives are filtered out
by requiring that ``parse_date_string`` actually returns a valid date.
"""

from __future__ import annotations

import re
import logging
from typing import List, Tuple

from .models       import AbsoluteDate, RelativeDate, DateEntry
from .date_parsing import parse_date_string

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentence splitter
# ---------------------------------------------------------------------------

_SENT_END = re.compile(r'(?<=[.;])\s+(?=[A-Z])')

def _sentences(text: str) -> List[str]:
    """Rough sentence splitter that handles abbreviations well enough."""
    # Keep clause boundaries introduced by semicolons too
    parts = _SENT_END.split(text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Relative-date patterns
# ---------------------------------------------------------------------------
# Each pattern must have named groups:
#   quantity  — the number (digits or words)
#   unit      — days / weeks / months / years
#   direction — after / within / from / before / prior / following (optional)
#   anchor    — the rest of the phrase naming the anchor event

_WORD_NUM = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|fifty|sixty|ninety|hundred|\d+)'

_REL_PATTERNS: List[re.Pattern] = [
    # "within 30 days of the Closing Date"
    # "no later than 20 business days after Completion"
    re.compile(
        r'(?:within|no later than|not later than|not more than)\s+'
        r'(?P<quantity>' + _WORD_NUM + r')\s+'
        r'(?:business\s+|calendar\s+|working\s+)?(?P<unit>days?|weeks?|months?|years?)\s+'
        r'(?:of|from|after|following)\s+'
        r'(?P<anchor>[^,;.]{3,80})',
        re.IGNORECASE,
    ),
    # "20 days after the date of signing"
    # "six months following Completion"
    re.compile(
        r'(?P<quantity>' + _WORD_NUM + r')\s+'
        r'(?:business\s+|calendar\s+|working\s+)?(?P<unit>days?|weeks?|months?|years?)\s+'
        r'(?P<direction>after|following|from|prior to|before)\s+'
        r'(?P<anchor>[^,;.]{3,80})',
        re.IGNORECASE,
    ),
    # "not less than 14 days before the Longstop Date"
    re.compile(
        r'(?:not less than|at least|no fewer than)\s+'
        r'(?P<quantity>' + _WORD_NUM + r')\s+'
        r'(?:business\s+|calendar\s+|working\s+)?(?P<unit>days?|weeks?|months?|years?)\s+'
        r'(?P<direction>before|prior to)\s+'
        r'(?P<anchor>[^,;.]{3,80})',
        re.IGNORECASE,
    ),
]


_WORD_TO_INT: dict = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "ninety": 90, "hundred": 100,
}

_UNIT_TO_DAYS: dict = {
    "day": 1, "week": 7, "month": 30, "year": 365,
}


def _word_to_int(s: str) -> int:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return _WORD_TO_INT.get(s, 1)


def _unit_to_days(unit: str) -> int:
    unit = unit.rstrip("s").lower()   # normalise plural
    return _UNIT_TO_DAYS.get(unit, 1)


def _is_before(direction: str) -> bool:
    direction = (direction or "after").lower()
    return any(w in direction for w in ("before", "prior"))


def _extract_relative(sentence: str) -> Tuple[List[RelativeDate], List[Tuple[int, int]]]:
    """Return (relative_dates, list_of_(start, end) spans consumed)."""
    results: List[RelativeDate]          = []
    consumed: List[Tuple[int, int]]      = []

    for pattern in _REL_PATTERNS:
        for m in pattern.finditer(sentence):
            quantity  = _word_to_int(m.group("quantity"))
            unit      = _unit_to_days(m.group("unit"))
            direction = m.groupdict().get("direction", "after") or "after"
            anchor    = m.group("anchor").strip().rstrip(".,;")
            raw       = m.group(0)

            delta = quantity * unit
            if _is_before(direction):
                delta = -delta

            results.append(RelativeDate(
                delta_days=delta,
                anchor_label=anchor,
                raw=raw,
                context=sentence,
            ))
            consumed.append((m.start(), m.end()))

    return results, consumed


# ---------------------------------------------------------------------------
# Absolute-date patterns
# ---------------------------------------------------------------------------
# We cast a wide net and let the date-parsing layer validate.

_DATE_CANDIDATES: List[re.Pattern] = [
    # ISO / numeric:  2025-01-31  |  31/01/2025  |  31.01.2025  |  01-31-2025
    re.compile(
        r'\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b'
    ),
    # Written month (long or short), e.g.:
    #   31 January 2025  |  January 31, 2025  |  31st of January 2025
    #   31 Jan 2025  |  Jan 31st 2025
    re.compile(
        r'\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?)'
        r'(?:January|February|March|April|May|June|July|August|September|'
        r'October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        r'(?:[,\s]+\d{2,4})?\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'\b(?:January|February|March|April|May|June|July|August|September|'
        r'October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        r'\s+\d{1,2}(?:st|nd|rd|th)?(?:[,\s]+\d{2,4})?\b',
        re.IGNORECASE,
    ),
]


def _overlaps(start: int, end: int, consumed: List[Tuple[int, int]]) -> bool:
    return any(s <= start < e or s < end <= e for s, e in consumed)


def _extract_absolute(
    sentence: str,
    consumed: List[Tuple[int, int]],
    dayfirst: bool = True,
) -> List[AbsoluteDate]:
    """Find absolute dates in *sentence*, skipping spans already consumed."""
    seen_dates: set = set()
    results: List[AbsoluteDate] = []

    for pattern in _DATE_CANDIDATES:
        for m in pattern.finditer(sentence):
            if _overlaps(m.start(), m.end(), consumed):
                continue
            raw = m.group(0).strip()
            d   = parse_date_string(raw, dayfirst=dayfirst)
            if d is None:
                continue
            if d in seen_dates:
                continue
            seen_dates.add(d)
            results.append(AbsoluteDate(date=d, raw=raw, context=sentence))

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DateExtractor:
    """
    Extract all date references from a block of text.

    Parameters
    ----------
    dayfirst:
        Passed to the date-parsing layer for ambiguous numeric formats.
        ``True`` (default) → European dd/mm/yyyy.
        ``False`` → American mm/dd/yyyy.
    """

    def __init__(self, dayfirst: bool = True) -> None:
        self.dayfirst = dayfirst

    def extract(self, text: str) -> List[DateEntry]:
        """
        Return every date reference found in *text*, in document order.

        Relative dates are listed before absolute dates within the same
        sentence (they are found first to avoid anchor-phrase bleed-over).
        """
        entries: List[DateEntry] = []

        for sentence in _sentences(text):
            rel_entries, consumed = _extract_relative(sentence)
            abs_entries           = _extract_absolute(sentence, consumed, self.dayfirst)
            entries.extend(rel_entries)
            entries.extend(abs_entries)

        log.debug("Extracted %d date entries", len(entries))
        return entries
