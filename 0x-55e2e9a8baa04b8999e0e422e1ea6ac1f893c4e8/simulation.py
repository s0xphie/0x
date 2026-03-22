from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol
import copy
import hashlib
import shutil

from .graph import SandpileConfiguration
from .netpbm import NetpbmImage, read_netpbm, write_netpbm


@dataclass
class ImageStateSurface:
    image: NetpbmImage

    @classmethod
    def from_path(cls, path: str | Path) -> "ImageStateSurface":
        return cls(image=read_netpbm(resolve_state_image_path(path)))

    def to_path(self, path: str | Path) -> None:
        write_netpbm(self.image, path)

    def read_value(self, x: int, y: int) -> int:
        return self.image.pixels[y][x]

    def write_value(self, x: int, y: int, value: int) -> None:
        self.image.pixels[y][x] = value

    def overlay_configuration(self, configuration: SandpileConfiguration, vertex_layout: dict[str, tuple[int, int]]) -> None:
        for vertex, chips in configuration.chips.items():
            if vertex not in vertex_layout:
                continue
            x, y = vertex_layout[vertex]
            self.write_value(x, y, chips)

    def flatten_pixels(self) -> list[int]:
        return [value for row in self.image.pixels for value in row]

    def increment_lowest_grain(self) -> tuple[int, int]:
        lowest_value = min(self.flatten_pixels())
        for y, row in enumerate(self.image.pixels):
            for x, value in enumerate(row):
                if value == lowest_value:
                    self.write_value(x, y, value + 1)
                    self.image.max_value = max(self.image.max_value, value + 1)
                    return x, y
        raise ValueError("cannot increment an empty image surface")

    def increment_center_grain(self) -> tuple[int, int]:
        center_x = self.image.width // 2
        center_y = self.image.height // 2
        next_value = self.read_value(center_x, center_y) + 1
        self.write_value(center_x, center_y, next_value)
        self.image.max_value = max(self.image.max_value, next_value)
        return center_x, center_y

    def apply_centered_seed(self, seed_surface: "ImageStateSurface") -> tuple[int, int]:
        if seed_surface.image.width > self.image.width or seed_surface.image.height > self.image.height:
            raise ValueError("seed surface does not fit inside the target surface")

        start_x = (self.image.width - seed_surface.image.width) // 2
        start_y = (self.image.height - seed_surface.image.height) // 2
        for y in range(seed_surface.image.height):
            for x in range(seed_surface.image.width):
                seeded_value = self.read_value(start_x + x, start_y + y) + seed_surface.read_value(x, y)
                self.write_value(start_x + x, start_y + y, seeded_value)
                self.image.max_value = max(self.image.max_value, seeded_value)
        return start_x, start_y


class RewriteRule(Protocol):
    name: str

    def apply(self, surface: ImageStateSurface) -> ImageStateSurface:
        ...


@dataclass(frozen=True)
class CenterGrainRewriteRule:
    name: str = "center"

    def apply(self, surface: ImageStateSurface) -> ImageStateSurface:
        next_surface = clone_surface(surface)
        next_surface.increment_center_grain()
        return next_surface


@dataclass(frozen=True)
class LowestGrainRewriteRule:
    name: str = "lowest"

    def apply(self, surface: ImageStateSurface) -> ImageStateSurface:
        next_surface = clone_surface(surface)
        next_surface.increment_lowest_grain()
        return next_surface


@dataclass(frozen=True)
class CenteredSeedRewriteRule:
    seed_surface: ImageStateSurface
    name: str = "seed"

    def apply(self, surface: ImageStateSurface) -> ImageStateSurface:
        next_surface = clone_surface(surface)
        next_surface.apply_centered_seed(self.seed_surface)
        return next_surface


@dataclass(frozen=True)
class ArchivedState:
    state_id: str
    signature: str
    branch: tuple[str, ...]
    directory: Path
    image_path: Path
    topples: int = 0
    parent_state_id: str | None = None
    lineage_depth: int = 0


@dataclass(frozen=True)
class BranchPolicy:
    root_width: int = 127
    decay_numerator: int = 64
    decay_denominator: int = 100
    stop_numerator: int = 36
    stop_denominator: int = 100
    max_depth: int = 16
    max_total_nodes: int = 2048

    def level_widths(self) -> list[int]:
        widths: list[int] = []
        current = self.root_width
        minimum = max(1, (self.root_width * self.stop_numerator + self.stop_denominator - 1) // self.stop_denominator)
        while current >= minimum and len(widths) < self.max_depth:
            widths.append(current)
            current = max(1, (current * self.decay_numerator + self.decay_denominator - 1) // self.decay_denominator)
        return widths


@dataclass(frozen=True)
class TreeLevelSummary:
    depth: int
    requested_width: int
    produced_nodes: int
    toppled_nodes: int
    unique_signatures: int


@dataclass(frozen=True)
class TreeGenerationSummary:
    total_nodes: int
    max_depth: int
    level_summaries: list[TreeLevelSummary]
    max_depth_paths: list[str]


@dataclass(frozen=True)
class ArchivedStateChain:
    states: list[ArchivedState]

    @property
    def image_paths(self) -> list[Path]:
        return [state.image_path for state in self.states]

    @property
    def signatures(self) -> list[str]:
        return [state.signature for state in self.states]

    @property
    def stem(self) -> ArchivedState:
        if not self.states:
            raise ValueError("archived state chain is empty")
        return self.states[-1]


@dataclass(frozen=True)
class ChainReviewStep:
    lineage_depth: int
    state_id: str
    image_path: Path
    signature: str
    total_grains: int
    changed_cells_from_previous: int
    repeated_signature: bool


@dataclass(frozen=True)
class ChainReview:
    length: int
    repeated_signatures: list[str]
    steps: list[ChainReviewStep]


@dataclass(frozen=True)
class StateReference:
    image_path: Path
    canonical_path: Path
    signature: str


@dataclass(frozen=True)
class DedupeSummary:
    canonical_count: int
    duplicate_count: int
    references: list[StateReference]


@dataclass(frozen=True)
class CanonicalStateRecord:
    canonical_path: Path
    signature: str
    occurrence_count: int
    duplicate_count: int
    min_lineage_depth: int
    max_lineage_depth: int
    state_ids: list[str]
    sample_paths: list[str]
    parent_canonical_paths: list[str]
    child_canonical_paths: list[str]


@dataclass(frozen=True)
class CanonicalStateIndex:
    records: list[CanonicalStateRecord]


@dataclass
class SimulationWorkspace:
    root: Path

    @classmethod
    def create(cls, root: str | Path) -> "SimulationWorkspace":
        workspace_root = Path(root)
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "canonical_states").mkdir(exist_ok=True)
        (workspace_root / "states").mkdir(exist_ok=True)
        (workspace_root / "state_tree").mkdir(exist_ok=True)
        (workspace_root / "runs").mkdir(exist_ok=True)
        return cls(root=workspace_root)

    def state_path(self, name: str, magic: str = "P2") -> Path:
        suffix = ".pbm" if magic == "P1" else ".pgm"
        return self.root / "states" / f"{name}{suffix}"

    def initialize_surface(
        self,
        name: str,
        width: int,
        height: int,
        fill: int = 0,
        magic: str = "P2",
        max_value: int = 255,
    ) -> Path:
        image = NetpbmImage(
            magic=magic,
            width=width,
            height=height,
            pixels=[[fill for _ in range(width)] for _ in range(height)],
            max_value=max_value,
        )
        path = self.state_path(name, magic)
        write_netpbm(image, path)
        return path

    def snapshot(self, name: str, surface: ImageStateSurface) -> Path:
        path = self.state_path(name, surface.image.magic)
        surface.to_path(path)
        return path

    def archive_surface(
        self,
        surface: ImageStateSurface,
        branch: Iterable[int | str] = (),
        prefix: str = "sandpile_state",
        topples: int = 0,
        state_id_override: str | None = None,
        parent: ArchivedState | None = None,
        canonicalize: bool = False,
    ) -> ArchivedState:
        normalized_branch = tuple(str(part) for part in branch)
        state_id = state_id_override or surface_state_id(surface)
        signature = surface_signature(surface)
        state_label = f"{prefix}{state_id}"
        if parent is None:
            directory = self.root / "state_tree" / state_label
            for part in normalized_branch:
                directory = directory / part
        else:
            directory = parent.directory / state_label
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / f"{state_label}.pgm"
        if canonicalize:
            canonical_path = self.canonical_state_path(signature)
            if canonical_path.exists():
                write_state_reference(image_path, canonical_path, signature)
            else:
                surface.to_path(image_path)
                shutil.copyfile(image_path, canonical_path)
        else:
            surface.to_path(image_path)
        return ArchivedState(
            state_id=state_id,
            signature=signature,
            branch=normalized_branch,
            directory=directory,
            image_path=image_path,
            topples=topples,
            parent_state_id=parent.state_id if parent is not None else None,
            lineage_depth=parent.lineage_depth + 1 if parent is not None else 0,
        )

    def spawn_child_state(
        self,
        parent: ArchivedState,
        surface: ImageStateSurface,
        topples: int = 1,
        prefix: str = "sandpile_state",
        max_depth: int = 16,
        state_id_override: str | None = None,
        canonicalize: bool = False,
    ) -> ArchivedState:
        if len(parent.branch) >= max_depth:
            raise ValueError(f"maximum archive depth {max_depth} reached")
        unary_label = "1" * (len(parent.branch) + 1)
        return self.archive_surface(
            surface,
            branch=(*parent.branch, unary_label),
            prefix=prefix,
            topples=topples,
            state_id_override=state_id_override,
            parent=parent,
            canonicalize=canonicalize,
        )

    def canonical_state_path(self, signature: str) -> Path:
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
        return self.root / "canonical_states" / f"{digest}.pgm"


def surface_signature(surface: ImageStateSurface) -> str:
    values = surface.flatten_pixels()
    width = max(1, len(format(max(surface.image.max_value, 1), "x")))
    encoded = "".join(f"{value:0{width}x}" for value in values)
    return f"0x{encoded}"


def surface_state_id(surface: ImageStateSurface) -> str:
    total_grains = sum(surface.flatten_pixels())
    return f"0x{total_grains:02x}"


def clone_surface(surface: ImageStateSurface) -> ImageStateSurface:
    return ImageStateSurface(
        image=NetpbmImage(
            magic=surface.image.magic,
            width=surface.image.width,
            height=surface.image.height,
            pixels=copy.deepcopy(surface.image.pixels),
            max_value=surface.image.max_value,
        )
    )


def placeholder_image() -> NetpbmImage:
    return NetpbmImage(
        magic="P2",
        width=1,
        height=1,
        pixels=[[0]],
        max_value=1,
    )


def reference_path_for_image(path: str | Path) -> Path:
    image_path = Path(path)
    return image_path.with_suffix(image_path.suffix + ".ref")


def write_state_reference(image_path: str | Path, canonical_path: str | Path, signature: str) -> Path:
    ref_path = reference_path_for_image(image_path)
    canonical = Path(canonical_path).resolve()
    ref_path.write_text(
        f"signature={signature}\ncanonical_path={canonical}\n",
        encoding="utf-8",
    )
    write_netpbm(placeholder_image(), image_path)
    return ref_path


def read_state_reference(path: str | Path) -> StateReference | None:
    image_path = Path(path)
    ref_path = reference_path_for_image(image_path)
    if not ref_path.exists():
        return None

    data: dict[str, str] = {}
    for line in ref_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()

    canonical_path = Path(data["canonical_path"])
    signature = data.get("signature", "")
    return StateReference(
        image_path=image_path,
        canonical_path=canonical_path,
        signature=signature,
    )


def resolve_state_image_path(path: str | Path) -> Path:
    image_path = Path(path)
    reference = read_state_reference(image_path)
    if reference is not None:
        return reference.canonical_path
    return image_path


def initialize_identity_surface(
    workspace: SimulationWorkspace,
    width: int = 35,
    height: int = 35,
    name: str = "sandpile_state",
) -> ImageStateSurface:
    path = workspace.initialize_surface(
        name=name,
        width=width,
        height=height,
        fill=0,
        magic="P2",
        max_value=1,
    )
    return ImageStateSurface.from_path(path)


def resolve_rewrite_rule(
    rewrite_rule: RewriteRule | None = None,
    successor_mode: str = "center",
    successor_seed: ImageStateSurface | None = None,
) -> RewriteRule:
    if rewrite_rule is not None:
        return rewrite_rule
    if successor_mode == "center":
        return CenterGrainRewriteRule()
    if successor_mode == "lowest":
        return LowestGrainRewriteRule()
    if successor_mode == "seed":
        if successor_seed is None:
            raise ValueError("seed successor mode requires a seed surface")
        return CenteredSeedRewriteRule(seed_surface=successor_seed)
    raise ValueError(f"unsupported successor mode: {successor_mode}")


def succ(
    surface: ImageStateSurface,
    mode: str = "center",
    seed_surface: ImageStateSurface | None = None,
    rewrite_rule: RewriteRule | None = None,
) -> ImageStateSurface:
    return resolve_rewrite_rule(
        rewrite_rule=rewrite_rule,
        successor_mode=mode,
        successor_seed=seed_surface,
    ).apply(surface)


def stabilize_surface(surface: ImageStateSurface, threshold: int = 4) -> tuple[ImageStateSurface, int]:
    stabilized = clone_surface(surface)
    total_topples = 0
    width = stabilized.image.width
    height = stabilized.image.height

    while True:
        delta = [[0 for _ in range(width)] for _ in range(height)]
        toppled = False

        for y in range(height):
            for x in range(width):
                value = stabilized.read_value(x, y)
                if value < threshold:
                    continue
                topple_count = value // threshold
                if topple_count == 0:
                    continue
                toppled = True
                total_topples += topple_count
                delta[y][x] -= threshold * topple_count
                if x > 0:
                    delta[y][x - 1] += topple_count
                if x + 1 < width:
                    delta[y][x + 1] += topple_count
                if y > 0:
                    delta[y - 1][x] += topple_count
                if y + 1 < height:
                    delta[y + 1][x] += topple_count

        if not toppled:
            break

        for y in range(height):
            for x in range(width):
                stabilized.write_value(x, y, stabilized.read_value(x, y) + delta[y][x])

    stabilized.image.max_value = max(max(stabilized.flatten_pixels(), default=0), 1)
    return stabilized, total_topples


def generate_successor_chain(
    workspace: SimulationWorkspace,
    root_surface: ImageStateSurface,
    depth: int = 16,
    prefix: str = "sandpile_state",
    include_identity_root: bool = True,
    successor_mode: str = "center",
    successor_seed: ImageStateSurface | None = None,
    rewrite_rule: RewriteRule | None = None,
) -> list[ArchivedState]:
    max_successor_steps = 15 if include_identity_root else 16
    bounded_depth = max(0, min(depth, max_successor_steps))
    archived_states: list[ArchivedState] = []
    current_surface = clone_surface(root_surface)
    rule = resolve_rewrite_rule(
        rewrite_rule=rewrite_rule,
        successor_mode=successor_mode,
        successor_seed=successor_seed,
    )
    for y in range(current_surface.image.height):
        for x in range(current_surface.image.width):
            current_surface.write_value(x, y, 0)
    current_surface.image.max_value = 1
    current_branch: tuple[str, ...] = ()
    if include_identity_root:
        identity_state = workspace.archive_surface(
            current_surface,
            branch=current_branch,
            prefix=prefix,
            topples=0,
            state_id_override="0x10",
        )
        archived_states.append(identity_state)

    for step in range(1, bounded_depth + 1):
        current_surface = succ(current_surface, rewrite_rule=rule)
        current_surface, topples = stabilize_surface(current_surface)
        if topples > 0 and len(current_branch) < 16:
            current_branch = (*current_branch, "1" * (len(current_branch) + 1))
        current_state = workspace.archive_surface(
            current_surface,
            branch=current_branch,
            prefix=prefix,
            topples=topples,
            state_id_override=f"0x{step:02x}",
        )
        archived_states.append(current_state)

    return archived_states


def generate_successor_tree(
    workspace: SimulationWorkspace,
    root_surface: ImageStateSurface,
    prefix: str = "sandpile_state",
    include_identity_root: bool = True,
    successor_mode: str = "center",
    successor_seed: ImageStateSurface | None = None,
    branch_policy: BranchPolicy | None = None,
    rewrite_rule: RewriteRule | None = None,
) -> list[ArchivedState]:
    policy = branch_policy or BranchPolicy()
    archived_states: list[ArchivedState] = []
    identity_surface = clone_surface(root_surface)
    rule = resolve_rewrite_rule(
        rewrite_rule=rewrite_rule,
        successor_mode=successor_mode,
        successor_seed=successor_seed,
    )

    def next_state_id(counter: int) -> str:
        if counter >= 0x10:
            counter += 1
        return f"0x{counter:02x}"

    frontier: list[tuple[ArchivedState, ImageStateSurface]] = []
    next_counter = 1

    if include_identity_root:
        identity_state = workspace.archive_surface(
            identity_surface,
            branch=(),
            prefix=prefix,
            topples=0,
            state_id_override="0x10",
        )
        archived_states.append(identity_state)
        frontier = [(identity_state, identity_surface)]

    for level_width in policy.level_widths():
        if not frontier or len(archived_states) >= policy.max_total_nodes:
            break

        parent_surfaces = [clone_surface(surface) for _, surface in frontier]
        next_frontier: list[tuple[ArchivedState, ImageStateSurface]] = []

        for child_index in range(level_width):
            if len(archived_states) >= policy.max_total_nodes:
                break

            parent_index = child_index % len(frontier)
            parent_state, _ = frontier[parent_index]
            parent_surfaces[parent_index] = succ(parent_surfaces[parent_index], rewrite_rule=rule)
            child_surface, topples = stabilize_surface(parent_surfaces[parent_index])
            parent_surfaces[parent_index] = child_surface

            if topples > 0 and len(parent_state.branch) < policy.max_depth:
                archived_state = workspace.spawn_child_state(
                    parent_state,
                    child_surface,
                    topples=topples,
                    prefix=prefix,
                    max_depth=policy.max_depth,
                    state_id_override=next_state_id(next_counter),
                )
            else:
                archived_state = workspace.archive_surface(
                    child_surface,
                    branch=parent_state.branch,
                    prefix=prefix,
                    topples=topples,
                    state_id_override=next_state_id(next_counter),
                    parent=parent_state,
                )
            next_counter += 1
            archived_states.append(archived_state)
            next_frontier.append((archived_state, child_surface))

        frontier = next_frontier

    return archived_states


def generate_successor_subtree_from_stem(
    workspace: SimulationWorkspace,
    stem_path: str | Path,
    prefix: str = "sandpile_state",
    successor_mode: str = "center",
    successor_seed: ImageStateSurface | None = None,
    branch_policy: BranchPolicy | None = None,
    rewrite_rule: RewriteRule | None = None,
    canonicalize: bool = False,
) -> list[ArchivedState]:
    policy = branch_policy or BranchPolicy()
    stem_chain = load_archived_state_chain(stem_path)
    stem_state = stem_chain.stem
    stem_surface = ImageStateSurface.from_path(stem_state.image_path)
    archived_states: list[ArchivedState] = []
    frontier: list[tuple[ArchivedState, ImageStateSurface]] = [(stem_state, stem_surface)]
    rule = resolve_rewrite_rule(
        rewrite_rule=rewrite_rule,
        successor_mode=successor_mode,
        successor_seed=successor_seed,
    )
    max_numeric_state_id = 0
    for image_path in workspace.root.joinpath("state_tree").rglob("sandpile_state*.pgm"):
        label = image_path.stem
        if not label.startswith(prefix):
            continue
        try:
            numeric = int(label.removeprefix(prefix), 16)
        except ValueError:
            continue
        max_numeric_state_id = max(max_numeric_state_id, numeric)
    next_counter = max_numeric_state_id + 1

    def next_state_id(counter: int) -> str:
        if counter >= 0x10:
            counter += 1
        return f"0x{counter:02x}"

    remaining_depth = max(0, policy.max_depth - stem_state.lineage_depth)
    level_widths = policy.level_widths()[:remaining_depth]

    for level_width in level_widths:
        if not frontier or len(archived_states) >= policy.max_total_nodes:
            break

        parent_surfaces = [clone_surface(surface) for _, surface in frontier]
        next_frontier: list[tuple[ArchivedState, ImageStateSurface]] = []

        for child_index in range(level_width):
            if len(archived_states) >= policy.max_total_nodes:
                break

            parent_index = child_index % len(frontier)
            parent_state, _ = frontier[parent_index]
            parent_surfaces[parent_index] = succ(parent_surfaces[parent_index], rewrite_rule=rule)
            child_surface, topples = stabilize_surface(parent_surfaces[parent_index])
            parent_surfaces[parent_index] = child_surface

            state_id = next_state_id(next_counter)
            if topples > 0 and len(parent_state.branch) < policy.max_depth:
                archived_state = workspace.spawn_child_state(
                    parent_state,
                    child_surface,
                    topples=topples,
                    prefix=prefix,
                    max_depth=policy.max_depth,
                    state_id_override=state_id,
                    canonicalize=canonicalize,
                )
            else:
                archived_state = workspace.archive_surface(
                    child_surface,
                    branch=parent_state.branch,
                    prefix=prefix,
                    topples=topples,
                    state_id_override=state_id,
                    parent=parent_state,
                    canonicalize=canonicalize,
                )

            next_counter += 1
            archived_states.append(archived_state)
            next_frontier.append((archived_state, child_surface))

        frontier = next_frontier

    return archived_states


def summarize_archived_tree(archived_states: Iterable[ArchivedState]) -> TreeGenerationSummary:
    states = list(archived_states)
    if not states:
        return TreeGenerationSummary(
            total_nodes=0,
            max_depth=0,
            level_summaries=[],
            max_depth_paths=[],
        )

    depth_buckets: dict[int, list[ArchivedState]] = {}
    max_depth = 0
    for state in states:
        depth = state.lineage_depth
        max_depth = max(max_depth, depth)
        depth_buckets.setdefault(depth, []).append(state)

    level_summaries: list[TreeLevelSummary] = []
    for depth in sorted(depth_buckets):
        bucket = depth_buckets[depth]
        level_summaries.append(
            TreeLevelSummary(
                depth=depth,
                requested_width=len(bucket),
                produced_nodes=len(bucket),
                toppled_nodes=sum(1 for state in bucket if state.topples > 0),
                unique_signatures=len({state.signature for state in bucket}),
            )
        )

    max_depth_paths = [str(state.image_path) for state in states if state.lineage_depth == max_depth]
    return TreeGenerationSummary(
        total_nodes=len(states),
        max_depth=max_depth,
        level_summaries=level_summaries,
        max_depth_paths=max_depth_paths,
    )


def deduplicate_state_tree(workspace_root: str | Path) -> DedupeSummary:
    workspace = SimulationWorkspace.create(workspace_root)
    state_tree_root = workspace.root / "state_tree"
    canonical_by_signature: dict[str, Path] = {}
    references: list[StateReference] = []

    for image_path in sorted(state_tree_root.rglob("sandpile_state*.pgm")):
        if reference_path_for_image(image_path).exists():
            continue
        surface = ImageStateSurface.from_path(image_path)
        signature = surface_signature(surface)
        canonical_path = canonical_by_signature.get(signature)
        if canonical_path is None:
            canonical_path = workspace.canonical_state_path(signature)
            if not canonical_path.exists():
                shutil.copyfile(image_path, canonical_path)
            canonical_by_signature[signature] = canonical_path
            continue

        write_state_reference(image_path, canonical_path, signature)
        references.append(
            StateReference(
                image_path=image_path,
                canonical_path=canonical_path,
                signature=signature,
            )
        )

    return DedupeSummary(
        canonical_count=len(canonical_by_signature),
        duplicate_count=len(references),
        references=references,
    )


def build_canonical_state_index(workspace_root: str | Path) -> CanonicalStateIndex:
    workspace = SimulationWorkspace.create(workspace_root)
    state_tree_root = workspace.root / "state_tree"
    aggregates: dict[Path, dict[str, object]] = {}

    for image_path in sorted(state_tree_root.rglob("sandpile_state*.pgm")):
        resolved_path = resolve_state_image_path(image_path).resolve()
        surface = ImageStateSurface.from_path(image_path)
        signature = surface_signature(surface)
        state_label = image_path.stem
        state_id = state_label.removeprefix("sandpile_state")
        lineage_depth = max(0, len(image_path.relative_to(state_tree_root).parts) - 2)
        reference = read_state_reference(image_path)

        aggregate = aggregates.setdefault(
            resolved_path,
            {
                "signature": signature,
                "occurrence_count": 0,
                "duplicate_count": 0,
                "min_lineage_depth": lineage_depth,
                "max_lineage_depth": lineage_depth,
                "state_ids": set(),
                "sample_paths": [],
                "parents": set(),
                "children": set(),
            },
        )
        aggregate["occurrence_count"] = int(aggregate["occurrence_count"]) + 1
        if reference is not None:
            aggregate["duplicate_count"] = int(aggregate["duplicate_count"]) + 1
        aggregate["min_lineage_depth"] = min(int(aggregate["min_lineage_depth"]), lineage_depth)
        aggregate["max_lineage_depth"] = max(int(aggregate["max_lineage_depth"]), lineage_depth)
        cast_state_ids = aggregate["state_ids"]
        assert isinstance(cast_state_ids, set)
        cast_state_ids.add(state_id)
        cast_samples = aggregate["sample_paths"]
        assert isinstance(cast_samples, list)
        if len(cast_samples) < 5:
            cast_samples.append(str(image_path))

        parent_dir = image_path.parent.parent
        if parent_dir.name.startswith("sandpile_state"):
            parent_image = parent_dir / f"{parent_dir.name}.pgm"
            if parent_image.exists():
                parent_resolved = resolve_state_image_path(parent_image).resolve()
                if parent_resolved != resolved_path:
                    parents = aggregate["parents"]
                    assert isinstance(parents, set)
                    parents.add(str(parent_resolved))
                    parent_surface = ImageStateSurface.from_path(parent_image)
                    parent_aggregate = aggregates.setdefault(
                        parent_resolved,
                        {
                            "signature": surface_signature(parent_surface),
                            "occurrence_count": 0,
                            "duplicate_count": 0,
                            "min_lineage_depth": max(0, lineage_depth - 1),
                            "max_lineage_depth": max(0, lineage_depth - 1),
                            "state_ids": set(),
                            "sample_paths": [],
                            "parents": set(),
                            "children": set(),
                        },
                    )
                    children = parent_aggregate["children"]
                    assert isinstance(children, set)
                    children.add(str(resolved_path))

    records: list[CanonicalStateRecord] = []
    for canonical_path in sorted(aggregates, key=lambda path: str(path)):
        aggregate = aggregates[canonical_path]
        records.append(
            CanonicalStateRecord(
                canonical_path=canonical_path,
                signature=str(aggregate["signature"]),
                occurrence_count=int(aggregate["occurrence_count"]),
                duplicate_count=int(aggregate["duplicate_count"]),
                min_lineage_depth=int(aggregate["min_lineage_depth"]),
                max_lineage_depth=int(aggregate["max_lineage_depth"]),
                state_ids=sorted(str(value) for value in aggregate["state_ids"]),
                sample_paths=list(aggregate["sample_paths"]),
                parent_canonical_paths=sorted(str(value) for value in aggregate["parents"]),
                child_canonical_paths=sorted(str(value) for value in aggregate["children"]),
            )
        )

    return CanonicalStateIndex(records=records)


def load_archived_state_chain(path: str | Path) -> ArchivedStateChain:
    image_path = Path(path)
    if image_path.suffix != ".pgm":
        raise ValueError("archived state chain loader expects a .pgm path")
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    states: list[ArchivedState] = []
    current_image = image_path
    lineage_depth = 0

    while True:
        state_dir = current_image.parent
        state_label = state_dir.name
        if not state_label.startswith("sandpile_state"):
            break

        branch_parts: list[str] = []
        probe = state_dir.parent
        while probe.name and not probe.name.startswith("sandpile_state") and probe.name != "state_tree":
            branch_parts.append(probe.name)
            probe = probe.parent
        branch = tuple(reversed(branch_parts))

        surface = ImageStateSurface.from_path(current_image)
        state_id = state_label.removeprefix("sandpile_state")
        states.append(
            ArchivedState(
                state_id=state_id,
                signature=surface_signature(surface),
                branch=branch,
                directory=state_dir,
                image_path=current_image,
                topples=0,
                parent_state_id=probe.name.removeprefix("sandpile_state") if probe.name.startswith("sandpile_state") else None,
                lineage_depth=lineage_depth,
            )
        )

        if probe.name == "state_tree" or not probe.name.startswith("sandpile_state"):
            break

        parent_image = probe / f"{probe.name}.pgm"
        if not parent_image.exists():
            break
        current_image = parent_image
        lineage_depth += 1

    states.reverse()
    normalized_states = [
        ArchivedState(
            state_id=state.state_id,
            signature=state.signature,
            branch=state.branch,
            directory=state.directory,
            image_path=state.image_path,
            topples=state.topples,
            parent_state_id=states[index - 1].state_id if index > 0 else None,
            lineage_depth=index,
        )
        for index, state in enumerate(states)
    ]
    return ArchivedStateChain(states=normalized_states)


def list_descendant_leaf_paths(path: str | Path) -> list[Path]:
    chain = load_archived_state_chain(path)
    stem_directory = chain.stem.directory
    all_images = sorted(stem_directory.rglob("sandpile_state*.pgm"))
    leaves: list[Path] = []
    for image_path in all_images:
        state_dir = image_path.parent
        has_child_states = any(child.is_dir() and child.name.startswith("sandpile_state") for child in state_dir.iterdir())
        if not has_child_states:
            leaves.append(image_path)
    return leaves


def review_archived_state_chain(path: str | Path) -> ChainReview:
    chain = load_archived_state_chain(path)
    repeated_signatures: list[str] = []
    seen_signatures: set[str] = set()
    steps: list[ChainReviewStep] = []
    previous_surface: ImageStateSurface | None = None

    for state in chain.states:
        surface = ImageStateSurface.from_path(state.image_path)
        pixels = surface.flatten_pixels()
        total_grains = sum(pixels)
        if previous_surface is None:
            changed_cells = 0
        else:
            current_pixels = surface.flatten_pixels()
            previous_pixels = previous_surface.flatten_pixels()
            changed_cells = sum(
                1
                for current_value, previous_value in zip(current_pixels, previous_pixels)
                if current_value != previous_value
            )
        repeated_signature = state.signature in seen_signatures
        if repeated_signature and state.signature not in repeated_signatures:
            repeated_signatures.append(state.signature)
        seen_signatures.add(state.signature)
        steps.append(
            ChainReviewStep(
                lineage_depth=state.lineage_depth,
                state_id=state.state_id,
                image_path=state.image_path,
                signature=state.signature,
                total_grains=total_grains,
                changed_cells_from_previous=changed_cells,
                repeated_signature=repeated_signature,
            )
        )
        previous_surface = surface

    return ChainReview(
        length=len(chain.states),
        repeated_signatures=repeated_signatures,
        steps=steps,
    )
