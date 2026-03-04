"""
visualize_cli.py — command-line interface for visualizing timelines as graphs.

Usage::

    poetry run visualise_dates contract.docx
    poetry run visualise_dates contract.docx --output timeline.png
    poetry run visualise_dates contract.docx --show
"""

import argparse
import sys
from pathlib import Path

from .analyser import DocumentAnalyser
from .visualiser import TimelineVisualiser


def main():
    """Entry point for the visualization CLI."""
    parser = argparse.ArgumentParser(
        description="Visualize legal timeline dates as a networkx graph."
    )
    parser.add_argument(
        "docx_path",
        help="Path to the Word document to analyse"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output path for the graph image (e.g., 'timeline.png', 'timeline.pdf')"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the graph in an interactive matplotlib window"
    )
    parser.add_argument(
        "--figsize",
        type=str,
        default="14,10",
        help="Figure size as 'width,height' in inches (default: 14,10)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Resolution in dots per inch (default: 150)"
    )
    
    args = parser.parse_args()
    
    try:
        # Analyze the document
        analyser = DocumentAnalyser()
        result = analyser.analyse(args.docx_path)
        
        # Create visualizer
        visualiser = TimelineVisualiser(result.tree)
        
        # Print graph stats
        stats = visualiser.graph_stats()
        print(f"Graph statistics:")
        print(f"  Nodes: {stats['num_nodes']}")
        print(f"  Edges: {stats['num_edges']}")
        print(f"  Root nodes: {stats['num_roots']}")
        print(f"  Max depth: {stats['max_depth']}")
        print(f"  Is DAG: {stats['is_dag']}")
        print()
        
        # Parse figsize if provided
        try:
            figsize_tuple = tuple(map(float, args.figsize.split(',')))
            if len(figsize_tuple) != 2:
                raise ValueError("figsize must have exactly 2 values")
        except ValueError as e:
            print(f"Error parsing figsize: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Save or show
        if args.output:
            visualiser.save_graph(
                args.output,
                figsize=figsize_tuple,
                dpi=args.dpi
            )
            print(f"✓ Graph saved to: {args.output}")
        
        if args.show:
            print("Opening interactive graph viewer...")
            visualiser.show(figsize=figsize_tuple)
        
        if not args.output and not args.show:
            print("No output specified. Use --output to save or --show to display.")
            sys.exit(1)
        
    except FileNotFoundError:
        print(f"Error: File not found: {args.docx_path}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Install visualization dependencies with: poetry install --with visualisation", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
