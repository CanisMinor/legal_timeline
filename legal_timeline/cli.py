"""
cli.py — command-line interface for legal timeline analysis.

Usage::

    poetry run legal-timeline contract.docx
    poetry run legal-timeline contract.docx --output timeline.docx
"""

import argparse
import sys
from pathlib import Path

from .analyser import DocumentAnalyser


def main():
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract, categorise, and visualise key dates from legal Word documents."
    )
    parser.add_argument(
        "docx_path",
        help="Path to the Word document to analyse"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output path for the generated timeline (defaults to 'timeline.docx')"
    )
    
    args = parser.parse_args()
    
    try:
        analyser = DocumentAnalyser()
        result = analyser.analyse(args.docx_path)
        
        # Print summary to console
        print(result.flat_summary())
        print("\n" + "=" * 60)
        
        # Export to docx
        output_path = args.output or "timeline.docx"
        result.export_docx(output_path)
        print(f"✓ Timeline exported to: {output_path}")
        
    except FileNotFoundError:
        print(f"Error: File not found: {args.docx_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
