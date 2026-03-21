from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .compiled import CompiledWorkspaceIndex, build_compiled_workspace_index
from .expert import build_expert_assessment, ExpertAssessmentRecord
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
from .initialization import build_startup_sequence, StartupInitializationVector, StartupSequence
from .memristor import (
    build_memristor_map,
    integrate_ternlsb_into_memristor_map,
    MemristorIntegrationRecord,
    MemristorMapRecord,
)
from .recrystallization import build_recrystallization, RecrystallizationRecord
from .oxfoi import (
    build_oxfoi_expression,
    build_triton_instruction,
    build_triton_state,
    execute_triton_instruction,
    evaluate_oxfoi_expression,
    OxfoiEvaluationRecord,
    OxfoiExpressionRecord,
    TritonOxfoiExecutionRecord,
    TritonOxfoiInstructionRecord,
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
from .programs import ProgramDescription, describe_ternlsb_execution
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


@dataclass(frozen=True)
class InitializationVectorRecord:
    seed_path: str
    prefix: str
    global_recursive_limit: int
    materialized_recursive_steps: int
    checkpoint_interval_steps: int
    persisted_checkpoint_count: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MachineStateRecord:
    machine_id: str
    init_origin: str
    current_state_id: str | None
    startup_surface_count: int
    startup_checkpoint_count: int
    startup_event_count: int
    oxfoi_expression_id: str | None
    oxfoi_transition_id: str | None
    oxfoi_field_domain: str | None
    oxfoi_instruction_width_words: int | None
    memristor_map_id: str | None
    memristor_lattice_family: str | None
    memristor_modulated_site_count: int
    triton_instruction_id: str | None
    triton_instruction_kind: str | None
    triton_instruction_width_words: int | None
    triton_field_domain: str | None
    triton_state_id: str | None
    recrystallization_id: str | None
    recrystallized_state_id: str | None
    recrystallization_source: str | None
    production_pointer_id: str | None
    target_domain: str | None
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
class BuildInitializationVectorRecordNode(DagNode):
    def __init__(
        self,
        vector_key: str = "initialization_vector",
        output_key: str = "initialization_vector_record",
    ):
        super().__init__(
            name="build_initialization_vector_record",
            inputs=[vector_key],
            outputs=[output_key],
        )
        self.vector_key = vector_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        vector: StartupInitializationVector = context[self.vector_key]
        record = InitializationVectorRecord(
            seed_path=str(vector.seed_path),
            prefix=vector.prefix,
            global_recursive_limit=int(vector.global_recursive_limit),
            materialized_recursive_steps=int(vector.materialized_recursive_steps),
            checkpoint_interval_steps=int(vector.checkpoint_interval_steps),
            persisted_checkpoint_count=int(vector.persisted_frame_count),
            metadata={
                "recursion_steps_per_checkpoint": int(vector.recursion_steps_per_frame),
            },
        )
        return {self.output_key: record}


@dataclass
class BuildStartupSequenceNode(DagNode):
    def __init__(
        self,
        initialization_vector_key: str = "initialization_vector",
        workspace_root_key: str = "workspace_root",
        output_key: str = "startup_sequence",
    ):
        super().__init__(
            name="build_startup_sequence",
            inputs=[initialization_vector_key],
            outputs=[output_key],
        )
        self.initialization_vector_key = initialization_vector_key
        self.workspace_root_key = workspace_root_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        vector: StartupInitializationVector = context[self.initialization_vector_key]
        workspace_root = context.get(self.workspace_root_key)
        if workspace_root is None:
            workspace = context.get("workspace")
            if workspace is not None:
                workspace_root = getattr(workspace, "root", None)
        sequence = build_startup_sequence(
            vector=vector,
            workspace_root=workspace_root,
        )
        return {self.output_key: sequence}


@dataclass
class BuildOxfoiEvaluationNode(DagNode):
    def __init__(
        self,
        initialization_record_key: str = "initialization_vector_record",
        expression_key: str = "oxfoi_expression",
        output_key: str = "oxfoi_evaluation",
        pointer_key: str = "production_pointer",
        payload_key: str = "oxfoi_expression_payload",
        field_domain_key: str = "oxfoi_field_domain",
        instruction_width_key: str = "oxfoi_instruction_width_words",
        single_use_key: str = "oxfoi_single_use",
    ):
        super().__init__(
            name="build_oxfoi_evaluation",
            inputs=[initialization_record_key],
            outputs=[output_key, expression_key],
        )
        self.initialization_record_key = initialization_record_key
        self.expression_key = expression_key
        self.output_key = output_key
        self.pointer_key = pointer_key
        self.payload_key = payload_key
        self.field_domain_key = field_domain_key
        self.instruction_width_key = instruction_width_key
        self.single_use_key = single_use_key

    def run(self, context: DagContext) -> DagContext:
        initialization_record: InitializationVectorRecord = context[self.initialization_record_key]
        expression = context.get(self.expression_key)
        if expression is None:
            expression = build_oxfoi_expression(
                str(context.get(self.payload_key, "init.single_use")),
                field_domain=str(context.get(self.field_domain_key, "B")),
                instruction_width_words=int(context.get(self.instruction_width_key, 1)),
                single_use=bool(context.get(self.single_use_key, True)),
            )
        pointer: ProductionPointerRecord | None = context.get(self.pointer_key)
        evaluation = evaluate_oxfoi_expression(
            initialization_record,
            expression,
            pointer=pointer,
        )
        return {
            self.expression_key: expression,
            self.output_key: evaluation,
        }


@dataclass
class BuildTritonOxfoiExecutionNode(DagNode):
    def __init__(
        self,
        initialization_record_key: str = "initialization_vector_record",
        instruction_key: str = "triton_oxfoi_instruction",
        output_key: str = "triton_oxfoi_execution",
        instruction_kind_key: str = "triton_instruction_kind",
        instruction_arg_key: str = "triton_instruction_argument",
        field_domain_key: str = "triton_field_domain",
    ):
        super().__init__(
            name="build_triton_oxfoi_execution",
            inputs=[initialization_record_key],
            outputs=[output_key, instruction_key],
        )
        self.initialization_record_key = initialization_record_key
        self.instruction_key = instruction_key
        self.output_key = output_key
        self.instruction_kind_key = instruction_kind_key
        self.instruction_arg_key = instruction_arg_key
        self.field_domain_key = field_domain_key

    def run(self, context: DagContext) -> DagContext:
        initialization_record: InitializationVectorRecord = context[self.initialization_record_key]
        instruction = context.get(self.instruction_key)
        if instruction is None:
            instruction = build_triton_instruction(
                str(context.get(self.instruction_kind_key, "push")),
                argument=context.get(self.instruction_arg_key, 1),
                field_domain=str(context.get(self.field_domain_key, "B")),
            )
        input_state = context.get("triton_oxfoi_state")
        if input_state is None:
            input_state = build_triton_state(
                initialization_record,
                field_domain=instruction.field_domain,
            )
        execution = execute_triton_instruction(
            initialization_record,
            instruction,
            input_state=input_state,
        )
        return {
            self.instruction_key: instruction,
            self.output_key: execution,
            "triton_oxfoi_state": execution.output_state,
        }


@dataclass
class BuildMachineStateRecordNode(DagNode):
    def __init__(
        self,
        initialization_record_key: str = "initialization_vector_record",
        stem_path_key: str = "stem_path",
        startup_sequence_key: str = "startup_sequence",
        startup_event_key: str = "startup_event_index",
        startup_event_manifest_key: str = "startup_event_manifest_path",
        oxfoi_evaluation_key: str = "oxfoi_evaluation",
        oxfoi_event_key: str = "oxfoi_event_index",
        oxfoi_event_manifest_key: str = "oxfoi_event_manifest_path",
        memristor_map_key: str = "memristor_map",
        memristor_integration_key: str = "memristor_integration",
        triton_execution_key: str = "triton_oxfoi_execution",
        triton_event_key: str = "triton_oxfoi_event_index",
        triton_event_manifest_key: str = "triton_oxfoi_event_manifest_path",
        causal_graph_manifest_key: str = "causal_graph_manifest_path",
        hypergraph_manifest_key: str = "hypergraph_candidate_manifest_path",
        recrystallization_key: str = "recrystallization",
        recrystallization_manifest_key: str = "recrystallization_manifest_path",
        production_pointer_key: str = "production_pointer",
        production_pointer_manifest_key: str = "production_pointer_manifest_path",
        output_key: str = "machine_state_record",
    ):
        super().__init__(
            name="build_machine_state_record",
            inputs=[initialization_record_key],
            outputs=[output_key],
        )
        self.initialization_record_key = initialization_record_key
        self.stem_path_key = stem_path_key
        self.startup_sequence_key = startup_sequence_key
        self.startup_event_key = startup_event_key
        self.startup_event_manifest_key = startup_event_manifest_key
        self.oxfoi_evaluation_key = oxfoi_evaluation_key
        self.oxfoi_event_key = oxfoi_event_key
        self.oxfoi_event_manifest_key = oxfoi_event_manifest_key
        self.memristor_map_key = memristor_map_key
        self.memristor_integration_key = memristor_integration_key
        self.triton_execution_key = triton_execution_key
        self.triton_event_key = triton_event_key
        self.triton_event_manifest_key = triton_event_manifest_key
        self.causal_graph_manifest_key = causal_graph_manifest_key
        self.hypergraph_manifest_key = hypergraph_manifest_key
        self.recrystallization_key = recrystallization_key
        self.recrystallization_manifest_key = recrystallization_manifest_key
        self.production_pointer_key = production_pointer_key
        self.production_pointer_manifest_key = production_pointer_manifest_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        initialization_record: InitializationVectorRecord = context[self.initialization_record_key]
        stem_path = context.get(self.stem_path_key)
        startup_sequence: StartupSequence | None = context.get(self.startup_sequence_key)
        startup_event_index: UpdateEventIndex | None = context.get(self.startup_event_key)
        startup_event_manifest_path = context.get(self.startup_event_manifest_key)
        oxfoi_evaluation: OxfoiEvaluationRecord | None = context.get(self.oxfoi_evaluation_key)
        oxfoi_event_index: UpdateEventIndex | None = context.get(self.oxfoi_event_key)
        oxfoi_event_manifest_path = context.get(self.oxfoi_event_manifest_key)
        memristor_map: MemristorMapRecord | None = context.get(self.memristor_map_key)
        memristor_integration: MemristorIntegrationRecord | None = context.get(self.memristor_integration_key)
        triton_execution = context.get(self.triton_execution_key)
        triton_event_index: UpdateEventIndex | None = context.get(self.triton_event_key)
        triton_event_manifest_path = context.get(self.triton_event_manifest_key)
        causal_graph_manifest_path = context.get(self.causal_graph_manifest_key)
        hypergraph_manifest_path = context.get(self.hypergraph_manifest_key)
        recrystallization: RecrystallizationRecord | None = context.get(self.recrystallization_key)
        recrystallization_manifest_path = context.get(self.recrystallization_manifest_key)
        pointer: ProductionPointerRecord | None = context.get(self.production_pointer_key)
        production_pointer_manifest_path = context.get(self.production_pointer_manifest_key)

        startup_surface_count = len(startup_sequence.surfaces) if startup_sequence is not None else 0
        startup_checkpoint_count = len(startup_sequence.persisted_paths) if startup_sequence is not None else 0
        startup_event_count = len(startup_event_index.records) if startup_event_index is not None else 0
        oxfoi_expression_id = oxfoi_evaluation.expression.expression_id if oxfoi_evaluation is not None else None
        oxfoi_transition_id = oxfoi_evaluation.transition.transition_id if oxfoi_evaluation is not None else None
        oxfoi_field_domain = oxfoi_evaluation.expression.field_domain if oxfoi_evaluation is not None else None
        oxfoi_instruction_width_words = (
            oxfoi_evaluation.expression.instruction_width_words if oxfoi_evaluation is not None else None
        )
        triton_instruction_id = triton_execution.instruction.instruction_id if triton_execution is not None else None
        triton_instruction_kind = triton_execution.instruction.instruction_kind if triton_execution is not None else None
        triton_instruction_width_words = (
            triton_execution.instruction.instruction_width_words if triton_execution is not None else None
        )
        triton_field_domain = triton_execution.instruction.field_domain if triton_execution is not None else None
        triton_state_id = triton_execution.output_state.state_id if triton_execution is not None else None
        current_state_id = pointer.current_state_id if pointer is not None else (
            oxfoi_evaluation.output_state.state_id if oxfoi_evaluation is not None else None
        )
        machine_id = f"mach_{_pointer_digest(initialization_record.prefix, current_state_id or '', oxfoi_expression_id or '')}"
        record = MachineStateRecord(
            machine_id=machine_id,
            init_origin=initialization_record.prefix,
            current_state_id=current_state_id,
            startup_surface_count=startup_surface_count,
            startup_checkpoint_count=startup_checkpoint_count,
            startup_event_count=startup_event_count,
            oxfoi_expression_id=oxfoi_expression_id,
            oxfoi_transition_id=oxfoi_transition_id,
            oxfoi_field_domain=oxfoi_field_domain,
            oxfoi_instruction_width_words=oxfoi_instruction_width_words,
            memristor_map_id=memristor_map.map_id if memristor_map is not None else None,
            memristor_lattice_family=memristor_map.lattice_family if memristor_map is not None else None,
            memristor_modulated_site_count=(
                len(memristor_integration.modulation_sites) if memristor_integration is not None else 0
            ),
            triton_instruction_id=triton_instruction_id,
            triton_instruction_kind=triton_instruction_kind,
            triton_instruction_width_words=triton_instruction_width_words,
            triton_field_domain=triton_field_domain,
            triton_state_id=triton_state_id,
            recrystallization_id=recrystallization.recrystallization_id if recrystallization is not None else None,
            recrystallized_state_id=recrystallization.selected_state_id if recrystallization is not None else None,
            recrystallization_source=recrystallization.selected_source if recrystallization is not None else None,
            production_pointer_id=pointer.pointer_id if pointer is not None else None,
            target_domain=pointer.target_domain if pointer is not None else None,
            target_confidence=float(pointer.target_confidence) if pointer is not None else 0.0,
            metadata={
                "global_recursive_limit": initialization_record.global_recursive_limit,
                "materialized_recursive_steps": initialization_record.materialized_recursive_steps,
                "persisted_checkpoint_count": initialization_record.persisted_checkpoint_count,
                "stem_path": str(Path(stem_path).resolve()) if stem_path is not None else None,
                "startup_final_path": str(startup_sequence.final_path) if startup_sequence is not None else None,
                "startup_event_manifest_path": (
                    str(Path(startup_event_manifest_path).resolve()) if startup_event_manifest_path is not None else None
                ),
                "oxfoi_event_manifest_path": (
                    str(Path(oxfoi_event_manifest_path).resolve()) if oxfoi_event_manifest_path is not None else None
                ),
                "triton_event_manifest_path": (
                    str(Path(triton_event_manifest_path).resolve()) if triton_event_manifest_path is not None else None
                ),
                "causal_graph_manifest_path": (
                    str(Path(causal_graph_manifest_path).resolve()) if causal_graph_manifest_path is not None else None
                ),
                "hypergraph_candidate_manifest_path": (
                    str(Path(hypergraph_manifest_path).resolve()) if hypergraph_manifest_path is not None else None
                ),
                "recrystallization_manifest_path": (
                    str(Path(recrystallization_manifest_path).resolve())
                    if recrystallization_manifest_path is not None
                    else None
                ),
                "production_pointer_manifest_path": (
                    str(Path(production_pointer_manifest_path).resolve())
                    if production_pointer_manifest_path is not None
                    else None
                ),
                "pointer_preferred_output": pointer.preferred_output if pointer is not None else None,
                "oxfoi_event_count": len(oxfoi_event_index.records) if oxfoi_event_index is not None else 0,
                "memristor_loop_density": (
                    memristor_map.metadata.get("loop_density") if memristor_map is not None else None
                ),
                "memristor_fundamental_loop_rank": (
                    memristor_map.metadata.get("fundamental_loop_rank") if memristor_map is not None else None
                ),
                "memristor_relaxation_score": (
                    memristor_map.metadata.get("relaxation_score") if memristor_map is not None else None
                ),
                "memristor_average_conductance": (
                    memristor_integration.metadata.get("average_conductance")
                    if memristor_integration is not None
                    else None
                ),
                "memristor_relaxation_projection_score": (
                    memristor_integration.metadata.get("relaxation_projection_score")
                    if memristor_integration is not None
                    else None
                ),
                "triton_event_count": len(triton_event_index.records) if triton_event_index is not None else 0,
                "startup_alignment_score": (
                    pointer.safety_bounds.get("startup_alignment_score") if pointer is not None else None
                ),
                "oxfoi_alignment_score": (
                    pointer.safety_bounds.get("oxfoi_alignment_score") if pointer is not None else None
                ),
                "memristor_alignment_score": (
                    pointer.safety_bounds.get("memristor_alignment_score") if pointer is not None else None
                ),
                "triton_alignment_score": (
                    pointer.safety_bounds.get("triton_alignment_score") if pointer is not None else None
                ),
                "recrystallization_score": (
                    recrystallization.selected_score if recrystallization is not None else None
                ),
                "recrystallization_candidate_count": (
                    len(recrystallization.candidates) if recrystallization is not None else 0
                ),
                "triton_operand_stack": (
                    list(triton_execution.output_state.operand_stack) if triton_execution is not None else None
                ),
            },
        )
        return {self.output_key: record}


@dataclass
class BuildExpertAssessmentNode(DagNode):
    def __init__(
        self,
        machine_state_key: str = "machine_state_record",
        production_pointer_key: str = "production_pointer",
        hypergraph_key: str = "hypergraph_candidate_index",
        causal_graph_key: str = "causal_graph_index",
        output_key: str = "expert_assessment",
    ):
        super().__init__(
            name="build_expert_assessment",
            inputs=[machine_state_key],
            outputs=[output_key],
        )
        self.machine_state_key = machine_state_key
        self.production_pointer_key = production_pointer_key
        self.hypergraph_key = hypergraph_key
        self.causal_graph_key = causal_graph_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        machine_state: MachineStateRecord = context[self.machine_state_key]
        pointer: ProductionPointerRecord | None = context.get(self.production_pointer_key)
        hypergraph_index: HypergraphCandidateIndex | None = context.get(self.hypergraph_key)
        causal_graph_index: CausalGraphIndex | None = context.get(self.causal_graph_key)
        assessment = build_expert_assessment(
            machine_state,
            production_pointer=pointer,
            hypergraph_index=hypergraph_index,
            causal_graph_index=causal_graph_index,
        )
        return {self.output_key: assessment}


@dataclass
class BuildRecrystallizationNode(DagNode):
    def __init__(
        self,
        machine_state_key: str = "machine_state_record",
        production_pointer_key: str = "production_pointer",
        expert_assessment_key: str = "expert_assessment",
        hypergraph_key: str = "hypergraph_candidate_index",
        causal_graph_key: str = "causal_graph_index",
        output_key: str = "recrystallization",
    ):
        super().__init__(
            name="build_recrystallization",
            inputs=[machine_state_key],
            outputs=[output_key],
        )
        self.machine_state_key = machine_state_key
        self.production_pointer_key = production_pointer_key
        self.expert_assessment_key = expert_assessment_key
        self.hypergraph_key = hypergraph_key
        self.causal_graph_key = causal_graph_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        machine_state: MachineStateRecord = context[self.machine_state_key]
        pointer: ProductionPointerRecord | None = context.get(self.production_pointer_key)
        expert_assessment: ExpertAssessmentRecord | None = context.get(self.expert_assessment_key)
        hypergraph_index: HypergraphCandidateIndex | None = context.get(self.hypergraph_key)
        causal_graph_index: CausalGraphIndex | None = context.get(self.causal_graph_key)
        return {
            self.output_key: build_recrystallization(
                machine_state,
                production_pointer=pointer,
                expert_assessment=expert_assessment,
                hypergraph_index=hypergraph_index,
                causal_graph_index=causal_graph_index,
            )
        }


@dataclass
class PersistExpertAssessmentNode(DagNode):
    def __init__(
        self,
        expert_assessment_key: str = "expert_assessment",
        workspace_key: str = "workspace",
        output_key: str = "expert_assessment_manifest_path",
    ):
        super().__init__(
            name="persist_expert_assessment",
            inputs=[expert_assessment_key, workspace_key],
            outputs=[output_key],
        )
        self.expert_assessment_key = expert_assessment_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        assessment: ExpertAssessmentRecord = context[self.expert_assessment_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / f"{assessment.assessment_id}.json"
        manifest_path.write_text(json.dumps(asdict(assessment), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistRecrystallizationNode(DagNode):
    def __init__(
        self,
        recrystallization_key: str = "recrystallization",
        workspace_key: str = "workspace",
        output_key: str = "recrystallization_manifest_path",
    ):
        super().__init__(
            name="persist_recrystallization",
            inputs=[recrystallization_key, workspace_key],
            outputs=[output_key],
        )
        self.recrystallization_key = recrystallization_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        record: RecrystallizationRecord = context[self.recrystallization_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / f"{record.recrystallization_id}.json"
        manifest_path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistMachineStateRecordNode(DagNode):
    def __init__(
        self,
        machine_state_key: str = "machine_state_record",
        workspace_key: str = "workspace",
        output_key: str = "machine_state_manifest_path",
    ):
        super().__init__(
            name="persist_machine_state_record",
            inputs=[machine_state_key, workspace_key],
            outputs=[output_key],
        )
        self.machine_state_key = machine_state_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        machine_state: MachineStateRecord = context[self.machine_state_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / f"{machine_state.machine_id}.json"
        manifest_path.write_text(json.dumps(asdict(machine_state), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class BuildMemristorMapNode(DagNode):
    def __init__(
        self,
        initialization_record_key: str = "initialization_vector_record",
        output_key: str = "memristor_map",
        lattice_size_key: str = "memristor_lattice_size",
        field_domain_key: str = "memristor_field_domain",
    ):
        super().__init__(
            name="build_memristor_map",
            inputs=[initialization_record_key],
            outputs=[output_key],
        )
        self.initialization_record_key = initialization_record_key
        self.output_key = output_key
        self.lattice_size_key = lattice_size_key
        self.field_domain_key = field_domain_key

    def run(self, context: DagContext) -> DagContext:
        initialization_record: InitializationVectorRecord = context[self.initialization_record_key]
        lattice_size = int(context.get(self.lattice_size_key, 5))
        field_domain = str(context.get(self.field_domain_key, "B"))
        memristor_map = build_memristor_map(
            initialization_record,
            lattice_size=lattice_size,
            field_domain=field_domain,
        )
        return {self.output_key: memristor_map}


@dataclass
class BuildMemristorIntegrationNode(DagNode):
    def __init__(
        self,
        memristor_map_key: str = "memristor_map",
        oxfoi_evaluation_key: str = "oxfoi_evaluation",
        ternlsb_payload_key: str = "ternlsb_payload",
        output_key: str = "memristor_integration",
    ):
        super().__init__(
            name="build_memristor_integration",
            inputs=[memristor_map_key],
            outputs=[output_key],
        )
        self.memristor_map_key = memristor_map_key
        self.oxfoi_evaluation_key = oxfoi_evaluation_key
        self.ternlsb_payload_key = ternlsb_payload_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        memristor_map: MemristorMapRecord = context[self.memristor_map_key]
        oxfoi_evaluation: OxfoiEvaluationRecord | None = context.get(self.oxfoi_evaluation_key)
        ternlsb_payload = str(context.get(self.ternlsb_payload_key, ""))
        integration = integrate_ternlsb_into_memristor_map(
            memristor_map,
            oxfoi_evaluation=oxfoi_evaluation,
            ternlsb_payload=ternlsb_payload,
        )
        return {self.output_key: integration}


@dataclass
class PersistCausalGraphIndexNode(DagNode):
    def __init__(
        self,
        causal_graph_key: str = "causal_graph_index",
        workspace_key: str = "workspace",
        output_key: str = "causal_graph_manifest_path",
    ):
        super().__init__(
            name="persist_causal_graph_index",
            inputs=[causal_graph_key, workspace_key],
            outputs=[output_key],
        )
        self.causal_graph_key = causal_graph_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        causal_graph: CausalGraphIndex = context[self.causal_graph_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / "causal_graph_index.json"
        manifest_path.write_text(json.dumps(asdict(causal_graph), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistHypergraphCandidateIndexNode(DagNode):
    def __init__(
        self,
        hypergraph_key: str = "hypergraph_candidate_index",
        workspace_key: str = "workspace",
        output_key: str = "hypergraph_candidate_manifest_path",
    ):
        super().__init__(
            name="persist_hypergraph_candidate_index",
            inputs=[hypergraph_key, workspace_key],
            outputs=[output_key],
        )
        self.hypergraph_key = hypergraph_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        hypergraph_index: HypergraphCandidateIndex = context[self.hypergraph_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / "hypergraph_candidate_index.json"
        manifest_path.write_text(json.dumps(asdict(hypergraph_index), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistStartupEventIndexNode(DagNode):
    def __init__(
        self,
        event_index_key: str = "startup_event_index",
        workspace_key: str = "workspace",
        output_key: str = "startup_event_manifest_path",
    ):
        super().__init__(
            name="persist_startup_event_index",
            inputs=[event_index_key, workspace_key],
            outputs=[output_key],
        )
        self.event_index_key = event_index_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        event_index: UpdateEventIndex = context[self.event_index_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / "startup_event_index.json"
        manifest_path.write_text(json.dumps(asdict(event_index), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistOxfoiEventIndexNode(DagNode):
    def __init__(
        self,
        event_index_key: str = "oxfoi_event_index",
        workspace_key: str = "workspace",
        output_key: str = "oxfoi_event_manifest_path",
    ):
        super().__init__(
            name="persist_oxfoi_event_index",
            inputs=[event_index_key, workspace_key],
            outputs=[output_key],
        )
        self.event_index_key = event_index_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        event_index: UpdateEventIndex = context[self.event_index_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / "oxfoi_event_index.json"
        manifest_path.write_text(json.dumps(asdict(event_index), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


@dataclass
class PersistTritonOxfoiEventIndexNode(DagNode):
    def __init__(
        self,
        event_index_key: str = "triton_oxfoi_event_index",
        workspace_key: str = "workspace",
        output_key: str = "triton_oxfoi_event_manifest_path",
    ):
        super().__init__(
            name="persist_triton_oxfoi_event_index",
            inputs=[event_index_key, workspace_key],
            outputs=[output_key],
        )
        self.event_index_key = event_index_key
        self.workspace_key = workspace_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        event_index: UpdateEventIndex = context[self.event_index_key]
        workspace: SimulationWorkspace = context[self.workspace_key]
        manifest_path = workspace.root / "runs" / "triton_oxfoi_event_index.json"
        manifest_path.write_text(json.dumps(asdict(event_index), indent=2, sort_keys=True), encoding="utf-8")
        return {self.output_key: manifest_path}


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
class DescribeTernLSBProgramNode(DagNode):
    def __init__(
        self,
        program_key: str = "decoded_ternlsb_program",
        execution_key: str = "ternlsb_execution",
        output_key: str = "ternlsb_program_description",
    ):
        super().__init__(
            name="describe_ternlsb_program",
            inputs=[program_key, execution_key],
            outputs=[output_key],
        )
        self.program_key = program_key
        self.execution_key = execution_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        program: TernLSBProgram = context[self.program_key]
        execution: TernLSBExecutionRecord = context[self.execution_key]
        description = describe_ternlsb_execution(program, execution)
        return {self.output_key: description}


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
class BuildCompiledWorkspaceIndexNode(DagNode):
    def __init__(
        self,
        workspace_key: str = "workspace",
        output_key: str = "compiled_workspace_index",
        enabled_key: str = "use_compiled_workspace_index",
    ):
        super().__init__(
            name="build_compiled_workspace_index",
            inputs=[workspace_key],
            outputs=[output_key],
        )
        self.workspace_key = workspace_key
        self.output_key = output_key
        self.enabled_key = enabled_key

    def run(self, context: DagContext) -> DagContext:
        if not bool(context.get(self.enabled_key, True)):
            return {}
        workspace: SimulationWorkspace = context[self.workspace_key]
        index: CompiledWorkspaceIndex = build_compiled_workspace_index(workspace.root)
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
class BuildStartupEventIndexNode(DagNode):
    def __init__(
        self,
        startup_sequence_key: str = "startup_sequence",
        initialization_vector_key: str = "initialization_vector",
        output_key: str = "startup_event_index",
    ):
        super().__init__(
            name="build_startup_event_index",
            inputs=[startup_sequence_key, initialization_vector_key],
            outputs=[output_key],
        )
        self.startup_sequence_key = startup_sequence_key
        self.initialization_vector_key = initialization_vector_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        from .initialization import StartupSequence

        sequence: StartupSequence = context[self.startup_sequence_key]
        vector: StartupInitializationVector = context[self.initialization_vector_key]
        records: list[UpdateEventRecord] = []
        steps_per_checkpoint = max(1, int(vector.recursion_steps_per_frame))

        previous_id = "startup:root"
        records.append(
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('startup', 'root', vector.prefix)}",
                event_type="startup_begin",
                input_ids=[],
                output_ids=[previous_id],
                state_ids=[previous_id],
                metadata={
                    "seed_path": str(vector.seed_path),
                    "prefix": vector.prefix,
                    "global_recursive_limit": int(vector.global_recursive_limit),
                    "materialized_recursive_steps": int(vector.materialized_recursive_steps),
                },
            )
        )

        for step_index, _surface in enumerate(sequence.surfaces[1:], start=1):
            state_id = f"startup:{step_index}"
            event_type = "startup_checkpoint" if step_index % steps_per_checkpoint == 0 else "startup_transition"
            records.append(
                UpdateEventRecord(
                    event_id=f"evt_{_pointer_digest('startup', previous_id, state_id)}",
                    event_type=event_type,
                    input_ids=[previous_id],
                    output_ids=[state_id],
                    state_ids=[previous_id, state_id],
                    metadata={
                        "step_index": step_index,
                        "checkpoint_interval_steps": steps_per_checkpoint,
                        "is_checkpoint": step_index % steps_per_checkpoint == 0,
                    },
                )
            )
            previous_id = state_id

        records.append(
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('startup', 'final', previous_id)}",
                event_type="startup_complete",
                input_ids=[previous_id],
                output_ids=[str(sequence.final_path)],
                state_ids=[previous_id],
                metadata={
                    "final_path": str(sequence.final_path),
                    "persisted_checkpoint_count": len(sequence.persisted_paths),
                    "surface_count": len(sequence.surfaces),
                },
            )
        )
        return {self.output_key: UpdateEventIndex(records=records)}


@dataclass
class BuildOxfoiEventIndexNode(DagNode):
    def __init__(
        self,
        oxfoi_evaluation_key: str = "oxfoi_evaluation",
        output_key: str = "oxfoi_event_index",
    ):
        super().__init__(
            name="build_oxfoi_event_index",
            inputs=[oxfoi_evaluation_key],
            outputs=[output_key],
        )
        self.oxfoi_evaluation_key = oxfoi_evaluation_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        evaluation: OxfoiEvaluationRecord = context[self.oxfoi_evaluation_key]
        expression = evaluation.expression
        transition = evaluation.transition
        records = [
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('oxfoi', 'expression', expression.expression_id)}",
                event_type="oxfoi_expression",
                input_ids=[],
                output_ids=[expression.expression_id],
                state_ids=[evaluation.input_state.state_id],
                metadata={
                    "field_domain": expression.field_domain,
                    "instruction_width_words": expression.instruction_width_words,
                    "single_use": expression.single_use,
                    "payload": expression.payload,
                },
            ),
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('oxfoi', 'transition', transition.transition_id)}",
                event_type="oxfoi_transition",
                input_ids=[evaluation.input_state.state_id, expression.expression_id],
                output_ids=[evaluation.output_state.state_id],
                state_ids=[evaluation.input_state.state_id, evaluation.output_state.state_id],
                metadata={
                    "transition_id": transition.transition_id,
                    "field_domain": transition.field_domain,
                    "instruction_width_words": transition.instruction_width_words,
                    "displacement_kind": transition.displacement_kind,
                    **dict(transition.metadata),
                },
            ),
        ]
        return {self.output_key: UpdateEventIndex(records=records)}


@dataclass
class BuildTritonOxfoiEventIndexNode(DagNode):
    def __init__(
        self,
        execution_key: str = "triton_oxfoi_execution",
        output_key: str = "triton_oxfoi_event_index",
    ):
        super().__init__(
            name="build_triton_oxfoi_event_index",
            inputs=[execution_key],
            outputs=[output_key],
        )
        self.execution_key = execution_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        execution: TritonOxfoiExecutionRecord = context[self.execution_key]
        instruction = execution.instruction
        records = [
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('triton', 'instruction', instruction.instruction_id)}",
                event_type="triton_instruction",
                input_ids=[],
                output_ids=[instruction.instruction_id],
                state_ids=[execution.input_state.state_id],
                metadata={
                    "instruction_kind": instruction.instruction_kind,
                    "instruction_width_words": instruction.instruction_width_words,
                    "argument": instruction.argument,
                    "field_domain": instruction.field_domain,
                },
            ),
            UpdateEventRecord(
                event_id=f"evt_{_pointer_digest('triton', 'execution', execution.output_state.state_id, instruction.instruction_id)}",
                event_type="triton_execution",
                input_ids=[execution.input_state.state_id, instruction.instruction_id],
                output_ids=[execution.output_state.state_id],
                state_ids=[execution.input_state.state_id, execution.output_state.state_id],
                metadata={
                    "instruction_kind": instruction.instruction_kind,
                    "instruction_width_words": instruction.instruction_width_words,
                    "field_domain": instruction.field_domain,
                    **dict(execution.metadata),
                },
            ),
        ]
        return {self.output_key: UpdateEventIndex(records=records)}


@dataclass
class BuildCausalGraphIndexNode(DagNode):
    def __init__(
        self,
        update_event_key: str = "update_event_index",
        startup_event_key: str = "startup_event_index",
        oxfoi_event_key: str = "oxfoi_event_index",
        triton_event_key: str = "triton_oxfoi_event_index",
        output_key: str = "causal_graph_index",
    ):
        super().__init__(
            name="build_causal_graph_index",
            inputs=[],
            outputs=[output_key],
        )
        self.update_event_key = update_event_key
        self.startup_event_key = startup_event_key
        self.oxfoi_event_key = oxfoi_event_key
        self.triton_event_key = triton_event_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        records: list[UpdateEventRecord] = []
        update_event_index: UpdateEventIndex | None = context.get(self.update_event_key)
        startup_event_index: UpdateEventIndex | None = context.get(self.startup_event_key)
        oxfoi_event_index: UpdateEventIndex | None = context.get(self.oxfoi_event_key)
        triton_event_index: UpdateEventIndex | None = context.get(self.triton_event_key)
        if update_event_index is not None:
            records.extend(update_event_index.records)
        if startup_event_index is not None:
            records.extend(startup_event_index.records)
        if oxfoi_event_index is not None:
            records.extend(oxfoi_event_index.records)
        if triton_event_index is not None:
            records.extend(triton_event_index.records)
        dependencies: list[CausalDependencyRecord] = []

        state_to_generation_event: dict[str, str] = {}
        chain_events: list[UpdateEventRecord] = []
        startup_events: list[UpdateEventRecord] = []
        collapse_events: list[UpdateEventRecord] = []
        oxfoi_expression_events: list[UpdateEventRecord] = []
        oxfoi_transition_events: list[UpdateEventRecord] = []
        triton_instruction_events: list[UpdateEventRecord] = []
        triton_execution_events: list[UpdateEventRecord] = []

        for record in records:
            if record.event_type == "subtree_generation":
                for state_id in record.output_ids:
                    state_to_generation_event[state_id] = record.event_id
            elif record.event_type == "chain_transition":
                chain_events.append(record)
            elif record.event_type in {"startup_begin", "startup_transition", "startup_checkpoint", "startup_complete"}:
                startup_events.append(record)
            elif record.event_type == "canonical_collapse":
                collapse_events.append(record)
            elif record.event_type == "oxfoi_expression":
                oxfoi_expression_events.append(record)
            elif record.event_type == "oxfoi_transition":
                oxfoi_transition_events.append(record)
            elif record.event_type == "triton_instruction":
                triton_instruction_events.append(record)
            elif record.event_type == "triton_execution":
                triton_execution_events.append(record)

        for previous, current in zip(startup_events, startup_events[1:]):
            dependency_id = f"dep_{_pointer_digest('startup', previous.event_id, current.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=previous.event_id,
                    effect_event_id=current.event_id,
                    dependency_type="startup_order",
                    metadata={},
                )
            )

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

        for expression_event, transition_event in zip(oxfoi_expression_events, oxfoi_transition_events):
            dependency_id = f"dep_{_pointer_digest('oxfoi', expression_event.event_id, transition_event.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=expression_event.event_id,
                    effect_event_id=transition_event.event_id,
                    dependency_type="oxfoi_expression_application",
                    metadata={
                        "expression_id": expression_event.output_ids[0] if expression_event.output_ids else None,
                        "displacement_kind": transition_event.metadata.get("displacement_kind"),
                    },
                )
            )

        for instruction_event, execution_event in zip(triton_instruction_events, triton_execution_events):
            dependency_id = f"dep_{_pointer_digest('triton', instruction_event.event_id, execution_event.event_id)}"
            dependencies.append(
                CausalDependencyRecord(
                    dependency_id=dependency_id,
                    cause_event_id=instruction_event.event_id,
                    effect_event_id=execution_event.event_id,
                    dependency_type="triton_instruction_application",
                    metadata={
                        "instruction_id": instruction_event.output_ids[0] if instruction_event.output_ids else None,
                        "instruction_kind": execution_event.metadata.get("instruction_kind"),
                        "instruction_width_words": execution_event.metadata.get("instruction_width_words"),
                    },
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
        startup_event_key: str = "startup_event_index",
        oxfoi_event_key: str = "oxfoi_event_index",
        memristor_integration_key: str = "memristor_integration",
        triton_event_key: str = "triton_oxfoi_event_index",
        causal_graph_key: str = "causal_graph_index",
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
        self.startup_event_key = startup_event_key
        self.oxfoi_event_key = oxfoi_event_key
        self.memristor_integration_key = memristor_integration_key
        self.triton_event_key = triton_event_key
        self.causal_graph_key = causal_graph_key
        self.output_key = output_key

    def run(self, context: DagContext) -> DagContext:
        stem_path = context[self.stem_path_key]
        chain_review: ChainReview = context[self.chain_review_key]
        generated_states: list[ArchivedState] = list(context[self.generated_states_key])
        canonical_index: CanonicalStateIndex = context[self.canonical_index_key]
        dedupe_summary: DedupeSummary = context[self.dedupe_key]
        startup_event_index: UpdateEventIndex | None = context.get(self.startup_event_key)
        oxfoi_event_index: UpdateEventIndex | None = context.get(self.oxfoi_event_key)
        memristor_integration: MemristorIntegrationRecord | None = context.get(self.memristor_integration_key)
        triton_event_index: UpdateEventIndex | None = context.get(self.triton_event_key)
        causal_graph_index: CausalGraphIndex | None = context.get(self.causal_graph_key)

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

        if startup_event_index is not None:
            startup_records = [
                record
                for record in startup_event_index.records
                if record.event_type in {"startup_checkpoint", "startup_complete"}
            ]
            for record in startup_records:
                records.append(
                    HyperedgeCandidateRecord(
                        edge_type="startup_checkpoint_relation",
                        input_nodes=list(record.input_ids),
                        output_nodes=list(record.output_ids),
                        support_nodes=[
                            str(record.metadata.get("final_path"))
                            if record.event_type == "startup_complete"
                            else f"startup_step:{record.metadata.get('step_index', 0)}"
                        ],
                        metadata={
                            "event_id": record.event_id,
                            "event_type": record.event_type,
                            "step_index": int(record.metadata.get("step_index", 0)),
                            "is_checkpoint": bool(record.metadata.get("is_checkpoint", record.event_type == "startup_checkpoint")),
                        },
                    )
                )

        if oxfoi_event_index is not None:
            for record in oxfoi_event_index.records:
                if record.event_type not in {"oxfoi_expression", "oxfoi_transition"}:
                    continue
                support_nodes = []
                if record.event_type == "oxfoi_transition":
                    support_nodes.append(str(record.metadata.get("displacement_kind", "")))
                records.append(
                    HyperedgeCandidateRecord(
                        edge_type=f"{record.event_type}_relation",
                        input_nodes=list(record.input_ids),
                        output_nodes=list(record.output_ids),
                        support_nodes=support_nodes,
                        metadata={
                            "event_id": record.event_id,
                            **dict(record.metadata),
                        },
                    )
                )

        if triton_event_index is not None:
            for record in triton_event_index.records:
                if record.event_type not in {"triton_instruction", "triton_execution"}:
                    continue
                support_nodes = []
                if record.event_type == "triton_execution":
                    support_nodes.extend(
                        [
                            str(record.metadata.get("instruction_kind", "")),
                            str(record.metadata.get("instruction_width_words", "")),
                        ]
                    )
                records.append(
                    HyperedgeCandidateRecord(
                        edge_type=f"{record.event_type}_relation",
                        input_nodes=list(record.input_ids),
                        output_nodes=list(record.output_ids),
                        support_nodes=support_nodes,
                        metadata={
                            "event_id": record.event_id,
                            **dict(record.metadata),
                        },
                    )
                )

        if memristor_integration is not None:
            records.append(
                HyperedgeCandidateRecord(
                    edge_type="memristor_modulation_relation",
                    input_nodes=[memristor_integration.expression_id] if memristor_integration.expression_id else [],
                    output_nodes=[memristor_integration.map_id],
                    support_nodes=[f"{q},{r}" for q, r in memristor_integration.modulation_sites],
                    metadata={
                        "integration_id": memristor_integration.integration_id,
                        "target_domain": memristor_integration.target_domain,
                        **dict(memristor_integration.metadata),
                    },
                )
            )

        if causal_graph_index is not None:
            for dependency in causal_graph_index.records:
                if dependency.dependency_type == "startup_order":
                    records.append(
                        HyperedgeCandidateRecord(
                            edge_type="startup_causal_segment",
                            input_nodes=[dependency.cause_event_id],
                            output_nodes=[dependency.effect_event_id],
                            support_nodes=[],
                            metadata={
                                "dependency_id": dependency.dependency_id,
                                "dependency_type": dependency.dependency_type,
                            },
                        )
                    )
                elif dependency.dependency_type == "oxfoi_expression_application":
                    records.append(
                        HyperedgeCandidateRecord(
                            edge_type="oxfoi_causal_segment",
                            input_nodes=[dependency.cause_event_id],
                            output_nodes=[dependency.effect_event_id],
                            support_nodes=[
                                str(dependency.metadata.get("expression_id", "")),
                                str(dependency.metadata.get("displacement_kind", "")),
                            ],
                            metadata={
                                "dependency_id": dependency.dependency_id,
                                "dependency_type": dependency.dependency_type,
                                **dict(dependency.metadata),
                            },
                        )
                    )
                elif dependency.dependency_type == "triton_instruction_application":
                    records.append(
                        HyperedgeCandidateRecord(
                            edge_type="triton_causal_segment",
                            input_nodes=[dependency.cause_event_id],
                            output_nodes=[dependency.effect_event_id],
                            support_nodes=[
                                str(dependency.metadata.get("instruction_id", "")),
                                str(dependency.metadata.get("instruction_kind", "")),
                            ],
                            metadata={
                                "dependency_id": dependency.dependency_id,
                                "dependency_type": dependency.dependency_type,
                                **dict(dependency.metadata),
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
        startup_checkpoint_edges = [
            record for record in hypergraph_index.records if record.edge_type == "startup_checkpoint_relation"
        ]
        startup_causal_edges = [
            record for record in hypergraph_index.records if record.edge_type == "startup_causal_segment"
        ]
        oxfoi_expression_edges = [
            record for record in hypergraph_index.records if record.edge_type == "oxfoi_expression_relation"
        ]
        oxfoi_transition_edges = [
            record for record in hypergraph_index.records if record.edge_type == "oxfoi_transition_relation"
        ]
        oxfoi_causal_edges = [
            record for record in hypergraph_index.records if record.edge_type == "oxfoi_causal_segment"
        ]
        triton_instruction_edges = [
            record for record in hypergraph_index.records if record.edge_type == "triton_instruction_relation"
        ]
        triton_execution_edges = [
            record for record in hypergraph_index.records if record.edge_type == "triton_execution_relation"
        ]
        triton_causal_edges = [
            record for record in hypergraph_index.records if record.edge_type == "triton_causal_segment"
        ]
        memristor_modulation_edges = [
            record for record in hypergraph_index.records if record.edge_type == "memristor_modulation_relation"
        ]
        next_edge_types = sorted({record.edge_type for record in hypergraph_index.records})
        ranked_outputs: list[dict[str, Any]] = []
        seen_outputs: set[str] = set()
        startup_alignment_score = len(startup_checkpoint_edges) + len(startup_causal_edges)
        oxfoi_alignment_score = len(oxfoi_expression_edges) + len(oxfoi_transition_edges) + len(oxfoi_causal_edges)
        triton_alignment_score = len(triton_instruction_edges) + len(triton_execution_edges) + len(triton_causal_edges)
        memristor_alignment_score = max(
            len(memristor_modulation_edges),
            int(
                round(
                    sum(
                        float(record.metadata.get("loop_density", 0.0)) * float(record.metadata.get("modulated_site_count", 0))
                        + float(record.metadata.get("relaxation_projection_score", 0.0))
                        for record in memristor_modulation_edges
                    )
                )
            ),
        )
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
                        "startup_alignment": startup_alignment_score,
                        "oxfoi_alignment": oxfoi_alignment_score,
                        "triton_alignment": triton_alignment_score,
                        "memristor_alignment": memristor_alignment_score,
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
        target_confidence = min(
            1.0,
            0.04 * startup_alignment_score
            + 0.03 * oxfoi_alignment_score
            + 0.02 * triton_alignment_score
            + 0.01 * memristor_alignment_score,
        )

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
                "startup_alignment_score": startup_alignment_score,
                "oxfoi_alignment_score": oxfoi_alignment_score,
                "triton_alignment_score": triton_alignment_score,
                "memristor_alignment_score": memristor_alignment_score,
                "ray_locked": True,
            },
            target_domain="supersingular_isogeny",
            target_confidence=target_confidence,
            metadata={
                "signature": current_signature,
                "branch": list(current_state.branch),
                "chain_length": len(chain.states),
                "hyperedge_count": len(hypergraph_index.records),
                "stem_root_state_id": chain.states[0].state_id,
                "startup_checkpoint_relation_count": len(startup_checkpoint_edges),
                "startup_causal_segment_count": len(startup_causal_edges),
                "oxfoi_expression_relation_count": len(oxfoi_expression_edges),
                "oxfoi_transition_relation_count": len(oxfoi_transition_edges),
                "oxfoi_causal_segment_count": len(oxfoi_causal_edges),
                "triton_instruction_relation_count": len(triton_instruction_edges),
                "triton_execution_relation_count": len(triton_execution_edges),
                "triton_causal_segment_count": len(triton_causal_edges),
                "memristor_modulation_relation_count": len(memristor_modulation_edges),
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


class StartupMachinePipeline(Dag):
    def __init__(self) -> None:
        super().__init__(
            nodes=[
                BuildInitializationVectorRecordNode(),
                BuildStartupSequenceNode(),
                BuildStartupEventIndexNode(),
                BuildCausalGraphIndexNode(),
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
                DescribeTernLSBProgramNode(),
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
