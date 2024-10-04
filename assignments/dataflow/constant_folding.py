import argparse
import pdb  # noqa
import sys

# Get lib
sys.path.append("../../assignments/")
from lib import utils, cfg  # noqa


def constant_folding(instrs):
    block_map, preds, succs = cfg.construct_cfg(instrs)
    return instrs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Reads from a program from `prog.json` and starts pdb at inserted lines.",
    )
    args = parser.parse_args()
    prog = utils.load_bril("prog.json") if args.debug else utils.load_bril()
    pdb.set_trace()
    # do something
    for f in prog["functions"]:
        f["instrs"] = constant_folding(f["instrs"])
    utils.emit_bril(prog)
