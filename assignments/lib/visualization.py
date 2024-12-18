from collections import defaultdict

import matplotlib.pyplot as plt
import networkx as nx
import pydot
from matplotlib import cm
from matplotlib.colors import Normalize
from networkx.drawing.nx_pydot import graphviz_layout


def get_tree_root(vertices: set[str], edges: dict[str, set[str]]) -> str:
    import ipdb

    in_degree: dict[str, int] = defaultdict(lambda: 0)
    for dst in edges.values():
        for v in dst:
            in_degree[v] += 1
    possible_roots = [v for v in vertices if in_degree[v] == 0]
    assert len(possible_roots) == 1, "Found more than 1 root for a tree!"
    return possible_roots[0]


def visualize_graph(
    vertices: set[str],
    edges: dict[str, set[str]],
    output_filename: str = "graph.png",
    vertex_colors: dict[str, int] | None = None,
    tree_layout: bool = False,
    node_labels: dict[str, str] = None,
):
    """
    Visualizes a graph and saves it as a PNG file.

    Parameters:
    vertices (set of str): The set of vertices of the graph.
    edges (dict of str to set of str): A dictionary representing the edges of the graph,
                                       where the key is a vertex and the value is a set of connected vertices.
    output_filename (str): The filename where the graph image will be saved.
    tree_layout (bool): whether to use a tree style layout. Best for CFGs
    """
    # Create a directed graph
    G = nx.DiGraph()

    # Add vertices to the graph
    G.add_nodes_from(vertices)

    # Add edges to the graph
    for source, targets in edges.items():
        for target in targets:
            G.add_edge(source, target)

    # Set up node colors
    if vertex_colors:
        # Normalize the color values to fit in the range [0, 1] for colormap
        norm = Normalize(vmin=0, vmax=max(vertex_colors.values()))
        node_colors = [
            cm.viridis(norm(vertex_colors[node]))
            if vertex_colors[node] != -1
            else "red"
            for node in G.nodes()
        ]
    else:
        node_colors = "lightblue"  # Default color if no vertex colors are provided

    # Draw the graph
    plt.figure(figsize=(10, 10))
    if tree_layout:
        # Assuming this a proper tree, there will only ever be a single root
        root = get_tree_root(vertices, edges)
        # pos = graphviz_layout(G, prog="neato", root=root)
        pos = graphviz_layout(G, prog="dot", root=root)
    else:
        pos = nx.spring_layout(G, seed=42)
    nx.draw(
        G,
        pos,
        with_labels=not node_labels,
        node_color=node_colors,
        edge_color="gray",
        node_size=3000,
        font_size=16,
        font_weight="bold",
        arrowsize=20,
    )
    if node_labels:
        nx.draw_networkx_labels(
            G,
            pos,
            labels=node_labels,
            font_size=10,
            font_color="black",
            font_weight="bold",
        )

    # Save the graph as a PNG file
    plt.savefig(output_filename, format="PNG")
    plt.close()
