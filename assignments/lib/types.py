from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ControlFlowGraph:
    block_map: OrderedDict[str, List[Dict]]
    predecessors: Dict[str, List[str]]
    successors: Dict[str, List[str]]


# Instructions that terminate a basic block.
TERMINATOR_OPS = "br", "jmp", "ret"


# Constant operations that are resolvable
RESOLVABLE_OPS = {
    "add": lambda x, y: x + y,
    "mul": lambda x, y: x * y,
    "sub": lambda x, y: x - y,
    "div": lambda x, y: x / y,
    "eq": lambda x, y: x == y,
    "lt": lambda x, y: x < y,
    "gt": lambda x, y: x > y,
    "le": lambda x, y: x <= y,
    "ge": lambda x, y: x >= y,
    "not": lambda x: not x,
    "and": lambda x, y: x and y,
    "or": lambda x, y: x or y,
}


# Define side-effect operations that should not be moved
SIDE_EFFECT_OPS = {"print", "call", "store", "ret"}


# Possible expressions we consider
EXPRESSIONS = {
    "add",
    "mul",
    "sub",
    "div",
    "eq",
    "lt",
    "gt",
    "le",
    "ge",
    "not",
    "and",
    "or",
}


# Number of args per expression
NUM_ARGS = {
    "add": 2,
    "mul": 2,
    "sub": 2,
    "div": 2,
    "eq": 2,
    "lt": 2,
    "gt": 2,
    "le": 2,
    "ge": 2,
    "not": 1,
    "and": 2,
    "or": 2,
}
