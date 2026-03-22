Supersingularity Invariants

Scoping note

- Future agents should read `SCOPE.md` and `README.md` before relying on this file.

Semantic invariants

- Graph semantics dominate image semantics.
- A sink is part of the sandpile model, not optional metadata.
- Reduced Laplacian conventions must remain explicit.
- Edge multiplicity and degree must not be discarded.
- Stabilization is a semantic event, not merely a visual effect.

Storage invariants

- Stored state must remain parseable and reproducible.
- Canonical collapse must preserve provenance.
- A deduplicated state must still resolve to its canonical content.
- Manifests must reference stable state identities.

DAG invariants

- DAG nodes emit typed semantic objects, not arbitrary blobs.
- Rewrite, stabilization, collapse, and recurrence should remain distinguishable.
- Hypergraph candidates are provisional until relation classes stabilize.
- Compilation should follow demonstrated structure, not precede it.

Production-pointer invariants

- A production pointer must remain bounded by explicit recursion limits.
- A production pointer must stay scoped to a ray.
- Preferred continuation must be derived deterministically from recorded context.
- Pointer manifests must be serializable and reloadable.
- Pointer safety bounds must remain explicit.

Supersingular target invariants

- The long-term target is sandpile / critical-group structure on supersingular isogeny graphs.
- Regular grids are calibration cases, not final semantics.
- The code must not conflate image adjacency with isogeny adjacency.
- The theory PDFs constrain the architecture even when the implementation is incomplete.

Oxfoi and Triton VM invariants

- If Oxfoi or Triton VM semantics are integrated, the base arithmetic field is the B-field `F_p` with Oxfoi prime `p = 2^64 - 2^32 + 1`.
- Registers, stack elements, and RAM cells must be interpreted as B-field elements unless an explicit extension-field step is being modeled.
- Triton VM semantics assume a Harvard architecture: program memory is read-only and distinct from RAM.
- Triton VM is a stack machine with RAM, so stack transitions and RAM transitions must remain distinguishable in semantic records.
- Instruction width is not uniform. Instructions may occupy one word or two words, and any instruction-pointer or production-pointer model must preserve this fact.
- Single-word and double-word instructions must not be normalized into one fixed-width encoding if that would erase program semantics.
- If extension-field reasoning is required for soundness, the X-field is `F_{p^3} = F_p[X] / <X^3 - X + 1>`, using the Shah polynomial `X^3 - X + 1`.
- B-field semantics and X-field semantics must remain distinguishable in the code and in manifests.
- Any future arithmetization layer should preserve the fact that the transition function is intended to yield low-degree transition-verification polynomials over `F_p`.

Things this repo must not conflate

- Storage format with mathematical object.
- Viewer intuition with proof of correctness.
- Recursive occurrence tree with final causal or hypergraph structure.
- Canonical state identity with loss of branch history.
- Current regular-grid experiments with completed supersingular-isogeny support.
