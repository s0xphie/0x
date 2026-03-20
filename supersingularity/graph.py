from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from math import gcd
from typing import Any


VertexId = str


@dataclass(frozen=True)
class Edge:
    u: VertexId
    v: VertexId
    multiplicity: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_endpoints(self) -> tuple[VertexId, VertexId]:
        return tuple(sorted((self.u, self.v)))


@dataclass
class UndirectedGraph:
    vertices: list[VertexId]
    edges: list[Edge]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        vertex_set = set(self.vertices)
        for edge in self.edges:
            if edge.u not in vertex_set or edge.v not in vertex_set:
                raise ValueError(f"edge references unknown vertex: {edge}")
            if edge.multiplicity < 1:
                raise ValueError(f"edge multiplicity must be positive: {edge}")

    def adjacency(self) -> dict[VertexId, dict[VertexId, int]]:
        result = {vertex: {} for vertex in self.vertices}
        for edge in self.edges:
            if edge.u == edge.v:
                result[edge.u][edge.v] = result[edge.u].get(edge.v, 0) + 2 * edge.multiplicity
                continue
            result[edge.u][edge.v] = result[edge.u].get(edge.v, 0) + edge.multiplicity
            result[edge.v][edge.u] = result[edge.v].get(edge.u, 0) + edge.multiplicity
        return result

    def degree(self, vertex: VertexId) -> int:
        return sum(self.adjacency()[vertex].values())

    def laplacian(self, sink: VertexId | None = None) -> "LaplacianData":
        adjacency = self.adjacency()
        matrix: list[list[int]] = []
        for row_vertex in self.vertices:
            row: list[int] = []
            for col_vertex in self.vertices:
                if row_vertex == col_vertex:
                    row.append(sum(adjacency[row_vertex].values()))
                else:
                    row.append(-adjacency[row_vertex].get(col_vertex, 0))
            matrix.append(row)

        if sink is None:
            return LaplacianData(
                vertex_order=list(self.vertices),
                matrix=matrix,
                reduced_vertex_order=list(self.vertices),
                reduced_matrix=[list(row) for row in matrix],
            )

        if sink not in self.vertices:
            raise ValueError(f"unknown sink vertex: {sink}")

        sink_index = self.vertices.index(sink)
        reduced_vertices = [v for v in self.vertices if v != sink]
        reduced_matrix = [
            [value for col_index, value in enumerate(row) if col_index != sink_index]
            for row_index, row in enumerate(matrix)
            if row_index != sink_index
        ]
        return LaplacianData(
            vertex_order=list(self.vertices),
            matrix=matrix,
            reduced_vertex_order=reduced_vertices,
            reduced_matrix=reduced_matrix,
        )


@dataclass
class SandpileModel:
    graph: UndirectedGraph
    sink: VertexId
    metadata: dict[str, Any] = field(default_factory=dict)

    def laplacian(self) -> "LaplacianData":
        return self.graph.laplacian(self.sink)

    @property
    def active_vertices(self) -> list[VertexId]:
        return [vertex for vertex in self.graph.vertices if vertex != self.sink]


@dataclass
class LaplacianData:
    vertex_order: list[VertexId]
    matrix: list[list[int]]
    reduced_vertex_order: list[VertexId]
    reduced_matrix: list[list[int]]


@dataclass
class SandpileGroupInvariant:
    invariant_factors: list[int]
    order: int
    rank: int
    sylow: dict[int, list[int]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_reduced_laplacian(
        cls,
        reduced_matrix: list[list[int]],
        metadata: dict[str, Any] | None = None,
    ) -> "SandpileGroupInvariant":
        if not reduced_matrix:
            return cls(invariant_factors=[], order=1, rank=0, sylow={}, metadata=metadata or {})

        diagonal = _smith_diagonal(reduced_matrix)
        invariant_factors = [abs(value) for value in diagonal if abs(value) > 1]
        order = 1
        for value in invariant_factors:
            order *= value

        if not invariant_factors:
            order = 1

        return cls(
            invariant_factors=invariant_factors,
            order=order,
            rank=len(invariant_factors),
            sylow=_factor_invariants_by_prime(invariant_factors),
            metadata=metadata or {},
        )


@dataclass
class SandpileConfiguration:
    model: SandpileModel
    chips: dict[VertexId, int]

    def total_chips(self) -> int:
        return sum(self.chips.values())

    def is_stable(self) -> bool:
        adjacency = self.model.graph.adjacency()
        for vertex in self.model.active_vertices:
            if self.chips.get(vertex, 0) >= sum(adjacency[vertex].values()):
                return False
        return True

    def topple_once(self, vertex: VertexId) -> "SandpileConfiguration":
        if vertex == self.model.sink:
            raise ValueError("cannot topple the sink")

        adjacency = self.model.graph.adjacency()
        degree = sum(adjacency[vertex].values())
        if self.chips.get(vertex, 0) < degree:
            raise ValueError(f"vertex {vertex} is not unstable")

        updated = dict(self.chips)
        updated[vertex] = updated.get(vertex, 0) - degree
        for neighbor, multiplicity in adjacency[vertex].items():
            if neighbor == self.model.sink:
                continue
            updated[neighbor] = updated.get(neighbor, 0) + multiplicity
        return SandpileConfiguration(model=self.model, chips=updated)

    def canonical_chips(self) -> dict[VertexId, int]:
        return {vertex: self.chips.get(vertex, 0) for vertex in self.model.active_vertices}


@dataclass
class ToppleRecord:
    vertex: VertexId
    count: int


@dataclass
class StabilizationResult:
    initial: SandpileConfiguration
    stabilized: SandpileConfiguration
    total_topples: int
    topple_records: list[ToppleRecord]


def add_chip(configuration: SandpileConfiguration, vertex: VertexId, amount: int = 1) -> SandpileConfiguration:
    if amount < 0:
        raise ValueError("chip amount must be non-negative")
    if vertex == configuration.model.sink:
        raise ValueError("cannot add chips directly to the sink")
    if vertex not in configuration.model.graph.vertices:
        raise ValueError(f"unknown vertex: {vertex}")

    updated = configuration.canonical_chips()
    updated[vertex] = updated.get(vertex, 0) + amount
    return SandpileConfiguration(model=configuration.model, chips=updated)


def rebind_configuration(
    configuration: SandpileConfiguration,
    model: SandpileModel,
) -> SandpileConfiguration:
    if configuration.model.sink != model.sink:
        raise ValueError("configuration sink does not match the target sandpile model")

    source_vertices = set(configuration.model.active_vertices)
    target_vertices = set(model.active_vertices)
    if source_vertices != target_vertices:
        raise ValueError("configuration vertices do not match the target sandpile model")
    if _active_adjacency_signature(configuration.model) != _active_adjacency_signature(model):
        raise ValueError("configuration graph structure does not match the target sandpile model")

    rebound = {vertex: configuration.chips.get(vertex, 0) for vertex in model.active_vertices}
    return SandpileConfiguration(model=model, chips=rebound)


def stabilize_configuration(configuration: SandpileConfiguration) -> StabilizationResult:
    adjacency = configuration.model.graph.adjacency()
    current = SandpileConfiguration(
        model=configuration.model,
        chips=configuration.canonical_chips(),
    )
    topple_records: list[ToppleRecord] = []
    total_topples = 0

    while True:
        unstable_vertices = [
            vertex
            for vertex in current.model.active_vertices
            if current.chips.get(vertex, 0) >= sum(adjacency[vertex].values())
        ]
        if not unstable_vertices:
            break

        vertex = unstable_vertices[0]
        degree = sum(adjacency[vertex].values())
        topple_count = current.chips.get(vertex, 0) // degree
        updated = current.canonical_chips()
        updated[vertex] -= degree * topple_count
        for neighbor, multiplicity in adjacency[vertex].items():
            if neighbor == current.model.sink:
                continue
            updated[neighbor] = updated.get(neighbor, 0) + multiplicity * topple_count

        current = SandpileConfiguration(model=current.model, chips=updated)
        topple_records.append(ToppleRecord(vertex=vertex, count=topple_count))
        total_topples += topple_count

    return StabilizationResult(
        initial=configuration,
        stabilized=current,
        total_topples=total_topples,
        topple_records=topple_records,
    )


def configuration_signature(configuration: SandpileConfiguration) -> str:
    values = [configuration.chips.get(vertex, 0) for vertex in configuration.model.active_vertices]
    width = max(1, len(format(max(values, default=0), "x")))
    encoded = "".join(f"{value:0{width}x}" for value in values)
    return f"0x{encoded}"


def sandpile_features(
    configuration: SandpileConfiguration,
    stabilization: StabilizationResult | None = None,
) -> dict[str, Any]:
    active_vertices = configuration.model.active_vertices
    adjacency = configuration.model.graph.adjacency()
    chips = configuration.canonical_chips()
    stabilized = stabilization.stabilized if stabilization is not None else configuration
    stabilized_chips = stabilized.canonical_chips()

    return {
        "sink": configuration.model.sink,
        "active_vertex_count": len(active_vertices),
        "active_vertices": list(active_vertices),
        "degree_by_vertex": {
            vertex: sum(adjacency[vertex].values())
            for vertex in active_vertices
        },
        "total_chips": configuration.total_chips(),
        "support_size": sum(1 for value in chips.values() if value > 0),
        "is_stable": configuration.is_stable(),
        "pre_stabilization_signature": configuration_signature(configuration),
        "stabilized_signature": configuration_signature(stabilized),
        "stabilized_total_chips": sum(stabilized_chips.values()),
        "stabilized_support_size": sum(1 for value in stabilized_chips.values() if value > 0),
        "total_topples": stabilization.total_topples if stabilization is not None else 0,
        "topple_sequence": [
            {"vertex": record.vertex, "count": record.count}
            for record in (stabilization.topple_records if stabilization is not None else [])
        ],
    }


def _active_adjacency_signature(model: SandpileModel) -> tuple[tuple[VertexId, tuple[tuple[VertexId, int], ...]], ...]:
    adjacency = model.graph.adjacency()
    active_vertices = tuple(model.active_vertices)
    return tuple(
        (
            vertex,
            tuple(
                sorted(
                    (neighbor, multiplicity)
                    for neighbor, multiplicity in adjacency[vertex].items()
                )
            ),
        )
        for vertex in active_vertices
    )


def _determinant(matrix: list[list[int]]) -> int:
    size = len(matrix)
    if size == 0:
        return 1
    if size == 1:
        return matrix[0][0]
    if size == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]

    total = 0
    for col, value in enumerate(matrix[0]):
        minor = [
            [entry for inner_col, entry in enumerate(row) if inner_col != col]
            for row in matrix[1:]
        ]
        total += ((-1) ** col) * value * _determinant(minor)
    return total


def _all_k_minors(matrix: list[list[int]], k: int) -> list[int]:
    from itertools import combinations

    row_indices = range(len(matrix))
    col_indices = range(len(matrix[0])) if matrix else range(0)
    minors: list[int] = []
    for chosen_rows in combinations(row_indices, k):
        for chosen_cols in combinations(col_indices, k):
            minor = [
                [matrix[row][col] for col in chosen_cols]
                for row in chosen_rows
            ]
            minors.append(abs(_determinant(minor)))
    return minors


def _smith_diagonal(matrix: list[list[int]]) -> list[int]:
    rows = len(matrix)
    cols = len(matrix[0]) if matrix else 0
    max_rank = min(rows, cols)
    if max_rank == 0:
        return []

    determinantal_divisors: list[int] = [1]
    for k in range(1, max_rank + 1):
        minors = [minor for minor in _all_k_minors(matrix, k) if minor != 0]
        if not minors:
            break
        determinantal_divisors.append(reduce(gcd, minors))

    diagonal: list[int] = []
    for index in range(1, len(determinantal_divisors)):
        diagonal.append(determinantal_divisors[index] // determinantal_divisors[index - 1])
    return diagonal


def _prime_factorization(value: int) -> dict[int, int]:
    n = abs(value)
    factors: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= n:
        while n % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            n //= divisor
        divisor += 1
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def _factor_invariants_by_prime(invariant_factors: list[int]) -> dict[int, list[int]]:
    sylow: dict[int, list[int]] = {}
    for value in invariant_factors:
        for prime, exponent in _prime_factorization(value).items():
            sylow.setdefault(prime, []).append(prime ** exponent)
    return sylow
