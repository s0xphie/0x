from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .graph import (
    add_chip,
    configuration_signature,
    rebind_configuration,
    sandpile_features,
    SandpileGroupInvariant,
    SandpileConfiguration,
    SandpileModel,
    stabilize_configuration,
    StabilizationResult,
    UndirectedGraph,
)
from .simulation import ArchivedState, ImageStateSurface, SimulationWorkspace
from .simulation import (
    CanonicalStateIndex,
    ChainReview,
    DedupeSummary,
    build_canonical_state_index,
    deduplicate_state_tree,
    generate_successor_subtree_from_stem,
    load_archived_state_chain,
    review_archived_state_chain,
    resolve_state_image_path,
    surface_signature,
    summarize_archived_tree,
)
from .ternlsb import (
    apply_ternlsb_program,
    decode_ternlsb_program,
    encode_ternlsb_program,
    TernLSBExecutionRecord,
    TernLSBProgram,
)


DagContext = dict[str, Any]


@dataclass
class DagNode:
    name: str
    inputs: list[str]
    outputs: list[str]

    def run(self, context: DagContext) -> DagContext:
        raise NotImplementedError

    def _require(self, context: DagContext) -> None:
        missing = [key for key in self.inputs if key not in context]
        if missing:
            raise KeyError(f"{self.name} missing inputs: {', '.join(missing)}")


@dataclass
class Dag:
    nodes: list[DagNode] = field(default_factory=list)

    def run(self, seed_context: DagContext | None = None) -> DagContext:
        context: DagContext = dict(seed_context or {})
        for node in self.nodes:
            node._require(context)
            updates = node.run(context)
            context.update(updates)
        return context


@dataclass(frozen=True)
class HyperedgeCandidateRecord:
    edge_type: str
    input_nodes: list[str]
    output_nodes: list[str]
    support_nodes: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class HypergraphCandidateIndex:
    records: list[HyperedgeCandidateRecord]


@dataclass(frozen=True)
class UpdateEventRecord:
    event_id: str
    event_type: str
    input_ids: list[str]
    output_ids: list[str]
    state_ids: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class UpdateEventIndex:
    records: list[UpdateEventRecord]


@dataclass(frozen=True)
class CausalDependencyRecord:
    dependency_id: str
    cause_event_id: str
    effect_event_id: str
    dependency_type: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CausalGraphIndex:
    records: list[CausalDependencyRecord]


@dataclass(frozen=True)
class ProductionPointerRecord:
    pointer_id: str
    ray_id: str
    stem_path: str
    current_state_id: str
    canonical_path: str | None
    rewrite_rule: str
    recursion_depth: int
    recursion_limit: int
    can_descend: bool
    next_edge_types: list[str]
    allowed_outputs_ranked: list[dict[str, Any]]
    preferred_output: str | None
    safety_bounds: dict[str, Any]
    target_domain: str
    target_confidence: float
    metadata: dict[str, Any]


def _pointer_digest(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class BuildSandpileModelNode(DagNode):
    sink_key: str = "sink"

    def __init__(self, graph_key: str = "graph", sink_key: str = "sink", output_key: str = "sandpile_model"):
        super().__init__(
            name="build_sandpile_model",
            inputs=[graph_key, sink_key],
            outputs=[output_key],
        )
        self.graph_key = graph_key
        self.sink_key = sink_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        return {
            self.output_key: SandpileModel(
                graph=context[self.graph_key],
                sink=context[self.sink_key],
            )
        }


@dataclass
class ComputeSandpileGroupNode(DagNode):
    default_enabled: bool = True

    def __init__(
        self,
        model_key: str = "sandpile_model",
        output_key: str = "sandpile_group",
        default_enabled: bool = True,
    ):
        super().__init__(
            name="compute_sandpile_group",
            inputs=[model_key],
            outputs=[output_key],
        )
        self.model_key = model_key
        self.output_key = output_key
        self.default_enabled = default_enabled

    def run(self, context: DagContext) -> DagContext:
        if not bool(context.get("compute_group_invariant", self.default_enabled)):
            return {}
        model: SandpileModel = context[self.model_key]
        laplacian = model.laplacian()
        invariant = SandpileGroupInvariant.from_reduced_laplacian(
            laplacian.reduced_matrix,
            metadata={"sink": model.sink, "vertex_order": laplacian.reduced_vertex_order},
        )
        return {self.output_key: invariant, "laplacian": laplacian}


@dataclass
class RebindConfigurationNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        model_key: str = "sandpile_model",
        output_key: str = "configuration",
    ):
        super().__init__(
            name="rebind_configuration",
            inputs=[configuration_key, model_key],
            outputs=[output_key],
        )
        self.configuration_key = configuration_key
        self.model_key = model_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        configuration: SandpileConfiguration = context[self.configuration_key]
        model: SandpileModel = context[self.model_key]
        rebound = rebind_configuration(configuration, model)
        return {self.output_key: rebound}


@dataclass
class ProjectSandpileToImageNode(DagNode):
    def __init__(
        self,
        group_key: str = "sandpile_group",
        workspace_key: str = "workspace",
        output_key: str = "image_surface",
        state_name: str = "sandpile_group",
    ):
        super().__init__(
            name="project_sandpile_to_image",
            inputs=[group_key, workspace_key],
            outputs=[output_key, "image_path"],
        )
        self.group_key = group_key
        self.workspace_key = workspace_key
        self.output_key = output_key
        self.state_name = state_name

    def run(self, context: DagContext) -> DagContext:
        invariant: SandpileGroupInvariant = context[self.group_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        width = max(1, len(invariant.invariant_factors))
        path = workspace.initialize_surface(
            self.state_name,
            width=width,
            height=1,
            fill=0,
            magic="P2",
            max_value=max(invariant.invariant_factors, default=1),
        )
        surface = ImageStateSurface.from_path(path)
        if invariant.invariant_factors:
            for index, value in enumerate(invariant.invariant_factors):
                surface.write_value(index, 0, value)
        workspace.snapshot(self.state_name, surface)
        return {self.output_key: surface, "image_path": path}


class GraphToSandpilePipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                BuildSandpileModelNode(),
                ComputeSandpileGroupNode(),
                ProjectSandpileToImageNode(),
            ]
        )


@dataclass
class ProjectConfigurationToImageNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        workspace_key: str = "workspace",
        output_key: str = "image_surface",
        state_name: str = "sandpile_state",
    ):
        super().__init__(
            name="project_configuration_to_image",
            inputs=[configuration_key, workspace_key],
            outputs=[output_key, "image_path"],
        )
        self.configuration_key = configuration_key
        self.workspace_key = workspace_key
        self.output_key = output_key
        self.state_name = state_name

    def run(self, context: DagContext) -> DagContext:
        configuration = context[self.configuration_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        width = int(context["grid_cols"])
        height = int(context["grid_rows"])
        max_value = max(max(configuration.chips.values(), default=0), 1)
        path = workspace.initialize_surface(
            self.state_name,
            width=width,
            height=height,
            fill=0,
            magic="P2",
            max_value=max_value,
        )
        surface = ImageStateSurface.from_path(path)
        vertex_layout = context["vertex_layout"]
        surface.overlay_configuration(configuration, vertex_layout)
        workspace.snapshot(self.state_name, surface)
        archived_state = workspace.archive_surface(surface, branch=(), prefix=self.state_name)
        return {
            self.output_key: surface,
            "image_path": path,
            "archived_state": archived_state,
        }


@dataclass
class AddGrainNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        output_key: str = "propagated_configuration",
        vertex_key: str = "addition_vertex",
        amount_key: str = "addition_amount",
    ):
        super().__init__(
            name="add_grain",
            inputs=[configuration_key],
            outputs=[output_key],
        )
        self.configuration_key = configuration_key
        self.output_key = output_key
        self.vertex_key = vertex_key
        self.amount_key = amount_key

    def run(self, context: DagContext) -> DagContext:
        configuration: SandpileConfiguration = context[self.configuration_key]
        target_vertex = context.get(self.vertex_key)
        if target_vertex is None:
            graph_metadata = configuration.model.graph.metadata
            target_vertex = graph_metadata.get("center_vertex")
        if target_vertex is None:
            active_vertices = configuration.model.active_vertices
            if not active_vertices:
                raise ValueError("cannot add a grain to an empty active vertex set")
            target_vertex = active_vertices[0]

        amount = int(context.get(self.amount_key, 1))
        propagated = add_chip(configuration, target_vertex, amount=amount)
        return {
            self.output_key: propagated,
            self.vertex_key: target_vertex,
            self.amount_key: amount,
        }


@dataclass
class StabilizeConfigurationNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        output_key: str = "stabilized_configuration",
        result_key: str = "stabilization",
    ):
        super().__init__(
            name="stabilize_configuration",
            inputs=[configuration_key],
            outputs=[output_key, result_key],
        )
        self.configuration_key = configuration_key
        self.output_key = output_key
        self.result_key = result_key

    def run(self, context: DagContext) -> DagContext:
        configuration: SandpileConfiguration = context[self.configuration_key]
        result = stabilize_configuration(configuration)
        return {
            self.output_key: result.stabilized,
            self.result_key: result,
        }


@dataclass
class ExtractSandpileFeaturesNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        stabilization_key: str = "stabilization",
        group_key: str = "sandpile_group",
        output_key: str = "sandpile_features",
    ):
        super().__init__(
            name="extract_sandpile_features",
            inputs=[configuration_key],
            outputs=[output_key],
        )
        self.configuration_key = configuration_key
        self.stabilization_key = stabilization_key
        self.group_key = group_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        configuration: SandpileConfiguration = context[self.configuration_key]
        stabilization: StabilizationResult | None = context.get(self.stabilization_key)
        features = sandpile_features(configuration, stabilization)
        invariant: SandpileGroupInvariant | None = context.get(self.group_key)
        if invariant is not None:
            features.update(
                {
                    "sandpile_group_order": invariant.order,
                    "sandpile_group_rank": invariant.rank,
                    "sandpile_group_invariant_factors": list(invariant.invariant_factors),
                    "sandpile_group_sylow": dict(invariant.sylow),
                }
            )
        return {self.output_key: features}


@dataclass
class EmitOntologyRecordNode(DagNode):
    def __init__(
        self,
        features_key: str = "sandpile_features",
        configuration_key: str = "configuration",
        graph_key: str = "graph",
        output_key: str = "ontology_record",
    ):
        super().__init__(
            name="emit_ontology_record",
            inputs=[features_key, configuration_key, graph_key],
            outputs=[output_key],
        )
        self.features_key = features_key
        self.configuration_key = configuration_key
        self.graph_key = graph_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        features = dict(context[self.features_key])
        configuration: SandpileConfiguration = context[self.configuration_key]
        graph: UndirectedGraph = context[self.graph_key]
        record = {
            "entity": "sandpile_state",
            "graph_family": graph.metadata.get("graph_family", "undirected"),
            "graph_parameters": dict(graph.metadata),
            "sink": configuration.model.sink,
            "stabilized_configuration_signature": configuration_signature(configuration),
            "features": features,
        }
        return {self.output_key: record}


@dataclass
class DecodeTernLSBNode(DagNode):
    def __init__(
        self,
        surface_key: str = "carrier_surface",
        output_key: str = "decoded_ternlsb_program",
        cell_size_key: str = "ternlsb_cell_size",
        alphabet_key: str = "ternlsb_alphabet",
    ):
        super().__init__(
            name="decode_ternlsb",
            inputs=[surface_key],
            outputs=[output_key],
        )
        self.surface_key = surface_key
        self.output_key = output_key
        self.cell_size_key = cell_size_key
        self.alphabet_key = alphabet_key

    def run(self, context: DagContext) -> DagContext:
        surface: ImageStateSurface = context[self.surface_key]
        program = decode_ternlsb_program(
            surface,
            alphabet=str(context.get(self.alphabet_key, "ASN")),
            cell_size=int(context.get(self.cell_size_key, 1)),
        )
        return {
            self.output_key: program,
            self.cell_size_key: program.cell_size,
            self.alphabet_key: program.alphabet,
        }


@dataclass
class ApplyTernLSBProgramNode(DagNode):
    def __init__(
        self,
        configuration_key: str = "configuration",
        program_key: str = "decoded_ternlsb_program",
        output_key: str = "ternlsb_configuration",
        execution_key: str = "ternlsb_execution",
        target_vertex_key: str = "ternlsb_target_vertex",
    ):
        super().__init__(
            name="apply_ternlsb_program",
            inputs=[configuration_key, program_key],
            outputs=[output_key, execution_key],
        )
        self.configuration_key = configuration_key
        self.program_key = program_key
        self.output_key = output_key
        self.execution_key = execution_key
        self.target_vertex_key = target_vertex_key

    def run(self, context: DagContext) -> DagContext:
        configuration: SandpileConfiguration = context[self.configuration_key]
        program: TernLSBProgram = context[self.program_key]
        target_vertex = context.get(self.target_vertex_key)
        next_configuration, execution = apply_ternlsb_program(
            configuration,
            program,
            target_vertex=target_vertex,
        )
        return {
            self.output_key: next_configuration,
            self.execution_key: execution,
            self.target_vertex_key: execution.metadata["target_vertex"],
        }


@dataclass
class EncodeTernLSBNode(DagNode):
    def __init__(
        self,
        surface_key: str = "cycle_surface",
        program_key: str = "decoded_ternlsb_program",
        workspace_key: str = "workspace",
        output_key: str = "stego_surface",
        image_path_key: str = "stego_image_path",
        state_name: str = "ternlsb_carrier_state",
    ):
        super().__init__(
            name="encode_ternlsb",
            inputs=[surface_key, program_key, workspace_key],
            outputs=[output_key, image_path_key],
        )
        self.surface_key = surface_key
        self.program_key = program_key
        self.workspace_key = workspace_key
        self.output_key = output_key
        self.image_path_key = image_path_key
        self.state_name = state_name

    def run(self, context: DagContext) -> DagContext:
        surface: ImageStateSurface = context[self.surface_key]
        program: TernLSBProgram = context[self.program_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        encoded = encode_ternlsb_program(
            surface,
            instructions=program.instructions,
            alphabet=program.alphabet,
            cell_size=program.cell_size,
        )
        image_path = workspace.snapshot(self.state_name, encoded)
        return {
            self.output_key: encoded,
            self.image_path_key: image_path,
        }


@dataclass
class BuildStegoCycleEventIndexNode(DagNode):
    def __init__(
        self,
        carrier_key: str = "carrier_surface",
        program_key: str = "decoded_ternlsb_program",
        execution_key: str = "ternlsb_execution",
        cycle_surface_key: str = "cycle_surface",
        stego_surface_key: str = "stego_surface",
        image_path_key: str = "image_path",
        stego_image_path_key: str = "stego_image_path",
        output_key: str = "stego_update_event_index",
    ):
        super().__init__(
            name="build_stego_cycle_event_index",
            inputs=[
                carrier_key,
                program_key,
                execution_key,
                cycle_surface_key,
                stego_surface_key,
                image_path_key,
                stego_image_path_key,
            ],
            outputs=[output_key],
        )
        self.carrier_key = carrier_key
        self.program_key = program_key
        self.execution_key = execution_key
        self.cycle_surface_key = cycle_surface_key
        self.stego_surface_key = stego_surface_key
        self.image_path_key = image_path_key
        self.stego_image_path_key = stego_image_path_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        carrier_surface: ImageStateSurface = context[self.carrier_key]
        program: TernLSBProgram = context[self.program_key]
        execution: TernLSBExecutionRecord = context[self.execution_key]
        cycle_surface: ImageStateSurface = context[self.cycle_surface_key]
        stego_surface: ImageStateSurface = context[self.stego_surface_key]
        cycle_image_path = Path(context[self.image_path_key])
        stego_image_path = Path(context[self.stego_image_path_key])

        carrier_signature = surface_signature(carrier_surface)
        cycle_signature = surface_signature(cycle_surface)
        stego_signature = surface_signature(stego_surface)
        initial_configuration_signature = execution.initial_signature
        final_configuration_signature = execution.final_signature
        instruction_digest = _pointer_digest(program.instructions, program.alphabet, str(program.cell_size))

        decode_event = UpdateEventRecord(
            event_id=f"evt_{_pointer_digest('ternlsb_decode', carrier_signature, instruction_digest)}",
            event_type="ternlsb_decode",
            input_ids=[carrier_signature],
            output_ids=[instruction_digest],
            state_ids=[carrier_signature],
            metadata={
                "instructions": program.instructions,
                "alphabet": program.alphabet,
                "cell_size": program.cell_size,
                "capacity": program.capacity,
            },
        )
        apply_event = UpdateEventRecord(
            event_id=f"evt_{_pointer_digest('ternlsb_apply', instruction_digest, final_configuration_signature)}",
            event_type="ternlsb_apply",
            input_ids=[instruction_digest, initial_configuration_signature],
            output_ids=[final_configuration_signature],
            state_ids=[initial_configuration_signature, final_configuration_signature],
            metadata={
                "instruction_count": len(program.instructions),
                "total_topples": execution.total_topples,
                "step_count": len(execution.steps),
                "target_vertex": execution.metadata.get("target_vertex"),
            },
        )
        project_event = UpdateEventRecord(
            event_id=f"evt_{_pointer_digest('ternlsb_project', final_configuration_signature, cycle_signature)}",
            event_type="ternlsb_project",
            input_ids=[final_configuration_signature],
            output_ids=[cycle_signature],
            state_ids=[cycle_signature],
            metadata={
                "image_path": str(cycle_image_path),
            },
        )
        encode_event = UpdateEventRecord(
            event_id=f"evt_{_pointer_digest('ternlsb_encode', cycle_signature, stego_signature)}",
            event_type="ternlsb_encode",
            input_ids=[cycle_signature, instruction_digest],
            output_ids=[stego_signature],
            state_ids=[cycle_signature, stego_signature],
            metadata={
                "image_path": str(stego_image_path),
                "instructions": program.instructions,
                "alphabet": program.alphabet,
                "cell_size": program.cell_size,
            },
        )
        return {
            self.output_key: UpdateEventIndex(
                records=[decode_event, apply_event, project_event, encode_event]
            )
        }


@dataclass
class ReviewArchivedStateChainNode(DagNode):
    def __init__(
        self,
        stem_path_key: str = "stem_path",
        output_key: str = "chain_review",
    ):
        super().__init__(
            name="review_archived_state_chain",
            inputs=[stem_path_key],
            outputs=[output_key],
        )
        self.stem_path_key = stem_path_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = context[self.stem_path_key]
        review = review_archived_state_chain(stem_path)
        return {self.output_key: review}


@dataclass
class GenerateRecursiveSubtreeNode(DagNode):
    def __init__(
        self,
        stem_path_key: str = "stem_path",
        workspace_key: str = "workspace",
        output_key: str = "generated_states",
        summary_key: str = "tree_summary",
    ):
        super().__init__(
            name="generate_recursive_subtree",
            inputs=[stem_path_key, workspace_key],
            outputs=[output_key, summary_key],
        )
        self.stem_path_key = stem_path_key
        self.workspace_key = workspace_key
        self.output_key = output_key
        self.summary_key = summary_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = context[self.stem_path_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        generated = generate_successor_subtree_from_stem(
            workspace=workspace,
            stem_path=stem_path,
            successor_mode=context.get("successor_mode", "center"),
            successor_seed=context.get("successor_seed"),
            branch_policy=context.get("branch_policy"),
        )
        summary = summarize_archived_tree(generated)
        return {
            self.output_key: generated,
            self.summary_key: summary,
        }


@dataclass
class DeduplicateStateTreeNode(DagNode):
    def __init__(
        self,
        workspace_key: str = "workspace",
        output_key: str = "dedupe_summary",
    ):
        super().__init__(
            name="deduplicate_state_tree",
            inputs=[workspace_key],
            outputs=[output_key],
        )
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        workspace: SimulationWorkspace = context[self.workspace_key]
        summary = deduplicate_state_tree(workspace.root)
        return {self.output_key: summary}


@dataclass
class BuildCanonicalStateIndexNode(DagNode):
    def __init__(
        self,
        workspace_key: str = "workspace",
        output_key: str = "canonical_state_index",
    ):
        super().__init__(
            name="build_canonical_state_index",
            inputs=[workspace_key],
            outputs=[output_key],
        )
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        workspace: SimulationWorkspace = context[self.workspace_key]
        index = build_canonical_state_index(workspace.root)
        return {self.output_key: index}


@dataclass
class BuildUpdateEventIndexNode(DagNode):
    def __init__(
        self,
        stem_path_key: str = "stem_path",
        chain_review_key: str = "chain_review",
        generated_states_key: str = "generated_states",
        dedupe_key: str = "dedupe_summary",
        output_key: str = "update_event_index",
    ):
        super().__init__(
            name="build_update_event_index",
            inputs=[stem_path_key, chain_review_key, generated_states_key, dedupe_key],
            outputs=[output_key],
        )
        self.stem_path_key = stem_path_key
        self.chain_review_key = chain_review_key
        self.generated_states_key = generated_states_key
        self.dedupe_key = dedupe_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = Path(context[self.stem_path_key])
        chain_review: ChainReview = context[self.chain_review_key]
        generated_states: list[ArchivedState] = list(context[self.generated_states_key])
        dedupe_summary: DedupeSummary = context[self.dedupe_key]
        records: list[UpdateEventRecord] = []

        stem_chain = load_archived_state_chain(stem_path)
        for index, step in enumerate(chain_review.steps[1:], start=1):
            previous = chain_review.steps[index - 1]
            event_id = f"evt_{_pointer_digest('chain', previous.state_id, step.state_id, str(step.lineage_depth))}"
            records.append(
                UpdateEventRecord(
                    event_id=event_id,
                    event_type="chain_transition",
                    input_ids=[previous.state_id],
                    output_ids=[step.state_id],
                    state_ids=[previous.state_id, step.state_id],
                    metadata={
                        "from_depth": previous.lineage_depth,
                        "to_depth": step.lineage_depth,
                        "changed_cells": step.changed_cells_from_previous,
                        "repeated_signature": step.repeated_signature,
                        "stem_root_state_id": stem_chain.states[0].state_id if stem_chain.states else None,
                    },
                )
            )

        for state in generated_states:
            event_id = f"evt_{_pointer_digest('grow', state.parent_state_id or 'root', state.state_id, state.signature)}"
            records.append(
                UpdateEventRecord(
                    event_id=event_id,
                    event_type="subtree_generation",
                    input_ids=[state.parent_state_id] if state.parent_state_id is not None else [],
                    output_ids=[state.state_id],
                    state_ids=[value for value in [state.parent_state_id, state.state_id] if value is not None],
                    metadata={
                        "lineage_depth": state.lineage_depth,
                        "topples": state.topples,
                        "signature": state.signature,
                        "branch": list(state.branch),
                        "image_path": str(state.image_path),
                    },
                )
            )

        for reference in dedupe_summary.references:
            event_id = f"evt_{_pointer_digest('collapse', str(reference.image_path), str(reference.canonical_path), reference.signature)}"
            records.append(
                UpdateEventRecord(
                    event_id=event_id,
                    event_type="canonical_collapse",
                    input_ids=[str(reference.image_path)],
                    output_ids=[str(reference.canonical_path)],
                    state_ids=[],
                    metadata={
                        "signature": reference.signature,
                        "reference_path": str(reference.image_path.with_suffix(reference.image_path.suffix + '.ref')),
                    },
                )
            )

        return {self.output_key: UpdateEventIndex(records=records)}


@dataclass
class BuildCausalGraphIndexNode(DagNode):
    def __init__(
        self,
        update_event_key: str = "update_event_index",
        output_key: str = "causal_graph_index",
    ):
        super().__init__(
            name="build_causal_graph_index",
            inputs=[update_event_key],
            outputs=[output_key],
        )
        self.update_event_key = update_event_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        update_event_index: UpdateEventIndex = context[self.update_event_key]
        records = list(update_event_index.records)
        dependencies: list[CausalDependencyRecord] = []

        state_to_generation_event: dict[str, str] = {}
        chain_events: list[UpdateEventRecord] = []
        collapse_events: list[UpdateEventRecord] = []

        for record in records:
            if record.event_type == "subtree_generation":
                for state_id in record.output_ids:
                    state_to_generation_event[state_id] = record.event_id
            elif record.event_type == "chain_transition":
                chain_events.append(record)
            elif record.event_type == "canonical_collapse":
                collapse_events.append(record)

        for previous, current in zip(chain_events, chain_events[1:]):
            dependency_id = f"dep_{_pointer_digest('chain', previous.event_id, current.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=previous.event_id,
                    effect_event_id=current.event_id,
                    dependency_type="chain_order",
                    metadata={},
                )
            )

        for record in records:
            if record.event_type != "subtree_generation":
                continue
            if not record.input_ids:
                continue
            parent_state_id = record.input_ids[0]
            parent_event_id = state_to_generation_event.get(parent_state_id)
            if parent_event_id is None:
                continue
            dependency_id = f"dep_{_pointer_digest('grow', parent_event_id, record.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=parent_event_id,
                    effect_event_id=record.event_id,
                    dependency_type="growth_from_parent_state",
                    metadata={"parent_state_id": parent_state_id},
                )
            )

        for record in collapse_events:
            collapsed_path = record.input_ids[0] if record.input_ids else ""
            collapsed_state_id = Path(collapsed_path).stem.removeprefix("sandpile_state") if collapsed_path else ""
            source_event_id = state_to_generation_event.get(collapsed_state_id)
            if source_event_id is None:
                continue
            dependency_id = f"dep_{_pointer_digest('collapse', source_event_id, record.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=source_event_id,
                    effect_event_id=record.event_id,
                    dependency_type="collapse_of_generated_state",
                    metadata={"state_id": collapsed_state_id},
                )
            )

        return {self.output_key: CausalGraphIndex(records=dependencies)}


@dataclass
class BuildHypergraphCandidateIndexNode(DagNode):
    def __init__(
        self,
        stem_path_key: str = "stem_path",
        chain_review_key: str = "chain_review",
        generated_states_key: str = "generated_states",
        canonical_index_key: str = "canonical_state_index",
        dedupe_key: str = "dedupe_summary",
        output_key: str = "hypergraph_candidate_index",
    ):
        super().__init__(
            name="build_hypergraph_candidate_index",
            inputs=[stem_path_key, chain_review_key, generated_states_key, canonical_index_key, dedupe_key],
            outputs=[output_key],
        )
        self.stem_path_key = stem_path_key
        self.chain_review_key = chain_review_key
        self.generated_states_key = generated_states_key
        self.canonical_index_key = canonical_index_key
        self.dedupe_key = dedupe_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = context[self.stem_path_key]
        chain_review: ChainReview = context[self.chain_review_key]
        generated_states: list[ArchivedState] = list(context[self.generated_states_key])
        canonical_index: CanonicalStateIndex = context[self.canonical_index_key]
        dedupe_summary: DedupeSummary = context[self.dedupe_key]

        signature_to_canonical = {
            record.signature: str(record.canonical_path)
            for record in canonical_index.records
        }
        path_to_canonical = {
            str(resolve_state_image_path(reference.image_path).resolve()): str(reference.canonical_path.resolve())
            for reference in dedupe_summary.references
        }

        def canonical_for_signature(signature: str) -> str | None:
            return signature_to_canonical.get(signature)

        def canonical_for_image(image_path: Path) -> str:
            resolved = str(resolve_state_image_path(image_path).resolve())
            return path_to_canonical.get(resolved, resolved)

        records: list[HyperedgeCandidateRecord] = []
        stem_chain = load_archived_state_chain(stem_path)

        for index, step in enumerate(chain_review.steps[1:], start=1):
            previous = chain_review.steps[index - 1]
            records.append(
                HyperedgeCandidateRecord(
                    edge_type="stem_chain_transition",
                    input_nodes=[previous.state_id],
                    output_nodes=[step.state_id],
                    support_nodes=[
                        value
                        for value in [
                            canonical_for_signature(previous.signature),
                            canonical_for_signature(step.signature),
                        ]
                        if value is not None
                    ],
                    metadata={
                        "from_depth": previous.lineage_depth,
                        "to_depth": step.lineage_depth,
                        "changed_cells": step.changed_cells_from_previous,
                        "repeated_signature": step.repeated_signature,
                    },
                )
            )

        for state in generated_states:
            support_nodes = [canonical_for_image(state.image_path)]
            if state.parent_state_id is not None:
                records.append(
                    HyperedgeCandidateRecord(
                        edge_type="recursive_generation",
                        input_nodes=[state.parent_state_id],
                        output_nodes=[state.state_id],
                        support_nodes=support_nodes,
                        metadata={
                            "lineage_depth": state.lineage_depth,
                            "topples": state.topples,
                            "signature": state.signature,
                            "branch": list(state.branch),
                        },
                    )
                )

        for reference in dedupe_summary.references:
            records.append(
                HyperedgeCandidateRecord(
                    edge_type="canonical_collapse",
                    input_nodes=[str(reference.image_path)],
                    output_nodes=[str(reference.canonical_path)],
                    support_nodes=[reference.signature],
                    metadata={
                        "reference_path": str(reference.image_path.with_suffix(reference.image_path.suffix + ".ref")),
                    },
                )
            )

        if stem_chain.states:
            stem_root = stem_chain.states[0]
            stem_leaf = stem_chain.states[-1]
            records.append(
                HyperedgeCandidateRecord(
                    edge_type="stem_scope",
                    input_nodes=[stem_root.state_id],
                    output_nodes=[stem_leaf.state_id],
                    support_nodes=[
                        value
                        for value in [
                            canonical_for_signature(stem_root.signature),
                            canonical_for_signature(stem_leaf.signature),
                        ]
                        if value is not None
                    ],
                    metadata={
                        "path_length": len(stem_chain.states),
                        "repeated_signatures": list(chain_review.repeated_signatures),
                    },
                )
            )

        return {self.output_key: HypergraphCandidateIndex(records=records)}


@dataclass
class BuildProductionPointerNode(DagNode):
    def __init__(
        self,
        stem_path_key: str = "stem_path",
        workspace_key: str = "workspace",
        canonical_index_key: str = "canonical_state_index",
        hypergraph_key: str = "hypergraph_candidate_index",
        output_key: str = "production_pointer",
        manifest_key: str = "production_pointer_manifest_path",
    ):
        super().__init__(
            name="build_production_pointer",
            inputs=[stem_path_key, workspace_key, canonical_index_key, hypergraph_key],
            outputs=[output_key, manifest_key],
        )
        self.stem_path_key = stem_path_key
        self.workspace_key = workspace_key
        self.canonical_index_key = canonical_index_key
        self.hypergraph_key = hypergraph_key
        self.output_key = output_key
        self.manifest_key = manifest_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = Path(context[self.stem_path_key])
        workspace: SimulationWorkspace = context[self.workspace_key]
        canonical_index: CanonicalStateIndex = context[self.canonical_index_key]
        hypergraph_index: HypergraphCandidateIndex = context[self.hypergraph_key]
        chain = load_archived_state_chain(stem_path)
        if not chain.states:
            raise ValueError("cannot build a production pointer from an empty stem chain")

        current_state = chain.stem
        current_signature = current_state.signature
        canonical_path = next(
            (str(record.canonical_path) for record in canonical_index.records if record.signature == current_signature),
            None,
        )

        generated_edges = [
            record
            for record in hypergraph_index.records
            if record.edge_type == "recursive_generation" and current_state.state_id in record.input_nodes
        ]
        next_edge_types = sorted({record.edge_type for record in hypergraph_index.records})
        ranked_outputs: list[dict[str, Any]] = []
        seen_outputs: set[str] = set()
        for record in sorted(
            generated_edges,
            key=lambda edge: (
                -int(edge.metadata.get("topples", 0)),
                int(edge.metadata.get("lineage_depth", current_state.lineage_depth)),
                edge.output_nodes[0] if edge.output_nodes else "",
            ),
        ):
            for output in record.output_nodes:
                if output in seen_outputs:
                    continue
                seen_outputs.add(output)
                ranked_outputs.append(
                    {
                        "state_id": output,
                        "edge_type": record.edge_type,
                        "lineage_depth": int(record.metadata.get("lineage_depth", current_state.lineage_depth)),
                        "topples": int(record.metadata.get("topples", 0)),
                        "signature": str(record.metadata.get("signature", "")),
                        "branch": list(record.metadata.get("branch", [])),
                    }
                )
        preferred_output = ranked_outputs[0]["state_id"] if ranked_outputs else None

        branch_policy = context.get("branch_policy")
        recursion_limit = int(getattr(branch_policy, "max_depth", 16))
        rewrite_rule = context.get("rewrite_rule")
        rewrite_rule_name = getattr(rewrite_rule, "name", None) or str(context.get("successor_mode", "center"))
        can_descend = current_state.lineage_depth < recursion_limit
        ray_id = f"ray_{_pointer_digest(str(chain.states[0].image_path), current_state.state_id, rewrite_rule_name)}"
        pointer_id = f"pp_{_pointer_digest(ray_id, current_state.signature, preferred_output or '')}"

        pointer = ProductionPointerRecord(
            pointer_id=pointer_id,
            ray_id=ray_id,
            stem_path=str(stem_path),
            current_state_id=current_state.state_id,
            canonical_path=canonical_path,
            rewrite_rule=rewrite_rule_name,
            recursion_depth=current_state.lineage_depth,
            recursion_limit=recursion_limit,
            can_descend=can_descend,
            next_edge_types=next_edge_types,
            allowed_outputs_ranked=ranked_outputs,
            preferred_output=preferred_output,
            safety_bounds={
                "max_depth": recursion_limit,
                "current_depth": current_state.lineage_depth,
                "depth_remaining": max(0, recursion_limit - current_state.lineage_depth),
                "has_generated_children": bool(generated_edges),
                "ray_locked": True,
            },
            target_domain="supersingular_isogeny",
            target_confidence=0.0,
            metadata={
                "signature": current_signature,
                "branch": list(current_state.branch),
                "chain_length": len(chain.states),
                "hyperedge_count": len(hypergraph_index.records),
                "stem_root_state_id": chain.states[0].state_id,
            },
        )
        manifest_path = workspace.root / "runs" / f"{pointer.pointer_id}.json"
        manifest_path.write_text(json.dumps(asdict(pointer), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: pointer, self.manifest_key: manifest_path}


class RegularSandpileStatePipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                ProjectConfigurationToImageNode(),
            ]
        )


class GraphSandpileOntologyPipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                BuildSandpileModelNode(),
                RebindConfigurationNode(),
                ComputeSandpileGroupNode(default_enabled=False),
                AddGrainNode(configuration_key="configuration", output_key="propagated_configuration"),
                StabilizeConfigurationNode(
                    configuration_key="propagated_configuration",
                    output_key="stabilized_configuration",
                    result_key="stabilization",
                ),
                ExtractSandpileFeaturesNode(
                    configuration_key="propagated_configuration",
                    stabilization_key="stabilization",
                ),
                ProjectConfigurationToImageNode(
                    configuration_key="stabilized_configuration",
                    output_key="image_surface",
                    state_name="sandpile_state",
                ),
                EmitOntologyRecordNode(
                    features_key="sandpile_features",
                    configuration_key="stabilized_configuration",
                    graph_key="graph",
                ),
            ]
        )


class StegoSandpileCyclePipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                DecodeTernLSBNode(),
                ApplyTernLSBProgramNode(),
                ProjectConfigurationToImageNode(
                    configuration_key="ternlsb_configuration",
                    output_key="cycle_surface",
                    state_name="ternlsb_cycle_state",
                ),
                EncodeTernLSBNode(),
                BuildStegoCycleEventIndexNode(),
            ]
        )


class RecursiveStateTreePipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                ReviewArchivedStateChainNode(),
                GenerateRecursiveSubtreeNode(),
                DeduplicateStateTreeNode(),
                BuildCanonicalStateIndexNode(),
                BuildUpdateEventIndexNode(),
                BuildCausalGraphIndexNode(),
                BuildHypergraphCandidateIndexNode(),
                BuildProductionPointerNode(),
            ]
        )


def make_workspace(path: str | Path) -> SimulationWorkspace:
    return SimulationWorkspace.create(path)


def seed_graph_context(
    graph: UndirectedGraph,
    sink: str,
    workspace_root: str | Path,
) -> DagContext:
    return {
        "compute_group_invariant": True,
        "graph": graph,
        "sink": sink,
        "workspace": SimulationWorkspace.create(workspace_root),
    }
