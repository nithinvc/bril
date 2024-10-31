import argparse
from collections import defaultdict
from typing import Iterator

from lib import control_flow_graph, dataflow, utils
from lib.types import ControlFlowGraph


def dead_store_elimination(prog: dict, points_to):
    # Run dead store analysis
    # Remove instructions of the form:
    # 1. store x y
    # INTERMEDIATE INSTRS
    # 2. store x z
    # We can remove the first store if and only if the memory location of x is not used between the two stores.
    cfg = control_flow_graph.construct_cfg(prog["instrs"], block_only=True)
    optimized_blocks = {}
    for block_name, block in cfg.block_map.items():
        # keep track of stores
        prev_stores = defaultdict(lambda: False)
        optimized_instrs = []
        block_points_to = points_to.get(block_name, {})
        for instr in reversed(block):
            dest = instr.get("dest", None)
            args = instr.get("args", [])
            op = instr.get("op", None)

            if op == "store":
                ptr = args[0]
                val = args[1]
                memory_locations = block_points_to.get(ptr, set())
                # We check every memory location, if any of them are used, we can't remove the store
                remove = True
                for loc in memory_locations:
                    remove = remove and prev_stores[loc]
                # If there is ALL in the memory locations, we can't remove the store
                if remove and "ALL" not in memory_locations:
                    continue
                # Otherwise, mark each memory location as being touched and initialized
                for loc in memory_locations:
                    prev_stores[loc] = True
            else:
                if op == "load":
                    # load is the only other one that can touch memory locations
                    # if there is a load, we have to mark each of the memory locations as dirty
                    # false means we can not remove the instr
                    ptr = args[0]
                    for loc in block_points_to.get(ptr, set()):
                        prev_stores[loc] = False
                elif op == "ptradd" or op == "id":
                    # We need to mark the mem location of the ptr as dirty
                    ptr = args[0]
                    for loc in block_points_to.get(ptr, set()):
                        prev_stores[loc] = False
                # Else, add the instruction

            optimized_instrs.append(instr)
        optimized_blocks[block_name] = list(reversed(optimized_instrs))

    for block_name, block in cfg.block_map.items():
        cfg.block_map[block_name] = optimized_blocks[block_name]

    return control_flow_graph.reassemble(cfg)


def store_to_load_forwarding(prog, out_facts):
    pass


def redundant_load_elimination(prog, out_facts):
    pass


def alias_analysis(prog, alias_analysis_type):
    # alias_analysis_type: dse, rle, stl

    ### Conduct the alias analysis ###

    # Compute CFG
    cfg: ControlFlowGraph = control_flow_graph.construct_cfg(prog["instrs"])

    # State: var -> set of memory locations
    # We use a defaultdict to ensure that we can add new variables on the fly
    # We initialize the first set of function arguments to all memory locations - conservative init since we are doing intra-procedural analysis
    ALL = "ALL"  # Token to indicate all memory locations

    def empty_fact_fn():
        empty_fact = defaultdict(lambda: set())
        # We init the function args to all memory locations
        for arg in prog.get("args", []):
            # Check if the arg is a pointer
            arg_type = arg.get("type", None)
            if isinstance(arg_type, dict) and "ptr" in arg_type:
                empty_fact[arg["name"]].add(ALL)
        return empty_fact

    # Forward data analysis
    analysis_direction = "forward"

    # Meet func: union for each variable's memory locations
    def meet_func(in_facts: Iterator[defaultdict]):
        joined_in_fact = empty_fact_fn()
        for in_fact in in_facts:
            for var, locations in in_fact.items():
                joined_in_fact[var] |= locations
        return joined_in_fact

    # NOTE: We actually have no way of producing the line number since we are working on a block level.
    # As an alterantive, we instead use {block_name}.{line_number} since the block name is unique. The provides a "local" line number.
    def name_function(block_key, line_number):
        return f"{block_key}.{line_number}"

    # Transfer function for each instruction
    def transfer_func(in_facts, block, block_key):
        out_facts = in_facts  # Copy the in facts
        for lineno, line in enumerate(block):
            op = line["op"]

            # alloc
            if op == "alloc":
                # New memory location
                ptr = line["dest"]
                out_facts[ptr].add(name_function(block_key, lineno))

            elif (
                op == "id" or op == "ptradd"
            ):  # We treat ptradd as the same as id (offset = 0, conservative case)
                # x = id y
                # Check if y is a ptr, if it is, add the location of it to x
                x = line["dest"]
                y = line["args"][0]
                if y in in_facts:
                    out_facts[x] |= in_facts[y]  # Union the possible memory locations

            # load p
            elif op == "load":
                # x = load p
                # load p could point to a pointer that's stored in memory, so we take a conservative approach and mark as any
                x = line["dest"]
                out_facts[x].add(ALL)

            # store p y
            elif op == "store":
                # store p y -> noop
                pass

        return out_facts

    def fact_equality_checker(x, y):
        # NOTE: There are some ALL cases that we don't handle. We just assume we keep adding to the memory locations.
        # The all case need to be handled by downstream analysis
        # Check equality in both directions since we are dealing with mapping -> set
        for (
            var,
            locs,
        ) in x.items():
            if var not in y:
                return False
            if locs != y[var]:
                return False
        for var, locs in y.items():
            if var not in x:
                return False
            if locs != x[var]:
                return False
        return True

    # We only care about the out_facts since it tells us the global memory locations
    _, alias_facts = dataflow.solve_dataflow(
        cfg=cfg,
        empty_fact_fn=empty_fact_fn,
        transfer_fn=transfer_func,
        meet_fn=meet_func,
        fact_equality_checker=fact_equality_checker,
        mode=analysis_direction,
        include_block_name=True,
    )

    # TODO Actually call the individual memory optimizations
    if alias_analysis_type == "dse":
        return dead_store_elimination(prog, alias_facts)
    elif alias_analysis_type == "rle":
        return redundant_load_elimination(prog, alias_facts)
    elif alias_analysis_type == "stl":
        return store_to_load_forwarding(prog, alias_facts)
    return alias_facts


def print_formatted_alias_analysis(alias_facts):
    for block_name, block_facts in alias_facts.items():
        print(f"Block: {block_name}")
        for var, locs in block_facts.items():
            print(f"\t{var}: {locs}")


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
    prog = utils.load_bril()
    for f in prog["functions"]:
        if args.dse:
            f["instrs"] = alias_analysis(f, "dse")
        if args.rle:
            f["instrs"] = alias_analysis(f, "rle")
        if args.stl:
            f["instrs"] = alias_analysis(f, "stl")
        if args.debug:
            print_formatted_alias_analysis(alias_analysis(f, None))

    if not args.turnt and not args.debug:
        utils.emit_bril(prog)
