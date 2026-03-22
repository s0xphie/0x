from __future__ import annotations

from argparse import ArgumentParser
from contextlib import contextmanager
from pathlib import Path
from shutil import get_terminal_size
from time import sleep
import os
import sys
import termios
import tty

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supersingularity.simulation import (
        BranchPolicy,
        generate_successor_subtree_from_stem,
        ImageStateSurface,
        list_descendant_leaf_paths,
        load_archived_state_chain,
        read_state_reference,
        review_archived_state_chain,
        SimulationWorkspace,
    )
else:
    from .simulation import (
        BranchPolicy,
        generate_successor_subtree_from_stem,
        ImageStateSurface,
        list_descendant_leaf_paths,
        load_archived_state_chain,
        read_state_reference,
        review_archived_state_chain,
        SimulationWorkspace,
    )


ASCII_RAMP = " .:-=+*#%@"
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_TREE = PACKAGE_ROOT / "workspace" / "state_tree"
MAX_GROW_LINEAGE_DEPTH = 16
MEMORY_FOOTER_LINES = 3


def render_surface_text(
    surface: ImageStateSurface,
    cell_width: int = 2,
    overlay_lines: list[str] | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
) -> str:
    max_value = max(surface.image.max_value, 1)
    rows: list[str] = []
    for row in surface.image.pixels:
        chunks = []
        for value in row:
            index = min(len(ASCII_RAMP) - 1, (value * (len(ASCII_RAMP) - 1)) // max_value)
            chunks.append(ASCII_RAMP[index] * cell_width)
        rows.append("".join(chunks))

    if overlay_lines:
        for row_index, overlay in enumerate(overlay_lines):
            if row_index >= len(rows):
                break
            base = list(rows[row_index])
            text = list(overlay[: len(base)])
            for col_index, char in enumerate(text):
                base[col_index] = char
            rows[row_index] = "".join(base)

    if target_width is not None:
        rows = [row.ljust(target_width)[:target_width] for row in rows]
    if target_height is not None:
        if len(rows) < target_height:
            row_width = target_width if target_width is not None else max((len(row) for row in rows), default=0)
            rows.extend(" " * row_width for _ in range(target_height - len(rows)))
        else:
            rows = rows[:target_height]
    return "\n".join(rows)


def format_chain_address(path: str | Path) -> tuple[str, str]:
    chain = load_archived_state_chain(path)
    hex_address = " -> ".join(state.state_id for state in chain.states)
    unary_address = "/".join(part for state in chain.states for part in state.branch) or "(root)"
    return hex_address, unary_address


def build_chain_frame(
    path: str | Path,
    title: str | None = None,
    target_size: tuple[int, int] | None = None,
    cell_width: int = 2,
) -> str:
    review = review_archived_state_chain(path)
    state = review.steps[-1]
    surface = ImageStateSurface.from_path(state.image_path)
    overlay_lines = [
        state.state_id,
    ]
    target_width = None
    target_height = None
    if target_size is not None:
        target_width = target_size[0] * cell_width
        target_height = target_size[1]
    body = render_surface_text(
        surface,
        cell_width=cell_width,
        overlay_lines=overlay_lines,
        target_width=target_width,
        target_height=target_height,
    )
    memory_footer = render_memory_footer(path, width=target_width or max((len(line) for line in body.splitlines()), default=0))
    return f"{body}\n{memory_footer}\n"


def iter_chain_paths(path: str | Path) -> list[Path]:
    chain = load_archived_state_chain(path)
    return [state.image_path for state in chain.states]


def iter_leaf_walk_paths(stem_path: str | Path) -> list[list[Path]]:
    leaves = list_descendant_leaf_paths(stem_path)
    return [iter_chain_paths(leaf) for leaf in leaves]


def nearest_branching_anchor(path: str | Path) -> Path:
    chain = load_archived_state_chain(path)
    for state in reversed(chain.states):
        leaves = list_descendant_leaf_paths(state.image_path)
        if len(leaves) > 1:
            return state.image_path
    return chain.states[0].image_path


def related_leaf_walks(path: str | Path) -> list[list[Path]]:
    anchor = nearest_branching_anchor(path)
    walks = iter_leaf_walk_paths(anchor)
    target = Path(path).resolve()

    def walk_score(walk: list[Path]) -> tuple[int, str]:
        resolved = [frame.resolve() for frame in walk]
        contains_target = 0 if target in resolved else 1
        return (contains_target, str(walk[-1]))

    return sorted(walks, key=walk_score)


def default_view_path() -> Path:
    root = DEFAULT_STATE_TREE
    if not root.exists():
        raise FileNotFoundError(str(root))

    candidates = sorted(root.rglob("sandpile_state*.pgm"))
    if not candidates:
        raise FileNotFoundError(f"no archived sandpile states found in {root}")

    def score(path: Path) -> tuple[int, int, str]:
        rel = path.relative_to(root)
        depth = len(rel.parts) - 2
        return (depth, len(str(rel)), str(rel))

    return max(candidates, key=score)


def infer_target_size(paths: list[Path]) -> tuple[int, int]:
    max_width = 1
    max_height = 1
    for path in paths:
        surface = ImageStateSurface.from_path(path)
        max_width = max(max_width, surface.image.width)
        max_height = max(max_height, surface.image.height)
    return max_width, max_height


def immediate_child_paths(path: str | Path) -> list[Path]:
    chain = load_archived_state_chain(path)
    state_dir = chain.stem.directory
    children: list[Path] = []
    for child in sorted(state_dir.iterdir()):
        if not child.is_dir() or not child.name.startswith("sandpile_state"):
            continue
        image_path = child / f"{child.name}.pgm"
        if image_path.exists():
            children.append(image_path)
    return children


def subtree_stats(path: str | Path) -> tuple[int, int, int]:
    chain = load_archived_state_chain(path)
    stem = chain.stem
    all_images = sorted(stem.directory.rglob("sandpile_state*.pgm"))
    leaves = list_descendant_leaf_paths(path)
    max_extra_depth = 0
    for image_path in all_images:
        extra_depth = max(0, len(image_path.relative_to(stem.directory).parts) - 2)
        max_extra_depth = max(max_extra_depth, extra_depth)
    return len(all_images), len(leaves), max_extra_depth


def compact_chain_labels(path: str | Path, limit: int = 5) -> str:
    chain = load_archived_state_chain(path)
    labels = [state.state_id for state in chain.states]
    if len(labels) <= limit:
        return "->".join(labels)
    head = labels[:2]
    tail = labels[-2:]
    return "->".join([*head, "..", *tail])


def render_memory_footer(path: str | Path, width: int) -> str:
    review = review_archived_state_chain(path)
    chain = load_archived_state_chain(path)
    current = chain.stem
    node_count, leaf_count, max_extra_depth = subtree_stats(path)
    child_count = len(immediate_child_paths(path))
    reference = read_state_reference(current.image_path)
    reference_flag = "ref" if reference is not None else "raw"
    repeat_flag = "rep" if review.steps[-1].repeated_signature else "new"
    lines = [
        f"m:{current.state_id} d:{current.lineage_depth} ch:{child_count} lf:{leaf_count} sub:{node_count} mx:{max_extra_depth}",
        f"lin:{compact_chain_labels(path)}",
        f"mem:{reference_flag} {repeat_flag} sig:{current.signature[:14]}",
    ]
    return "\n".join(line.ljust(width)[:width] for line in lines)


def render_live_status(
    path: str | Path,
    cycle: int,
    status: str,
    width: int,
) -> str:
    node_count, leaf_count, max_extra_depth = subtree_stats(path)
    line = f"cy:{cycle} lf:{leaf_count} sub:{node_count} mx:{max_extra_depth} {status}"
    return line.ljust(width)[:width]


@contextmanager
def fullscreen_terminal() -> None:
    try:
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        yield
    finally:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


def redraw_frame(frame: str) -> None:
    sys.stdout.write("\x1b[H")
    sys.stdout.write(frame)
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


def frame_geometry(paths: list[Path], reserved_lines: int = 1) -> tuple[tuple[int, int], int]:
    target_size = infer_target_size(paths)
    terminal = get_terminal_size(fallback=(80, 24))
    cell_width = 2 if target_size[0] * 2 <= terminal.columns else 1
    max_rows = max(1, terminal.lines - reserved_lines)
    fitted_size = (min(target_size[0], terminal.columns // max(1, cell_width)), min(target_size[1], max_rows))
    return fitted_size, cell_width


@contextmanager
def raw_stdin():
    if not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key() -> str:
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return (line[:1] if line else "q").lower()
    with raw_stdin():
        char = sys.stdin.read(1)
    if char == "\x1b":
        return "q"
    if char in {"\r", "\n"}:
        return "n"
    return char.lower()


def prompt_action(frame: str, prompt: str) -> str:
    redraw_frame(f"{frame.rstrip()}\n\n{prompt}")
    return read_key()


def workspace_root_for_path(path: str | Path) -> Path:
    probe = Path(path).resolve()
    for parent in [probe.parent, *probe.parents]:
        if parent.name == "workspace":
            return parent
    raise FileNotFoundError(f"could not infer workspace root from {path}")


def incremental_growth_policy(stem_depth: int, breadth: int = 2) -> BranchPolicy:
    target_depth = max(stem_depth + 1, 1)
    return BranchPolicy(
        root_width=max(1, breadth),
        decay_numerator=1,
        decay_denominator=1,
        stop_numerator=100,
        stop_denominator=100,
        max_depth=target_depth,
        max_total_nodes=max(1, breadth),
    )


def grow_from_view_path(path: str | Path, breadth: int = 2) -> tuple[int, int]:
    workspace = SimulationWorkspace.create(workspace_root_for_path(path))
    chain = load_archived_state_chain(path)
    total_grown = 0
    skipped = 0

    for state in reversed(chain.states):
        if state.lineage_depth >= MAX_GROW_LINEAGE_DEPTH:
            skipped += 1
            continue
        state_path = state.image_path
        seed_surface = ImageStateSurface.from_path(state_path)
        states = generate_successor_subtree_from_stem(
            workspace,
            state_path,
            successor_mode="seed",
            successor_seed=seed_surface,
            branch_policy=incremental_growth_policy(state.lineage_depth, breadth=breadth),
            canonicalize=True,
        )
        total_grown += len(states)

    return total_grown, skipped


def sweep_grow_from_path(path: str | Path, breadth: int = 1) -> tuple[int, int, int]:
    touched = 0
    total_grown = 0
    total_skipped = 0
    seen: set[Path] = set()

    for walk in related_leaf_walks(path):
        for frame_path in walk:
            resolved = frame_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            touched += 1
            grown, skipped = grow_from_view_path(frame_path, breadth=breadth)
            total_grown += grown
            total_skipped += skipped

    return touched, total_grown, total_skipped


def animate_paths(paths: list[Path], delay: float = 0.2, repeat: int = 1, label: str | None = None) -> None:
    if not paths:
        raise ValueError("no paths to animate")
    target_size, cell_width = frame_geometry(paths, reserved_lines=MEMORY_FOOTER_LINES)
    with fullscreen_terminal():
        iteration = 0
        while repeat <= 0 or iteration < repeat:
            for index, path in enumerate(paths, start=1):
                title = label or f"Frame {index}/{len(paths)}"
                redraw_frame(build_chain_frame(path, title=title, target_size=target_size, cell_width=cell_width))
                sleep(delay)
            iteration += 1


def animate_chain(path: str | Path, delay: float = 0.35, repeat: int = 1) -> None:
    animate_paths(iter_chain_paths(path), delay=delay, repeat=repeat, label="Chain")


def animate_leaf_walk(
    stem_path: str | Path,
    delay: float = 0.2,
    dwell: float = 0.6,
    repeat: int = 1,
) -> None:
    leaf_walks = iter_leaf_walk_paths(stem_path)
    if not leaf_walks:
        raise ValueError("no descendant leaves under the chosen stem")
    target_size, cell_width = frame_geometry([path for walk in leaf_walks for path in walk], reserved_lines=MEMORY_FOOTER_LINES)
    with fullscreen_terminal():
        iteration = 0
        while repeat <= 0 or iteration < repeat:
            for leaf_index, walk in enumerate(leaf_walks, start=1):
                for frame_index, path in enumerate(walk, start=1):
                    redraw_frame(
                        build_chain_frame(
                            path,
                            title=f"Leaf {leaf_index}/{len(leaf_walks)}  Frame {frame_index}/{len(walk)}",
                            target_size=target_size,
                            cell_width=cell_width,
                        )
                    )
                    sleep(delay)
                sleep(dwell)
            iteration += 1


def animate_auto_walk(
    path: str | Path,
    delay: float = 0.2,
    dwell: float = 0.6,
    repeat: int = 0,
    interactive: bool = True,
) -> None:
    current_path = Path(path)
    with fullscreen_terminal():
        iteration = 0
        while repeat <= 0 or iteration < repeat:
            leaf_walks = related_leaf_walks(current_path)
            if not leaf_walks:
                animate_chain(current_path, delay=delay, repeat=1)
                break
            target_size, cell_width = frame_geometry(
                [path for walk in leaf_walks for path in walk],
                reserved_lines=MEMORY_FOOTER_LINES + 1,
            )
            last_frame = ""
            last_leaf_path = current_path
            for leaf_index, walk in enumerate(leaf_walks, start=1):
                for frame_index, frame_path in enumerate(walk, start=1):
                    last_leaf_path = frame_path
                    last_frame = build_chain_frame(
                        frame_path,
                        title=f"Auto  Leaf {leaf_index}/{len(leaf_walks)}  Frame {frame_index}/{len(walk)}",
                        target_size=target_size,
                        cell_width=cell_width,
                    )
                    redraw_frame(last_frame)
                    sleep(delay)
                sleep(dwell)
            current_path = last_leaf_path
            if interactive and sys.stdin.isatty():
                action = prompt_action(
                    last_frame,
                    "[Enter] continue  [g] grow from current leaf  [q] quit: ",
                )
                if action in {"q", "quit", "x"}:
                    break
                if action == "g":
                    grown, skipped = grow_from_view_path(current_path)
                    notice = (
                        f"{last_frame.rstrip()}\n\n"
                        f"+{grown} states"
                        f"{'  skipped ' + str(skipped) + ' capped branch(es)' if skipped else ''}\n"
                    )
                    redraw_frame(notice)
                    sleep(max(dwell, 0.4))
            iteration += 1


def animate_live_growth(
    path: str | Path,
    delay: float = 0.15,
    dwell: float = 0.4,
    repeat: int = 0,
    growth_interval: int = 1,
    growth_breadth: int = 2,
    sweep: bool = False,
) -> None:
    current_path = Path(path)
    with fullscreen_terminal():
        cycle = 0
        last_status = "boot"
        while repeat <= 0 or cycle < repeat:
            leaf_walks = related_leaf_walks(current_path)
            if not leaf_walks:
                leaf_walks = [iter_chain_paths(current_path)]
            target_size, cell_width = frame_geometry(
                [frame for walk in leaf_walks for frame in walk],
                reserved_lines=MEMORY_FOOTER_LINES + 2,
            )

            for leaf_index, walk in enumerate(leaf_walks, start=1):
                for frame_index, frame_path in enumerate(walk, start=1):
                    current_path = frame_path
                    frame = build_chain_frame(
                        frame_path,
                        target_size=target_size,
                        cell_width=cell_width,
                    )
                    width = target_size[0] * cell_width
                    status = render_live_status(
                        frame_path,
                        cycle=cycle,
                        status=f"walk {leaf_index}/{len(leaf_walks)} frame {frame_index}/{len(walk)} {last_status}",
                        width=width,
                    )
                    redraw_frame(f"{frame.rstrip()}\n{status}\n")
                    sleep(delay)
                sleep(dwell)

            cycle += 1
            if growth_interval > 0 and cycle % growth_interval == 0:
                if sweep:
                    touched, grown, skipped = sweep_grow_from_path(current_path, breadth=growth_breadth)
                    last_status = f"sweep t:{touched} +{grown} skip:{skipped}"
                else:
                    grown, skipped = grow_from_view_path(current_path, breadth=growth_breadth)
                    last_status = f"grow +{grown} skip:{skipped}"
            else:
                last_status = "refresh"


def navigate_space(
    path: str | Path,
    delay: float = 0.15,
    dwell: float = 0.4,
) -> None:
    current_path = Path(path)
    with fullscreen_terminal():
        leaf_walks = related_leaf_walks(current_path)
        if not leaf_walks:
            leaf_walks = [iter_chain_paths(current_path)]
        leaf_index = 0
        frame_index = 0

        while True:
            if not leaf_walks:
                leaf_walks = [iter_chain_paths(current_path)]
                leaf_index = 0
                frame_index = 0
            target_size, cell_width = frame_geometry(
                [path for walk in leaf_walks for path in walk],
                reserved_lines=MEMORY_FOOTER_LINES + 1,
            )

            leaf_index = max(0, min(leaf_index, len(leaf_walks) - 1))
            walk = leaf_walks[leaf_index]
            frame_index = max(0, min(frame_index, len(walk) - 1))
            frame_path = walk[frame_index]
            current_path = frame_path
            frame = build_chain_frame(frame_path, target_size=target_size, cell_width=cell_width)

            action = prompt_action(
                frame,
                (
                    f"[n/p h/l a g r q]  leaf {leaf_index + 1}/{len(leaf_walks)}  frame {frame_index + 1}/{len(walk)} > "
                ),
            )

            if action in {"q", "quit", "x"}:
                break
            if action in {"", "n", "j"}:
                if frame_index + 1 < len(walk):
                    frame_index += 1
                elif leaf_index + 1 < len(leaf_walks):
                    leaf_index += 1
                    frame_index = 0
                else:
                    leaf_index = 0
                    frame_index = 0
                continue
            if action in {"p", "k", "b"}:
                if frame_index > 0:
                    frame_index -= 1
                elif leaf_index > 0:
                    leaf_index -= 1
                    frame_index = len(leaf_walks[leaf_index]) - 1
                else:
                    leaf_index = len(leaf_walks) - 1
                    frame_index = len(leaf_walks[leaf_index]) - 1
                continue
            if action in {"l", "]"}:
                leaf_index = (leaf_index + 1) % len(leaf_walks)
                frame_index = min(frame_index, len(leaf_walks[leaf_index]) - 1)
                continue
            if action in {"h", "["}:
                leaf_index = (leaf_index - 1) % len(leaf_walks)
                frame_index = min(frame_index, len(leaf_walks[leaf_index]) - 1)
                continue
            if action == "a":
                for autoplay_leaf_index, autoplay_walk in enumerate(leaf_walks, start=1):
                    for autoplay_frame_index, autoplay_path in enumerate(autoplay_walk, start=1):
                        redraw_frame(build_chain_frame(autoplay_path))
                        sleep(delay)
                    sleep(dwell)
                continue
            if action == "g":
                grown, skipped = grow_from_view_path(current_path)
                redraw_frame(
                    f"{frame.rstrip()}\n\n+{grown} states"
                    f"{'  skipped ' + str(skipped) + ' capped branch(es)' if skipped else ''}\n"
                )
                sleep(max(dwell, 0.4))
                leaf_walks = related_leaf_walks(current_path)
                leaf_index = 0
                frame_index = 0
                continue
            if action == "r":
                leaf_walks = related_leaf_walks(current_path)
                leaf_index = 0
                frame_index = 0
                continue


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Animate archived sandpile chains in the terminal.")
    parser.add_argument("path", nargs="?", help="Path to a stem or leaf .pgm file")
    parser.add_argument("--mode", choices=["navigate", "auto", "chain", "leaves", "live"], default="navigate")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--dwell", type=float, default=0.6)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--growth-interval", type=int, default=1)
    parser.add_argument("--growth-breadth", type=int, default=2)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--no-interactive", action="store_true")
    args = parser.parse_args(argv)
    path = args.path or str(default_view_path())
    repeat = 0 if args.loop else args.repeat
    interactive = args.interactive or (args.mode == "auto" and not args.no_interactive)

    if args.mode == "chain":
        animate_chain(path, delay=args.delay, repeat=repeat)
    elif args.mode == "leaves":
        animate_leaf_walk(path, delay=args.delay, dwell=args.dwell, repeat=repeat)
    elif args.mode == "navigate":
        navigate_space(path, delay=args.delay, dwell=args.dwell)
    elif args.mode == "live":
        animate_live_growth(
            path,
            delay=args.delay,
            dwell=args.dwell,
            repeat=repeat,
            growth_interval=max(1, args.growth_interval),
            growth_breadth=max(1, args.growth_breadth),
            sweep=args.sweep,
        )
    else:
        animate_auto_walk(
            path,
            delay=args.delay,
            dwell=args.dwell,
            repeat=repeat,
            interactive=interactive,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
