from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .simulation import ImageStateSurface, SimulationWorkspace, stabilize_surface, succ


DEFAULT_STARTUP_SEED_PATH = Path(__file__).resolve().parent / "workspace" / "states" / "sandpile_state.pgm"
DEFAULT_STARTUP_PREFIX = "startup_state"
DEFAULT_STARTUP_CHECKPOINT_INTERVAL = 128
GLOBAL_RECURSION_LIMIT = 2**32


@dataclass(frozen=True)
class StartupInitializationVector:
    seed_path: Path = DEFAULT_STARTUP_SEED_PATH
    prefix: str = DEFAULT_STARTUP_PREFIX
    global_recursive_limit: int = GLOBAL_RECURSION_LIMIT
    materialized_recursive_steps: int = 1024
    checkpoint_interval_steps: int = DEFAULT_STARTUP_CHECKPOINT_INTERVAL

    @property
    def persisted_frame_count(self) -> int:
        return max(1, self.materialized_recursive_steps // max(1, self.checkpoint_interval_steps)) + 1

    @property
    def recursion_steps_per_frame(self) -> int:
        return max(1, self.checkpoint_interval_steps)


@dataclass
class StartupSequence:
    surfaces: list[ImageStateSurface]
    persisted_paths: list[Path]

    @property
    def final_path(self) -> Path:
        return self.persisted_paths[-1]


DEFAULT_STARTUP_VECTOR = StartupInitializationVector()


def build_startup_sequence(
    vector: StartupInitializationVector = DEFAULT_STARTUP_VECTOR,
    workspace_root: str | Path | None = None,
) -> StartupSequence:
    if not vector.seed_path.exists():
        raise FileNotFoundError(str(vector.seed_path))

    workspace_path = Path(workspace_root) if workspace_root is not None else Path(__file__).resolve().parent / "workspace"
    workspace = SimulationWorkspace.create(workspace_path)
    root_surface = ImageStateSurface.from_path(vector.seed_path)
    for y in range(root_surface.image.height):
        for x in range(root_surface.image.width):
            root_surface.write_value(x, y, 0)
    root_surface.image.max_value = 1
    root_state = workspace.archive_surface(
        root_surface,
        prefix=vector.prefix,
        topples=0,
        state_id_override="0x10",
    )

    current_surface = root_surface
    current_state = root_state
    surfaces = [ImageStateSurface.from_path(root_state.image_path)]
    archived_paths = [root_state.image_path]
    steps_per_checkpoint = max(1, vector.recursion_steps_per_frame)

    def next_startup_state_id(counter: int) -> str:
        if counter >= 0x10:
            counter += 1
        return f"0x{counter:02x}"

    checkpoint_counter = 0
    checkpoint_topples = 0
    for step_index in range(1, vector.materialized_recursive_steps + 1):
        current_surface = succ(current_surface, mode="center")
        current_surface, topples = stabilize_surface(current_surface)
        checkpoint_topples += topples
        surfaces.append(current_surface)
        if step_index % steps_per_checkpoint != 0:
            continue
        checkpoint_counter += 1
        current_state = workspace.archive_surface(
            current_surface,
            prefix=vector.prefix,
            topples=checkpoint_topples,
            state_id_override=next_startup_state_id(checkpoint_counter),
            parent=current_state,
        )
        archived_paths.append(current_state.image_path)
        checkpoint_topples = 0

    if len(archived_paths) == 1:
        archived_paths.append(root_state.image_path)

    return StartupSequence(
        surfaces=surfaces,
        persisted_paths=archived_paths,
    )
