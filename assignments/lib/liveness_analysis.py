from .dataflow import solve_dataflow
from .types import ControlFlowGraph


def gen(block):
    """Variables that are written in the block."""
    return {i["dest"] for i in block if "dest" in i}


def union(sets):
    out = set()
    for s in sets:
        out.update(s)
    return out


def use(block):
    """Variables that are read before they are written in the block."""
    defined = set()  # Locally defined.
    used = set()
    for i in block:
        used.update(v for v in i.get("args", []) if v not in defined)
        if "dest" in i:
            defined.add(i["dest"])
    return used


def liveness_analysis(
    cfg: ControlFlowGraph,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    empty_fact_fn = lambda: set()
    fact_equality_checker = lambda s1, s2: s1 == s2

    def transfer_fn(out: set[str], blk):
        use_vars: set[str] = use(blk)
        gen_vars: set[str] = gen(blk)
        return use_vars.union(out - gen_vars)

    def meet_fn(facts):
        out = set()
        for f in facts:
            out = out.union(f)
        return out

    mode = "backward"

    in_facts, out_facts = solve_dataflow(
        cfg=cfg,
        meet_fn=meet_fn,
        transfer_fn=transfer_fn,
        empty_fact_fn=empty_fact_fn,
        mode=mode,
        fact_equality_checker=fact_equality_checker,
        include_block_name=False,
    )
    return in_facts, out_facts
