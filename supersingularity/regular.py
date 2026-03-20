from __future__ import annotations

from dataclasses import dataclass

from .graph import Edge, SandpileConfiguration, SandpileModel, UndirectedGraph


def grid_vertex(x: int, y: int) -> str:
    return f"v:{x},{y}"


def make_grid_graph(rows: int, cols: int) -> tuple[UndirectedGraph, dict[str, tuple[int, int]]]:
    vertices = [grid_vertex(x, y) for y in range(rows) for x in range(cols)]
    edges: list[Edge] = []
    for y in range(rows):
        for x in range(cols):
            if x + 1 < cols:
                edges.append(Edge(grid_vertex(x, y), grid_vertex(x + 1, y)))
            if y + 1 < rows:
                edges.append(Edge(grid_vertex(x, y), grid_vertex(x, y + 1)))
    layout = {grid_vertex(x, y): (x, y) for y in range(rows) for x in range(cols)}
    center_vertex = grid_vertex(cols // 2, rows // 2)
    metadata = {
        "rows": rows,
        "cols": cols,
        "center_vertex": center_vertex,
        "graph_family": "grid",
    }
    return UndirectedGraph(vertices=vertices, edges=edges, metadata=metadata), layout


def centered_configuration(model: SandpileModel, grain: int = 1) -> SandpileConfiguration:
    rows = int(model.graph.metadata["rows"])
    cols = int(model.graph.metadata["cols"])
    center_x = cols // 2
    center_y = rows // 2
    center_vertex = grid_vertex(center_x, center_y)
    chips = {vertex: 0 for vertex in model.graph.vertices if vertex != model.sink}
    if center_vertex == model.sink:
        raise ValueError("chosen sink overlaps the center vertex")
    chips[center_vertex] = grain
    return SandpileConfiguration(model=model, chips=chips)
