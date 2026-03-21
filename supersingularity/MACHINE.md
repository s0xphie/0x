Supersingularity Machine

Purpose

- This file defines the current unique machine in explicit terms.
- It is meant to stabilize identity, not to freeze future growth.

Machine identity

- The machine is a graph-directed, recursively materialized sandpile system.
- It is not only a viewer, not only a DAG, and not only a collection of `.pgm` files.
- It is the composition of:
  - a semantic graph layer
  - a recursive state generator
  - a typed event/history layer
  - a higher-order relation layer
  - a bounded continuation layer
  - a terminal projection layer

Core asymmetry

- Extension should be simple.
- Expression should be nontrivial.
- The local successor/rewrite rule may remain trivial while the resulting recursive surface, event history, and relation structure become rich.

Current machine components

1. Semantic object

- `graph.py` provides the graph-native object.
- Sandpile meaning is derived from the graph, not from image storage.

2. Initialization object

- `initialization.py` provides the startup initialization vector and startup sequence.
- Startup has:
  - a global recursive horizon
  - a materialized recursive prefix
  - sparse persisted checkpoints
  - a final current machine state

3. Recursive state object

- `simulation.py` materializes and archives recursive surfaces.
- `workspace/state_tree/` stores recursive state occurrence.
- `workspace/canonical_states/` stores deduplicated representatives.

4. Event object

- `dag.py` records typed transformations.
- Startup now exists as:
  - an initialization-vector record
  - a startup event index
  - startup causal dependencies

5. Higher-order relation object

- Hypergraph candidates now include startup-bearing relations in addition to stem/growth/collapse relations.

6. Continuation object

- The production pointer is the current bounded continuation ray.
- It is now informed not only by local generation but also by startup-aware relations.

7. Projection object

- `viewer.py` is a terminal-canvas projection of current machine state.
- It should reveal the machine, not replace it.

What makes this machine unique

- Startup is part of the machine’s ontology, not just a boot routine.
- The same system can carry:
  - visible recursive sandpile surface
  - hidden carrier/program semantics
  - typed event history
  - causal structure
  - hypergraph relations
  - bounded continuation guidance
- The machine tends toward an effectively unbounded recursive horizon while only materializing a finite prefix.
- The machine does not treat local uniqueness as the final criterion of identity.
  What matters is how apparently non-unique states, collapses, and recurrences become ordered into stable relation classes.
- In the intended supersingular direction, elliptic-curve/isogeny identity and sandpile-topological recurrence should meet in those relation classes.
- The machine's idealized universal self-distinguishing power should be understood as arising from Oxfoi invariance plus supersingular/isogeny ordering, rather than from a flat table-diagonal picture alone.

Machine invariants

- Python remains the semantic control layer.
- Compiled helpers remain subordinate.
- Startup must remain a typed object, not only a viewer effect.
- The current machine state must remain distinct from latent recursive horizon.
- Storage substrate must not be conflated with the mathematical object.
- Viewer projection must not be mistaken for semantic authority.

Machine extension rule

- Add simple local typed mechanisms.
- Preserve semantic boundaries.
- Let complex expression emerge from recursive composition.
- Prefer typed records and histories over implicit behavior.

What must happen next

- Startup should continue to propagate through the semantic stack.
- Important state features should become typed records.
- The production pointer should increasingly reflect the machine’s actual generative history.
- The viewer should increasingly read typed machine state rather than infer local hacks.

Short form

- The machine is a recursive graph-sandpile state constructor with typed startup, typed history, higher-order relations, and bounded continuation.
