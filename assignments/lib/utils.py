import itertools
import json
import sys

"""
Collection of common utility functions for CS265 assignments.
"""


def load_bril(file=sys.stdin):
    """
    From standard input, load a JSON-encoded Bril program.
    :args: file: file: input file. Defaults to standard in
    """
    if isinstance(file, str):
        with open(file) as f:
            return json.load(f)
    return json.load(file)


def emit_bril(prog, out=sys.stdout):
    """
    Emit a JSON-encoded Bril program to standard output.
    :args: prog: dict: JSON-encoded Bril program
    :args: out: file: output file
    """
    if isinstance(out, str):
        with open(out, "w") as f:
            json.dump(prog, f, indent=2)
    else:
        json.dump(prog, out, indent=2)


def flatten(ll):
    """Flatten an iterable of iterable to a single list."""
    return list(itertools.chain(*ll))


def fresh(seed, names):
    """Generate a new name that is not in `names` starting with `seed`."""
    i = 1
    while True:
        name = seed + str(i)
        if name not in names:
            return name
        i += 1
