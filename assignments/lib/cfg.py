from collections import OrderedDict

from .types import TERMINATOR_OPS
from .utils import flatten, fresh


def construct_cfg(instrs):
    """Given a list of Bril instructions, generates a valid control flow graph.
    Returns a tuple of the block map, predecessors, and successors.
        - Block map is ordered such that iterating the keys will yield the order in which blocks were generated.
    """
    # Form the initial blocks
    blocks = form_blocks(instrs)
    # Generate the block mapping
    block_map = generate_block_map(blocks)
    # Add terminators to all blocks
    add_terminators(block_map)
    # Ensure that there is an entry to the CFG
    add_entry(block_map)
    # Generate the predecessors and successors
    preds, succs = edges(block_map)
    return block_map, preds, succs


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
            name = fresh("b", by_name)

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
        for succ in successors(block[-1]):
            succs[name].append(succ)
            preds[succ].append(name)
    return preds, succs


def reassemble(blocks):
    """Flatten a CFG into an instruction list."""
    # This could optimize slightly by opportunistically eliminating
    # `jmp .next` and `ret` terminators where it is allowed.
    instrs = []
    for name, block in blocks.items():
        instrs.append({"label": name})
        instrs += block
    return instrs


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
