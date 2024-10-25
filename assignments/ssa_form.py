import argparse
from collections import defaultdict

from lib.control_flow_graph import construct_cfg, reassemble
from lib.utils import emit_bril, load_bril


def to_ssa(instrs):
    cfg = construct_cfg(instrs)

    # Stacks for renaming
    var_stack = defaultdict(list)
    var_defs = {}
    var_uses = {}
    var_version = defaultdict(list)

    for block_label, block in cfg.block_map.items():
        for instr in block:
            if "dest" in instr:
                var_defs.setdefault(instr["dest"], []).append((block_label, instr))
            if "args" in instr:
                for arg in instr["args"]:
                    var_uses.setdefault(arg, []).append((block_label, instr))

    dominator_tree = compute_dominators(cfg)
    # use dom analysis to find frontier to put phi funcs
    insert_phi_functions(cfg, var_defs, dominator_tree, var_stack)
    renamed_instrs = rename_variables_with_stacks(cfg, var_defs, var_uses, var_stack)

    # We output the new instructions and the corresponding cfg - cfg should be identical and helps avoid double computing
    return renamed_instrs, cfg


def insert_phi_functions(cfg, var_defs, dominator_tree, var_stack):
    phi_blocks = {}
    for var, defs in var_defs.items():
        def_blocks = {block for block, _ in defs}
        work_list = list(def_blocks)

        while work_list:
            block = work_list.pop()

            # successors of the dominating block
            for successor in cfg.successors[block]:
                if successor in def_blocks:
                    if successor not in phi_blocks:
                        phi_blocks[successor] = []
                    if var not in phi_blocks[successor]:
                        phi_blocks[successor].append(var)
                        work_list.append(successor)

    # insert phi funcs
    # Also init stack variables for renaming
    # TODO: Originally was an increasing version number, but the reference version is using a stack(?).
    # TODO: Why is this? There still seems to be an issue where variables are being used before they are defined in the output bril
    for block, phi_vars in phi_blocks.items():
        phi_instrs = []
        for var in phi_vars:
            phi_instr = {"op": "phi", "dest": var, "args": [], "labels": []}
            for pred in cfg.predecessors[block]:
                if pred in var_defs and any(var == d["dest"] for _, d in var_defs[var]):
                    phi_instr["args"].append(var)
                else:
                    phi_instr["args"].append("__undefined")
                phi_instr["labels"].append(pred)

            if var not in var_stack:
                var_stack[var] = []
            var_stack[var].append(phi_instr["dest"])

            phi_instrs.append(phi_instr)
        cfg.block_map[block] = phi_instrs + cfg.block_map[block]


# TODO: This doesn't seem to be correct? Or at least the rewritten version in the LICM file seems better
# TODO: Disambiguate and consolidate to one file
def compute_dominators(cfg):
    dom = {block: set(cfg.block_map.keys()) for block in cfg.block_map}
    entry = list(cfg.block_map.keys())[0]
    # Entry dominates itself
    dom[entry] = {entry}

    changed = True
    while changed:
        changed = False
        for block in cfg.block_map:
            if block == entry:
                continue
            new_dom = set(cfg.block_map.keys())
            for pred in cfg.predecessors[block]:
                new_dom &= dom[pred]
            new_dom.add(block)
            if new_dom != dom[block]:
                dom[block] = new_dom
                changed = True

    # generate the tree from the set
    dominator_tree = {block: set() for block in cfg.block_map}
    for block in cfg.block_map:
        for dom_block in dom[block]:
            if dom_block != block:
                dominator_tree[dom_block].add(block)

    return dominator_tree


def rename_variables_with_stacks(cfg, var_defs, var_uses, var_stack):
    renamed_instrs = []
    # TODO: Here we renamed with reference version previously
    for block_label, block in cfg.block_map.items():
        new_block = []
        for instr in block:
            if "dest" in instr:
                old_name = instr["dest"]
                if old_name in var_stack:
                    instr["dest"] = f"{old_name}.{len(var_stack[old_name]) - 1}"
                var_stack[old_name].append(instr["dest"])
            if "args" in instr:
                new_args = []
                for arg in instr["args"]:
                    if arg in var_stack:
                        new_args.append(f"{arg}.{len(var_stack[arg]) - 1}")
                    else:
                        new_args.append("__undefined" if arg == "undefined" else arg)
                instr["args"] = new_args
            new_block.append(instr)
        renamed_instrs.append((block_label, new_block))

    return renamed_instrs


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
    for f in prog["functions"]:
        renamed_instrs, cfg = to_ssa(f["instrs"])
        f["instrs"] = reassemble(cfg)

    emit_bril(prog)
