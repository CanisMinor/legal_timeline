"""
models.py — shared dataclasses for legal_timeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime    import date, timedelta
from typing      import List, Optional


# ---------------------------------------------------------------------------
# Date representations
# ---------------------------------------------------------------------------

@dataclass
class AbsoluteDate:
    """A concrete calendar date parsed from the document."""
    date:    date
    raw:     str        # verbatim matched text
    context: str = ""   # surrounding sentence

    def __str__(self) -> str:
        return self.date.strftime("%d %B %Y")

    def resolve(self, anchor: Optional[date] = None) -> List[date]:
        return [self.date]


@dataclass
class RelativeDate:
    """
    A date expressed relative to a named anchor.

    Example: "within 20 days of the Closing Date"
      → delta_days=20, anchor_label="Closing Date"

    Resolving requires knowing the anchor's actual date(s), which may
    themselves be relative — hence the branch-tree.
    """
    delta_days:   int    # positive = after anchor, negative = before
    anchor_label: str    # human-readable name of the anchor event
    raw:          str    # verbatim matched text
    context:      str = ""

    def resolve(self, anchor: date) -> List[date]:
        return [anchor + timedelta(days=self.delta_days)]

    def __str__(self) -> str:
        sign = "after" if self.delta_days >= 0 else "before"
        return f"{abs(self.delta_days)} days {sign} [{self.anchor_label}]"


# Union type used throughout
DateEntry = AbsoluteDate | RelativeDate


# ---------------------------------------------------------------------------
# Categorised entry
# ---------------------------------------------------------------------------

@dataclass
class CategorisedDate:
    """A date entry paired with its legal category."""
    category:   str
    date_entry: DateEntry
    confidence: float = 1.0   # 0–1

    def display_label(self) -> str:
        return str(self.date_entry)
