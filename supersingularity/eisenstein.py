from __future__ import annotations

from typing import Iterable

from .graph import Edge, SandpileConfiguration, SandpileModel, UndirectedGraph


AxialSite = tuple[int, int]
ConfigMap = dict[AxialSite, int]


EISENSTEIN_NEIGHBOR_OFFSETS: tuple[AxialSite, ...] = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, -1),
    (-1, 1),
)


def eisenstein_vertex(q: int, r: int) -> str:
    return f"e:{q},{r}"


def axial_distance(q: int, r: int, center_q: int, center_r: int) -> int:
    dq = q - center_q
    dr = r - center_r
    return max(abs(dq), abs(dr), abs(dq + dr))


def build_lattice_order(size: int) -> list[AxialSite]:
    center = size // 2
    cells: list[tuple[int, int, int, int]] = []
    for q in range(size):
        for r in range(size):
            dq = q - center
            dr = r - center
            dist = axial_distance(q, r, center, center)
            # Deterministic radial ordering is more stable than the old hash-based tie break.
            cells.append((dist, dq + dr, dr, dq))
    cells.sort()
    return [(center + dq, center + dr) for _, _, dr, dq in cells]


def config_from_sites(size: int, sites: Iterable[AxialSite], grain_count: int) -> ConfigMap:
    config: ConfigMap = {}
    if grain_count <= 0:
        return config
    for q, r in sites:
        if 0 <= q < size and 0 <= r < size:
            config[(q, r)] = config.get((q, r), 0) + grain_count
    return config


def config_from_points(
    size: int,
    points: ConfigMap | Iterable[tuple[int, int, int]],
) -> ConfigMap:
    config: ConfigMap = {}
    if isinstance(points, dict):
        items = ((site[0], site[1], grains) for site, grains in points.items())
    else:
        items = points
    for q, r, grains in items:
        if grains <= 0 or not (0 <= q < size and 0 <= r < size):
            continue
        config[(q, r)] = config.get((q, r), 0) + int(grains)
    return config


def corner_sites(size: int) -> list[AxialSite]:
    return [(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)]


def corner_wedge_config(size: int, grain_count: int = 2, depth: int = 4) -> ConfigMap:
    config: ConfigMap = {}
    for corner_index in range(4):
        for a in range(depth + 1):
            for b in range(depth - a + 1):
                q, r = a, b
                if corner_index == 1:
                    q = size - 1 - a
                elif corner_index == 2:
                    r = size - 1 - b
                elif corner_index == 3:
                    q = size - 1 - a
                    r = size - 1 - b
                weight = depth - (a + b) + 1
                config[(q, r)] = config.get((q, r), 0) + grain_count * weight
    return config


def expand_program_phase(phase_text: str, phase_span: int = 6) -> list[int]:
    motifs = ["".join(ch for ch in motif if ch.isdigit()) for motif in phase_text.split(",")]
    motifs = [motif for motif in motifs if motif]
    if not motifs:
        return []

    values: list[int] = []
    motif_index = 0
    while len(values) < phase_span:
        motif = motifs[motif_index % len(motifs)]
        for char in motif:
            values.append(int(char))
            if len(values) >= phase_span:
                break
        motif_index += 1
    return values


def parse_program_string(program_text: str, phase_span: int = 6) -> list[list[int]]:
    phases = [phase for phase in program_text.split() if phase.strip()]
    return [expanded for expanded in (expand_program_phase(phase, phase_span) for phase in phases) if expanded]


def make_eisenstein_graph(size: int) -> tuple[UndirectedGraph, dict[str, tuple[int, int]]]:
    if size < 2:
        raise ValueError("size must be at least 2")

    vertices = [eisenstein_vertex(q, r) for q in range(size) for r in range(size)]
    edges: list[Edge] = []
    seen_pairs: set[tuple[str, str]] = set()
    for q in range(size):
        for r in range(size):
            source = eisenstein_vertex(q, r)
            for dq, dr in EISENSTEIN_NEIGHBOR_OFFSETS:
                nq = q + dq
                nr = r + dr
                if not (0 <= nq < size and 0 <= nr < size):
                    continue
                target = eisenstein_vertex(nq, nr)
                pair = tuple(sorted((source, target)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                edges.append(Edge(source, target))

    center = size // 2
    graph = UndirectedGraph(
        vertices=vertices,
        edges=edges,
        metadata={
            "graph_family": "eisenstein",
            "rows": size,
            "cols": size,
            "size": size,
            "center_vertex": eisenstein_vertex(center, center),
            "neighbor_offsets": list(EISENSTEIN_NEIGHBOR_OFFSETS),
            "target_domain": "eisenstein_sandpile",
        },
    )
    # The image projection remains square-grid friendly while still preserving axial ids.
    layout = {eisenstein_vertex(q, r): (q, r) for q in range(size) for r in range(size)}
    return graph, layout


def centered_configuration(model: SandpileModel, grain: int = 1) -> SandpileConfiguration:
    size = int(model.graph.metadata["size"])
    center = size // 2
    center_vertex = eisenstein_vertex(center, center)
    chips = {vertex: 0 for vertex in model.graph.vertices if vertex != model.sink}
    if center_vertex == model.sink:
        raise ValueError("chosen sink overlaps the center vertex")
    chips[center_vertex] = grain
    return SandpileConfiguration(model=model, chips=chips)


def configuration_from_site_map(model: SandpileModel, site_map: ConfigMap) -> SandpileConfiguration:
    chips = {vertex: 0 for vertex in model.active_vertices}
    for (q, r), grain_count in site_map.items():
        vertex = eisenstein_vertex(q, r)
        if vertex == model.sink or vertex not in chips:
            continue
        chips[vertex] = chips.get(vertex, 0) + int(grain_count)
    return SandpileConfiguration(model=model, chips=chips)


def configuration_from_program_text(
    model: SandpileModel,
    program_text: str,
    phase_span: int = 6,
) -> SandpileConfiguration:
    size = int(model.graph.metadata["size"])
    lattice_order = build_lattice_order(size)
    phases = parse_program_string(program_text, phase_span=phase_span)
    site_map: ConfigMap = {}
    site_index = 0
    for phase in phases:
        for grain_count in phase:
            if site_index >= len(lattice_order):
                break
            site = lattice_order[site_index]
            if grain_count > 0:
                site_map[site] = site_map.get(site, 0) + grain_count
            site_index += 1
    return configuration_from_site_map(model, site_map)
