from lib import control_flow_graph
from lib.utils import emit_bril, load_bril


def main():
    prog = load_bril()
    for f in prog["functions"]:
        f["instrs"] = control_flow_graph.reassemble(
            control_flow_graph.construct_cfg(f["instrs"])
        )
    emit_bril(prog)


if __name__ == "__main__":
    main()
