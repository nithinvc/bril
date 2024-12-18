import argparse
from copy import deepcopy
from typing import Any, Iterable

import ipdb

from lib import dataflow, utils
from lib.control_flow_graph import (
    construct_cfg,
    reassemble,
    remove_critical_edges,
    visualize_cfg,
)
from lib.liveness_analysis import liveness_analysis
from lib.test_utils import generate_simple_lcm_cfg
from lib.types import EXPRESSIONS, NUM_ARGS, ControlFlowGraph
from lib.visualization import visualize_graph


def try_get_expression(block):
    assert (
        len(block) <= 1
    ), f"Found a block with more than 1 instruction! Expression Use {block}"
    if len(block) == 0:
        return None
    instr = block[0]
    op = instr["op"]
    if op in EXPRESSIONS:
        args = instr.get("args", [])
        assert (
            len(args) == NUM_ARGS[op]
        ), f"Mismatch in number of arguments for instr {instr}"
        exp = (op, instr.get("type"), *args)
        return exp
    return None


def expression_use(block):
    assert (
        len(block) <= 1
    ), f"Found a block with more than 1 instruction! Expression Use {block}"
    if len(block) == 0:
        return set()
    instr = block[0]
    op = instr["op"]
    out = set()
    if op in EXPRESSIONS:
        args = instr.get("args", [])
        assert (
            len(args) == NUM_ARGS[op]
        ), f"Mismatch in number of arguments for instr {instr}"
        exp = (op, instr.get("type"), *args)
        out.add(exp)
    return out


def expression_kill(block) -> set:
    # returns the variables that have been defined in this block
    assert (
        len(block) <= 1
    ), f"Found a block with more than 1 instruction! Expression Use {block}"
    if len(block) == 0:
        return set()
    out = set()
    instr = block[0]
    dest = instr.get("dest", None)
    if dest is not None:
        out.add(dest)
    return out


def compute_needed(cfg: ControlFlowGraph) -> tuple[dict, dict]:
    direction = "backward"
    empty_fact_fn = lambda: set()
    include_block_name = False

    def meet_fn(out_facts):
        out = None
        for facts in out_facts:
            if out is None:
                out = facts
            else:
                out = out.intersection(facts)
        if out is None:
            return set()
        return out

    def transfer_fn(out_fact, block, blockname):
        in_facts = set()
        used = expression_use(block)
        killed = expression_kill(block)
        # Compute x - ekill
        for exp in out_fact:
            is_killed = False
            for arg in exp[2:]:
                is_killed = is_killed or arg in killed
            if not is_killed:
                in_facts.add(exp)

        # Add all new expressions
        in_facts = in_facts | used
        return in_facts

    fact_equality_checker = lambda x, y: x == y

    in_facts, out_facts = dataflow.solve_dataflow(
        cfg=cfg,
        mode=direction,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        fact_equality_checker=fact_equality_checker,
        include_block_name=True,
    )
    return in_facts, out_facts


def compute_available(cfg: ControlFlowGraph, needed_in: dict) -> tuple[dict, dict]:
    empty_fact_fn = lambda: set()
    direction = "forward"
    fact_equality_checker = lambda x, y: x == y

    def transfer_fn(in_fact, block, block_name):
        needed = needed_in[block_name]
        killed = expression_kill(block)
        return (in_fact | needed) - killed

    def meet_fn(in_facts):
        out = None
        for f in in_facts:
            out = out.intersection(f) if out else f
        return out if out else set()

    in_facts, out_facts = dataflow.solve_dataflow(
        cfg=cfg,
        mode=direction,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        fact_equality_checker=fact_equality_checker,
        include_block_name=True,
    )
    return in_facts, out_facts


def compute_postponable(cfg: ControlFlowGraph, earliest: dict) -> tuple[dict, dict]:
    empty_fact_fn = lambda: set()
    direction = "forward"
    fact_equality_checker = lambda x, y: x == y

    def transfer_fn(in_fact, block, blockname):
        return (in_fact | earliest[blockname]) - expression_use(block)

    def meet_fn(in_facts):
        out = None
        for f in in_facts:
            out = out.intersection(f) if out else f
        return out if out else set()

    in_facts, out_facts = dataflow.solve_dataflow(
        cfg=cfg,
        mode=direction,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        fact_equality_checker=fact_equality_checker,
        include_block_name=True,
    )
    return in_facts, out_facts


def compute_earliest(
    cfg: ControlFlowGraph, needed_in_facts: dict, available_in_facts: dict
) -> dict:
    earliest = dict()
    for name in cfg.block_map.keys():
        earliest[name] = needed_in_facts[name] - available_in_facts[name]
    return earliest


def compute_latest(cfg: ControlFlowGraph, earliest: dict, postponable_in_facts: dict):
    latest = dict()
    universe = set()
    for e in earliest.values():
        universe = universe | e
    for name, block in cfg.block_map.items():
        curr = earliest[name] | postponable_in_facts[name]
        used = expression_use(block)
        succ_facts = []
        for succ in cfg.successors[name]:
            succ_facts.append(earliest[succ] | postponable_in_facts[succ])
        succ_fact = None
        for fact in succ_facts:
            succ_fact = succ_fact.intersection(fact) if succ_fact else fact
        if not succ_fact:
            succ_fact = set()
        succ_fact = universe - succ_fact
        right_term = succ_fact | used

        latest[name] = curr & right_term

    return latest


def compute_used(cfg: ControlFlowGraph, latest: dict):
    direction = "backward"
    empty_fact_fn = lambda: set()
    fact_equality_checker = lambda x, y: x == y

    def transfer_fn(out_fact, block, blockname):
        used = expression_use(block)
        return used | out_fact - latest[blockname]

    def meet_fn(out_facts):
        out = set()
        for f in out_facts:
            out = out | f
        return out

    in_facts, out_facts = dataflow.solve_dataflow(
        cfg=cfg,
        mode=direction,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        fact_equality_checker=fact_equality_checker,
        include_block_name=True,
    )
    return in_facts, out_facts


def lcm_program_transformation(
    cfg: ControlFlowGraph, latest: dict, used_out_facts: dict
):
    intermediates = dict()
    for name, block in cfg.block_map.items():
        # ipdb.set_trace()
        exp = try_get_expression(block)
        if not exp:
            continue
        should_replace = exp in latest[name].intersection(used_out_facts[name])
        if not should_replace:
            continue
        if exp not in intermediates:
            # Add this to the intermediates
            intermediate_var = utils.fresh("t", intermediates)
            intermediates[exp] = intermediate_var
            op = exp[0]
            dtype = exp[1]
            args = list(exp[2:])
            block.insert(
                0, {"op": op, "dest": intermediate_var, "args": args, "type": dtype}
            )
            instr = block[1]
        else:
            intermediate_var = intermediates[exp]
            instr = block[0]
        instr["op"] = "id"
        instr["args"] = [intermediate_var]
    return reassemble(cfg)


def convert_to_node_labels(facts):
    out = dict()
    for k, v in facts.items():
        out[k] = []
        for i in v:
            out[k].append(" ".join(i))
        out[k] = "\n".join(out[k])
    return out


def lazy_code_motion(prog, func_name: str, test: bool = False):
    if not test:
        cfg: ControlFlowGraph = construct_cfg(prog, per_line=True)
    else:
        cfg = generate_simple_lcm_cfg()
        visualize_cfg(cfg, filename="graphs/test-graph.png", visualize_instrs=True)
    # cfg = remove_critical_edges(cfg)

    visualize_cfg(
        cfg,
        filename=f"graphs/graph-nodes.png",
    )

    visualize_cfg(
        cfg, filename=f"graphs/graph-after-critical.png", visualize_instrs=True
    )

    needed_in_facts, needed_out_facts = compute_needed(cfg)

    visualize_cfg(
        cfg,
        filename=f"graphs/needed_in.png",
        node_labels=convert_to_node_labels(needed_in_facts),
    )
    visualize_cfg(
        cfg,
        filename=f"graphs/needed_out.png",
        node_labels=convert_to_node_labels(needed_out_facts),
    )

    available_in_facts, available_out_facts = compute_available(cfg, needed_in_facts)
    earliest = compute_earliest(
        cfg, needed_in_facts=needed_in_facts, available_in_facts=available_in_facts
    )

    visualize_cfg(
        cfg,
        filename=f"graphs/available_in.png",
        node_labels=convert_to_node_labels(available_in_facts),
    )
    visualize_cfg(
        cfg,
        filename=f"graphs/available_out.png",
        node_labels=convert_to_node_labels(available_out_facts),
    )
    visualize_cfg(
        cfg,
        filename=f"graphs/earliest.png",
        node_labels=convert_to_node_labels(earliest),
    )

    postponable_in_facts, postponable_out_facts = compute_postponable(cfg, earliest)
    latest = compute_latest(
        cfg, earliest=earliest, postponable_in_facts=postponable_in_facts
    )

    visualize_cfg(
        cfg,
        filename=f"graphs/postpone_in.png",
        node_labels=convert_to_node_labels(postponable_in_facts),
    )
    visualize_cfg(
        cfg,
        filename=f"graphs/postpone_out.png",
        node_labels=convert_to_node_labels(postponable_out_facts),
    )
    visualize_cfg(
        cfg,
        filename=f"graphs/latest.png",
        node_labels=convert_to_node_labels(latest),
    )

    used_in_facts, used_out_facts = compute_used(cfg, latest)

    visualize_cfg(
        cfg,
        filename=f"graphs/used_out.png",
        node_labels=convert_to_node_labels(used_out_facts),
    )

    visualize_cfg(
        cfg,
        filename=f"graphs/used_in.png",
        node_labels=convert_to_node_labels(used_in_facts),
    )

    prog = lcm_program_transformation(cfg, latest=latest, used_out_facts=used_out_facts)

    visualize_cfg(
        cfg,
        filename=f"graphs/finalized_graph.png",
        visualize_instrs=True,
    )

    return prog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="bril prog json to use", default=None)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    test = args.test
    if not test:
        file = args.file
        if file:
            prog = utils.load_bril(file)
        else:
            prog = utils.load_bril()

        for f in prog["functions"]:
            f["instrs"] = lazy_code_motion(f["instrs"], f["name"])
        utils.emit_bril(prog)
    else:
        lazy_code_motion(None, "test", True)


if __name__ == "__main__":
    main()
