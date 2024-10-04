import sys

# Get lib
sys.path.append("../../assignments/")
from lib import utils  # noqa


def is_pure_instr(instr):
    # Effect instructions don't have a 'dest' key
    return "dest" in instr


def _trivial_deadcode_elimination(instrs):
    used_vars = set()
    for instr in instrs:
        for arg in instr.get("args", []):
            used_vars.add(arg)

    new_instrs = []
    modified = False
    for instr in instrs:
        if instr.get("dest") not in used_vars and is_pure_instr(instr):
            # We removed an instruction so set modified to true
            modified = True
        else:
            # Otherwise, we need to keep the instruction
            new_instrs.append(instr)
    return new_instrs, modified


def trivial_deadcode_elimination(instrs):
    modified = True
    while modified:
        instrs, modified = _trivial_deadcode_elimination(instrs)
    return instrs


if __name__ == "__main__":
    prog = utils.load_bril()
    for f in prog["functions"]:
        f["instrs"] = trivial_deadcode_elimination(f["instrs"])
    utils.emit_bril(prog)
