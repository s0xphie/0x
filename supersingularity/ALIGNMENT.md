Supersingularity Alignment

This note maps the theory PDFs to the current codebase.

Scoping note

- Future agents should start with `SCOPE.md`, then read this file together with `ARCHITECTURE.md`, `ROADMAP.md`, and `INVARIANTS.md`.

Source theory

- `Sandpile_groups_of_supersingular_isogeny_graphs.pdf`
- `Computing_sandpile_configurations_using_integer_li.pdf`
- `hypergraphs.pdf`

Core claim

The package should evolve toward a graph-native sandpile and rewrite system whose higher-order relations can eventually be compiled into a hypergraph. The regular grid case is the calibration space. The supersingular isogeny case is the intended mathematical target.

Theory to preserve

- Supersingular isogeny graphs are graph objects, not image objects.
- Sandpile groups come from reduced Laplacians with an explicit sink choice.
- Edge multiplicity and degree are semantically meaningful.
- Stabilization and recurrence are graph-native concepts.
- Update events, rewrite order, and causal dependence matter.
- Hypergraph compilation should happen only after relation types and invariance behavior are sufficiently stable.

Module alignment

- `graph.py`
  Owns graph semantics, sandpile models, Laplacians, stabilization, and invariants.
- `regular.py`
  Owns the regular grid calibration case and vertex layouts for projection.
- `simulation.py`
  Owns state persistence, recursive generation, dedupe, canonical-state indexing, and rewrite-rule execution over stored surfaces.
- `dag.py`
  Owns typed derivations, ontology records, hypergraph candidates, and production pointers.
- `netpbm.py`
  Owns image parsing and serialization only.
- `viewer.py`
  Owns terminal traversal and visual intuition only.

Important current gap

The recursive `.pgm` machinery is more operational than the supersingular-isogeny implementation. The DAG and production-pointer work should be treated as the bridge that keeps the current regular-grid experiments aligned with the eventual supersingular target.

Near-term interpretation

- Regular Abelian sandpile runs are executable probes.
- Canonical-state collapse is a quotient view over those probes.
- Hypergraph candidates are provisional higher-order relations.
- Production pointers are bounded continuation artifacts.

Long-term interpretation

- Replace regular-grid-only semantics with graph-native semantics wherever possible.
- Add a supersingular isogeny graph constructor and associated metadata.
- Compare update-order behavior and recurrence structure across graph families.
