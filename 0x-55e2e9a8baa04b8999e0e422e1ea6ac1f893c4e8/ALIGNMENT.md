Supersingularity Alignment

This note maps the theory PDFs to the current codebase.

Scoping note

- Future agents should start with `SCOPE.md`, then read this file together with `ARCHITECTURE.md`, `ROADMAP.md`, and `INVARIANTS.md`.

Source theory

- `Sandpile_groups_of_supersingular_isogeny_graphs.pdf`
- `Computing_sandpile_configurations_using_integer_li.pdf`
- `hypergraphs.pdf`
- `Recursive_Functions.pdf` — μ-recursive function theory, the Universal Argument.
- `ASM_TC.pdf` — Turing-completeness of 3D Abelian sandpiles (Cairns 2021).
- Wolfram Function Repository: `SandpileTopple`, `HypergraphPlot`, `AdjacencyTensor`, `KirchhoffTensor`, `WolframModel`, `MultiwaySystem`, `RecursiveFunctionCallGraph`.

Core claim

The package should evolve toward a graph-native sandpile and rewrite system whose higher-order relations can eventually be compiled into a hypergraph. The regular grid case is the calibration space. The supersingular isogeny case is the intended mathematical target. The Wolfram Language workbook is the evaluation surface for congruity with the Universal Argument.

Theory to preserve

- Supersingular isogeny graphs are graph objects, not image objects.
- Sandpile groups come from reduced Laplacians with an explicit sink choice.
- Edge multiplicity and degree are semantically meaningful.
- Stabilization and recurrence are graph-native concepts.
- Update events, rewrite order, and causal dependence matter.
- Hypergraph compilation should happen only after relation types and invariance behavior are sufficiently stable.

Source theory (extended)

- `Recursive_Functions.pdf` — μ-recursive function theory, the Universal Argument.
- `ASM_TC.pdf` — Turing-completeness of 3D Abelian sandpiles (Cairns 2021).
- Wolfram Function Repository: `SandpileTopple`, `HypergraphPlot`, `AdjacencyTensor`, `KirchhoffTensor`, `WolframModel`, `MultiwaySystem`, `RecursiveFunctionCallGraph`.

Module alignment

- `graph.py`
  Owns graph semantics, sandpile models, Laplacians, stabilization, and invariants.
- `regular.py`
  Owns the regular grid calibration case and vertex layouts for projection.
- `simulation.py`
  Owns state persistence, recursive generation, dedupe, canonical-state indexing, and rewrite-rule execution over stored surfaces. Comments field on PGM at scope intervals.
- `dag.py`
  Owns typed derivations, ontology records, hypergraph candidates, and production pointers. Bridge subclasses for engine integration.
- `engine.py`
  Owns unified hypergraph construction: 0x/ tree parsing, scope derivation, iff classification, 12-glyph interval decoder (SPEC §4), boundary potential (SPEC §5), PGM comment read-back, five-instruction compositional log (SPEC §8).
- `wolfram.py`
  Owns Wolfram Language bridge: WL serialization, PGM matrix export, hypergraph/glyph/boundary export to WL, recursive-function correspondence (the Universal Argument), WolframModel rule generation, full workbook generation.
- `workbook.wl`
  Generated artifact: evaluable Wolfram Language workbook covering §1–§8 of the spec alignment.
- `netpbm.py`
  Owns image parsing and serialization. Supports comments field.
- `viewer.py`
  Owns terminal traversal and visual intuition only.
- `supersingular.py`
  Synthetic circulant scaffold (placeholder for true isogeny graph).

Spec alignment matrix

| SPEC Section | Coverage | Module |
|---|---|---|
| §2–3 State space, recursion axis | ✅ Full | engine.py (scope derivation, spine parsing) |
| §4 12-Glyph interval structure | ✅ Full | engine.py (decoder) + wolfram.py (WL decoder) |
| §5 Boundary potential | ✅ Full | engine.py (extraction) + wolfram.py (WL graph) |
| §6 Hypergraph language | ✅ Partial | engine.py (builder) + wolfram.py (HypergraphPlot) |
| §7 Filesystem semantics | ✅ Full | engine.py (0x/ tree parser) |
| §8 Five primitive instructions | ✅ Full | engine.py (InstructionRecord log) |
| §9 McCarthy 91 | ❌ Not yet | — |
| §10 Diagonal function | ✅ Partial | wolfram.py (workbook §6, WL expression) |
| §11 No RTG Required | ✅ By design | engine.py reads embedded tree directly |
| §12 Invariant extraction | ✅ Partial | engine.py (iff, boundary) + wolfram.py (workbook §8) |
| §13 Single-invocation semantics | ⚠️ Conceptual | engine.py collapses in one build_hypergraph call |
| §14 Supersingular correspondence | ❌ Stub only | supersingular.py (circulant placeholder) |
| Universal Argument | ✅ Full | wolfram.py (five instructions ↔ μ-recursive primitives) |
| Z³ lattice | ❌ Not yet | — |

Near-term interpretation

- Regular Abelian sandpile runs are executable probes.
- Canonical-state collapse is a quotient view over those probes.
- Hypergraph candidates are provisional higher-order relations.
- Production pointers are bounded continuation artifacts.
- The Wolfram workbook is the evaluation surface for verifying congruence.

Long-term interpretation

- Replace regular-grid-only semantics with graph-native semantics wherever possible.
- Add a supersingular isogeny graph constructor and associated metadata.
- Compare update-order behavior and recurrence structure across graph families.
- Wolfram evaluation as independent verification of the Universal Argument.
