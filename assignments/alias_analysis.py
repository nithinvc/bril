import argparse

from lib import dataflow, utils
from lib.types import ControlFlowGraph


def alias_analysis(prog, alias_analysis_type):
    # alias_analysis_type: dse, rle, stl
    test = ControlFlowGraph
    out = dataflow

    # Conduct the alias analysis

    # We initialize the first set of function arguments to all memory locations - conservative init since we are doing intra-procedural analysis

    # Forward data analysis

    # State: var -> set of memory locations

    # Meet func: union for each variable's memory locations
    # NOTE: We actually have no way of producing the line number since we are working on a block level.
    # As an alterantive, we instead use {block_name}.{line_number} since the block name is unique. The provides a "local" line number.

    # Transfer function for each instruction
    def transfer_func(in_facts, block):
        # alloc

        # id y

        # ptradd p offset (assume offset can = 0)

        # load p

        # store p y
        pass

    pass


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
