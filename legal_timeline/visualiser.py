"""
visualiser.py — convert BranchTree to networkx graph and visualize.

Usage::

    from legal_timeline.visualiser import TimelineVisualiser
    from legal_timeline import DocumentAnalyser

    analyser = DocumentAnalyser()
    result = analyser.analyse("contract.docx")
    
    visualiser = TimelineVisualiser(result.tree)
    visualiser.save_graph("timeline.png")
    visualiser.show()  # Display in matplotlib window
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False

from .timeline import BranchTree, TimelineNode

log = logging.getLogger(__name__)


class TimelineVisualiser:
    """
    Convert a BranchTree to a networkx directed graph and visualize it.
    
    Parameters
    ----------
    tree : BranchTree
        The timeline tree to visualize.
    """
    
    def __init__(self, tree: BranchTree) -> None:
        if not HAS_VISUALIZATION:
            raise ImportError(
                "Visualization requires networkx and matplotlib. "
                "Install with: pip install networkx matplotlib"
            )
        
        self.tree = tree
        self.graph = self._build_graph()
    
    def _build_graph(self) -> nx.DiGraph:
        """
        Convert the BranchTree to a networkx directed graph.
        
        Each node is labeled with its date and category. Edges connect
        parent nodes to their children.
        """
        G = nx.DiGraph()
        
        # Add nodes with attributes
        for node in self.tree.all_nodes():
            node_id = id(node)
            date_str = node.date.strftime("%d %b %Y") if node.is_resolved else "?"
            
            G.add_node(
                node_id,
                label=f"{node.category}\n{date_str}",
                category=node.category,
                date=node.date,
                is_resolved=node.is_resolved,
                date_str=date_str,
                raw_label=node.label,
            )
        
        # Add edges (parent → child relationships)
        for node in self.tree.all_nodes():
            for child in node.children:
                G.add_edge(id(node), id(child))
        
        return G
    
    def save_graph(
        self,
        filepath: str,
        figsize: tuple = (14, 10),
        dpi: int = 150,
    ) -> None:
        """
        Save the graph visualization to a file.
        
        Parameters
        ----------
        filepath : str
            Output file path (e.g., 'timeline.png', 'timeline.pdf')
        figsize : tuple
            Figure size as (width, height) in inches. Default (14, 10).
        dpi : int
            Resolution in dots per inch. Default 150.
        """
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        self._draw_graph(ax)
        fig.savefig(filepath, bbox_inches='tight', dpi=dpi)
        plt.close(fig)
        log.info(f"Graph saved to {filepath}")
    
    def show(self, figsize: tuple = (14, 10)) -> None:
        """
        Display the graph in an interactive matplotlib window.
        
        Parameters
        ----------
        figsize : tuple
            Figure size as (width, height) in inches. Default (14, 10).
        """
        fig, ax = plt.subplots(figsize=figsize)
        self._draw_graph(ax)
        plt.tight_layout()
        plt.show()
    
    def _draw_graph(self, ax) -> None:
        """
        Internal method to draw the graph on a matplotlib axes.
        """
        # Use a hierarchical layout
        pos = self._compute_hierarchy_layout()
        
        # Separate resolved and unresolved nodes
        resolved_nodes = [
            n for n in self.graph.nodes()
            if self.graph.nodes[n].get('is_resolved', True)
        ]
        unresolved_nodes = [
            n for n in self.graph.nodes()
            if not self.graph.nodes[n].get('is_resolved', True)
        ]
        
        # Draw edges
        nx.draw_networkx_edges(
            self.graph,
            pos,
            ax=ax,
            edge_color='gray',
            arrows=True,
            arrowsize=20,
            arrowstyle='->',
            width=1.5,
            connectionstyle='arc3,rad=0.1',
        )
        
        # Draw resolved nodes
        nx.draw_networkx_nodes(
            self.graph,
            pos,
            nodelist=resolved_nodes,
            node_color='#4CAF50',
            node_size=2000,
            ax=ax,
            node_shape='o',
        )
        
        # Draw unresolved nodes
        nx.draw_networkx_nodes(
            self.graph,
            pos,
            nodelist=unresolved_nodes,
            node_color='#FF9800',
            node_size=2000,
            ax=ax,
            node_shape='s',
        )
        
        # Draw labels
        labels = {
            n: self.graph.nodes[n]['label']
            for n in self.graph.nodes()
        }
        nx.draw_networkx_labels(
            self.graph,
            pos,
            labels=labels,
            font_size=8,
            font_weight='bold',
            ax=ax,
        )
        
        ax.set_title("Legal Timeline — Date Dependency Graph", fontsize=14, fontweight='bold')
        ax.axis('off')
    
    def _compute_hierarchy_layout(self) -> dict:
        """
        Compute node positions using a hierarchical layering algorithm.
        
        Nodes are arranged by depth (distance from root), with siblings
        spread horizontally.
        """
        pos = {}
        
        # Group nodes by depth
        depth_groups = {}
        for node in self.graph.nodes():
            # Find depth by traversing back to root
            depth = self._get_node_depth(node)
            if depth not in depth_groups:
                depth_groups[depth] = []
            depth_groups[depth].append(node)
        
        # Assign positions
        max_depth = max(depth_groups.keys()) if depth_groups else 0
        
        for depth, nodes in depth_groups.items():
            y = -(depth * 2)  # Vertical position from depth
            n_nodes = len(nodes)
            
            for i, node in enumerate(nodes):
                x = (i - n_nodes / 2 + 0.5) * 3  # Horizontal spread
                pos[node] = (x, y)
        
        return pos
    
    def _get_node_depth(self, node_id: int) -> int:
        """Get the depth of a node (distance from its root)."""
        depth = 0
        # Find all paths to roots and use the shortest
        try:
            # In a DAG, we can have multiple paths; find the shortest
            all_roots = [
                n for n in self.graph.nodes()
                if self.graph.in_degree(n) == 0
            ]
            if all_roots:
                min_dist = min(
                    (
                        nx.shortest_path_length(self.graph, root, node_id)
                        if nx.has_path(self.graph, root, node_id)
                        else float('inf')
                    )
                    for root in all_roots
                )
                depth = min_dist if min_dist != float('inf') else 0
        except (nx.NetworkXError, nx.NetworkXNoPath):
            depth = 0
        
        return depth
    
    def get_graph(self) -> nx.DiGraph:
        """
        Return the underlying networkx DiGraph object for further manipulation.
        """
        return self.graph
    
    def graph_stats(self) -> dict:
        """
        Return basic statistics about the graph.
        """
        return {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'num_roots': sum(1 for n in self.graph.nodes() if self.graph.in_degree(n) == 0),
            'max_depth': max(
                (self._get_node_depth(n) for n in self.graph.nodes()),
                default=0
            ),
            'is_dag': nx.is_directed_acyclic_graph(self.graph),
        }
