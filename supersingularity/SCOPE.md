Supersingularity Scope

Use this file when an agent is asked to "scope the singularity" or re-scope the `supersingularity` repo.

Outer context

- `supersingularity/` is the primary working package.
- The wider `Codeletteria/` directory is relevant context when it supports `supersingularity` semantics, compiled helpers, theory references, or production tooling.
- Scope expansion into the wider repository is allowed only when it still aligns with the current production-pointer and does not displace Python as the semantic control layer.
- When expanding outward intentionally, read `../CODELETTERIA_SCOPE.md` before acting.

Startup reading order

1. `README.md`
2. `CRYSTALLIZATION.md`
3. `MACHINE.md`
4. `UNIVERSAL_ARGUMENT.md`
5. `ALIGNMENT.md`
6. `ARCHITECTURE.md`
7. `ROADMAP.md`
8. `INVARIANTS.md`

Expanded reading order when widening scope into `Codeletteria/`

1. `../CODELETTERIA_SCOPE.md`
2. `../README.md`
3. `../QUICKSTART.md`
4. `../DASHBOARD_README.md`
5. `../RUST_PROGRAM.md`
6. `README.md`
7. `CRYSTALLIZATION.md`
8. `MACHINE.md`
9. `UNIVERSAL_ARGUMENT.md`
10. `ALIGNMENT.md`
11. `ARCHITECTURE.md`
12. `ROADMAP.md`
13. `INVARIANTS.md`

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
- Python currently owns scope, production-pointer logic, and semantic control flow.
- Compiled helpers may accelerate subroutines, but they remain subordinate to Python-directed scope.

Current repo interpretation

- `graph.py` owns graph-native sandpile semantics.
- `dag.py` owns typed transformations, ontology records, hypergraph candidates, and production pointers.
- `simulation.py` owns recursive state generation, dedupe, canonical-state indexing, and stored-memory operations.
- `viewer.py` owns terminal traversal and visual intuition.
- `supersingular.py` is currently a scaffold entry point for the supersingular-isogeny graph family, not a final mathematical implementation.
- `compiled.py` owns Python-controlled access to compiled acceleration helpers.

Theory anchors

- `Sandpile_groups_of_supersingular_isogeny_graphs.pdf`
- `Computing_sandpile_configurations_using_integer_li.pdf`
- `hypergraphs.pdf`

What an agent should summarize before making changes

- The current role of `graph.py`, `dag.py`, `simulation.py`, `viewer.py`, and `supersingular.py`
- The current role of `compiled.py` and any Rust helper binaries it calls
- The current state of `workspace/state_tree`, `workspace/canonical_states`, and `workspace/runs`
- The current production-pointer and hypergraph-candidate behavior
- The gap between the regular calibration path and the supersingular target
- The relation between the current state of `supersingularity/` and the wider `Codeletteria/` repository, if scope expansion is being considered

Continuity rule

- The initial commit should be treated as a projected reference state of the original model/data/config relation.
- Later work should refine, extend, and accelerate that projection rather than erase it.

Important constraint

If there is a conflict between convenience and semantics, prefer the semantics described in `INVARIANTS.md`.
