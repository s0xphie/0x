Supersingularity Invariants

Scoping note

- Future agents should read `SCOPE.md` and `README.md` before relying on this file.

Semantic invariants

- Graph semantics dominate image semantics.
- Python-directed semantic control currently dominates compiled acceleration helpers.
- Local state uniqueness is provisional; stable relation classes are more important than naive one-off distinctness.
- A sink is part of the sandpile model, not optional metadata.
- Reduced Laplacian conventions must remain explicit.
- Edge multiplicity and degree must not be discarded.
- Stabilization is a semantic event, not merely a visual effect.
- The production pointer is the current scope boundary for safe continuation.
- Scope expansion into wider `Codeletteria` context is allowed only when it still aligns with the active production pointer and declared theory anchors.

Storage invariants

- Stored state must remain parseable and reproducible.
- Canonical collapse must preserve provenance.
- A deduplicated state must still resolve to its canonical content.
- Manifests must reference stable state identities.

DAG invariants

- DAG nodes emit typed semantic objects, not arbitrary blobs.
- Rewrite, stabilization, collapse, and recurrence should remain distinguishable.
- Stego decode/apply/project/encode phases should remain distinguishable from sandpile-native phases.
- Hypergraph candidates are provisional until relation classes stabilize.
- Compilation should follow demonstrated structure, not precede it.

Production-pointer invariants

- A production pointer must remain bounded by explicit recursion limits.
- A production pointer must stay scoped to a ray.
- Preferred continuation must be derived deterministically from recorded context.
- Pointer manifests must be serializable and reloadable.
- Pointer safety bounds must remain explicit.
- Any compiled helper integrated into the system must remain callable under Python control and must not supersede pointer-defined scope.

Supersingular target invariants

- The long-term target is sandpile / critical-group structure on supersingular isogeny graphs.
- Regular grids are calibration cases, not final semantics.
- The code should preserve the possibility that what appears non-unique in the Abelian sandpile stabilization game becomes uniquely meaningful only through ordered relation, recurrence, and collapse structure.
- The code must not conflate image adjacency with isogeny adjacency.
- The theory PDFs constrain the architecture even when the implementation is incomplete.
- Any future universal self-distinguishing or diagonal-like layer should be modeled through Oxfoi invariance and supersingular/isogeny relation geometry, not reduced to a flat enumeration metaphor that erases those structures.

Oxfoi and Triton VM invariants

- If Oxfoi or Triton VM semantics are integrated, the base arithmetic field is the B-field `F_p` with Oxfoi prime `p = 2^64 - 2^32 + 1`.
- Registers and RAM cells must be interpreted as B-field elements unless an explicit extension-field step is being modeled.
- Do not hard-code Harvard architecture assumptions unless an integrated machine model requires them.
- Do not hard-code stack-machine assumptions unless an integrated machine model requires them.
- Instruction width is not uniform. Instructions may occupy one word or two words, and any instruction-pointer or production-pointer model must preserve this fact.
- Single-word and double-word instructions must not be normalized into one fixed-width encoding if that would erase program semantics.
- If extension-field reasoning is required for soundness, the X-field is `F_{p^3} = F_p[X] / <X^3 - X + 1>`, using the Shah polynomial `X^3 - X + 1`.
- B-field semantics and X-field semantics must remain distinguishable in the code and in manifests.
- Any future arithmetization layer should preserve the fact that the transition function is intended to yield low-degree transition-verification polynomials over `F_p`.

Continuity invariants

- The initial commit remains a projected reference state of the original model/data/config relation.
- Later commits should refine or extend that projection rather than silently replace it.
- The system should become increasingly self-descriptive, but not by dropping the original external theory anchors.

Things this repo must not conflate

- Storage format with mathematical object.
- Viewer intuition with proof of correctness.
- Recursive occurrence tree with final causal or hypergraph structure.
- Canonical state identity with loss of branch history.
- Current regular-grid experiments with completed supersingular-isogeny support.
- Compiled acceleration with semantic authority.
- Wider `Codeletteria` context with permission to drift outside production-pointer scope.
