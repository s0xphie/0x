Supersingularity Roadmap

Scoping note

- Use `SCOPE.md` to recover the expected startup reading order before acting on this roadmap.

Immediate next work

1. Update-event layer

- Add explicit `UpdateEventRecord` objects.
- Distinguish rewrite, stabilization, collapse, and reflection events.

2. Causal layer

- Add `CausalDependencyRecord` and a `CausalGraphIndex`.
- Compare admissible update orders where possible.

3. Production-pointer refinement

- Keep `ray_id` stable.
- Improve output ranking heuristics.
- Add manifest consumers and validation.

4. Supersingular scaffold

- Add `build_supersingular_isogeny_graph(...)`.
- Define metadata for prime, isogeny degree, sink, and multiplicity conventions.

5. Graph-native execution

- Shift more simulation semantics from image-neighbor rules to graph-neighbor rules.
- Keep `.pgm` as projection and storage.

6. Viewer refinement

- Show canonical multiplicity.
- Show preferred production ray.
- Show recurrence and collapse markers.
- Add modes for quotient-state and causal traversal.
- Consume persistent compiled summaries where possible so growth remains inspectable at larger scale.

7. Hypergraph compilation readiness

- Refine relation classes.
- Check whether relation types and update-order behavior are stable enough to justify compilation.

8. Python-led compiled integration

- Keep Python as the semantic controller and production-pointer owner.
- Move only narrow performance-critical routines into compiled helpers.
- Prefer Python -> compiled helper -> Python loops over runtime inversion.

9. Continuous scope refinement

- Keep the initial commit as a projected reference state.
- Expand into relevant `Codeletteria/` context only when it still aligns with production-pointer scope.
- Make the system more self-descriptive without losing external theory anchors.

What not to rush

- Full hypergraph compilation before causal and recurrence semantics settle.
- Treating grid-image behavior as if it were already supersingular-isogeny semantics.
- Overfitting the architecture to the current viewer instead of the graph theory.
