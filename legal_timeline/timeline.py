"""
timeline.py — build a branched timeline from categorised date entries.

Why branching?
--------------
A document may contain relative dates like "20 days after the Closing Date"
where "Closing Date" is itself uncertain (or has multiple possible values).
Each possible anchor value produces a different concrete date, creating a
*branch* in the timeline.

Data model
----------
``TimelineNode``
    One node per *concrete resolved date*.  Nodes can have children (branches
    that depend on this node's date).

``BranchTree``
    Holds all root nodes (absolute dates or unresolvable relative dates) plus
    the full node graph.  Call ``render_text()`` for a simple textual view or
    iterate ``all_nodes()`` for programmatic access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime    import date
from typing      import Dict, List, Optional, Tuple

from .models import AbsoluteDate, CategorisedDate, RelativeDate

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass
class TimelineNode:
    """One concrete event on the timeline."""
    category:     str
    date:         date
    label:        str         # human-readable: raw text or "X days after …"
    is_resolved:  bool = True  # False if anchor could not be matched
    children:     List["TimelineNode"] = field(default_factory=list, repr=False)
    parent:       Optional["TimelineNode"] = field(default=None, repr=False)

    def add_child(self, child: "TimelineNode") -> None:
        child.parent = self
        self.children.append(child)

    def depth(self) -> int:
        d = 0
        n = self.parent
        while n:
            d += 1
            n = n.parent
        return d


# ---------------------------------------------------------------------------
# BranchTree
# ---------------------------------------------------------------------------

class BranchTree:
    """
    A possibly branching timeline built from ``CategorisedDate`` entries.

    Construction
    ------------
    Pass a list of ``CategorisedDate`` objects to ``BranchTree.build()``.

    1. All ``AbsoluteDate`` entries become root nodes.
    2. For each ``RelativeDate`` we try to match its ``anchor_label`` to an
       existing node's category (or label) using fuzzy substring matching.
       * If a match is found: a child node is added under *each* matching
         anchor node, creating branches where the anchor itself has multiple
         dates.
       * If no match is found: the entry becomes an *unresolved* root node
         (its date is stored as ``date.min`` and flagged).
    """

    def __init__(self) -> None:
        self.roots: List[TimelineNode] = []
        self._all:  List[TimelineNode] = []

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, entries: List[CategorisedDate]) -> "BranchTree":
        tree = cls()

        # Pass 1 — absolute dates as roots
        for cd in entries:
            if isinstance(cd.date_entry, AbsoluteDate):
                node = TimelineNode(
                    category=cd.category,
                    date=cd.date_entry.date,
                    label=cd.date_entry.raw,
                )
                tree._add_root(node)

        # Pass 2 — relative dates, try to anchor
        for cd in entries:
            if not isinstance(cd.date_entry, RelativeDate):
                continue
            rel     = cd.date_entry
            anchors = tree._find_anchors(rel.anchor_label)

            if anchors:
                for anchor_node in anchors:
                    resolved_dates = rel.resolve(anchor_node.date)
                    for d in resolved_dates:
                        child = TimelineNode(
                            category=cd.category,
                            date=d,
                            label=str(rel),
                            is_resolved=True,
                        )
                        anchor_node.add_child(child)
                        tree._all.append(child)
            else:
                # Unresolved — store as root with sentinel date
                node = TimelineNode(
                    category=cd.category,
                    date=date.min,
                    label=f"[UNRESOLVED] {rel}",
                    is_resolved=False,
                )
                tree._add_root(node)
                log.warning("Could not resolve anchor %r for %r", rel.anchor_label, rel.raw)

        # Sort roots chronologically (unresolved last)
        tree.roots.sort(key=lambda n: (not n.is_resolved, n.date))
        return tree

    def _add_root(self, node: TimelineNode) -> None:
        self.roots.append(node)
        self._all.append(node)

    def _find_anchors(self, anchor_label: str) -> List[TimelineNode]:
        """
        Find all nodes whose category or label contains the anchor phrase.
        Uses case-insensitive substring matching.
        """
        needle = anchor_label.lower().strip()
        matches: List[TimelineNode] = []
        for node in self._all:
            haystack = f"{node.category} {node.label}".lower()
            if needle in haystack or _partial_match(needle, haystack):
                matches.append(node)
        return matches

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def all_nodes(self) -> List[TimelineNode]:
        """Return every node in the tree, breadth-first."""
        result: List[TimelineNode] = []
        queue = list(self.roots)
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(node.children)
        return result

    # ------------------------------------------------------------------
    # Flat view: category → list of (date, label) sorted chronologically
    # ------------------------------------------------------------------

    def flat_view(self) -> Dict[str, List[Tuple[date, str, bool]]]:
        """
        Return a dict mapping category → [(date, label, is_resolved), …],
        sorted chronologically within each category.
        """
        view: Dict[str, List[Tuple[date, str, bool]]] = {}
        for node in self.all_nodes():
            view.setdefault(node.category, []).append(
                (node.date, node.label, node.is_resolved)
            )
        for lst in view.values():
            lst.sort(key=lambda t: (not t[2], t[0]))
        return view

    # ------------------------------------------------------------------
    # Text rendering
    # ------------------------------------------------------------------

    def render_text(self) -> str:
        """Return an ASCII tree representation of the timeline."""
        lines: List[str] = ["BRANCHED TIMELINE", "=" * 60]
        for root in self.roots:
            lines.extend(_render_node(root, prefix=""))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render_text()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _partial_match(needle: str, haystack: str) -> bool:
    """True if the *key words* of needle (≥4 chars) all appear in haystack."""
    words = [w for w in needle.split() if len(w) >= 4]
    return bool(words) and all(w in haystack for w in words)


def _render_node(node: TimelineNode, prefix: str) -> List[str]:
    date_str = node.date.strftime("%d %b %Y") if node.is_resolved else "??"
    resolved = "" if node.is_resolved else " [UNRESOLVED]"
    line = f"{prefix}[{date_str}] {node.category}: {node.label}{resolved}"
    lines = [line]
    for i, child in enumerate(node.children):
        is_last   = i == len(node.children) - 1
        connector = "└─ " if is_last else "├─ "
        child_ext = "   " if is_last else "│  "
        child_lines = _render_node(child, prefix=prefix + child_ext)
        # Replace leading prefix on first child line with the connector
        first = child_lines[0]
        child_lines[0] = prefix + connector + first[len(prefix + child_ext):]
        lines.extend(child_lines)
    return lines
