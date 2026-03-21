Supersingularity Package

This package is a clean workspace for supersingular-isogeny graph experiments, sandpile-group projections, and later simulation work.

Scope first

- If an agent is asked to "scope the singularity", start with `SCOPE.md`.
- The main design documents are:
  - `SCOPE.md`
  - `CRYSTALLIZATION.md`
  - `MACHINE.md`
  - `UNIVERSAL_ARGUMENT.md`
  - `ALIGNMENT.md`
  - `ARCHITECTURE.md`
  - `ROADMAP.md`
  - `INVARIANTS.md`

What it contains

- `graph.py`: graph, sandpile model, Laplacian, and invariant objects.
- `dag.py`: a small DAG runner and a first `graph -> sandpile -> image` pipeline.
- `netpbm.py`: tiny Netpbm reader/writer for `P1` and `P2` images.
- `simulation.py`: image-backed simulation workspace utilities.

Design direction

- The graph is the stable structural object.
- Sandpile algebra is computed from the graph, not mixed into image state.
- Simulation state can live in Netpbm files, so a run can read and write directly to image surfaces.
- The current regular-grid path is a calibration case.
- The supersingular-isogeny path is the intended mathematical target.

Example

```python
from supersingularity import Edge, GraphToSandpilePipeline, UndirectedGraph
from supersingularity.dag import seed_graph_context

graph = UndirectedGraph(
    vertices=["a", "b", "c"],
    edges=[
        Edge("a", "b"),
        Edge("b", "c"),
        Edge("c", "a"),
    ],
)

pipeline = GraphToSandpilePipeline()
context = seed_graph_context(graph, sink="a", workspace_root="supersingularity/workspace")
result = pipeline.run(context)

print(result["sandpile_group"])
print(result["image_path"])
```

Each projected regular state is also archived into a recursive tree under `workspace/state_tree/`. The state folder is indexed by a compact successor id like `0x01`, `0x02`, `0x03`, while the full pixel signature remains available in Python on the archived state object.

Example tree shape

```text
supersingularity/workspace/state_tree/
  sandpile_state0x01/
    sandpile_state0x01.pgm
    1/
      sandpile_state0x02/
        sandpile_state0x02.pgm
        11/
          ...
```

Unary successor chain

```python
from supersingularity import generate_successor_chain
from supersingularity.simulation import ImageStateSurface, SimulationWorkspace

workspace = SimulationWorkspace.create("supersingularity/workspace")
surface = ImageStateSurface.from_path("supersingularity/workspace/states/sandpile_state.pgm")
chain = generate_successor_chain(workspace, surface, depth=4)

for state in chain:
    print(state.image_path)
```

For the regular Abelian sandpile path, this now treats `succ(state)` as "add one grain to the center pixel" by default, then stabilize. Archives only recurse into unary branch labels like `1`, `11`, `111` when stabilization actually produces topples, up to depth `16`.

Regular Abelian sandpile image state

```python
from supersingularity import centered_configuration, make_grid_graph
from supersingularity.dag import RegularSandpileStatePipeline
from supersingularity.graph import SandpileModel
from supersingularity.simulation import SimulationWorkspace

graph, vertex_layout = make_grid_graph(rows=5, cols=5)
model = SandpileModel(graph=graph, sink="v:0,0")
configuration = centered_configuration(model, grain=1)
workspace = SimulationWorkspace.create("supersingularity/workspace")

pipeline = RegularSandpileStatePipeline()
result = pipeline.run(
    {
        "configuration": configuration,
        "workspace": workspace,
        "vertex_layout": vertex_layout,
        "grid_rows": 5,
        "grid_cols": 5,
    }
)

print(result["image_path"])
```

Simulation workspace layout

```text
supersingularity/workspace/
  states/
    sandpile_group.pgm
  runs/
```
