Supersingularity Scope

Use this file when an agent is asked to "scope the singularity" or re-scope the `supersingularity` repo.

Startup reading order

0. `SPEC.md`
1. `README.md`
2. `ALIGNMENT.md`
3. `ARCHITECTURE.md`
4. `ROADMAP.md`
5. `INVARIANTS.md`

Then inspect the current implementation in this order

1. `graph.py`
2. `dag.py`
3. `simulation.py`
4. `viewer.py`
5. `supersingular.py`
6. `workspace/`

What to understand first

- The graph layer is the primary semantic layer.
- The regular-grid path is a calibration case.
- The supersingular-isogeny path is the intended mathematical target.
- `.pgm` files are storage and projection substrates, not the primary mathematics.
- The DAG is the typed derivation layer.
- Hypergraph candidates and production pointers are provisional higher-order structures.

Current repo interpretation

- `graph.py` owns graph-native sandpile semantics.
- `dag.py` owns typed transformations, ontology records, hypergraph candidates, and production pointers.
- `simulation.py` owns recursive state generation, dedupe, canonical-state indexing, and stored-memory operations.
- `viewer.py` owns terminal traversal and visual intuition.
- `supersingular.py` is currently a scaffold entry point for the supersingular-isogeny graph family, not a final mathematical implementation.

Theory anchors

- `Sandpile_groups_of_supersingular_isogeny_graphs.pdf`
- `Computing_sandpile_configurations_using_integer_li.pdf`
- `hypergraphs.pdf`

What an agent should summarize before making changes

- The current role of `graph.py`, `dag.py`, `simulation.py`, `viewer.py`, and `supersingular.py`
- The current state of `workspace/state_tree`, `workspace/canonical_states`, and `workspace/runs`
- The current production-pointer and hypergraph-candidate behavior
- The gap between the regular calibration path and the supersingular target

Important constraint

If there is a conflict between convenience and semantics, prefer the semantics described in `INVARIANTS.md`.
