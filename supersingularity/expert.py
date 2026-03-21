from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .dag import CausalGraphIndex, HypergraphCandidateIndex, MachineStateRecord, ProductionPointerRecord


def _expert_digest(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ExpertObservationRecord:
    observation_id: str
    kind: str
    summary: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ExpertRecommendationRecord:
    recommendation_id: str
    action: str
    rationale: str
    priority: float
    target_state_id: str | None
    target_domain: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ExpertAssessmentRecord:
    assessment_id: str
    machine_id: str
    pointer_id: str | None
    observations: tuple[ExpertObservationRecord, ...]
    recommendations: tuple[ExpertRecommendationRecord, ...]
    metadata: dict[str, Any]


def build_expert_assessment(
    machine_state: "MachineStateRecord",
    *,
    production_pointer: "ProductionPointerRecord" | None = None,
    hypergraph_index: "HypergraphCandidateIndex" | None = None,
    causal_graph_index: "CausalGraphIndex" | None = None,
) -> ExpertAssessmentRecord:
    startup_alignment = float(machine_state.metadata.get("startup_alignment_score") or 0.0)
    oxfoi_alignment = float(machine_state.metadata.get("oxfoi_alignment_score") or 0.0)
    memristor_alignment = float(machine_state.metadata.get("memristor_alignment_score") or 0.0)
    triton_alignment = float(machine_state.metadata.get("triton_alignment_score") or 0.0)
    memristor_density = float(machine_state.metadata.get("memristor_loop_density") or 0.0)
    target_confidence = float(machine_state.target_confidence)
    causal_count = len(causal_graph_index.records) if causal_graph_index is not None else 0
    hyper_count = len(hypergraph_index.records) if hypergraph_index is not None else 0

    observations: list[ExpertObservationRecord] = []
    recommendations: list[ExpertRecommendationRecord] = []

    observations.append(
        ExpertObservationRecord(
            observation_id=f"obs_{_expert_digest(machine_state.machine_id, 'continuation')}",
            kind="continuation_strength",
            summary="The machine has a crystallized continuation ray with reusable relational memory.",
            score=target_confidence,
            metadata={
                "target_confidence": target_confidence,
                "causal_record_count": causal_count,
                "hypergraph_record_count": hyper_count,
            },
        )
    )
    observations.append(
        ExpertObservationRecord(
            observation_id=f"obs_{_expert_digest(machine_state.machine_id, 'alignment')}",
            kind="alignment_surface",
            summary="Startup, Oxfoi, TritonVM, and memristor layers are all contributing structured guidance.",
            score=startup_alignment + oxfoi_alignment + triton_alignment + memristor_alignment,
            metadata={
                "startup_alignment_score": startup_alignment,
                "oxfoi_alignment_score": oxfoi_alignment,
                "triton_alignment_score": triton_alignment,
                "memristor_alignment_score": memristor_alignment,
            },
        )
    )
    if memristor_alignment > 0 or machine_state.memristor_map_id is not None:
        observations.append(
            ExpertObservationRecord(
                observation_id=f"obs_{_expert_digest(machine_state.machine_id, 'memristor')}",
                kind="memristor_relaxation",
                summary="Memristor relaxation geometry is present and can guide exploration over the lattice.",
                score=max(memristor_alignment, memristor_density),
                metadata={
                    "memristor_map_id": machine_state.memristor_map_id,
                    "memristor_loop_density": memristor_density,
                    "memristor_relaxation_score": machine_state.metadata.get("memristor_relaxation_score"),
                    "memristor_relaxation_projection_score": machine_state.metadata.get(
                        "memristor_relaxation_projection_score"
                    ),
                },
            )
        )

    preferred_output = production_pointer.preferred_output if production_pointer is not None else None
    recommendations.append(
        ExpertRecommendationRecord(
            recommendation_id=f"rec_{_expert_digest(machine_state.machine_id, 'expand')}",
            action="expand_preferred_ray",
            rationale="Continue along the current production-pointer ray to explore structurally preferred descendants.",
            priority=target_confidence + startup_alignment * 0.01 + oxfoi_alignment * 0.01,
            target_state_id=preferred_output,
            target_domain=machine_state.target_domain,
            metadata={
                "pointer_id": production_pointer.pointer_id if production_pointer is not None else None,
                "rewrite_rule": production_pointer.rewrite_rule if production_pointer is not None else None,
            },
        )
    )
    recommendations.append(
        ExpertRecommendationRecord(
            recommendation_id=f"rec_{_expert_digest(machine_state.machine_id, 'memristor-guided')}",
            action="follow_memristor_relaxation",
            rationale="Use loop density and relaxation projection to guide exploration orthogonally toward grounded structure.",
            priority=memristor_alignment * 0.05 + memristor_density,
            target_state_id=preferred_output,
            target_domain="eisenstein_memristor",
            metadata={
                "memristor_map_id": machine_state.memristor_map_id,
                "modulated_site_count": machine_state.memristor_modulated_site_count,
                "loop_density": memristor_density,
            },
        )
    )
    recommendations.append(
        ExpertRecommendationRecord(
            recommendation_id=f"rec_{_expert_digest(machine_state.machine_id, 'carrier')}",
            action="identify_carrier_states",
            rationale="Search for carrier states where ternLSB modulation and sandpile relaxation reinforce one another.",
            priority=oxfoi_alignment * 0.03 + triton_alignment * 0.02,
            target_state_id=preferred_output,
            target_domain="ternlsb_carrier",
            metadata={
                "oxfoi_expression_id": machine_state.oxfoi_expression_id,
                "triton_instruction_kind": machine_state.triton_instruction_kind,
            },
        )
    )

    recommendations.sort(key=lambda record: record.priority, reverse=True)
    assessment_id = f"expert_{_expert_digest(machine_state.machine_id, production_pointer.pointer_id if production_pointer else '')}"
    return ExpertAssessmentRecord(
        assessment_id=assessment_id,
        machine_id=machine_state.machine_id,
        pointer_id=production_pointer.pointer_id if production_pointer is not None else None,
        observations=tuple(observations),
        recommendations=tuple(recommendations),
        metadata={
            "target_confidence": target_confidence,
            "causal_record_count": causal_count,
            "hypergraph_record_count": hyper_count,
        },
    )
