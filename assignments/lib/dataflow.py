from collections import defaultdict
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional

from lib.types import ControlFlowGraph

# "Fact" can be anything, but the join and meet functions need to defined on the same type
Fact_T = Any
# Function that returns an empty fact
Empty_Fact_Fn_T = Callable[[], Fact_T]
# Block is a list of instrs
Block_T = List[Dict]
# Transfer function - takes in the facts from the beginning / end of the block, the block, and computes the new facts
Transfer_fn_T = Callable[[Fact_T, Block_T, Optional[bool]], Fact_T]
# Meet / join function should take in a list of facts and return a single fact that represents the meet / join of all the facts
Meet_fn_T = Callable[[Iterator[Fact_T]], Fact_T]
# Given two facts, return True if they are the same
Fact_Equality_Checker_T = Callable[[Fact_T, Fact_T], bool]


# We can either have forward or backward dataflow analysis
def forward_data_flow(
    cfg: ControlFlowGraph,
    empty_fact_fn: Empty_Fact_Fn_T,
    transfer_fn: Transfer_fn_T,
    meet_fn: Meet_fn_T,
    fact_equality_checker: Fact_Equality_Checker_T,
    include_block_name: bool = False,
):
    # Initialize original facts
    in_facts = defaultdict(empty_fact_fn)
    out_facts = defaultdict(empty_fact_fn)

    # Starting from the top since block_map is an ordered dict
    worklist = list(cfg.block_map.keys())
    while len(worklist) > 0:
        block_key = worklist.pop(0)
        block = cfg.block_map[block_key]
        # Meet inputs for the block
        in_facts[block_key] = meet_fn(
            out_facts[predecessor] for predecessor in cfg.predecessors[block_key]
        )

        # Compute the new fact
        args = [in_facts[block_key], block]
        if include_block_name:
            args = [in_facts[block_key], block, block_key]
        new_out_fact = transfer_fn(*args)
        # The fact is different than what we have
        # Add to worklist and update out[block]
        if not fact_equality_checker(new_out_fact, out_facts[block_key]):
            out_facts[block_key] = new_out_fact
            worklist.extend(cfg.successors[block_key])
    return in_facts, out_facts


def backward_data_flow(
    cfg: ControlFlowGraph,
    empty_fact_fn: Empty_Fact_Fn_T,
    transfer_fn: Transfer_fn_T,
    meet_fn: Meet_fn_T,
    fact_equality_checker: Fact_Equality_Checker_T,
    include_block_name: bool = False,
):
    # Initialize original facts
    in_facts = defaultdict(empty_fact_fn)
    out_facts = defaultdict(empty_fact_fn)

    # Starting worklist is the reverse of the block_map keys
    # We reverse since we want to go bottom to top but ultimately the starting worklist doesn't matter
    worklist = list(cfg.block_map.keys())
    worklist.reverse()
    while len(worklist) > 0:
        block_key = worklist.pop(0)
        block = cfg.block_map[block_key]

        # Meet the output facts of all the successors
        # We're going "bottom up"
        out_facts[block_key] = meet_fn(
            in_facts[successor] for successor in cfg.successors[block_key]
        )

        # Now compute the new in fact from the out_fact and block
        args = [out_facts[block_key], block]
        if include_block_name:
            args = [out_facts[block_key], block, block_key]
        new_in_fact = transfer_fn(*args)
        # Check if the new in fact is different old one
        if not fact_equality_checker(new_in_fact, in_facts[block_key]):
            in_facts[block_key] = new_in_fact
            # Add all of the predecessors to the worklist since their out facts will change
            worklist.extend(cfg.predecessors[block_key])
    return in_facts, out_facts


def solve_dataflow(
    cfg: ControlFlowGraph,
    empty_fact_fn: Empty_Fact_Fn_T,
    transfer_fn: Transfer_fn_T,
    meet_fn: Meet_fn_T,
    fact_equality_checker: Fact_Equality_Checker_T,
    mode: Literal["forward", "backward"],
    include_block_name: bool = False,
):
    """
    Solve the dataflow problem.
    args:
        cfg (ControlFlowGraph): Control flow graph of the function to use.
        empty_fact_fn (Empty_Fact_Fn_T): Callable factory that should return an empty fact. Takes no args.
        transfer_fn (Transfer_fn_T): Callable that takes in a Fact and Block of instructions, returning the corresponding computed fact.
        meet_fn (Meet_fn_T): Callable that takes in an iterable of facts and joins / meets them.
        fact_equality_checker (Fact_Equality_Checker_T): Callable that returns true if two facts are equivalent
        mode (string): Either 'forward' or 'backward'.
        include_block_name (bool): If true, the block name will be passed in as an argument to the transfer function. Default is False.
    """
    if mode == "forward":
        return forward_data_flow(
            cfg,
            empty_fact_fn,
            transfer_fn,
            meet_fn,
            fact_equality_checker,
            include_block_name=include_block_name,
        )
    elif mode == "backward":
        return backward_data_flow(
            cfg,
            empty_fact_fn,
            transfer_fn,
            meet_fn,
            fact_equality_checker,
            include_block_name=include_block_name,
        )
    else:
        raise ValueError("Mode should be either 'forward' or 'backward'")


### Code for turnt from the examples ###
def fmt(val):
    """Guess a good way to format a data flow value. (Works for sets and
    dicts, at least.)
    """
    if isinstance(val, set):
        if val:
            return ", ".join(v for v in sorted(val))
        else:
            return "∅"
    elif isinstance(val, dict):
        if val:
            return ", ".join("{}: {}".format(k, v) for k, v in sorted(val.items()))
        else:
            return "∅"
    else:
        return str(val)


def dump_df_turnt(in_facts, out_facts):
    for block in in_facts.keys():
        print("{}:".format(block))
        print("  in: ", fmt(in_facts[block]))
        print("  out:", fmt(out_facts[block]))
