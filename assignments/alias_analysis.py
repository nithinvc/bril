import argparse
from collections import defaultdict
from typing import Iterator

from lib import control_flow_graph, dataflow, utils
from lib.types import ControlFlowGraph


def dead_store_elimination(prog, out_facts):
    pass


def store_to_load_forwarding(prog, out_facts):
    pass


def redundant_load_elimination(prog, out_facts):
    pass


def alias_analysis(prog, alias_analysis_type):
    # alias_analysis_type: dse, rle, stl
    out = dataflow

    ### Conduct the alias analysis ###

    # Compute CFG
    cfg: ControlFlowGraph = control_flow_graph.construct_cfg(prog["instrs"])

    # State: var -> set of memory locations
    # We use a defaultdict to ensure that we can add new variables on the fly
    # We initialize the first set of function arguments to all memory locations - conservative init since we are doing intra-procedural analysis
    empty_fact_fn = lambda: defaultdict(lambda: set())
    # TODO The initialization of the first set of function arguments

    # Forward data analysis
    analysis_direction = "forward"

    # Meet func: union for each variable's memory locations
    def meet_func(in_facts: Iterator[defaultdict]):
        joined_in_fact = empty_fact_fn()
        for in_fact in in_facts:
            for var, locations in in_fact.items():
                joined_in_fact[var] |= locations
        return joined_in_fact

    # NOTE: We actually have no way of producing the line number since we are working on a block level.
    # As an alterantive, we instead use {block_name}.{line_number} since the block name is unique. The provides a "local" line number.
    def name_function(block_key, line_number):
        return f"{block_key}.{line_number}"

    # Transfer function for each instruction
    def transfer_func(in_facts, block, block_key):
        out_facts = in_facts  # Copy the in facts
        for lineno, line in block:
            # alloc

            # id y

            # ptradd p offset (assume offset can = 0)

            # load p

            # store p y
            pass
        return out_facts

    def fact_equality_checker(x, y):
        # Check equality in both directions since we are dealing with mapping -> set
        for (
            var,
            locs,
        ) in x.items():
            if var not in y:
                return False
            if locs != y[var]:
                return False
        for var, locs in y.items():
            if var not in x:
                return False
            if locs != x[var]:
                return False
        return True

    # We only care about the out_facts since it tells us the global memory locations
    _, alias_analysis = dataflow.solve_dataflow(
        cfg=cfg,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_func,
        meet_fn=meet_func,
        fact_equality_checker=fact_equality_checker,
        analysis_direction=analysis_direction,
        include_block_name=True,
    )

    # TODO Actually call the individual memory optimizations


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Reads from a program from `prog.json` and starts pdb at inserted lines.",
    )
    parser.add_argument(
        "--turnt",
        action="store_true",
        help="Instead of emitting bril, emits turnt formatting",
    )

    parser.add_argument("--dse", action="store_true", help="Run dead store elimination")
    parser.add_argument(
        "--rle", action="store_true", help="Run redundant load elimination"
    )
    parser.add_argument(
        "--stl", action="store_true", help="Run store to load forwarding"
    )

    args = parser.parse_args()
    prog = utils.load_bril("prog.json") if args.debug else utils.load_bril()
    for f in prog["functions"]:
        if args.dse:
            f["instrs"] = alias_analysis(f["instrs"], "dse")
        if args.rle:
            f["instrs"] = alias_analysis(f["instrs"], "rle")
        if args.stl:
            f["instrs"] = alias_analysis(f["instrs"], "stl")

    if not args.turnt:
        utils.emit_bril(prog)
