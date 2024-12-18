import warnings
from collections import OrderedDict, defaultdict
from copy import deepcopy

import briltxt

from .types import TERMINATOR_OPS, ControlFlowGraph
from .utils import flatten, fresh
from .visualization import visualize_graph


def get_predecessors_counts(cfg: ControlFlowGraph) -> dict[str, int]:
    """Returns a dict mapping from vertex name to number of preds"""
    mapping = defaultdict(lambda: 0)
    for v in cfg.block_map.keys():
        mapping[v] = len(cfg.predecessors[v])
    return mapping


def get_tree_root(cfg: ControlFlowGraph) -> str:
    possible_roots: list[str] = []
    for k, v in cfg.block_map.items():
        if len(cfg.predecessors[k]) == 0:
            possible_roots.append(k)
    assert len(possible_roots) == 0, "Found more than one possible tree root"
    return possible_roots[0]


def remove_critical_edges(cfg: ControlFlowGraph) -> ControlFlowGraph:
    """
    Removes any critical edges and returns a control graph where
    each edge has been split and added a node.
    """

    # Copy so we don't change the original cfg
    new_cfg = deepcopy(cfg)

    for name, block in cfg.block_map.items():
        # Check if there is more than one pred
        preds = cfg.predecessors[name]
        if len(preds) > 1:
            # In which case we split each of the nodes
            for p in preds:
                new_name = fresh("_b", new_cfg.block_map)
                new_cfg.block_map[new_name] = []
                new_cfg.predecessors[new_name] = [p]
                new_cfg.successors[new_name] = [name]

                new_cfg.successors[p].remove(name)
                new_cfg.predecessors[name].remove(p)

    return new_cfg


def instr_to_string(instr: dict) -> str:
    return briltxt.instr_to_string(instr)


def visualize_cfg(
    cfg: ControlFlowGraph,
    filename: str,
    visualize_instrs: bool = False,
    node_labels: dict[str, str] | None = None,
):
    vertices: set[str] = set(cfg.block_map.keys())  # Must have all vertices
    edges: dict[str, set[str]] = defaultdict(set)
    for v in cfg.successors.keys():
        for succ in cfg.successors[v]:
            edges[v].add(succ)
    for v in cfg.predecessors.keys():
        for pred in cfg.predecessors[v]:
            edges[pred].add(v)

    if not node_labels and visualize_instrs:
        node_labels: dict[str, str] = dict()
        for v in vertices:
            instrs = cfg.block_map[v]
            node_labels[v] = "\n".join([instr_to_string(instr) for instr in instrs])

    visualize_graph(
        vertices,
        edges,
        output_filename=filename,
        tree_layout=True,
        node_labels=node_labels,
    )


def remove_inserted_jmps(block_map: OrderedDict) -> OrderedDict:
    new_block_map = OrderedDict()
    for name, block in block_map.items():
        new_block = []
        for instr in block:
            op = instr["op"]
            if op == "jmp":
                jump_labels = instr.get("labels", [])
                assert (
                    len(jump_labels) <= 1
                ), f"Found a jump instruction with more than 1 destination! {instr}"
                # Test if generated jump
                if not jump_labels[0].startswith("_b"):
                    new_block.append(instr)
            else:
                new_block.append(instr)
        new_block_map[name] = new_block
    return new_block_map


def restrict_to_single_instr(cfg: ControlFlowGraph) -> ControlFlowGraph:
    """generates a new control flow graph such that each block only has one instruction max"""
    new_cfg = ControlFlowGraph(
        block_map=OrderedDict(),
        predecessors=cfg.predecessors,
        successors=cfg.successors,
    )
    for name, block in cfg.block_map.items():
        if len(block) <= 1:
            new_cfg.block_map[name] = block
        else:
            # At MOST there should be two instructions
            assert (
                len(block) == 2
            ), "Found a block where there are more than two instructions!"
            instr1, instr2 = (
                block  # I'm pretty sure that instr1 is always an expression and instr2 is a jump or ret statement
            )
            # Add new blocks
            new_cfg.block_map[name] = [instr1]
            new_block_name = fresh("_b", cfg.block_map)
            new_cfg.block_map[new_block_name] = [instr2]
            # Now we need to update all preds and succs
            # How we update will depend on the actual type of instr2
            op = instr2["op"]
            new_cfg.predecessors[new_block_name] = []
            new_cfg.successors[new_block_name] = []
            # case 1. ret
            if op == "ret":
                new_cfg.successors[name].append(new_block_name)
                new_cfg.predecessors[new_block_name].append(name)
            # case 2. jmp
            elif op == "jmp":
                curr_succ = instr2["labels"]
                assert (
                    len(curr_succ) == 1
                ), f"Trying to jump to multiple labels? {curr_succ}"
                curr_succ = curr_succ[0]
                new_cfg.successors[name].append(new_block_name)
                new_cfg.successors[name].remove(curr_succ)

                new_cfg.successors[new_block_name].append(curr_succ)
                new_cfg.predecessors[new_block_name].append(name)

                new_cfg.predecessors[curr_succ].remove(name)
                new_cfg.predecessors[curr_succ].append(new_block_name)

            # case 3. branch - ignored
            else:
                assert False, f"Got to an unk instruction {op}"

    return new_cfg


def prune_empty_cfg_blocks(cfg: ControlFlowGraph) -> ControlFlowGraph:
    new_cfg = deepcopy(cfg)
    for name, block in cfg.block_map.items():
        if len(block) == 0:
            # Remove the block
            del new_cfg.block_map[name]
            # We replace the successors and preds
            preds = new_cfg.predecessors[name]
            succs = new_cfg.successors[name]
            del new_cfg.predecessors[name]
            del new_cfg.successors[name]

            # Replace child nodes
            for p in preds:
                new_cfg.successors[p].remove(name)
                new_cfg.successors[p].extend(succs)

            for s in succs:
                new_cfg.predecessors[s].remove(name)
                new_cfg.predecessors[s].extend(preds)

    return new_cfg


def construct_cfg(
    instrs,
    block_only: bool = False,
    per_line: bool = False,
    remove_extra_jmps: bool = True,
) -> ControlFlowGraph:
    """Given a list of Bril instructions, generates a valid control flow graph.
    block_only (Optional, Bool):
        return only the blocks with labels. This ensures we don't add extra instructions
    Returns a tuple of the block map, predecessors, and successors.
        - Block map is ordered such that iterating the keys will yield the order in which blocks were generated.
    """
    # Form the initial blocks
    blocks = form_blocks(instrs) if not per_line else form_line_blocks(instrs)
    # Generate the block mapping
    block_map = generate_block_map(blocks)
    # Add terminators to all blocks
    add_terminators(block_map)
    # Ensure that there is an entry to the CFG
    add_entry(block_map)
    if block_only:
        return ControlFlowGraph(block_map=block_map, predecessors=None, successors=None)
    # Generate the predecessors and successors

    preds, succs = edges(block_map)

    if remove_extra_jmps:
        block_map = remove_inserted_jmps(block_map)
        cfg = ControlFlowGraph(
            block_map=block_map, predecessors=preds, successors=succs
        )
        cfg = restrict_to_single_instr(cfg)
        # TODO: The pruning operation is causing some weird edge not found issue? I think it is because the names of the blocks are not proping properly
        # cfg = prune_empty_cfg_blocks(cfg)
        return cfg

    return ControlFlowGraph(block_map=block_map, predecessors=preds, successors=succs)


def generate_block_map(blocks):
    """Given a sequence of basic blocks, which are lists of instructions,
    produce a `OrderedDict` mapping names to blocks.

    The name of the block comes from the label it starts with, if any.
    Anonymous blocks, which don't start with a label, get an
    automatically generated name. Blocks in the mapping have their
    labels removed.
    """
    by_name = OrderedDict()

    for block in blocks:
        # Generate a name for the block.
        if "label" in block[0]:
            # The block has a label. Remove the label but use it for the
            # block's name.
            name = block[0]["label"]
            block = block[1:]
        else:
            # Make up a new name for this anonymous block.
            name = fresh("_b", by_name)

        # Add the block to the mapping.
        by_name[name] = block

    return by_name


def successors(instr):
    """Get the list of jump target labels for an instruction.

    Raises a ValueError if the instruction is not a terminator (jump,
    branch, or return).
    """
    if instr["op"] in ("jmp", "br"):
        return instr["labels"]
    elif instr["op"] == "ret":
        return []  # No successors to an exit block.
    else:
        raise ValueError("{} is not a terminator".format(instr["op"]))


def add_terminators(blocks):
    """Given an ordered block map, modify the blocks to add terminators
    to all blocks (avoiding "fall-through" control flow transfers).
    """
    for i, block in enumerate(blocks.values()):
        if not block:
            if i == len(blocks) - 1:
                # In the last block, return.
                block.append({"op": "ret", "args": []})
            else:
                dest = list(blocks.keys())[i + 1]
                block.append({"op": "jmp", "labels": [dest]})
        elif block[-1]["op"] not in TERMINATOR_OPS:
            if i == len(blocks) - 1:
                block.append({"op": "ret", "args": []})
            else:
                # Otherwise, jump to the next block.
                dest = list(blocks.keys())[i + 1]
                block.append({"op": "jmp", "labels": [dest]})


def add_entry(blocks):
    """Ensure that a CFG has a unique entry block with no predecessors.

    If the first block already has no in-edges, do nothing. Otherwise,
    add a new block before it that has no in-edges but transfers control
    to the old first block.
    """
    first_lbl = next(iter(blocks.keys()))

    # Check for any references to the label.
    for instr in flatten(blocks.values()):
        if "labels" in instr and first_lbl in instr["labels"]:
            break
    else:
        return

    # References exist; insert a new block.
    new_lbl = fresh("entry", blocks)
    blocks[new_lbl] = []
    blocks.move_to_end(new_lbl, last=False)


def edges(blocks):
    """Given a block map containing blocks complete with terminators,
    generate two mappings: predecessors and successors. Both map block
    names to lists of block names.
    """
    preds = {name: [] for name in blocks}
    succs = {name: [] for name in blocks}
    for name, block in blocks.items():
        if len(block) == 0:
            continue  # Empty block
        for succ in successors(block[-1]):
            succs[name].append(succ)
            preds[succ].append(name)
    return preds, succs


def reassemble(cfg: ControlFlowGraph):
    """Flatten a CFG into an instruction list."""
    # This could optimize slightly by opportunistically eliminating
    # `jmp .next` and `ret` terminators where it is allowed.
    blocks = cfg.block_map
    instrs = []
    for name, block in blocks.items():
        if not name.startswith("_b"):
            instrs.append({"label": name})
        for instr in block:
            op = instr["op"]
            if op == "jmp":
                jmplabels = instr.get("labels", [])
                if len(jmplabels) == 1 and not jmplabels[0].startswith("_b"):
                    instrs.append(instr)
            else:
                instrs.append(instr)

    return instrs


def form_line_blocks(instrs):
    """Given a list of Bril instructions, generate a sequence of
    instruction lists representing the basic blocks in the program.

    Every instruction in `instr` will show up in exactly one block. Jump
    and branch instructions may only appear at the end of a block, and
    control can transfer only to the top of a basic block---so labels
    can only appear at the *start* of a basic block. Basic blocks may
    not be empty.

    """
    for instr in instrs:
        yield [instr]


def form_blocks(instrs):
    """Given a list of Bril instructions, generate a sequence of
    instruction lists representing the basic blocks in the program.

    Every instruction in `instr` will show up in exactly one block. Jump
    and branch instructions may only appear at the end of a block, and
    control can transfer only to the top of a basic block---so labels
    can only appear at the *start* of a basic block. Basic blocks may
    not be empty.

    """

    # Start with an empty block.
    cur_block = []

    for instr in instrs:
        if "op" in instr:  # It's an instruction.
            # Add the instruction to the currently-being-formed block.
            cur_block.append(instr)

            # If this is a terminator (branching instruction), it's the
            # last instruction in the block. Finish this block and
            # start a new one.
            if instr["op"] in TERMINATOR_OPS:
                yield cur_block
                cur_block = []

        else:  # It's a label.
            # End the block here (if it contains anything).
            if cur_block:
                yield cur_block

            # Start a new block with the label.
            cur_block = [instr]

    # Produce the final block, if any.
    if cur_block:
        yield cur_block


def print_blocks(bril):
    """Given a Bril program, print out its basic blocks."""
    try:
        # Local package as a result of the 'install.sh' script.
        import briltxt  # type: ignore
    except ModuleNotFoundError:
        print("briltxt module not found!")
        exit(1)

    func = bril["functions"][0]  # We only process one function.
    for block in form_blocks(func["instrs"]):
        # Mark the block.
        leader = block[0]
        if "label" in leader:
            print('block "{}":'.format(leader["label"]))
            block = block[1:]  # Hide the label, for concision.
        else:
            print("anonymous block:")

        # Print the instructions.
        for instr in block:
            print("  {}".format(briltxt.instr_to_string(instr)))
