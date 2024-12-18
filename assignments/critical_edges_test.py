import argparse
from collections import defaultdict
from typing import Any, Iterable, Optional

import ipdb

from lib import dataflow, utils
from lib.control_flow_graph import construct_cfg, remove_critical_edges, visualize_cfg
from lib.types import ControlFlowGraph
from lib.utils import emit_bril, load_bril
from lib.visualization import visualize_graph

"""
Simple script which runs the critcal edge removal code
"""


def test_remove_critical_edges(prog: dict[str, Any], func_name: str):
    original_cfg = construct_cfg(prog)
    modified_cfg = remove_critical_edges(original_cfg)
    ipdb.set_trace()

    # Visualize both graphs
    visualize_cfg(original_cfg, filename=f"graphs/original_cfg_{func_name}.png")
    visualize_cfg(modified_cfg, filename=f"graphs/modified_cfg_{func_name}.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="bril prog json to use", default=None)
    args = parser.parse_args()
    file = args.file
    if file:
        prog = utils.load_bril(file)
    else:
        prog = utils.load_bril()

    for f in prog["functions"]:
        f["instrs"] = test_remove_critical_edges(f["instrs"], f["name"])
    if not file:
        utils.emit_bril(prog)


if __name__ == "__main__":
    main()
