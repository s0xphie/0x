Supersingularity Roadmap

Scoping note

- Use `SCOPE.md` to recover the expected startup reading order before acting on this roadmap.

Completed work

0a. Unified engine (`engine.py`)

- 0x/ tree parser, scope derivation, iff classification.
- 12-glyph interval decoder (SPEC §4): 4 bands × 3 elements, nearest-anchor decoding.
- Boundary potential extraction (SPEC §5): ϕ_z(u,v) = h_z(u) - h_z(v).
- PGM comment metadata read-back.
- Five primitive instructions as compositional `InstructionRecord` log (SPEC §8).
- Unified hypergraph builder: 6757 nodes, 6818 edges, 23496 boundary edges.

0b. Wolfram Language bridge (`wolfram.py`)

- WL serialization helpers for lists, associations, matrices.
- PGM → Wolfram matrix export.
- `SandpileTopple` ResourceFunction bridge.
- Hypergraph → `HypergraphPlot` / `AdjacencyTensor` / `KirchhoffTensor` export.
- 12-glyph interval decoder in WL.
- Boundary potential → weighted directed graph in WL.
- Recursive function correspondence: five instructions ↔ μ-recursive primitives.
- `WolframModel` / `MultiwaySystem` rule generation from engine edges.
- Full workbook generator (`workbook.wl`): 8 sections, ~1MB evaluable output.

0c. The Universal Argument

- `Recursive_Functions.pdf` establishes: Zero, Successor, Projection → Composition, Primitive Recursion → μ-recursion → T-computability.
- Five instructions map: singularity↔Zero, init↔Successor, scope↔Projection, goto↔Composition, iff↔Primitive Recursion.
- `ASM_TC.pdf` confirms: Abelian sandpiles on Z³ are Turing-complete.
- SPEC §10 diagonal function D(x) = F_x(x) + 1 closes universality.
- Wolfram workbook §6 implements this correspondence as evaluable WL code.

Immediate next work

1. Wolfram evaluation & verification

- Evaluate `workbook.wl` in Mathematica or via `wolframscript`.
- Verify `SandpileTopple` reproduces the spine states from 0x/ tree.
- Verify `HypergraphPlot` renders the unified hypergraph correctly.
- Verify `MultiwaySystem` captures goto branching nondeterminism.
- Verify Kirchhoff tensor matches `graph.py` Laplacian for the 32×32 grid.
- Validate the diagonal function produces undecidable self-reference.

2. Update-event layer

- Add explicit `UpdateEventRecord` objects.
- Distinguish rewrite, stabilization, collapse, and reflection events.

3. Causal layer

- Add `CausalDependencyRecord` and a `CausalGraphIndex`.
- Compare admissible update orders where possible.

4. Production-pointer refinement

- Keep `ray_id` stable.
- Improve output ranking heuristics.
- Add manifest consumers and validation.

5. Supersingular scaffold

- Add `build_supersingular_isogeny_graph(...)`.
- Define metadata for prime p = 0xffffffff00000001, isogeny degree, sink, and multiplicity conventions.
- Wire into Wolfram workbook §8 (currently a stub).

6. Graph-native execution

- Shift more simulation semantics from image-neighbor rules to graph-neighbor rules.
- Keep `.pgm` as projection and storage.

7. Viewer refinement

- Show canonical multiplicity.
- Show preferred production ray.
- Show recurrence and collapse markers.
- Add modes for quotient-state and causal traversal.

8. Hypergraph compilation readiness

- Refine relation classes.
- Check whether relation types and update-order behavior are stable enough to justify compilation.
- Wolfram `WolframModel` evaluation as empirical test of rule-system convergence.

9. Wolfram workbook extension

- `.nb` notebook generation (cell-structured for Mathematica front end).
- Interactive manipulation of scope/period parameters.
- Side-by-side comparison: Python engine output vs Wolfram evaluation.
- Z³ lattice visualization with `Graphics3D`.

What not to rush

- Full hypergraph compilation before causal and recurrence semantics settle.
- Treating grid-image behavior as if it were already supersingular-isogeny semantics.
- Overfitting the architecture to the current viewer instead of the graph theory.
- Assuming Wolfram evaluation matches without empirical verification.
