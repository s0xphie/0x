from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, TYPE_CHECKING

from .eisenstein import build_lattice_order, make_eisenstein_graph

if TYPE_CHECKING:
    from .dag import InitializationVectorRecord
    from .oxfoi import OxfoiEvaluationRecord


def _memristor_digest(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class MemristorCellRecord:
    site: tuple[int, int]
    conductance: float
    flux: float
    charge: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MemristorMapRecord:
    map_id: str
    lattice_family: str
    field_domain: str
    lattice_size: int
    cells: tuple[MemristorCellRecord, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MemristorIntegrationRecord:
    integration_id: str
    map_id: str
    expression_id: str | None
    modulation_sites: tuple[tuple[int, int], ...]
    target_domain: str
    metadata: dict[str, Any]


def build_memristor_map(
    initialization: "InitializationVectorRecord",
    *,
    lattice_size: int = 5,
    field_domain: str = "B",
    base_conductance: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> MemristorMapRecord:
    size = max(2, int(lattice_size))
    order = build_lattice_order(size)
    graph, _layout = make_eisenstein_graph(size)
    fundamental_loop_rank = max(0, len(graph.edges) - len(graph.vertices) + 1)
    loop_density = float(fundamental_loop_rank) / float(max(1, len(graph.vertices)))
    cells: list[MemristorCellRecord] = []
    center = size // 2
    total_conductance = 0.0
    total_charge = 0.0
    for index, site in enumerate(order):
        q, r = site
        radial_distance = max(abs(q - center), abs(r - center), abs((q - center) + (r - center)))
        conductance = float(base_conductance) / float(1 + radial_distance)
        flux = float(index + 1) / float(len(order))
        charge = conductance * flux
        total_conductance += conductance
        total_charge += charge
        cells.append(
            MemristorCellRecord(
                site=site,
                conductance=conductance,
                flux=flux,
                charge=charge,
                metadata={
                    "rank": index,
                    "radial_distance": radial_distance,
                },
            )
        )
    average_conductance = total_conductance / float(len(cells))
    relaxation_score = total_charge / float(len(cells))
    map_id = f"memmap_{_memristor_digest(initialization.prefix, field_domain, size, initialization.seed_path)}"
    return MemristorMapRecord(
        map_id=map_id,
        lattice_family="eisenstein_memristor",
        field_domain=field_domain,
        lattice_size=size,
        cells=tuple(cells),
        metadata={
            "init_origin": initialization.prefix,
            "seed_path": initialization.seed_path,
            "global_recursive_limit": initialization.global_recursive_limit,
            "fundamental_loop_rank": fundamental_loop_rank,
            "loop_density": loop_density,
            "average_conductance": average_conductance,
            "relaxation_score": relaxation_score,
            **dict(metadata or {}),
        },
    )


def integrate_ternlsb_into_memristor_map(
    memristor_map: MemristorMapRecord,
    *,
    oxfoi_evaluation: "OxfoiEvaluationRecord" | None = None,
    ternlsb_payload: str = "",
    target_domain: str = "oxfoi_lattice",
) -> MemristorIntegrationRecord:
    payload = ternlsb_payload or (
        oxfoi_evaluation.expression.payload if oxfoi_evaluation is not None else ""
    )
    modulation_count = max(1, min(len(memristor_map.cells), len(payload) or 1))
    modulation_sites = tuple(cell.site for cell in memristor_map.cells[:modulation_count])
    expression_id = oxfoi_evaluation.expression.expression_id if oxfoi_evaluation is not None else None
    integration_id = f"memint_{_memristor_digest(memristor_map.map_id, expression_id, payload, target_domain)}"
    average_conductance = (
        sum(cell.conductance for cell in memristor_map.cells[:modulation_count]) / float(modulation_count)
    )
    loop_density = float(memristor_map.metadata.get("loop_density", 0.0))
    relaxation_projection_score = average_conductance * loop_density * float(modulation_count)
    return MemristorIntegrationRecord(
        integration_id=integration_id,
        map_id=memristor_map.map_id,
        expression_id=expression_id,
        modulation_sites=modulation_sites,
        target_domain=target_domain,
        metadata={
            "payload": payload,
            "modulated_site_count": modulation_count,
            "average_conductance": average_conductance,
            "fundamental_loop_rank": int(memristor_map.metadata.get("fundamental_loop_rank", 0)),
            "loop_density": loop_density,
            "relaxation_score": float(memristor_map.metadata.get("relaxation_score", 0.0)),
            "relaxation_projection_score": relaxation_projection_score,
            "field_domain": memristor_map.field_domain,
            "lattice_family": memristor_map.lattice_family,
        },
    )
