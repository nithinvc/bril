import argparse

from lib.control_flow_graph import construct_cfg
from lib.utils import emit_bril, fresh, load_bril


def to_ssa(instrs):
    # Step 1: Construct the control flow graph
    cfg = construct_cfg(instrs)

    # Step 2: Initialize structures for tracking variable definitions and uses
    var_defs = {}
    var_uses = {}

    for block_label, block in cfg.block_map.items():
        for instr in block:
            if "dest" in instr:  # Instruction defines a variable
                var_defs.setdefault(instr["dest"], []).append((block_label, instr))
            if "args" in instr:  # Instruction uses variables
                for arg in instr["args"]:
                    var_uses.setdefault(arg, []).append((block_label, instr))

    # Step 3: Perform dominance analysis
    dominator_tree = compute_dominators(cfg)

    # Step 4: Insert φ functions with undefined handling
    insert_phi_functions(cfg, var_defs, dominator_tree)

    # Step 5: Rename variables
    renamed_instrs = rename_variables(cfg, var_defs, var_uses)

    # Step 6: Emit SSA-transformed program
    return renamed_instrs, cfg


def insert_phi_functions(cfg, var_defs, dominator_tree):
    """
    Insert φ functions at control flow join points.
    We insert φ functions at join points where a variable is defined along multiple paths.
    If a variable is not defined on a particular path, we insert `__undefined`.
    """
    phi_blocks = {}

    # For each variable, check where it is defined and insert φ functions at join points
    for var, defs in var_defs.items():
        def_blocks = {block for block, _ in defs}
        work_list = list(def_blocks)

        while work_list:
            block = work_list.pop()
            doms = dominator_tree[block]  # Get all nodes dominated by the current block

            # Check the successors of this block for join points
            for successor in cfg.successors[block]:
                if successor in def_blocks:  # Join point found
                    if successor not in phi_blocks:
                        phi_blocks[successor] = []
                    if var not in phi_blocks[successor]:
                        phi_blocks[successor].append(var)
                        work_list.append(successor)

    # Insert the φ functions into the control flow graph
    for block, phi_vars in phi_blocks.items():
        phi_instrs = []
        for var in phi_vars:
            # Initialize the φ function with `__undefined` arguments by default
            phi_instr = {"op": "phi", "dest": var, "args": []}
            for pred in cfg.predecessors[block]:
                if pred in var_defs and any(var == d["dest"] for _, d in var_defs[var]):
                    phi_instr["args"].append(
                        var
                    )  # Use the variable defined in the predecessor
                else:
                    phi_instr["args"].append(
                        "__undefined"
                    )  # Variable is undefined on this path
            phi_instrs.append(phi_instr)
        cfg.block_map[block] = phi_instrs + cfg.block_map[block]


def compute_dominators(cfg):
    """
    Compute the dominator tree for each block in the control flow graph.
    A block B dominates block A if every path to A goes through B.
    """
    # Initialize dominators: each block is dominated by all blocks initially
    dom = {block: set(cfg.block_map.keys()) for block in cfg.block_map}
    entry = list(cfg.block_map.keys())[0]
    dom[entry] = {entry}  # Entry node dominates itself

    changed = True
    while changed:
        changed = False
        for block in cfg.block_map:
            if block == entry:
                continue
            # New dominator set for the current block
            new_dom = set(cfg.block_map.keys())
            for pred in cfg.predecessors[block]:
                new_dom &= dom[pred]
            new_dom.add(block)
            if new_dom != dom[block]:
                dom[block] = new_dom
                changed = True

    # Build dominator tree from dominator sets
    dominator_tree = {block: set() for block in cfg.block_map}
    for block in cfg.block_map:
        for dom_block in dom[block]:
            if dom_block != block:
                dominator_tree[dom_block].add(block)

    return dominator_tree


def rename_variables(cfg, var_defs, var_uses):
    """
    Rename variables to ensure each variable has a unique name in SSA form.
    """
    renamed_instrs = []
    var_version = {}

    for block_label, block in cfg.block_map.items():
        new_block = []
        for instr in block:
            # Rename defined variables
            if "dest" in instr:
                old_name = instr["dest"]
                new_name = fresh(old_name, var_version)
                instr["dest"] = new_name
                var_version[old_name] = new_name
            # Rename used variables
            if "args" in instr:
                new_args = []
                for arg in instr["args"]:
                    if arg in var_version:
                        new_args.append(var_version[arg])
                    else:
                        new_args.append(arg)  # No renaming if variable not seen yet
                instr["args"] = new_args
            new_block.append(instr)
        renamed_instrs.append((block_label, new_block))

    return renamed_instrs


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
        renamed_instrs, cfg = to_ssa(f["instrs"])
        f["instrs"] = to_instr_list(cfg)

    emit_bril(prog)
