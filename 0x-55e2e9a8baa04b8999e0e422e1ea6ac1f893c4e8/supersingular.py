from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin

from .graph import Edge, SandpileConfiguration, SandpileModel, UndirectedGraph


@dataclass(frozen=True)
class SupersingularIsogenyGraphSpec:
    prime: int
    isogeny_degree: int
    vertex_count: int
    sink_vertex: str
    construction: str = "synthetic_circulant_scaffold"


def supersingular_vertex(index: int) -> str:
    return f"ss:{index}"


def estimate_supersingular_vertex_count(prime: int) -> int:
    if prime <= 3:
        raise ValueError("prime must be greater than 3 for the current supersingular scaffold")
    # The true count of supersingular j-invariants is about p/12 up to small corrections.
    return max(3, prime // 12 + 1)


def build_supersingular_isogeny_graph(
    prime: int,
    isogeny_degree: int,
    vertex_count: int | None = None,
) -> tuple[UndirectedGraph, dict[str, tuple[int, int]], SupersingularIsogenyGraphSpec]:
    if prime <= 3:
        raise ValueError("prime must be greater than 3")
    if isogeny_degree < 2:
        raise ValueError("isogeny degree must be at least 2")
    if prime == isogeny_degree:
        raise ValueError("isogeny degree must be different from the residue characteristic")

    count = vertex_count or estimate_supersingular_vertex_count(prime)
    if count < 3:
        raise ValueError("vertex_count must be at least 3")

    regular_degree = isogeny_degree + 1
    if regular_degree % 2 == 1 and count % 2 == 1:
        if vertex_count is None:
            count += 1
        else:
            raise ValueError("odd regular degree requires an even vertex_count in this scaffold")

    vertices = [supersingular_vertex(index) for index in range(count)]
    sink_vertex = vertices[0]
    seed_vertex = vertices[1]

    offsets = list(range(1, min(count // 2 + 1, regular_degree // 2 + 1)))
    edges: list[Edge] = []
    seen_pairs: set[tuple[str, str]] = set()

    for index, vertex in enumerate(vertices):
        for offset in offsets:
            neighbor = vertices[(index + offset) % count]
            pair = tuple(sorted((vertex, neighbor)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            edges.append(
                Edge(
                    vertex,
                    neighbor,
                    metadata={
                        "isogeny_degree": isogeny_degree,
                        "construction": "synthetic_circulant_scaffold",
                    },
                )
            )

    if regular_degree % 2 == 1:
        if count % 2 == 0:
            half_turn = count // 2
            for index in range(count // 2):
                left = vertices[index]
                right = vertices[(index + half_turn) % count]
                edges.append(
                    Edge(
                        left,
                        right,
                        metadata={
                            "isogeny_degree": isogeny_degree,
                            "construction": "synthetic_circulant_scaffold",
                        },
                    )
                )
    graph = UndirectedGraph(
        vertices=vertices,
        edges=edges,
        metadata={
            "graph_family": "supersingular_isogeny",
            "prime": prime,
            "isogeny_degree": isogeny_degree,
            "regular_degree_target": regular_degree,
            "regular_degree_achieved": regular_degree,
            "vertex_count": count,
            "construction": "synthetic_circulant_scaffold",
            "is_true_isogeny_graph": False,
            "target_domain": "supersingular_isogeny",
            "center_vertex": seed_vertex,
            "seed_vertex": seed_vertex,
        },
    )

    radius = max(4, count)
    layout: dict[str, tuple[int, int]] = {}
    for index, vertex in enumerate(vertices):
        angle = (2 * pi * index) / count
        x = int(round(radius + radius * cos(angle)))
        y = int(round(radius + radius * sin(angle)))
        layout[vertex] = (x, y)

    spec = SupersingularIsogenyGraphSpec(
        prime=prime,
        isogeny_degree=isogeny_degree,
        vertex_count=count,
        sink_vertex=sink_vertex,
    )
    return graph, layout, spec


def supersingular_delta_configuration(
    model: SandpileModel,
    vertex: str | None = None,
    chips: int = 1,
) -> SandpileConfiguration:
    target = vertex or model.graph.metadata.get("center_vertex") or next(iter(model.active_vertices), None)
    if target is None:
        raise ValueError("cannot choose a seed vertex on an empty supersingular scaffold")
    if target == model.sink:
        raise ValueError("chosen seed vertex overlaps the sink")
    configuration = {candidate: 0 for candidate in model.active_vertices}
    configuration[target] = chips
    return SandpileConfiguration(model=model, chips=configuration)
