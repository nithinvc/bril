import argparse

from lib.control_flow_graph import construct_cfg
from lib.types import TERMINATOR_OPS
from lib.utils import emit_bril, flatten, load_bril
from ssa_form import compute_dominators


def loop_invariant_code_motion(instrs):
    # Step 1: Construct the control flow graph
    cfg = construct_cfg(instrs)

    # Step 2: Identify loops in the CFG
    natural_loops = find_loops(cfg)

    # Step 3: For each loop, find invariant instructions and move them outside the loop
    for loop_header, loop_blocks in natural_loops.items():
        loop_invariants = find_loop_invariants(cfg, loop_header, loop_blocks)
        hoist_invariants(cfg, loop_header, loop_invariants)

    # Step 4: Emit the transformed program
    return to_instr_list(cfg)


def find_loops(cfg):
    """
    Identify natural loops in the control flow graph, ensuring only single-entry natural loops are considered.
    Filter out non-loop back edges (e.g., those leading to termination blocks like .end).
    """
    loops = {}
    dominators = compute_dominators(cfg)

    for block in cfg.block_map:
        for successor in cfg.successors[block]:
            # Check for back edges indicating loops, exclude edges to .end
            if (
                successor in dominators[block] and successor != ".end"
            ):  # Back edge found, identifying a loop
                loop_header = successor
                loop_blocks = find_loop_blocks(cfg, block, loop_header)

                # Ensure that the loop header dominates all blocks in the loop and has only one entry
                if all(
                    loop_header in dominators[loop_block] for loop_block in loop_blocks
                ) and is_single_entry(cfg, loop_header, loop_blocks):
                    loops[loop_header] = loop_blocks

    return loops


def find_loop_blocks(cfg, block, loop_header):
    """
    Find all blocks that form the loop, starting from a back edge (block -> loop_header).
    Traverse backward from block to include all blocks in the loop.
    """
    loop_blocks = set()
    work_list = [block]

    while work_list:
        current_block = work_list.pop()
        if current_block not in loop_blocks:
            loop_blocks.add(current_block)
            for pred in cfg.predecessors[current_block]:
                if pred != loop_header:
                    work_list.append(pred)

    return loop_blocks


def is_single_entry(cfg, loop_header, loop_blocks):
    """
    Ensure that the loop has a single entry point (loop_header).
    There should be no other edges entering the loop from outside.
    """
    for block in loop_blocks:
        for pred in cfg.predecessors[block]:
            if pred not in loop_blocks and block != loop_header:
                return False
    return True


def find_loop_invariants(cfg, loop_header, loop_blocks):
    """
    Identify loop-invariant instructions in the loop.
    An instruction is loop-invariant if all of its operands are defined outside the loop
    or by other loop-invariant instructions.
    """
    loop_invariants = []
    invariants_set = set()

    for block_label in loop_blocks:
        for instr in cfg.block_map[block_label]:
            # Ensure branch conditions or terminator ops are not hoisted
            if instr["op"] in TERMINATOR_OPS:
                continue
            if "dest" in instr:
                if all(
                    is_invariant_operand(cfg, loop_blocks, arg, invariants_set)
                    for arg in instr.get("args", [])
                ):
                    loop_invariants.append((block_label, instr))
                    invariants_set.add(instr["dest"])

    return loop_invariants


def is_invariant_operand(cfg, loop_blocks, operand, invariants_set):
    """
    Check if an operand is loop-invariant:
    - It is defined outside the loop
    - It is defined by an instruction that is already known to be loop-invariant
    """
    for block in loop_blocks:
        for instr in cfg.block_map[block]:
            if "dest" in instr and instr["dest"] == operand:
                return False
    return operand in invariants_set or operand not in flatten(
        cfg.block_map[block] for block in loop_blocks
    )


def hoist_invariants(cfg, loop_header, loop_invariants):
    """
    Hoist the loop-invariant instructions to a preheader block.
    The preheader block is executed once before the loop starts.
    """
    # Create a new preheader block
    preheader_label = f"{loop_header}_preheader"
    preheader_block = []

    # Move loop-invariant instructions to the preheader
    for block_label, instr in loop_invariants:
        cfg.block_map[block_label].remove(instr)
        preheader_block.append(instr)

    # Insert the preheader block just before the loop header
    cfg.block_map[preheader_label] = preheader_block
    for pred in cfg.predecessors[loop_header]:
        cfg.successors[pred].remove(loop_header)
        cfg.successors[pred].append(preheader_label)
    cfg.successors[preheader_label] = [loop_header]


def to_instr_list(cfg):
    """
    Converts the control flow graph back into a linear list of instructions, suitable for emitting in JSON form.
    Each block's label is preserved, and instructions are flattened.
    """
    instr_list = []
    for block_label, block_instrs in cfg.block_map.items():
        instr_list.append({"label": block_label})
        instr_list.extend(block_instrs)
    return instr_list


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
    prog = load_bril()
    # do something
    for f in prog["functions"]:
        f["instrs"] = loop_invariant_code_motion(f["instrs"])

    emit_bril(prog)
