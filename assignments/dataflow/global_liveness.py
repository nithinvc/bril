import argparse
import pdb  # noqa
import sys
from typing import Dict, Iterator, Set  # noqa

# Get lib
sys.path.append("../../assignments/")
from dataflow import dump_df_turnt, solve_dataflow  # noqa
from lib import control_flow_graph, utils


def deadcode_elimination_liveness(in_facts: Set, out_facts: Set, block):
    # in_facts: unused
    idx_marked_for_deletion = []
    # The live variables start out as out_facts
    live_vars = out_facts.copy()
    # We traverse the block in reverse order
    for idx in range(len(block) - 1, -1, -1):
        instr = block[idx]
        dest = instr.get("dest", None)
        args = instr.get("args", [])
        marked_for_deletion = False
        if dest is not None:
            # There is no assignment and we can not delete this line
            # Check if dest is live. If not, delete this line
            if dest not in live_vars:
                idx_marked_for_deletion.append(idx)
                marked_for_deletion = True
        # If this line is not marked for deletion, add the args of it to live variables
        if not marked_for_deletion:
            for arg in args:
                live_vars.add(arg)
    for idx in sorted(idx_marked_for_deletion, reverse=True):
        del block[idx]
    return len(idx_marked_for_deletion) > 0


def global_liveness(instrs):
    cfg = control_flow_graph.construct_cfg(instrs)

    # We run a backward dataflow analysis
    # At the start, no variables are live so init to empty set
    def empty_fact_fn():
        return set()

    def gen(block):
        # Gen function returns the set of variables that are used in a block
        # These are "live variables"
        redefined_vars = set()
        used_vars = set()
        for instr in block:
            args = instr.get("args", [])
            for arg in args:
                # If arg has been defined in the block, we don't count it as an instance of the prev var being live
                # Since we are only concerned with incoming liveness
                if arg not in redefined_vars:
                    used_vars.add(arg)
            dest = instr.get("dest", None)
            if dest is not None:
                redefined_vars.add(dest)
        return used_vars

    def kill(block):
        # kill function returns the set of variables that are defined in a block
        # These variables are not considered live since they're essentially new variables, akin to being renamed
        defined_vars = set()
        for instr in block:
            dest = instr.get("dest", None)
            if dest is not None:
                defined_vars.add(dest)
        return defined_vars

    def transfer_fn(out_facts, block):
        # The transfer function is simply in(b) = gen(b) U (out(b) - kill(b))
        return gen(block).union(out_facts - kill(block))

    # Meet function is set union
    def meet_fn(facts: Iterator[Dict]):
        new_fact = empty_fact_fn()
        for fact in facts:
            new_fact = new_fact.union(fact)
        return new_fact

    in_facts, out_facts = solve_dataflow(
        cfg,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        # Set equality checker
        fact_equality_checker=lambda x, y: x == y,
        mode="backward",
    )
    # Now that we have the in_facts, out_facts, we perform deadcode elimination
    # We create a new cfg so we can get rid of any instructions we added during control graph creation
    cfg = control_flow_graph.construct_cfg(instrs, block_only=True)
    for block_key, block in cfg.block_map.items():
        # In place updates
        deadcode_elimination_liveness(
            in_facts=in_facts[block_key], out_facts=out_facts[block_key], block=block
        )

    return in_facts, out_facts, control_flow_graph.reassemble(cfg)


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
    args = parser.parse_args()
    prog = utils.load_bril("prog.json") if args.debug else utils.load_bril()
    # do something
    for f in prog["functions"]:
        in_facts, out_facts, f["instrs"] = global_liveness(f["instrs"])
        if args.turnt:
            dump_df_turnt(in_facts, out_facts)

    if not args.turnt:
        utils.emit_bril(prog)
