"""
categoriser.py — map extracted date entries to legal categories.

Each category is defined by a list of keyword/phrase patterns that are matched
against the ``context`` (surrounding sentence) and ``raw`` text of a date
entry.  The first matching category wins; a catch-all "General Date" category
is assigned when nothing matches.

Users can extend or replace the default ruleset by passing a custom
``rules`` list to ``DateCategoriser``.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing      import List, Optional

from .models import CategorisedDate, DateEntry

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------

@dataclass
class CategoryRule:
    """
    A single classification rule.

    Attributes
    ----------
    category:
        Human-readable category label (e.g. ``"Completion / Closing Date"``).
    patterns:
        List of regex patterns (case-insensitive).  A date entry matches this
        rule if *any* pattern matches its context or raw text.
    priority:
        Higher priority rules are tested first.  Default 0.
    """
    category: str
    patterns: List[str]
    priority: int = 0
    _compiled: List[re.Pattern] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> bool:
        return any(p.search(text) for p in self._compiled)


# ---------------------------------------------------------------------------
# Default ruleset  (roughly ordered by specificity / priority)
# ---------------------------------------------------------------------------

DEFAULT_RULES: List[CategoryRule] = [
    CategoryRule(
        category="Execution / Signing Date",
        patterns=[
            r'\bsign(ed|ing|ature)?\b', r'\bexecut(ed|ion|ing)\b',
            r'\bdate\s+of\s+(this\s+)?agreement\b', r'\beffective\s+date\b',
            r'\bcommencement\s+date\b', r'\bdate\s+hereof\b',
        ],
        priority=10,
    ),
    CategoryRule(
        category="Completion / Closing Date",
        patterns=[
            r'\bclosing\s+date\b', r'\bcompletion\s+date\b',
            r'\bclose\s+of\s+(the\s+)?transaction\b',
            r'\bsettlement\s+date\b',
        ],
        priority=10,
    ),
    CategoryRule(
        category="Longstop / Drop-Dead Date",
        patterns=[
            r'\blongstop\b', r'\bdrop.?dead\b', r'\boutsider\s+date\b',
            r'\blong.?stop\s+date\b', r'\btermination\s+deadline\b',
        ],
        priority=10,
    ),
    CategoryRule(
        category="Notice / Notification Deadline",
        patterns=[
            r'\bnotice\b', r'\bnotif(y|ication)\b',
            r'\bgive\s+(written\s+)?notice\b',
            r'\bserve[sd]?\s+notice\b',
        ],
        priority=8,
    ),
    CategoryRule(
        category="Payment / Consideration Date",
        patterns=[
            r'\bpayment\b', r'\bpurchase\s+price\b', r'\bconsideration\b',
            r'\binstalment\b', r'\binstallment\b',
            r'\bdeposit\b', r'\bremittance\b', r'\bfunds?\b.*\btransfer\b',
        ],
        priority=8,
    ),
    CategoryRule(
        category="Warranty / Representation Expiry",
        patterns=[
            r'\bwarrant(y|ies|ed)\b', r'\brepresentation\b',
            r'\bwarranty\s+(period|claim|breach)\b',
            r'\bindemnit(y|ies)\b',
        ],
        priority=8,
    ),
    CategoryRule(
        category="Condition Precedent Deadline",
        patterns=[
            r'\bcondition\s+precedent\b', r'\bCP\s+deadline\b',
            r'\bconditions?\s+to\s+closing\b',
            r'\bsatisf(y|ied|action)\s+of\s+(the\s+)?condition\b',
        ],
        priority=9,
    ),
    CategoryRule(
        category="Regulatory / Approval Date",
        patterns=[
            r'\bregulatory\b', r'\bapproval\b', r'\bauthori[sz]ation\b',
            r'\bclearance\b', r'\bantitrust\b', r'\bcompetition\s+(authority|commission)\b',
            r'\bfiling\s+deadline\b', r'\bgovernment(al)?\s+consent\b',
        ],
        priority=9,
    ),
    CategoryRule(
        category="Termination / Expiry Date",
        patterns=[
            r'\bterminat(e|ion|ed)\b', r'\bexpir(y|ation|e|ed)\b',
            r'\bend\s+(of|date)\b', r'\bterm\s+ends?\b',
            r'\blapse\b',
        ],
        priority=7,
    ),
    CategoryRule(
        category="Renewal / Extension Date",
        patterns=[
            r'\brenew(al|ed|s)?\b', r'\bextension\b', r'\broll.?over\b',
            r'\bauto.?renew\b',
        ],
        priority=7,
    ),
    CategoryRule(
        category="Submission / Filing Date",
        patterns=[
            r'\bsubmit(ted)?\b', r'\bsubmission\b', r'\bfil(e|ing|ed)\b',
            r'\bdeliver(y|ed)?\b.*\b(document|report|notice)\b',
            r'\bdue\s+date\b',
        ],
        priority=6,
    ),
    CategoryRule(
        category="Escrow / Holdback Date",
        patterns=[
            r'\bescrow\b', r'\bholdback\b', r'\bretention\b',
            r'\brelease\s+of\s+escrow\b',
        ],
        priority=8,
    ),
    CategoryRule(
        category="Employment / HR Date",
        patterns=[
            r'\bemployment\b', r'\bcommencement\s+of\s+(service|employment)\b',
            r'\bstart\s+date\b', r'\bnotice\s+period\b.*\bemploy\b',
            r'\bseverance\b', r'\bgardn?er?\s+leave\b',
        ],
        priority=6,
    ),
    CategoryRule(
        category="General Date",
        patterns=[r'.*'],   # catch-all, always matches
        priority=0,
    ),
]


# ---------------------------------------------------------------------------
# Categoriser
# ---------------------------------------------------------------------------

class DateCategoriser:
    """
    Assign a legal category to each ``DateEntry``.

    Parameters
    ----------
    rules:
        Ordered list of ``CategoryRule`` objects.  Defaults to
        ``DEFAULT_RULES``.  Rules are evaluated in *descending priority*
        order; the first match wins.
    """

    def __init__(self, rules: Optional[List[CategoryRule]] = None) -> None:
        self._rules: List[CategoryRule] = sorted(
            rules or DEFAULT_RULES,
            key=lambda r: r.priority,
            reverse=True,
        )

    def categorise(self, entries: List[DateEntry]) -> List[CategorisedDate]:
        """
        Map a list of ``DateEntry`` objects to ``CategorisedDate`` objects.
        """
        results: List[CategorisedDate] = []
        for entry in entries:
            search_text = f"{entry.context} {entry.raw}"
            category    = self._match(search_text)
            results.append(CategorisedDate(category=category, date_entry=entry))
            log.debug("  %r → %s", entry.raw, category)
        return results

    def _match(self, text: str) -> str:
        for rule in self._rules:
            if rule.matches(text):
                return rule.category
        return "General Date"
