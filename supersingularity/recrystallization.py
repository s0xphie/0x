from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .dag import CausalGraphIndex, HypergraphCandidateIndex, MachineStateRecord, ProductionPointerRecord
    from .expert import ExpertAssessmentRecord


def _recrystallization_digest(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RecrystallizationCandidateRecord:
    candidate_id: str
    state_id: str | None
    source: str
    score: float
    rationale: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RecrystallizationRecord:
    recrystallization_id: str
    machine_id: str
    pointer_id: str | None
    selected_state_id: str | None
    selected_source: str
    selected_score: float
    candidates: tuple[RecrystallizationCandidateRecord, ...]
    metadata: dict[str, Any]


def build_recrystallization(
    machine_state: "MachineStateRecord",
    *,
    production_pointer: "ProductionPointerRecord" | None = None,
    expert_assessment: "ExpertAssessmentRecord" | None = None,
    hypergraph_index: "HypergraphCandidateIndex" | None = None,
    causal_graph_index: "CausalGraphIndex" | None = None,
) -> RecrystallizationRecord:
    startup_alignment = float(machine_state.metadata.get("startup_alignment_score") or 0.0)
    oxfoi_alignment = float(machine_state.metadata.get("oxfoi_alignment_score") or 0.0)
    triton_alignment = float(machine_state.metadata.get("triton_alignment_score") or 0.0)
    memristor_alignment = float(machine_state.metadata.get("memristor_alignment_score") or 0.0)
    memristor_projection = float(machine_state.metadata.get("memristor_relaxation_projection_score") or 0.0)
    target_confidence = float(machine_state.target_confidence or 0.0)
    causal_count = len(causal_graph_index.records) if causal_graph_index is not None else 0
    hyper_count = len(hypergraph_index.records) if hypergraph_index is not None else 0

    candidates: list[RecrystallizationCandidateRecord] = []
    preferred_output = production_pointer.preferred_output if production_pointer is not None else None
    if preferred_output:
        candidates.append(
            RecrystallizationCandidateRecord(
                candidate_id=f"rcand_{_recrystallization_digest(machine_state.machine_id, preferred_output, 'pointer')}",
                state_id=preferred_output,
                source="production_pointer",
                score=(
                    target_confidence
                    + startup_alignment * 0.01
                    + oxfoi_alignment * 0.01
                    + triton_alignment * 0.01
                    + memristor_alignment * 0.005
                ),
                rationale="Serial recrystallization preserves the strongest coherent continuation ray when it remains aligned.",
                metadata={
                    "pointer_id": production_pointer.pointer_id if production_pointer is not None else None,
                    "rewrite_rule": production_pointer.rewrite_rule if production_pointer is not None else None,
                },
            )
        )

    if expert_assessment is not None and expert_assessment.recommendations:
        top = expert_assessment.recommendations[0]
        target_state_id = top.target_state_id or machine_state.current_state_id
        candidates.append(
            RecrystallizationCandidateRecord(
                candidate_id=f"rcand_{_recrystallization_digest(machine_state.machine_id, top.recommendation_id, 'expert')}",
                state_id=target_state_id,
                source="expert_assessment",
                score=float(top.priority) + memristor_projection * 0.01,
                rationale=top.rationale,
                metadata={
                    "recommendation_id": top.recommendation_id,
                    "action": top.action,
                    "target_domain": top.target_domain,
                    "fallback_to_current_state": top.target_state_id is None,
                },
            )
        )

    candidates.append(
        RecrystallizationCandidateRecord(
            candidate_id=f"rcand_{_recrystallization_digest(machine_state.machine_id, 'grounded-current')}",
            state_id=machine_state.current_state_id,
            source="grounded_current_state",
            score=target_confidence * 0.5 + memristor_alignment * 0.02,
            rationale="The machine can reselect its grounded current state while continuation pressure is still consolidating.",
            metadata={
                "current_state_id": machine_state.current_state_id,
                "causal_record_count": causal_count,
                "hypergraph_record_count": hyper_count,
            },
        )
    )

    candidates.sort(key=lambda record: record.score, reverse=True)
    selected = candidates[0]
    return RecrystallizationRecord(
        recrystallization_id=f"recry_{_recrystallization_digest(machine_state.machine_id, selected.candidate_id)}",
        machine_id=machine_state.machine_id,
        pointer_id=production_pointer.pointer_id if production_pointer is not None else None,
        selected_state_id=selected.state_id,
        selected_source=selected.source,
        selected_score=selected.score,
        candidates=tuple(candidates),
        metadata={
            "parallel_candidate_count": len(candidates),
            "serial_mode": "reselect_preferred_coherent_state",
            "startup_alignment_score": startup_alignment,
            "oxfoi_alignment_score": oxfoi_alignment,
            "triton_alignment_score": triton_alignment,
            "memristor_alignment_score": memristor_alignment,
            "memristor_relaxation_projection_score": memristor_projection,
            "causal_record_count": causal_count,
            "hypergraph_record_count": hyper_count,
        },
    )
