from collections import OrderedDict

from .types import ControlFlowGraph


def generate_simple_lcm_cfg() -> ControlFlowGraph:
    # Generate the blocks
    blocks = [
        ("entry", []),
        ("_b1", [{"op": "const", "dest": "b", "value": 1, "type": "int"}]),
        ("_b2", [{"op": "const", "dest": "c", "value": 4, "type": "int"}]),
        ("_b3", [{"op": "const", "dest": "cond", "value": True, "type": "bool"}]),
        ("branch", [{"op": "br", "labels": ["if", "else"]}]),
        ("if", [{"op": "const", "dest": "g", "value": 0, "type": "int"}]),
        ("_b4", [{"op": "const", "dest": "z", "value": 0, "type": "int"}]),
        ("_b6", []),
        ("else", [{"op": "add", "dest": "x", "args": ["b", "c"], "type": "int"}]),
        ("_b5", [{"op": "const", "dest": "w", "value": 0, "type": "int"}]),
        ("done", [{"op": "add", "dest": "y", "args": ["b", "c"], "type": "int"}]),
        ("done2", [{"op": "ret", "value": 0}]),
    ]
    block_map = OrderedDict()
    for k, v in blocks:
        block_map[k] = v

    succs = [
        ("entry", ["_b1"]),
        ("_b1", ["_b2"]),
        ("_b2", ["_b3"]),
        ("_b3", ["branch"]),
        ("branch", ["if", "else"]),
        ("if", ["_b4"]),
        ("_b4", ["_b6"]),
        ("_b6", ["done"]),
        ("else", ["_b5"]),
        ("_b5", ["done"]),
        ("done", ["done2"]),
        ("done2", []),
    ]

    succs_map = {}
    for k, v in succs:
        succs_map[k] = v

    preds = [
        ("entry", []),
        ("_b1", ["entry"]),
        ("_b2", ["_b1"]),
        ("_b3", ["_b2"]),
        ("branch", ["_b3"]),
        ("if", ["branch"]),
        ("_b4", ["if"]),
        ("_b6", ["_b4"]),
        ("else", ["branch"]),
        ("_b5", ["else"]),
        ("done", ["_b5", "_b6"]),
        ("done2", ["done"]),
    ]

    preds_map = {}
    for k, v in preds:
        preds_map[k] = v

    cfg = ControlFlowGraph(
        block_map=block_map, successors=succs_map, predecessors=preds_map
    )
    return cfg
