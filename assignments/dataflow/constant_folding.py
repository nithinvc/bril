import argparse
import pdb  # noqa
import sys
from typing import Dict, Iterator

# Get lib
sys.path.append("../../assignments/")
from lib import utils  # noqa
from lib.types import RESOLVABLE_OPS
from lib import control_flow_graph

from dataflow import solve_dataflow, dump_df_turnt


def resolve_op(op, args):
    return RESOLVABLE_OPS[op](*args)


def constant_folding_and_propogation(instrs):
    cfg = control_flow_graph.construct_cfg(instrs)
    # We construct the dataflow problem

    # Transfer function performs a local constant folding analysis (?)
    def transfer_fn(in_fact: Dict, block):
        out_fact = in_fact.copy()
        for instr in block:
            instr_op = instr["op"]
            args = instr.get("args", [])
            # If this is a constant assignment, we can add it to our fact set
            if instr_op == "const":
                out_fact[instr["dest"]] = instr["value"]
            # Check if this is an effect operation
            # If dest exists, we know this must be a value op
            elif instr_op in RESOLVABLE_OPS:
                # If all of the arguments are constants, we can compute the op and store the constant value
                all_args_are_const = all(arg in out_fact for arg in instr["args"])
                if all_args_are_const:
                    # All args are constants
                    # Resolve the args and compute the op
                    args = [out_fact[arg] for arg in instr["args"]]
                    resolved_output = resolve_op(instr_op, args)
                    # Transform this instruction into a constant assignment
                    instr["op"] = "const"
                    instr["value"] = resolved_output
                    # dest is the same
                    # type is the same
                    del instr["args"]  # No long have args in the const instruction case
            else:
                # We are in the case of an effect operation or conditional
                # Do nothing
                pass
        return out_fact

    # Meet function is the intersection, If we don't know what a constant is (differing values), we remove it
    def meet_fn(in_facts: Iterator[Dict]):
        # We need to init so we grab the first element
        out_fact = next(
            in_facts, dict()
        )  # If there are no elements, return an empty dict
        for fact in in_facts:
            # We only keep keys and values that are the same
            # If there is a key
            out_fact = {k: v for k, v in out_fact.items() if k in fact and v == fact[k]}
        return out_fact

    in_facts, out_facts = solve_dataflow(
        cfg,
        empty_fact_fn=lambda: dict(),  # Empty fact for constant folding is a mapping from var -> value
        transfer_fn=transfer_fn,
        meet_fn=meet_fn,
        fact_equality_checker=lambda x, y: x == y,  # Equality checker for dicts
        mode="forward",
    )

    # We can just return the flattened instructions from the block_map since we are modifiying the instructions in place (?)

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
        in_facts, out_facts, f["instrs"] = constant_folding_and_propogation(f["instrs"])
        if args.turnt:
            dump_df_turnt(in_facts, out_facts)

    if not args.turnt:
        utils.emit_bril(prog)
