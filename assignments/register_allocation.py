import argparse
from collections import defaultdict
from typing import Iterable, Optional

from lib import dataflow, utils
from lib.control_flow_graph import construct_cfg
from lib.liveness_analysis import liveness_analysis
from lib.types import ControlFlowGraph
from lib.visualization import visualize_graph


def construct_interference_graph(
    cfg: ControlFlowGraph,
    func_name: str | None = None,
) -> tuple[set[str], dict[str, set[str]]]:
    # step 1. construct initial liveness analysis sets
    # Uses a backward df analysis
    live_in, live_out = liveness_analysis(cfg)

    vertices: set[str] = set()
    edges: dict[str, set[str]] = defaultdict(set)

    # Vertices are always the set of all variables
    for in_set in live_in.values():
        for v in in_set:
            vertices.add(v)
    for out in live_out.values():
        for v in out:
            vertices.add(v)

    # Now compute edges

    # Connect edges for vertices in the same in set
    for in_set in live_in.values():
        for v1 in in_set:
            for v2 in in_set:
                if v1 == v2:
                    continue
                edges[v1].add(v2)
                edges[v2].add(v1)

    # Connect edges for vertices in the same out set
    for in_set in live_out.values():
        for v1 in in_set:
            for v2 in in_set:
                if v1 == v2:
                    continue
                edges[v1].add(v2)
                edges[v2].add(v1)

    # Now connect edges between the in and out sets since at any point,
    # these two variables *might* exist
    for blk_name in live_in.keys():
        for v1 in live_in[blk_name]:
            for v2 in live_out[blk_name]:
                if v1 == v2:
                    continue
                edges[v1].add(v2)
                edges[v2].add(v1)

    if func_name:
        visualize_graph(
            vertices,
            edges,
            output_filename=f"graphs/interference graph {func_name}.png",
        )
    return vertices, edges


Vertex_T = set[str]
Edges_T = dict[str, set[str]]
Graph_T = tuple[Vertex_T, Edges_T]


def remove_node(
    vertex: str, vertices: Vertex_T, edges: Edges_T
) -> tuple[Graph_T, set[str]]:
    """
    Removes the vertex and returns the graph and the set of neighbors
    """
    assert vertex in vertices, "tried to remove a vertex that had already been removed"
    vertices.remove(vertex)
    # bidirectional graph so walk through each possible edge
    for v2 in edges[vertex]:
        edges[v2].remove(vertex)
    underlying_edges = edges[vertex]
    # Delete the key, doesnt remove underlying_edges
    del edges[vertex]
    return (vertices, edges), underlying_edges


def add_node(
    vertex: str,
    vertices: Vertex_T,
    edges: Edges_T,
    prev_edges: Iterable[str] | None = None,
) -> Graph_T:
    assert vertex not in vertices, "Tried to add a vertex that already exists"
    vertices.add(vertex)
    if prev_edges:
        for v2 in prev_edges:
            if v2 in edges:
                # Possible that we try to add an edge to a spilled node
                edges[vertex].add(v2)
                edges[v2].add(vertex)

    return vertices, edges


def vertex_degree(vertex: str, edges: Edges_T) -> int:
    if vertex in edges:
        return len(edges[vertex])
    return 0


def find_and_assign_open_color(
    vertex: str,
    virtual_to_physical: dict[str, int],
    edges: dict[str, set[str]],
    num_physical_registers: int,
) -> dict[str, int]:
    neighbor_colors: set[int | None] = set()
    for v2 in edges[vertex]:
        neighbor_colors.add(virtual_to_physical.get(v2, None))
    for register in range(num_physical_registers):
        if register not in neighbor_colors:
            virtual_to_physical[vertex] = register
            return virtual_to_physical
    assert False, "Was not able to find a suitable physical register. Max number of neighbors colored already"


def number_of_neighbor_colors(
    vertex: str, virtual_to_physical: dict[str, int], edges: dict[str, set[str]]
) -> int:
    neighbor_colors: set[int | None] = set()
    for v2 in edges[vertex]:
        neighbor_colors.add(virtual_to_physical.get(v2, None))
    neighbor_colors.discard(None)
    return len(neighbor_colors)


def allocate_k_registers(
    cfg: ControlFlowGraph, k: int, func_name: str
) -> tuple[set[str], dict[str, int]]:
    """
    Returns the spilled registers
    """
    # prog: bril func
    num_physical_registers: int = k

    vertices: set[str]
    edges: dict[str, set[str]]
    vertices, edges = construct_interference_graph(cfg, func_name)

    # step 3: create two stacks, register stack and spill stack
    processed_vertices: list[
        tuple[
            str,
            set[str],
            str,
        ]
    ] = []

    # Helper strs
    tocolor = "to_color"
    tospill = "to_spill"

    while vertices:  # TODO: What is the cond for this loop
        # Grab the last vertex that qualifies
        vertex: str = ""
        for v in vertices:
            if vertex_degree(v, edges) < num_physical_registers:
                vertex = v
        # Two cases
        # Case 1: we found a suitable vertex
        if vertex:
            (vertices, edges), curr_edges = remove_node(vertex, vertices, edges)
            processed_vertices.append((vertex, curr_edges, tocolor))

        # Case 2: No suitable vertex
        else:
            # In this case we grab the vertex with the highest deg
            vertex_tuple: tuple[str, int] = ("", 0)
            for v in vertices:
                if vertex_tuple[1] < vertex_degree(v, edges):
                    vertex_tuple = (v, vertex_degree(v, edges))
            assert vertex_tuple[
                0
            ], "The vertex with max degree doens't exist in the case there are no edges with deg < num registers"
            vertex = vertex_tuple[0]
            (vertices, edges), curr_edges = remove_node(vertex, vertices, edges)
            processed_vertices.append((vertex, curr_edges, tospill))

    # Now process the stack of allocations?
    virtual_to_physical: dict[str, int] = defaultdict(lambda: -1)
    spill_set: set[str] = set()
    while processed_vertices:
        vertex, curr_edges, action = processed_vertices.pop()
        if action == tocolor:
            vertices, edges = add_node(vertex, vertices, edges, prev_edges=curr_edges)
            # Find the right color to assign, colors are numbers [0, num_physical_registers)
            virtual_to_physical = find_and_assign_open_color(
                vertex, virtual_to_physical, edges, num_physical_registers
            )

        elif action == tospill:
            # 1. Check if it is possible to color this vertex (it might be)

            # 1.1 optimistically add the node back in
            vertices, edges = add_node(vertex, vertices, edges, prev_edges=curr_edges)

            # 1.2 check if the neighbor colors is possible
            if (
                number_of_neighbor_colors(vertex, virtual_to_physical, edges)
                < num_physical_registers
            ):
                # 1.3 if possible, color
                virtual_to_physical = find_and_assign_open_color(
                    vertex,
                    virtual_to_physical,
                    edges,
                    num_physical_registers,
                )

            # 1.3a if not, undo adding the vertex and add it to the spill set
            else:
                (vertices, edges), curr_edges = remove_node(vertex, vertices, edges)
                # - else: add it to the spill set
                spill_set.add(vertex)
        else:
            assert False, f"Unknown action??? {action}"

    return spill_set, virtual_to_physical


def register_allocation(prog, num_physical_registers: int, func_name: str):
    # step 0. construct control flow graph
    cfg: ControlFlowGraph = construct_cfg(prog, per_line=True)

    # Attempt to color the prog with the total num of physical registers
    spill_set, virtual_to_physical = allocate_k_registers(
        cfg,
        k=num_physical_registers,
        func_name=func_name + " original" if func_name else "",
    )
    if spill_set:
        # Case that we have to spill some values
        # We now have 1 less register since we use it for loading and saving
        # This new temporary register will be used for storing and loading all the spilled variables
        spill_set, virtual_to_physical = allocate_k_registers(
            cfg,
            k=num_physical_registers - 1,
            func_name=func_name + " spilled" if func_name else "",
        )

    vertices, edges = construct_interference_graph(cfg)
    visualize_graph(
        vertices=vertices,
        edges=edges,
        vertex_colors=virtual_to_physical,
        output_filename=f"graphs/{func_name} Final Graph Coloring.png",
    )

    return len(spill_set) if spill_set else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="bril prog json to use", default=None)
    parser.add_argument(
        "--num_physical_registers",
        type=int,
        help="number of physical registers to use",
        default=16,
    )
    args = parser.parse_args()
    num_physical_registers: int = args.num_physical_registers
    file = args.file
    if file:
        prog = utils.load_bril(file)
    else:
        prog = utils.load_bril()

    physical_register_range = [i for i in range(2, num_physical_registers)]
    for f in prog["functions"]:
        spill_count = []
        for n_physical in physical_register_range:
            spill_count.append(
                register_allocation(
                    f["instrs"], n_physical, f["name"] if file else None
                )
            )

        print("spill for function", f["name"])
        print(spill_count)


if __name__ == "__main__":
    main()
