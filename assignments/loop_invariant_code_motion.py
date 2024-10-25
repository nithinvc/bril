from typing import Dict, List, Set, Tuple

from lib.control_flow_graph import construct_cfg, reassemble
from lib.types import ControlFlowGraph
from lib.utils import emit_bril, load_bril

# Define side-effect operations that should not be moved
SIDE_EFFECT_OPS = {"print", "call", "store", "ret"}


def compute_dominators(cfg: ControlFlowGraph) -> Dict[str, Set[str]]:
    # TODO: This should probably be moved to a dominator lib
    # This is probably the correct version when compared to the ssa version
    nodes = list(cfg.block_map.keys())
    start_node = nodes[0]
    dom = {n: set(nodes) for n in nodes}
    dom[start_node] = {start_node}
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n == start_node:
                continue
            preds = cfg.predecessors[n]
            if not preds:
                continue
            new_dom = set([n]).intersection(*[dom[p] for p in preds])
            if new_dom != dom[n]:
                dom[n] = new_dom
                changed = True
    return dom


def find_back_edges(
    cfg: ControlFlowGraph, dominators: Dict[str, Set[str]]
) -> List[Tuple[str, str]]:
    back_edges = []
    for n in cfg.block_map:
        for succ in cfg.successors[n]:
            if succ in dominators[n]:
                back_edges.append((n, succ))
    return back_edges


def find_natural_loops(
    cfg: ControlFlowGraph, back_edges: List[Tuple[str, str]]
) -> List[Tuple[str, Set[str]]]:
    """
    Returns a list of natural loops in the control flow graph
    """
    loops = []
    for n, m in back_edges:
        loop_nodes = set()
        stack = [n]
        while stack:
            node = stack.pop()
            if node not in loop_nodes:
                loop_nodes.add(node)
                stack.extend(cfg.predecessors[node])
        loops.append((m, loop_nodes))
    return loops


def create_preheaders(cfg: ControlFlowGraph, loops: List[Tuple[str, Set[str]]]):
    for header, loop_nodes in loops:
        preds = cfg.predecessors[header]
        loop_preds = [p for p in preds if p in loop_nodes]
        non_loop_preds = [p for p in preds if p not in loop_nodes]
        # new preheader
        preheader_name = f"{header}_preheader"
        cfg.block_map[preheader_name] = []
        cfg.predecessors[preheader_name] = non_loop_preds
        cfg.successors[preheader_name] = [header]
        # change refs + jmps as needed
        cfg.predecessors[header] = loop_preds + [preheader_name]
        for p in non_loop_preds:
            cfg.successors[p] = [
                preheader_name if s == header else s for s in cfg.successors[p]
            ]
            block = cfg.block_map[p]
            if block:
                instr = block[-1]
                if "op" in instr and instr["op"] in ["jmp", "br"]:
                    instr["labels"] = [
                        preheader_name if l == header else l for l in instr["labels"]
                    ]
        # We might have all loops preds
        if not non_loop_preds:
            cfg.predecessors[preheader_name] = loop_preds
            for p in loop_preds:
                cfg.successors[p] = [
                    s if s != header else preheader_name for s in cfg.successors[p]
                ]
                block = cfg.block_map[p]
                if block:
                    instr = block[-1]
                    if "op" in instr and instr["op"] in ["jmp", "br"]:
                        instr["labels"] = [
                            preheader_name if l == header else l
                            for l in instr["labels"]
                        ]
            cfg.predecessors[header] = [preheader_name]
            cfg.successors[preheader_name] = [header]


def is_loop_invariant(instr, loop_defs, invariant_vars, outside_vars) -> bool:
    if "dest" not in instr or "op" not in instr:
        return False
    # Quick check if the instr is side-effecting - helps avoid mem load / store instrs
    if instr["op"] in SIDE_EFFECT_OPS:
        return False
    args = instr.get("args", [])
    for arg in args:
        if arg in loop_defs and arg not in invariant_vars:
            return False
    return True


def perform_licm_on_function(func: Dict):
    cfg = construct_cfg(func["instrs"])
    dominators = compute_dominators(cfg)
    back_edges = find_back_edges(cfg, dominators)
    loops = find_natural_loops(cfg, back_edges)
    create_preheaders(cfg, loops)

    for header, loop_nodes in loops:
        outside_vars = set()
        loop_vars = set()
        for block_name in cfg.block_map:
            block = cfg.block_map[block_name]
            for instr in block:
                if "dest" in instr:
                    if block_name in loop_nodes:
                        loop_vars.add(instr["dest"])
                    else:
                        outside_vars.add(instr["dest"])
        # Grab the set of invariant instructions
        invariant_instrs = []
        invariant_vars = set()
        changed = True
        while changed:
            changed = False
            for block_name in loop_nodes:
                block = cfg.block_map[block_name]
                for instr in block:
                    if instr in invariant_instrs:
                        continue
                    if is_loop_invariant(
                        instr, loop_vars, invariant_vars, outside_vars
                    ):
                        invariant_instrs.append(instr)
                        invariant_vars.add(instr["dest"])
                        changed = True
        # here we move invariant instructions from the block to the header
        for block_name in loop_nodes:
            block = cfg.block_map[block_name]
            cfg.block_map[block_name] = [
                instr for instr in block if instr not in invariant_instrs
            ]
        preheader_name = f"{header}_preheader"
        cfg.block_map[preheader_name].extend(invariant_instrs)

    func["instrs"] = reassemble(cfg)


def perform_licm(prog: Dict):
    for func in prog["functions"]:
        perform_licm_on_function(func)
    return prog


if __name__ == "__main__":
    bril_prog = load_bril()
    bril_prog = perform_licm(bril_prog)
    emit_bril(bril_prog)
