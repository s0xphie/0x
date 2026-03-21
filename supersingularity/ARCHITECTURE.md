Supersingularity Architecture

Agent startup

- For future scoping, start with `SCOPE.md`.
- Treat `README.md`, `ALIGNMENT.md`, `ROADMAP.md`, and `INVARIANTS.md` as the core context surface.
- Treat the wider `Codeletteria/` repository as supporting context, not the default semantic center.

Package layers

1. Theory layer

- The PDFs define the intended mathematics and constraints.

2. Semantic layer

- `graph.py` defines graphs, sandpile models, configurations, stabilization, and invariants.
- This layer should dominate the interpretation of the system.

3. Execution and storage layer

- `simulation.py` executes rewrite and stabilization processes.
- `workspace/` stores state surfaces, recursive trees, canonical states, and manifests.

4. Orchestration layer

- `dag.py` records typed transformations and higher-order relations.
- `compiled.py` lets Python call compiled helpers without giving up semantic control.

5. Visualization layer

- `viewer.py` renders traversals for intuition and inspection.

6. Compiled acceleration layer

- Rust helpers may accelerate scanning, indexing, and carrier inspection.
- This layer is subordinate to Python scope and production-pointer logic.

Meaning of the main objects

- Graph
  The stable structural object.
- Configuration
  A typed chip distribution over a graph or projected surface.
- Rewrite rule
  A successor or transformation rule applied to a state.
- Update event
  A single typed transformation step.
- Canonical state
  A deduplicated representative of repeated stored states.
- Hypergraph candidate
  A provisional higher-order relation between states, events, and collapse objects.
- Production pointer
  A bounded continuation record that defines a safe local construction ray.
- Compiled workspace index
  A performance-oriented summary artifact consumed by Python.

Boundaries to keep clean

- `netpbm.py` does not define semantics.
- `.pgm` storage is a substrate, not the primary mathematics.
- `viewer.py` should reveal structure, not invent it.
- `dag.py` should describe semantic relations, not become a rendering layer.
- Compiled helpers should accelerate narrow subroutines, not redefine the system’s scope.
- Scope expansion into the wider repository must still pass through production-pointer-aligned Python orchestration.

Current execution flow

- Build or load graph/state objects.
- Generate or propagate configurations.
- Stabilize or rewrite.
- Archive surfaces into `workspace/state_tree/`.
- Deduplicate repeats into `workspace/canonical_states/`.
- Emit DAG records such as ontology records, hypergraph candidates, and production pointers.
- Optionally call compiled helpers for indexing or carrier inspection.
- View the resulting recursive object in the terminal.
