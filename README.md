# legal-timeline

A Python library that extracts, categorises, and visualises key dates from legal Word documents (contracts, shareholder agreements, NDAs, etc.).

## Features

- **Date extraction** — finds absolute dates in virtually any format and relative dates ("within 20 days of the Closing Date")
- **Date categorisation** — maps each date to a legal category (Completion, Warranty, Payment, Longstop, etc.)
- **Branched timeline** — relative dates whose anchor has multiple resolutions produce branches, modelling the true uncertainty in the document
- **Word document report** — generates a clean `.docx` with a two-column table (Category | Dates) plus an optional branch-tree appendix

## Installation

```bash
pip install legal-timeline
```

`dateparser` is the recommended date-parsing backend and is installed automatically. It handles ordinal words ("thirty-first of January"), multiple locales, and highly varied formats found in international contracts. `python-dateutil` is kept as an automatic fallback.

## Quick start

```python
from legal_timeline import DocumentAnalyser

analyser = DocumentAnalyser()
result   = analyser.analyse("shareholders_agreement.docx")

# Print the ASCII branch tree
print(result.branch_tree())

# Print a flat summary grouped by category
print(result.flat_summary())

# Export a formatted Word report
result.export_docx("timeline_report.docx")
```

## Date parsing

The library uses a **pluggable backend** (in `date_parsing.py`):

| Priority | Backend | Handles |
|----------|---------|---------|
| 1 | `dateparser` | Ordinals, locales, fuzzy natural language, 200+ formats |
| 2 | `dateutil` | Standard numeric & written formats |

You can check which backend is active:

```python
from legal_timeline.date_parsing import backend_name
print(backend_name())  # "dateparser" or "dateutil"
```

For ambiguous numeric dates like `01/02/2025`, pass `dayfirst=False` for American style:

```python
analyser = DocumentAnalyser(dayfirst=False)
```

## Supported date formats (examples)

| Format | Example |
|--------|---------|
| ISO | `2025-01-31` |
| European numeric | `31/01/2025`, `31.01.2025` |
| Written month | `31 January 2025`, `January 31st, 2025` |
| Short month | `31 Jan 2025`, `Jan 31, 2025` |
| Ordinal (dateparser) | `the thirty-first of January 2025` |
| Relative | `within 20 days of the Completion Date` |
| Relative (before) | `no later than 5 days before the Longstop Date` |
| Relative (months) | `18 months after the Closing Date` |

## Built-in categories

| Category | Triggered by |
|----------|-------------|
| Execution / Signing Date | signed, executed, effective date |
| Completion / Closing Date | closing date, completion date, settlement |
| Longstop / Drop-Dead Date | longstop, drop-dead, outsider date |
| Condition Precedent Deadline | condition precedent, CP deadline |
| Regulatory / Approval Date | regulatory, approval, clearance, antitrust |
| Notice / Notification Deadline | notice, notification |
| Payment / Consideration Date | payment, purchase price, instalment |
| Warranty / Representation Expiry | warranty, representation |
| Termination / Expiry Date | terminate, expiry, lapse |
| Renewal / Extension Date | renewal, extension, auto-renew |
| Submission / Filing Date | submit, file, deliver, due date |
| Escrow / Holdback Date | escrow, holdback, retention |
| Employment / HR Date | employment, start date, severance |
| General Date | catch-all fallback |

## Extending with custom categories

```python
from legal_timeline import DocumentAnalyser
from legal_timeline.categoriser import CategoryRule

my_rules = [
    CategoryRule(
        category="Option Exercise Window",
        patterns=[r'\boption\s+exercise\b', r'\bcall\s+option\b'],
        priority=15,
    )
]

analyser = DocumentAnalyser(extra_rules=my_rules)
result   = analyser.analyse("options_agreement.docx")
```

## Branch tree

Relative dates create branches off their anchor node. For example:

```
[30 Apr 2025] Completion / Closing Date: 30 April 2025
├─ [20 May 2025] Condition Precedent Deadline: 20 days after [the Completion Date]
└─ [22 Oct 2026] Warranty / Representation Expiry: 540 days after [the Completion Date]
[30 Jun 2025] Longstop / Drop-Dead Date: 30 June 2025
[??] Notice / Notification Deadline: [UNRESOLVED] 5 days before [the relevant deadline]
```

Dates marked `[UNRESOLVED]` could not be matched to a known anchor — they are surfaced for manual review.

## API reference

### `DocumentAnalyser`

```python
DocumentAnalyser(
    dayfirst=True,         # True=dd/mm (EU), False=mm/dd (US)
    extra_rules=None,      # prepend rules to the default set
    custom_rules=None,     # replace the default set entirely
)
```

### `AnalysisResult`

| Method / attribute | Description |
|--------------------|-------------|
| `.raw_entries` | `List[DateEntry]` — all extracted date objects |
| `.categorised` | `List[CategorisedDate]` — after classification |
| `.tree` | `BranchTree` — the resolved timeline |
| `.branch_tree()` | ASCII string of the tree |
| `.flat_summary()` | Grouped text summary |
| `.export_docx(path, title, show_branch_tree)` | Write Word report |

## Running tests

```bash
pip install pytest
pytest tests/ -v
```
