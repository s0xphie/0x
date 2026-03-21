from __future__ import annotations

from argparse import ArgumentParser
from contextlib import contextmanager
from functools import lru_cache
import json
from pathlib import Path
from select import select
from shutil import get_terminal_size
from time import sleep
import os
import sys
import termios
import tty

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supersingularity.compiled import build_compiled_workspace_index
    from supersingularity.engine import build_machine_context
    from supersingularity.expert import ExpertAssessmentRecord
    from supersingularity.expert import ExpertObservationRecord, ExpertRecommendationRecord
    from supersingularity.recrystallization import RecrystallizationCandidateRecord, RecrystallizationRecord
    from supersingularity.dag import (
        BuildCausalGraphIndexNode,
        BuildExpertAssessmentNode,
        BuildHypergraphCandidateIndexNode,
        BuildInitializationVectorRecordNode,
        BuildMachineStateRecordNode,
        BuildMemristorIntegrationNode,
        BuildMemristorMapNode,
        BuildOxfoiEvaluationNode,
        BuildOxfoiEventIndexNode,
        BuildProductionPointerNode,
        BuildRecrystallizationNode,
        BuildStartupEventIndexNode,
        BuildStartupSequenceNode,
        CausalGraphIndex,
        HypergraphCandidateIndex,
        MachineStateRecord,
        ProductionPointerRecord,
        PersistCausalGraphIndexNode,
        PersistExpertAssessmentNode,
        PersistHypergraphCandidateIndexNode,
        PersistMachineStateRecordNode,
        PersistOxfoiEventIndexNode,
        PersistRecrystallizationNode,
        PersistStartupEventIndexNode,
        StartupMachinePipeline,
        UpdateEventIndex,
    )
    from supersingularity.initialization import (
        DEFAULT_STARTUP_VECTOR,
        StartupInitializationVector,
        StartupSequence,
    )
    from supersingularity.simulation import (
        BranchPolicy,
        generate_successor_subtree_from_stem,
        ImageStateSurface,
        is_archived_state_directory,
        is_archived_state_image,
        list_descendant_leaf_paths,
        build_canonical_state_index,
        deduplicate_state_tree,
        load_archived_state_chain,
        read_state_reference,
        review_archived_state_chain,
        SimulationWorkspace,
        split_state_label,
    )
else:
    from .compiled import build_compiled_workspace_index
    from .engine import build_machine_context
    from .expert import ExpertAssessmentRecord
    from .expert import ExpertObservationRecord, ExpertRecommendationRecord
    from .recrystallization import RecrystallizationCandidateRecord, RecrystallizationRecord
    from .dag import (
        BuildCausalGraphIndexNode,
        BuildExpertAssessmentNode,
        BuildHypergraphCandidateIndexNode,
        BuildInitializationVectorRecordNode,
        BuildMachineStateRecordNode,
        BuildMemristorIntegrationNode,
        BuildMemristorMapNode,
        BuildOxfoiEvaluationNode,
        BuildOxfoiEventIndexNode,
        BuildProductionPointerNode,
        BuildRecrystallizationNode,
        BuildStartupEventIndexNode,
        BuildStartupSequenceNode,
        CausalGraphIndex,
        HypergraphCandidateIndex,
        MachineStateRecord,
        ProductionPointerRecord,
        PersistCausalGraphIndexNode,
        PersistExpertAssessmentNode,
        PersistHypergraphCandidateIndexNode,
        PersistMachineStateRecordNode,
        PersistOxfoiEventIndexNode,
        PersistRecrystallizationNode,
        PersistStartupEventIndexNode,
        StartupMachinePipeline,
        UpdateEventIndex,
    )
    from .initialization import (
        DEFAULT_STARTUP_VECTOR,
        StartupInitializationVector,
        StartupSequence,
    )
    from .simulation import (
        BranchPolicy,
        generate_successor_subtree_from_stem,
        ImageStateSurface,
        is_archived_state_directory,
        is_archived_state_image,
        list_descendant_leaf_paths,
        build_canonical_state_index,
        deduplicate_state_tree,
        load_archived_state_chain,
        read_state_reference,
        review_archived_state_chain,
        SimulationWorkspace,
        split_state_label,
    )


ASCII_RAMP = " .:-=+*#%@"
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_TREE = PACKAGE_ROOT / "workspace" / "state_tree"
MAX_GROW_LINEAGE_DEPTH = 16
MEMORY_FOOTER_LINES = 6
MAX_NAV_WALKS = 24
MAX_LIVE_WALKS = 48
DEFAULT_VIEW_SHORTLIST = 24
STARTUP_VECTOR = DEFAULT_STARTUP_VECTOR


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
        centered_rows: list[str] = []
        for row in rows:
            if len(row) <= target_width:
                centered_rows.append(row.ljust(target_width))
                continue
            start = max(0, (len(row) - target_width) // 2)
            centered_rows.append(row[start : start + target_width])
        rows = centered_rows
    if target_height is not None:
        if len(rows) < target_height:
            row_width = target_width if target_width is not None else max((len(row) for row in rows), default=0)
            rows.extend(" " * row_width for _ in range(target_height - len(rows)))
        else:
            start = max(0, (len(rows) - target_height) // 2)
            rows = rows[start : start + target_height]
    return "\n".join(rows)


def format_chain_address(path: str | Path) -> tuple[str, str]:
    chain = cached_archived_state_chain(path)
    hex_address = " -> ".join(state.state_id for state in chain.states)
    unary_address = "/".join(part for state in chain.states for part in state.branch) or "(root)"
    return hex_address, unary_address


def build_chain_frame(
    path: str | Path,
    title: str | None = None,
    target_size: tuple[int, int] | None = None,
    cell_width: int = 2,
) -> str:
    review = cached_chain_review(path)
    state = review.steps[-1]
    surface = ImageStateSurface.from_path(state.image_path)
    target_width = None
    target_height = None
    if target_size is not None:
        target_width = target_size[0] * cell_width
        target_height = target_size[1]
    body = render_surface_text(
        surface,
        cell_width=cell_width,
        target_width=target_width,
        target_height=target_height,
    )
    return f"{body}\n"


def build_surface_frame(
    surface: ImageStateSurface,
    overlay: str,
    footer_lines: list[str],
    target_size: tuple[int, int] | None = None,
    cell_width: int = 2,
) -> str:
    target_width = None
    target_height = None
    if target_size is not None:
        target_width = target_size[0] * cell_width
        target_height = target_size[1]
    body = render_surface_text(
        surface,
        cell_width=cell_width,
        target_width=target_width,
        target_height=target_height,
    )
    return f"{body}\n"


def redraw_startup_walk(
    startup_surfaces: list[ImageStateSurface],
    current_state_name: str,
    target_size: tuple[int, int],
    cell_width: int,
    start_index: int = 0,
) -> None:
    for startup_surface in startup_surfaces[max(0, start_index) :]:
        redraw_frame(
            build_surface_frame(
                startup_surface,
                overlay="startup",
                footer_lines=[
                    f"machine state: {current_state_name}",
                    "startup recursion active",
                ],
                target_size=target_size,
                cell_width=cell_width,
            )
        )


def iter_chain_paths(path: str | Path) -> list[Path]:
    chain = cached_archived_state_chain(path)
    return [state.image_path for state in chain.states]


def iter_leaf_walk_paths(stem_path: str | Path) -> list[list[Path]]:
    leaves = list_descendant_leaf_paths(stem_path)
    return [iter_chain_paths(leaf) for leaf in leaves]


def nearest_branching_anchor(path: str | Path) -> Path:
    chain = cached_archived_state_chain(path)
    for state in reversed(chain.states):
        leaves = list_descendant_leaf_paths(state.image_path)
        if len(leaves) > 1:
            return state.image_path
    return chain.states[0].image_path


@lru_cache(maxsize=16)
def production_pointer_guidance(workspace_root: str) -> dict[str, object]:
    runs_root = Path(workspace_root) / "runs"
    manifests: list[dict[str, object]] = []
    preferred_outputs: set[str] = set()
    current_states: set[str] = set()
    target_domains: set[str] = set()
    if runs_root.exists():
        for manifest_path in sorted(runs_root.glob("pp_*.json")):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            manifests.append(data)
            current_state = str(data.get("current_state_id", ""))
            preferred_output = str(data.get("preferred_output", ""))
            target_domain = str(data.get("target_domain", ""))
            if current_state:
                current_states.add(current_state)
            if preferred_output:
                preferred_outputs.add(preferred_output)
            if target_domain:
                target_domains.add(target_domain)
    return {
        "manifest_count": len(manifests),
        "preferred_outputs": preferred_outputs,
        "current_states": current_states,
        "target_domains": target_domains,
    }


@lru_cache(maxsize=2048)
def intrinsic_state_metrics(path: str | Path) -> tuple[int, int, int, int, int]:
    chain = cached_archived_state_chain(path)
    review = cached_chain_review(path)
    current = review.steps[-1]
    child_count = len(immediate_child_paths(path))
    novelty = 0 if current.repeated_signature else 1
    changed_cells = int(current.changed_cells_from_previous)
    lineage_depth = current.lineage_depth
    chain_length = len(chain.states)
    return (
        child_count,
        novelty,
        changed_cells,
        lineage_depth,
        chain_length,
    )


@lru_cache(maxsize=256)
def cached_leaf_paths_for_anchor(anchor_path: str) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(str(frame.resolve()) for frame in walk)
        for walk in iter_leaf_walk_paths(Path(anchor_path))
    )


@lru_cache(maxsize=1024)
def walk_priority_metrics(walk_key: tuple[str, ...], workspace_root: str) -> tuple[int, int, int, int, int, int, str]:
    guidance = production_pointer_guidance(workspace_root)
    preferred_outputs = guidance["preferred_outputs"]
    current_states = guidance["current_states"]
    pointer_hits = 0
    novelty = 0
    branch_points = 0
    changed_cells = 0
    depth_mass = 0
    chain_mass = 0
    for frame_path_text in walk_key:
        frame_path = Path(frame_path_text)
        review = cached_chain_review(frame_path)
        current = review.steps[-1]
        child_count, intrinsic_novelty, intrinsic_changed_cells, lineage_depth, chain_length = intrinsic_state_metrics(frame_path)
        if current.state_id in preferred_outputs or current.state_id in current_states:
            pointer_hits += 1
        novelty += intrinsic_novelty
        changed_cells += intrinsic_changed_cells
        depth_mass += lineage_depth
        chain_mass += chain_length
        if child_count > 1:
            branch_points += 1
    return (
        branch_points,
        novelty,
        changed_cells,
        depth_mass,
        chain_mass,
        pointer_hits,
        len(walk_key),
        walk_key[-1],
    )


def related_leaf_walks(path: str | Path, limit: int | None = None) -> list[list[Path]]:
    anchor = nearest_branching_anchor(path)
    anchor_key = str(Path(anchor).resolve())
    walks = [[Path(frame) for frame in walk] for walk in cached_leaf_paths_for_anchor(anchor_key)]
    target = Path(path).resolve()
    workspace_root = str(workspace_root_for_path(path).resolve())

    def walk_score(walk: list[Path]) -> tuple[int, int, int, int, int, int, int, str]:
        resolved = [frame.resolve() for frame in walk]
        contains_target = 0 if target in resolved else 1
        walk_key = tuple(str(frame) for frame in resolved)
        branch_points, novelty, changed_cells, depth_mass, chain_mass, pointer_hits, walk_length, tail = walk_priority_metrics(
            walk_key,
            workspace_root,
        )
        return (
            contains_target,
            -branch_points,
            -novelty,
            -changed_cells,
            -depth_mass,
            -chain_mass,
            -pointer_hits,
            -walk_length,
            tail,
        )

    ordered = sorted(walks, key=walk_score)
    if limit is not None:
        return ordered[: max(1, limit)]
    return ordered


def default_view_path() -> Path:
    root = DEFAULT_STATE_TREE
    if not root.exists():
        raise FileNotFoundError(str(root))

    candidates = []
    fallback_candidates = []
    for path in root.rglob("*.pgm"):
        if not is_archived_state_image(path):
            continue
        fallback_candidates.append(path)
        parsed = split_state_label(path.stem)
        if parsed is not None and parsed[0] == "sandpile_state":
            candidates.append(path)
    if not candidates:
        candidates = fallback_candidates
    if not candidates:
        raise FileNotFoundError(f"no archived sandpile states found in {root}")

    workspace_root = root.parent
    guidance = production_pointer_guidance(str(workspace_root.resolve()))

    def cheap_score(path: Path) -> tuple[int, int, int, str]:
        parsed = split_state_label(path.stem)
        state_value = -1
        if parsed is not None:
            try:
                state_value = int(parsed[1], 16)
            except ValueError:
                state_value = -1
        depth = len(path.relative_to(root).parts) - 2
        return (depth, state_value, len(path.parts), str(path))

    shortlisted = sorted(candidates, key=cheap_score, reverse=True)[:DEFAULT_VIEW_SHORTLIST]
    if shortlisted:
        candidates = shortlisted

    def score(path: Path) -> tuple[int, int, int, int, int, str]:
        chain = cached_archived_state_chain(path)
        current = chain.stem
        _, novelty, changed_cells, lineage_depth, chain_length = intrinsic_state_metrics(path)
        pointer_bonus = 1 if current.state_id in guidance["preferred_outputs"] or current.state_id in guidance["current_states"] else 0
        return (
            novelty,
            changed_cells,
            lineage_depth,
            chain_length,
            pointer_bonus,
            str(path),
        )

    return max(candidates, key=score)


@lru_cache(maxsize=1)
def startup_machine_context() -> dict[str, object] | None:
    if not STARTUP_VECTOR.seed_path.exists():
        return None
    pipeline = StartupMachinePipeline()
    return pipeline.run(
        {
            "initialization_vector": STARTUP_VECTOR,
            "workspace_root": PACKAGE_ROOT / "workspace",
        }
    )


def startup_sequence() -> StartupSequence:
    context = startup_machine_context()
    if context is None:
        fallback = default_view_path()
        return StartupSequence(
            surfaces=[ImageStateSurface.from_path(fallback)],
            persisted_paths=[fallback],
        )
    return context["startup_sequence"]


@lru_cache(maxsize=64)
def persisted_machine_state_record_for_path(path: str | Path) -> MachineStateRecord | None:
    resolved = Path(path).resolve()
    workspace_root = workspace_root_for_path(resolved)
    runs_root = workspace_root / "runs"
    if not runs_root.exists():
        return None
    current_state_id = cached_archived_state_chain(resolved).stem.state_id
    exact_match: MachineStateRecord | None = None
    state_match: MachineStateRecord | None = None
    manifests = sorted(
        runs_root.glob("mach_*.json"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    for manifest_path in manifests:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        manifest_stem_path = data.get("metadata", {}).get("stem_path")
        manifest_state_id = data.get("current_state_id")
        record = deserialize_machine_state_record(data)
        if manifest_stem_path == str(resolved):
            exact_match = record
            break
        if manifest_state_id == current_state_id and state_match is None:
            state_match = record
    return exact_match or state_match


def deserialize_machine_state_record(data: dict[str, object]) -> MachineStateRecord:
    payload = dict(data)
    payload.setdefault("memristor_map_id", None)
    payload.setdefault("memristor_lattice_family", None)
    payload.setdefault("memristor_modulated_site_count", 0)
    payload.setdefault("recrystallization_id", None)
    payload.setdefault("recrystallized_state_id", None)
    payload.setdefault("recrystallization_source", None)
    return MachineStateRecord(**payload)


@lru_cache(maxsize=64)
def persisted_expert_assessment_for_machine(path: str | Path) -> ExpertAssessmentRecord | None:
    resolved = Path(path).resolve()
    workspace_root = workspace_root_for_path(resolved)
    runs_root = workspace_root / "runs"
    if not runs_root.exists():
        return None
    machine = persisted_machine_state_record_for_path(resolved)
    if machine is None:
        return None
    for manifest_path in sorted(runs_root.glob("expert_*.json"), reverse=True):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("machine_id") == machine.machine_id:
            return deserialize_expert_assessment_record(data)
    return None


def deserialize_expert_assessment_record(data: dict[str, object]) -> ExpertAssessmentRecord:
    payload = dict(data)
    observations = tuple(ExpertObservationRecord(**record) for record in payload.get("observations", ()))
    recommendations = tuple(
        ExpertRecommendationRecord(**record) for record in payload.get("recommendations", ())
    )
    payload["observations"] = observations
    payload["recommendations"] = recommendations
    return ExpertAssessmentRecord(**payload)


def deserialize_recrystallization_record(data: dict[str, object]) -> RecrystallizationRecord:
    payload = dict(data)
    candidates = tuple(RecrystallizationCandidateRecord(**record) for record in payload.get("candidates", ()))
    payload["candidates"] = candidates
    return RecrystallizationRecord(**payload)


@lru_cache(maxsize=64)
def persisted_recrystallization_for_machine(path: str | Path) -> RecrystallizationRecord | None:
    resolved = Path(path).resolve()
    workspace_root = workspace_root_for_path(resolved)
    runs_root = workspace_root / "runs"
    if not runs_root.exists():
        return None
    machine = persisted_machine_state_record_for_path(resolved)
    if machine is None:
        return None
    for manifest_path in sorted(runs_root.glob("recry_*.json"), reverse=True):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("machine_id") == machine.machine_id:
            return deserialize_recrystallization_record(data)
    return None


@lru_cache(maxsize=16)
def persisted_causal_graph_index_for_workspace(workspace_root: str | Path) -> CausalGraphIndex | None:
    manifest_path = Path(workspace_root).resolve() / "runs" / "causal_graph_index.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return CausalGraphIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=16)
def persisted_hypergraph_candidate_index_for_workspace(workspace_root: str | Path) -> HypergraphCandidateIndex | None:
    manifest_path = Path(workspace_root).resolve() / "runs" / "hypergraph_candidate_index.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return HypergraphCandidateIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=16)
def persisted_update_event_index_for_workspace(workspace_root: str | Path, manifest_name: str) -> UpdateEventIndex | None:
    manifest_path = Path(workspace_root).resolve() / "runs" / manifest_name
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return UpdateEventIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=64)
def persisted_update_event_index_for_manifest(manifest_path: str | Path) -> UpdateEventIndex | None:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return UpdateEventIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=32)
def persisted_causal_graph_index_for_manifest(manifest_path: str | Path) -> CausalGraphIndex | None:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return CausalGraphIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=32)
def persisted_hypergraph_candidate_index_for_manifest(manifest_path: str | Path) -> HypergraphCandidateIndex | None:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return HypergraphCandidateIndex(**data)
    except Exception:
        return None


@lru_cache(maxsize=64)
def persisted_production_pointer_for_manifest(manifest_path: str | Path) -> ProductionPointerRecord | None:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return ProductionPointerRecord(**data)
    except Exception:
        return None


@lru_cache(maxsize=16)
def machine_state_record_for_path(path: str | Path) -> MachineStateRecord:
    resolved = Path(path).resolve()
    persisted = persisted_machine_state_record_for_path(resolved)
    persisted_expert = persisted_expert_assessment_for_machine(resolved)
    persisted_recrystallization = persisted_recrystallization_for_machine(resolved)
    if (
        persisted is not None
        and machine_state_record_is_complete(persisted)
        and persisted_expert is not None
        and persisted_recrystallization is not None
    ):
        return persisted
    workspace_root = workspace_root_for_path(resolved)
    workspace = SimulationWorkspace.create(workspace_root)
    context = build_machine_context(resolved, workspace)
    return context["machine_state_record"]


def machine_state_record_is_complete(record: MachineStateRecord) -> bool:
    metadata = record.metadata or {}
    required_keys = (
        "startup_event_manifest_path",
        "oxfoi_event_manifest_path",
        "causal_graph_manifest_path",
        "hypergraph_candidate_manifest_path",
        "recrystallization_manifest_path",
        "production_pointer_manifest_path",
    )
    return all(bool(metadata.get(key)) for key in required_keys)


def startup_chain_paths() -> list[Path]:
    return startup_sequence().persisted_paths


def startup_view_path() -> Path:
    sequence = startup_sequence()
    return intended_startup_target_path(sequence.final_path)


@lru_cache(maxsize=64)
def resolve_state_id_to_path(workspace_root: str | Path, state_id: str) -> Path | None:
    if not state_id:
        return None
    root = Path(workspace_root).resolve() / "state_tree"
    if not root.exists():
        return None
    candidates = []
    for path in root.rglob("*.pgm"):
        if not is_archived_state_image(path):
            continue
        parsed = split_state_label(path.stem)
        if parsed is None:
            continue
        if parsed[0] == "sandpile_state" and parsed[1] == state_id:
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda path: (len(path.relative_to(root).parts), str(path)))


def intended_startup_target_path(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    try:
        machine = machine_state_record_for_path(resolved)
    except Exception:
        try:
            return default_view_path()
        except Exception:
            return resolved

    pointer_manifest_path = machine.metadata.get("production_pointer_manifest_path")
    if pointer_manifest_path:
        pointer = persisted_production_pointer_for_manifest(pointer_manifest_path)
        if pointer is not None:
            preferred_output = pointer.preferred_output or ""
            preferred_path = resolve_state_id_to_path(workspace_root_for_path(resolved), preferred_output)
            if preferred_path is not None:
                return preferred_path
    try:
        fallback = default_view_path()
    except Exception:
        fallback = resolved
    return fallback if fallback != resolved else resolved


@lru_cache(maxsize=2048)
def surface_dimensions(path: str | Path) -> tuple[int, int]:
    surface = ImageStateSurface.from_path(path)
    return surface.image.width, surface.image.height


def infer_target_size(paths: list[Path]) -> tuple[int, int]:
    max_width = 1
    max_height = 1
    for path in paths:
        width, height = surface_dimensions(str(Path(path).resolve()))
        max_width = max(max_width, width)
        max_height = max(max_height, height)
    return max_width, max_height


@lru_cache(maxsize=128)
def cached_target_size(paths_key: tuple[str, ...]) -> tuple[int, int]:
    return infer_target_size([Path(path) for path in paths_key])


def _normalize_view_path(path: str | Path) -> str:
    return str(Path(path).resolve())


@lru_cache(maxsize=512)
def cached_archived_state_chain(path: str | Path):
    return load_archived_state_chain(_normalize_view_path(path))


@lru_cache(maxsize=512)
def cached_chain_review(path: str | Path):
    return review_archived_state_chain(_normalize_view_path(path))


def immediate_child_paths(path: str | Path) -> list[Path]:
    chain = cached_archived_state_chain(path)
    state_dir = chain.stem.directory
    children: list[Path] = []
    for child in sorted(state_dir.iterdir()):
        if not child.is_dir() or not is_archived_state_directory(child):
            continue
        image_path = child / f"{child.name}.pgm"
        if image_path.exists():
            children.append(image_path)
    return children


@lru_cache(maxsize=512)
def subtree_stats(path: str | Path) -> tuple[int, int, int]:
    chain = cached_archived_state_chain(path)
    stem = chain.stem
    all_images = sorted(image for image in stem.directory.rglob("*.pgm") if is_archived_state_image(image))
    leaves = list_descendant_leaf_paths(path)
    max_extra_depth = 0
    for image_path in all_images:
        extra_depth = max(0, len(image_path.relative_to(stem.directory).parts) - 2)
        max_extra_depth = max(max_extra_depth, extra_depth)
    return len(all_images), len(leaves), max_extra_depth


def compact_chain_labels(path: str | Path, limit: int = 5) -> str:
    chain = cached_archived_state_chain(path)
    labels = [state.state_id for state in chain.states]
    if len(labels) <= limit:
        return "->".join(labels)
    head = labels[:2]
    tail = labels[-2:]
    return "->".join([*head, "..", *tail])


def render_memory_footer(path: str | Path, width: int) -> str:
    review = cached_chain_review(path)
    chain = cached_archived_state_chain(path)
    current = chain.stem
    workspace_root = workspace_root_for_path(path).resolve()
    node_count, leaf_count, max_extra_depth = subtree_stats(path)
    child_count = len(immediate_child_paths(path))
    reference = read_state_reference(current.image_path)
    reference_flag = "ref" if reference is not None else "raw"
    repeat_flag = "rep" if review.steps[-1].repeated_signature else "new"
    try:
        workspace_line = compiled_workspace_snapshot(str(workspace_root))
    except Exception:
        workspace_line = "ws:unavailable"
    try:
        machine = machine_state_record_for_path(path)
        startup_event_index = (
            persisted_update_event_index_for_manifest(machine.metadata["startup_event_manifest_path"])
            if machine.metadata.get("startup_event_manifest_path")
            else None
        )
        oxfoi_event_index = (
            persisted_update_event_index_for_manifest(machine.metadata["oxfoi_event_manifest_path"])
            if machine.metadata.get("oxfoi_event_manifest_path")
            else None
        )
        triton_event_index = (
            persisted_update_event_index_for_manifest(machine.metadata["triton_event_manifest_path"])
            if machine.metadata.get("triton_event_manifest_path")
            else None
        )
        causal_graph = (
            persisted_causal_graph_index_for_manifest(machine.metadata["causal_graph_manifest_path"])
            if machine.metadata.get("causal_graph_manifest_path")
            else None
        )
        hypergraph_index = (
            persisted_hypergraph_candidate_index_for_manifest(machine.metadata["hypergraph_candidate_manifest_path"])
            if machine.metadata.get("hypergraph_candidate_manifest_path")
            else None
        )
        production_pointer = (
            persisted_production_pointer_for_manifest(machine.metadata["production_pointer_manifest_path"])
            if machine.metadata.get("production_pointer_manifest_path")
            else None
        )
        expert_assessment = persisted_expert_assessment_for_machine(path)
        recrystallization = persisted_recrystallization_for_machine(path)
        machine_line = (
            f"mach:{machine.machine_id[:12]} cur:{machine.current_state_id or '-'} "
            f"ox:{machine.oxfoi_field_domain or '-'}:{machine.oxfoi_instruction_width_words or 0} "
            f"tc:{machine.target_confidence:.2f}"
        )
        align_line = (
            f"init:{machine.init_origin} ss:{machine.startup_surface_count} "
            f"sa:{machine.metadata.get('startup_alignment_score', 0)} "
            f"oa:{machine.metadata.get('oxfoi_alignment_score', 0)}"
        )
        if machine.memristor_map_id is not None:
            align_line = (
                f"{align_line} mm:{machine.memristor_map_id[:12]} "
                f"ms:{machine.memristor_modulated_site_count} "
                f"md:{machine.metadata.get('memristor_loop_density', 0.0):.2f}"
            )
        relation_line = (
            f"cg:{len(causal_graph.records) if causal_graph is not None else '-'} "
            f"hg:{len(hypergraph_index.records) if hypergraph_index is not None else '-'}"
        )
        history_line = (
            f"se:{len(startup_event_index.records) if startup_event_index is not None else '-'} "
            f"oe:{len(oxfoi_event_index.records) if oxfoi_event_index is not None else '-'} "
            f"te:{len(triton_event_index.records) if triton_event_index is not None else '-'}"
        )
        pointer_line = (
            f"pp:{production_pointer.pointer_id[:12]} ray:{production_pointer.ray_id[:12]} "
            f"nx:{len(production_pointer.next_edge_types)}"
            if production_pointer is not None
            else "pp:unavailable"
        )
        expert_line = (
            f"ex:{expert_assessment.recommendations[0].action} "
            f"pr:{expert_assessment.recommendations[0].priority:.2f}"
            if expert_assessment is not None and expert_assessment.recommendations
            else "ex:unavailable"
        )
        recrystallization_line = (
            f"rc:{recrystallization.selected_state_id or '-'} "
            f"src:{recrystallization.selected_source[:12]} "
            f"rs:{recrystallization.selected_score:.2f}"
            if recrystallization is not None
            else "rc:unavailable"
        )
    except Exception:
        machine_line = "mach:unavailable"
        align_line = "init:unavailable"
        relation_line = (
            f"cg:{len(persisted_causal_graph_index_for_workspace(workspace_root).records) if persisted_causal_graph_index_for_workspace(workspace_root) is not None else '-'} "
            f"hg:{len(persisted_hypergraph_candidate_index_for_workspace(workspace_root).records) if persisted_hypergraph_candidate_index_for_workspace(workspace_root) is not None else '-'}"
        )
        history_line = (
            f"se:{len(persisted_update_event_index_for_workspace(workspace_root, 'startup_event_index.json').records) if persisted_update_event_index_for_workspace(workspace_root, 'startup_event_index.json') is not None else '-'} "
            f"oe:{len(persisted_update_event_index_for_workspace(workspace_root, 'oxfoi_event_index.json').records) if persisted_update_event_index_for_workspace(workspace_root, 'oxfoi_event_index.json') is not None else '-'} "
            f"te:{len(persisted_update_event_index_for_workspace(workspace_root, 'triton_oxfoi_event_index.json').records) if persisted_update_event_index_for_workspace(workspace_root, 'triton_oxfoi_event_index.json') is not None else '-'}"
        )
        pointer_line = "pp:unavailable"
        expert_line = "ex:unavailable"
        recrystallization_line = "rc:unavailable"
    lines = [
        f"m:{current.state_id} d:{current.lineage_depth} ch:{child_count} lf:{leaf_count} sub:{node_count} mx:{max_extra_depth}",
        machine_line,
        align_line,
        pointer_line,
        expert_line,
        recrystallization_line,
        f"mem:{reference_flag} {repeat_flag} sig:{current.signature[:14]} {relation_line} {history_line} {workspace_line}",
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


def organic_navigation_timeout(
    path: str | Path,
    delay: float,
    dwell: float,
    *,
    at_end_of_walk: bool,
    at_end_of_cycle: bool,
) -> float:
    review = cached_chain_review(path)
    current = review.steps[-1]
    child_count = len(immediate_child_paths(path))
    timeout = max(delay, 0.05)

    # Move briskly through quiet frames, but slow down when the state actually changes.
    changed_cells = max(0, current.changed_cells_from_previous)
    if changed_cells <= 1:
        timeout *= 0.8
    elif changed_cells >= 6:
        timeout *= 1.15

    # Repeated signatures usually mean less visual novelty, so don't over-dwell there.
    if current.repeated_signature:
        timeout *= 0.9

    # Branch points and walk boundaries deserve more "breath" in the rhythm.
    if child_count > 1:
        timeout = max(timeout, delay + min(0.25, 0.06 * child_count))
    if at_end_of_walk:
        timeout = max(timeout, dwell)
    if at_end_of_cycle:
        timeout = max(timeout, dwell * 1.15)

    return max(0.05, timeout)


def circle_leaf_score(path: str | Path) -> tuple[int, int, int, int]:
    surface = ImageStateSurface.from_path(path)
    width = surface.image.width
    height = surface.image.height
    center_x = width // 2
    center_y = height // 2
    circular_support = 0
    radial_mass = 0
    total_mass = 0
    for y, row in enumerate(surface.image.pixels):
        for x, value in enumerate(row):
            if value <= 0:
                continue
            total_mass += value
            dx = x - center_x
            dy = y - center_y
            radius_sq = dx * dx + dy * dy
            # Favor support close to a centered disk and penalize sparse off-axis noise.
            radial_mass -= radius_sq * value
            if abs(abs(dx) - abs(dy)) <= 2 or dx == 0 or dy == 0:
                circular_support += value
    chain_length = len(cached_archived_state_chain(path).states)
    return (circular_support, radial_mass, total_mass, chain_length)


@contextmanager
def fullscreen_terminal() -> None:
    use_alternate_screen = os.environ.get("SUPERSINGULARITY_ALT_SCREEN", "1").lower() not in {"0", "false", "no"}
    if not sys.stdout.isatty() or not use_alternate_screen:
        yield
        return
    try:
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        yield
    finally:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


def redraw_frame(frame: str) -> None:
    # Always clear and home so redraw stays pinned in one terminal region.
    # Some IDE terminals report TTY support inconsistently, but still honor ANSI.
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.write(frame)
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


def frame_geometry(paths: list[Path], reserved_lines: int = 1) -> tuple[tuple[int, int], int]:
    paths_key = tuple(str(Path(path).resolve()) for path in paths)
    target_size = cached_target_size(paths_key)
    terminal = get_terminal_size(fallback=(80, 24))
    cell_width = 2 if target_size[0] * 2 <= terminal.columns else 1
    max_rows = max(1, terminal.lines - reserved_lines)
    # Use the full available terminal canvas so smaller/larger graphs do not
    # move the prompt or other UI elements around between redraws.
    fitted_size = (max(1, terminal.columns // max(1, cell_width)), max_rows)
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


def read_key(timeout: float | None = None, default: str = "n") -> str:
    if not sys.stdin.isatty():
        if timeout is not None:
            ready, _, _ = select([sys.stdin], [], [], max(0.0, timeout))
            if not ready:
                return default
        line = sys.stdin.readline()
        return (line[:1] if line else default).lower()
    with raw_stdin():
        if timeout is not None:
            ready, _, _ = select([sys.stdin], [], [], max(0.0, timeout))
            if not ready:
                return default
        char = sys.stdin.read(1)
    if char == "\x1b":
        return "q"
    if char in {"\r", "\n"}:
        return "n"
    return char.lower()


def prompt_action(frame: str, prompt: str, timeout: float | None = None, default: str = "n") -> str:
    redraw_frame(f"{frame.rstrip()}\n\n{prompt}")
    return read_key(timeout=timeout, default=default)


def workspace_root_for_path(path: str | Path) -> Path:
    probe = Path(path).resolve()
    for parent in [probe.parent, *probe.parents]:
        if parent.name == "workspace":
            return parent
    raise FileNotFoundError(f"could not infer workspace root from {path}")


def invalidate_view_caches(path: str | Path | None = None) -> None:
    cached_archived_state_chain.cache_clear()
    cached_chain_review.cache_clear()
    cached_leaf_paths_for_anchor.cache_clear()
    intrinsic_state_metrics.cache_clear()
    subtree_stats.cache_clear()
    cached_target_size.cache_clear()
    surface_dimensions.cache_clear()
    walk_priority_metrics.cache_clear()
    production_pointer_guidance.cache_clear()
    machine_state_record_for_path.cache_clear()
    persisted_machine_state_record_for_path.cache_clear()
    persisted_expert_assessment_for_machine.cache_clear()
    persisted_recrystallization_for_machine.cache_clear()
    persisted_causal_graph_index_for_workspace.cache_clear()
    persisted_hypergraph_candidate_index_for_workspace.cache_clear()
    persisted_update_event_index_for_workspace.cache_clear()
    persisted_update_event_index_for_manifest.cache_clear()
    persisted_causal_graph_index_for_manifest.cache_clear()
    persisted_hypergraph_candidate_index_for_manifest.cache_clear()
    persisted_production_pointer_for_manifest.cache_clear()
    if path is None:
        compiled_workspace_snapshot.cache_clear()
        return
    try:
        workspace_root = str(workspace_root_for_path(path).resolve())
    except Exception:
        return
    compiled_workspace_snapshot.cache_clear()


@lru_cache(maxsize=16)
def compiled_workspace_snapshot(workspace_root: str) -> str:
    index = build_compiled_workspace_index(workspace_root)
    return (
        f"ws:{index.state_tree_images} raw:{index.raw_state_images} "
        f"ref:{index.reference_backed_images} can:{index.canonical_images} "
        f"uniq:{index.unique_signatures} depth:{index.max_lineage_depth}"
    )


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
    chain = cached_archived_state_chain(path)
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

    if total_grown > 0:
        invalidate_view_caches(path)
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

    if total_grown > 0:
        invalidate_view_caches(path)
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
    startup_paths: list[Path] | None = None,
) -> None:
    current_path = Path(path)
    with fullscreen_terminal():
        if startup_paths:
            current_path = startup_paths[-1]
        iteration = 0
        while repeat <= 0 or iteration < repeat:
            leaf_walks = related_leaf_walks(current_path, limit=MAX_NAV_WALKS)
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
            leaf_walks = related_leaf_walks(current_path, limit=MAX_LIVE_WALKS)
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
    startup_paths: list[Path] | None = None,
    startup_surfaces: list[ImageStateSurface] | None = None,
) -> None:
    current_path = Path(path)
    with fullscreen_terminal():
        if startup_surfaces:
            current_path = startup_paths[-1] if startup_paths else current_path
            target_size, cell_width = frame_geometry([current_path], reserved_lines=MEMORY_FOOTER_LINES)
            redraw_startup_walk(
                startup_surfaces,
                current_path.name,
                target_size=target_size,
                cell_width=cell_width,
                start_index=0,
            )

        target_size, cell_width = frame_geometry([current_path], reserved_lines=MEMORY_FOOTER_LINES)
        frame = build_chain_frame(current_path, target_size=target_size, cell_width=cell_width)
        width = target_size[0] * cell_width
        info = render_memory_footer(current_path, width=width)
        redraw_frame(f"{frame.rstrip()}\n{info}\n")
        while True:
            sleep(1.0)


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
    args = parser.parse_args(argv)
    startup_paths: list[Path] | None = None
    startup_surfaces: list[ImageStateSurface] | None = None
    if args.path:
        path = args.path
    else:
        sequence = startup_sequence()
        startup_paths = sequence.persisted_paths
        startup_surfaces = sequence.surfaces
        path = str(startup_view_path())
    repeat = 0 if args.loop else args.repeat

    if args.mode == "chain":
        animate_chain(path, delay=args.delay, repeat=repeat)
    elif args.mode == "leaves":
        animate_leaf_walk(path, delay=args.delay, dwell=args.dwell, repeat=repeat)
    elif args.mode == "navigate":
        navigate_space(
            path,
            delay=args.delay,
            dwell=args.dwell,
            startup_paths=startup_paths,
            startup_surfaces=startup_surfaces,
        )
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
            startup_paths=startup_paths,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
