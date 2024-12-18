import argparse
from copy import deepcopy
from typing import Any, Iterable

import ipdb
from briltxt import bril2txt

from lib import dataflow, utils
from lib.control_flow_graph import construct_cfg, reassemble, visualize_cfg
from lib.liveness_analysis import liveness_analysis
from lib.types import SIDE_EFFECT_OPS, ControlFlowGraph
from lib.visualization import visualize_graph


def dead_code_elimination(prog, func_name: str, iteration: int):
    # Alg 1 of the paper (dce)
    cfg: ControlFlowGraph = construct_cfg(prog, per_line=True)

    in_facts, out_facts = liveness_analysis(cfg)

    # Visualize the current cfg
    visualize_cfg(cfg, f"graphs/pre_cfg_iter={iteration}.png", visualize_instrs=True)

    # Now that we have liveness, we go through each instruction and determine if it needs to be removed
    # It is removed if the LHS is not part of the out live set and it is not a side effect instruction
    for blk_name, blk_instrs in cfg.block_map.items():
        in_set = in_facts[blk_name]
        out_set = out_facts[blk_name]
        # Grab the single instruction
        # ipdb.set_trace()
        marked_for_deletion = []
        # print("instruction", blk_instrs[0])
        # print("in_set", in_set)
        # print("out_set", out_set)
        for i in range(len(blk_instrs)):
            instr = blk_instrs[i]
            op = instr.get("op", None)
            if op is None:
                print("Got none op", instr)
            elif op in SIDE_EFFECT_OPS:
                continue
            else:
                # Non-side effect op
                # Check if the assignment is used
                dest = instr.get("dest", None)
                if dest and dest not in out_set:
                    # print("marked for deletion", instr)
                    marked_for_deletion.append(i)
        assert (
            len(marked_for_deletion) == 1 or len(marked_for_deletion) == 0
        ), "Deleting more than one instruction from block"
        if marked_for_deletion:
            blk_instrs.pop(marked_for_deletion[0])

    visualize_cfg(cfg, f"graphs/post_cfg_iter={iteration}.png", visualize_instrs=True)
    return reassemble(cfg)


def assignment_sinking(prog, func_name: str, iteration: int):
    return prog


def print_prog(prog):
    for p in prog:
        print(p)


def partial_dead_code_elimination(prog, func_name: str):
    # Partial dead code elimination is done on a per line basis
    converged = False
    iteration = 1
    while not converged:
        prev_prog = deepcopy(prog)
        # Step 1 dce
        prog = dead_code_elimination(prog, func_name, iteration)

        # Step 2 ask
        prog = assignment_sinking(prog, func_name, iteration)
        iteration += 1

        if len(prev_prog) == len(prog):
            are_same: bool = True
            for i1, i2 in zip(prev_prog, prog):
                are_same = are_same and i1 == i2
            converged: bool = are_same

    # Construct data flow analysis
    return prog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="bril prog json to use", default=None)
    args = parser.parse_args()
    file = args.file
    if file:
        prog = utils.load_bril(file)
    else:
        prog = utils.load_bril()

    for f in prog["functions"]:
        f["instrs"] = partial_dead_code_elimination(f["instrs"], f["name"])
    if not file:
        utils.emit_bril(prog)


if __name__ == "__main__":
    main()
