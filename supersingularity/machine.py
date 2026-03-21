from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supersingularity.engine import apply_successor_primitive, build_machine_context
    from supersingularity.primitive_input import parse_primitive_input
    from supersingularity.simulation import (
        SimulationWorkspace,
        load_archived_state_chain,
    )
    from supersingularity.viewer import startup_view_path
else:
    from .engine import apply_successor_primitive, build_machine_context
    from .primitive_input import parse_primitive_input
    from .simulation import (
        SimulationWorkspace,
        load_archived_state_chain,
    )
    from .viewer import startup_view_path


def summarize_machine_state(path: Path, workspace: SimulationWorkspace) -> str:
    context = build_machine_context(path, workspace)
    machine = context["machine_state_record"]
    pointer = context["production_pointer"]
    assessment = context["expert_assessment"]
    recrystallization = context["recrystallization"]
    chain = load_archived_state_chain(path)
    top_action = assessment.recommendations[0].action if assessment.recommendations else "-"
    top_priority = assessment.recommendations[0].priority if assessment.recommendations else 0.0
    return (
        f"s:{chain.stem.state_id} d:{chain.stem.lineage_depth} t:{chain.stem.topples} "
        f"m:{machine.machine_id[:10]} tc:{machine.target_confidence:.2f} "
        f"pp:{pointer.pointer_id[:10]} nx:{len(pointer.next_edge_types)} "
        f"ex:{top_action} pr:{top_priority:.2f} "
        f"rc:{recrystallization.selected_state_id or '-'} "
        f"rs:{recrystallization.selected_score:.2f}"
    )
def run_machine(
    path: str | None = None,
    *,
    steps: int = 0,
    interactive: bool = False,
    primitive_text: str = "successor",
) -> int:
    workspace = SimulationWorkspace.create(Path(__file__).resolve().parent / "workspace")
    current_path = Path(path).resolve() if path else startup_view_path()
    print(summarize_machine_state(current_path, workspace))
    for _ in range(max(0, steps)):
        primitive = parse_primitive_input(primitive_text)
        if primitive.canonical_name == "successor":
            current_path = apply_successor_primitive(current_path, workspace)
            print(summarize_machine_state(current_path, workspace))
    if not interactive:
        return 0
    while True:
        try:
            user_input = input("primitive> ")
        except EOFError:
            print()
            return 0
        command = user_input.strip().lower()
        if command in {"q", "quit", "exit"}:
            return 0
        try:
            primitive = parse_primitive_input(user_input)
        except ValueError as exc:
            print(f"input-error:{exc}")
            continue
        if primitive.canonical_name == "successor":
            current_path = apply_successor_primitive(current_path, workspace)
            print(summarize_machine_state(current_path, workspace))


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Run the supersingularity machine headlessly.")
    parser.add_argument("path", nargs="?", help="Optional starting archived .pgm path")
    parser.add_argument("--steps", type=int, default=0, help="Apply this many primitive successor steps headlessly.")
    parser.add_argument("--interactive", action="store_true", help="Keep a primitive prompt open after initialization.")
    parser.add_argument(
        "--primitive",
        default="successor",
        help="Primitive input to apply for headless stepping. Default: successor",
    )
    args = parser.parse_args(argv)
    return run_machine(
        args.path,
        steps=args.steps,
        interactive=args.interactive,
        primitive_text=args.primitive,
    )


if __name__ == "__main__":
    raise SystemExit(main())
