"""
tests/test_pipeline.py — end-to-end tests using a synthetic contract.

Run with:  pytest tests/ -v
"""

import pytest
from datetime import date
from pathlib  import Path
import tempfile

from docx import Document as DocxDocument

from legal_timeline                import DocumentAnalyser
from legal_timeline.extractor      import DateExtractor
from legal_timeline.categoriser    import DateCategoriser
from legal_timeline.timeline       import BranchTree
from legal_timeline.models         import AbsoluteDate, RelativeDate, CategorisedDate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNTHETIC_CONTRACT = """
SHARE PURCHASE AGREEMENT

This Agreement is entered into on 15 March 2025 (the "Signing Date").

1. Completion
   Completion shall take place on 30 April 2025 (the "Completion Date").

2. Conditions Precedent
   The Parties shall use reasonable endeavours to satisfy all conditions
   precedent no later than 20 business days after the Completion Date.

3. Regulatory Approval
   The Buyer shall file for regulatory clearance no later than 31 January 2025.
   Regulatory approval is expected by 28/02/2025.

4. Longstop Date
   If Completion has not occurred by 30 June 2025 (the "Longstop Date"),
   either Party may terminate this Agreement.

5. Warranties
   Warranty claims must be notified within 18 months of the Completion Date.
   The warranty period expires on 30 April 2026.

6. Payment
   The Purchase Price of £10,000,000 shall be paid on the Completion Date.
   A retention of £500,000 shall be released 12 months after Completion.

7. Notice
   Any notice under this Agreement shall be given no later than 5 days before
   the relevant deadline.
"""


def _make_docx(text: str) -> Path:
    """Write *text* into a temporary .docx and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    doc = DocxDocument()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(tmp.name)
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Unit tests — extractor
# ---------------------------------------------------------------------------

class TestDateExtractor:
    def test_absolute_iso(self):
        entries = DateExtractor().extract("Effective date: 2025-03-15.")
        assert any(
            isinstance(e, AbsoluteDate) and e.date == date(2025, 3, 15)
            for e in entries
        )

    def test_absolute_written(self):
        entries = DateExtractor().extract("Signed on 31 January 2025.")
        assert any(
            isinstance(e, AbsoluteDate) and e.date == date(2025, 1, 31)
            for e in entries
        )

    def test_absolute_numeric(self):
        entries = DateExtractor().extract("Payment due 31/01/2025.")
        assert any(isinstance(e, AbsoluteDate) and e.date == date(2025, 1, 31)
                   for e in entries)

    def test_relative_within(self):
        entries = DateExtractor().extract(
            "Notice must be given within 20 days of the Closing Date."
        )
        rel = [e for e in entries if isinstance(e, RelativeDate)]
        assert rel, "Expected at least one RelativeDate"
        assert rel[0].delta_days == 20
        assert "closing date" in rel[0].anchor_label.lower()

    def test_relative_before(self):
        entries = DateExtractor().extract(
            "Filing must be made no later than 5 days before the Longstop Date."
        )
        rel = [e for e in entries if isinstance(e, RelativeDate)]
        assert rel
        assert rel[0].delta_days == -5   # before → negative

    def test_relative_months(self):
        entries = DateExtractor().extract(
            "Warranty claims within 18 months after the Completion Date."
        )
        rel = [e for e in entries if isinstance(e, RelativeDate)]
        assert rel
        assert rel[0].delta_days == 18 * 30


# ---------------------------------------------------------------------------
# Unit tests — categoriser
# ---------------------------------------------------------------------------

class TestCategoriser:
    def _cat(self, context: str, raw: str = "01 Jan 2025") -> str:
        entry = AbsoluteDate(date=date(2025, 1, 1), raw=raw, context=context)
        result = DateCategoriser().categorise([entry])
        return result[0].category

    def test_completion(self):
        assert "Completion" in self._cat("This is the Closing Date of the deal.")

    def test_warranty(self):
        assert "Warranty" in self._cat("Warranty claims must be filed within 18 months.")

    def test_longstop(self):
        assert "Longstop" in self._cat("If not completed by the Longstop Date, terminate.")

    def test_payment(self):
        assert "Payment" in self._cat("The Purchase Price shall be paid on this date.")

    def test_general_fallback(self):
        assert "General" in self._cat("This happened sometime in history.")


# ---------------------------------------------------------------------------
# Integration test — full pipeline
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_analyse_returns_result(self):
        docx_path = _make_docx(SYNTHETIC_CONTRACT)
        result    = DocumentAnalyser().analyse(docx_path)

        assert result.raw_entries,  "Should have extracted raw entries"
        assert result.categorised,  "Should have categorised entries"
        assert result.tree.roots,   "Should have branch-tree roots"

    def test_flat_view_has_expected_categories(self):
        docx_path = _make_docx(SYNTHETIC_CONTRACT)
        result    = DocumentAnalyser().analyse(docx_path)
        flat      = result.tree.flat_view()

        found_cats = set(flat.keys())
        # At least some of these should appear
        expected = {
            "Completion / Closing Date",
            "Longstop / Drop-Dead Date",
            "Warranty / Representation Expiry",
        }
        assert found_cats & expected, (
            f"Expected some of {expected}; got {found_cats}"
        )

    def test_export_docx(self, tmp_path):
        docx_path = _make_docx(SYNTHETIC_CONTRACT)
        result    = DocumentAnalyser().analyse(docx_path)
        out       = tmp_path / "timeline.docx"
        result.export_docx(out)
        assert out.exists() and out.stat().st_size > 0

    def test_branch_tree_text(self):
        docx_path = _make_docx(SYNTHETIC_CONTRACT)
        result    = DocumentAnalyser().analyse(docx_path)
        tree_text = result.branch_tree()
        assert "BRANCHED TIMELINE" in tree_text


# ---------------------------------------------------------------------------
# Smoke test — date_parsing backend
# ---------------------------------------------------------------------------

class TestDateParsing:
    def test_backend_available(self):
        from legal_timeline.date_parsing import backend_name, parse_date_string
        name = backend_name()
        assert name in ("dateparser", "dateutil"), f"Unexpected backend: {name}"

    def test_common_formats(self):
        from legal_timeline.date_parsing import parse_date_string
        cases = [
            ("31 January 2025",   date(2025, 1, 31)),
            ("January 31, 2025",  date(2025, 1, 31)),
            ("31/01/2025",        date(2025, 1, 31)),
            ("2025-01-31",        date(2025, 1, 31)),
            ("31 Jan 2025",       date(2025, 1, 31)),
            ("31.01.2025",        date(2025, 1, 31)),
        ]
        for raw, expected in cases:
            result = parse_date_string(raw)
            assert result == expected, f"Failed for {raw!r}: got {result}"
