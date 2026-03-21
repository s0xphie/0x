from __future__ import annotations

from pathlib import Path

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
    PersistCausalGraphIndexNode,
    PersistExpertAssessmentNode,
    PersistHypergraphCandidateIndexNode,
    PersistMachineStateRecordNode,
    PersistOxfoiEventIndexNode,
    PersistRecrystallizationNode,
    PersistStartupEventIndexNode,
)
from .initialization import DEFAULT_STARTUP_VECTOR
from .simulation import (
    ImageStateSurface,
    SimulationWorkspace,
    build_canonical_state_index,
    deduplicate_state_tree,
    load_archived_state_chain,
    review_archived_state_chain,
    split_state_label,
    stabilize_surface,
    succ,
)


def next_state_id(workspace_root: Path, prefix: str = "sandpile_state") -> str:
    max_numeric_state_id = 0
    for image_path in workspace_root.joinpath("state_tree").rglob(f"{prefix}*.pgm"):
        parsed = split_state_label(image_path.stem)
        if parsed is None or parsed[0] != prefix:
            continue
        try:
            numeric = int(parsed[1], 16)
        except ValueError:
            continue
        max_numeric_state_id = max(max_numeric_state_id, numeric)
    counter = max_numeric_state_id + 1
    if counter >= 0x10:
        counter += 1
    return f"0x{counter:02x}"


def build_machine_context(path: Path, workspace: SimulationWorkspace) -> dict[str, object]:
    workspace_root = workspace.root
    context: dict[str, object] = {
        "initialization_vector": DEFAULT_STARTUP_VECTOR,
        "workspace_root": workspace_root,
        "workspace": workspace,
        "stem_path": path,
        "chain_review": review_archived_state_chain(path),
        "generated_states": [],
        "dedupe_summary": deduplicate_state_tree(workspace_root),
        "canonical_state_index": build_canonical_state_index(workspace_root),
        "memristor_lattice_size": 5,
        "oxfoi_expression_payload": "init.single_use",
        "oxfoi_instruction_width_words": 2,
    }
    for node in [
        BuildInitializationVectorRecordNode(),
        BuildStartupSequenceNode(),
        BuildStartupEventIndexNode(),
        PersistStartupEventIndexNode(),
        BuildMemristorMapNode(),
        BuildOxfoiEvaluationNode(),
        BuildMemristorIntegrationNode(),
        BuildOxfoiEventIndexNode(),
        PersistOxfoiEventIndexNode(),
        BuildCausalGraphIndexNode(),
        PersistCausalGraphIndexNode(),
        BuildHypergraphCandidateIndexNode(),
        PersistHypergraphCandidateIndexNode(),
        BuildProductionPointerNode(),
        BuildMachineStateRecordNode(),
        BuildExpertAssessmentNode(),
        PersistExpertAssessmentNode(),
        BuildRecrystallizationNode(),
        PersistRecrystallizationNode(),
        BuildMachineStateRecordNode(),
        PersistMachineStateRecordNode(),
    ]:
        context.update(node.run(context))
    return context


def apply_successor_primitive(path: Path, workspace: SimulationWorkspace) -> Path:
    chain = load_archived_state_chain(path)
    current_state = chain.stem
    surface = ImageStateSurface.from_path(current_state.image_path)
    next_surface = succ(surface, mode="center")
    next_surface, topples = stabilize_surface(next_surface)
    archived_state = workspace.archive_surface(
        next_surface,
        branch=current_state.branch,
        prefix="sandpile_state",
        topples=topples,
        state_id_override=next_state_id(workspace.root),
        parent=current_state,
    )
    return archived_state.image_path
