# Implementation vs. SPEC.md: Detailed Comparison Analysis

**Date:** March 22, 2026  
**Scope:** Python implementation files (simulation.py, dag.py, graph.py, regular.py, ternlsb.py, supersingular.py) vs. SPEC.md requirements

---

## Executive Summary

The implementation provides a **solid foundation** for sandpile physics and basic state management but has **significant gaps** in the specification's five semantic instructions, interval/glyph semantics, and hypergraph structure. The code works at the "storage and stabilization" layer but lacks the "semantic instruction execution" and "invariant preservation" layers that SPEC.md defines as core.

**Status:** 40% specification coverage (physics + storage layer implemented; semantic layer mostly missing)

---

## 1. FIVE SEMANTIC INSTRUCTIONS ANALYSIS

### 1.1 SCOPE Instruction

**SPEC.md Definition:**  
> Selects an interval family / relation class / address family. Must not implicitly widen beyond the active production pointer without an explicit scope transition.

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- No `scope` instruction or concept exists in the codebase
- No "production pointer" tracking or "address family" concepts
- No interval family selection mechanism
- `SimulationWorkspace` and `ImageStateSurface` manage storage but don't scope to intervals
- `DagContext` doesn't track active scope or scope boundaries

**What's Missing:**
1. No scope state machine
2. No production pointer object
3. No interval-family selector
4. No scope-transition logic
5. No boundaries enforcement on scope expansion

**Impact:** Cannot restrict operations to declared interval families or enforce scope-based safety

---

### 1.2 SINGULARITY Instruction

**SPEC.md Definition:**  
> Chooses or detects a distinguished point (seed, fixed point, ideal expression). Must be derivable from recorded context, not an ad hoc override.

**Implementation Status:** ⚠️ PARTIALLY IMPLEMENTED

**Findings:**
- Seed concept used informally in several places:
  - `/0x/seed/0x80.pgm` exists as filesystem reference (not loaded in code)
  - `CenteredSeedRewriteRule` applies seed as rewrite rule to surface
  - `supersingular_delta_configuration()` chooses a "seed vertex"
  - `_default_target_vertex()` selects default vertex (center or first active)

**Implementation Details:**
```python
# From ternlsb.py
def _default_target_vertex(configuration: SandpileConfiguration) -> str:
    graph_metadata = configuration.model.graph.metadata
    center_vertex = graph_metadata.get("center_vertex")
    ...
```

**What's Implemented Correctly:**
1. ✅ Center vertex metadata stored in graph
2. ✅ Seed can be applied as rewrite rule
3. ✅ Default vertex selection logic

**What's Missing:**
1. No formal "singularity" object or record
2. No derivation logging (how was singularity chosen?)
3. No fixed point detection mechanism
4. Seed 0x80 → 0x2a mapping (claimed in spec) not tracked
5. No "ideal expression" selection
6. Singularities not distinguishable from arbitrary mutations

**Impact:** Seed selection is ad hoc; cannot audit how singularities were chosen; missing the "recorded context" requirement

---

### 1.3 INIT Instruction

**SPEC.md Definition:**  
> Materializes a surface from a seed under the current scope. Must remain a deterministic scoped constructor and must not silently become an arbitrary mutation command.

**Implementation Status:** ⚠️ PARTIALLY IMPLEMENTED

**Findings:**
- Surface initialization exists but lacks scope enforcement:
  - `SimulationWorkspace.initialize_surface()` creates blank PGM with fill value
  - `ImageStateSurface.apply_centered_seed()` applies seed centered on surface
  - `CenteredSeedRewriteRule` wraps seeding as rewrite rule

**Implementation Details:**
```python
# From simulation.py
def initialize_surface(
    self,
    name: str,
    width: int,
    height: int,
    fill: int = 0,
    magic: str = "P2",
    max_value: int = 255,
) -> Path:
    image = NetpbmImage(...)
    path = self.state_path(name, magic)
    write_netpbm(image, path)
    return path
```

**What's Implemented Correctly:**
1. ✅ Deterministic initialization (fill value, dimension record)
2. ✅ Seeding as separate operation
3. ✅ Surfaces archived with provenance metadata

**What's Missing:**
1. No scope binding in init signature
2. No verification that init respects active interval family
3. No "materialization" logging (what rules applied?)
4. Boundary between pure init and mutation not enforced
5. No invariant check post-initialization

**Impact:** Cannot guarantee that initialized state respects declared interval rules; cannot audit init vs. mutation distinction

---

### 1.4 GOTO Instruction

**SPEC.md Definition:**  
> Traverses along a successor edge (filesystem step, isogeny edge, Collatz move, sandpile successor, etc.). Must respect traversal compatibility: it either preserves declared invariants or intentionally transitions between classes in a documented way.

**Implementation Status:** ⚠️ PARTIALLY IMPLEMENTED

**Findings:**
- Multiple successor mechanisms exist but lack compatibility checking:

1. **Stabilization (sandpile successor):**
   - `stabilize_configuration()` is pure physics, correctly implements toppling
   - Successor relation is mathematically sound
   - No invariant-compatibility logging

2. **Rewrite rules (filesystem/surface successor):**
   - `RewriteRule` protocol defines `apply(surface) → ImageStateSurface`
   - Three rules: `CenterGrainRewriteRule`, `LowestGrainRewriteRule`, `CenteredSeedRewriteRule`
   - Rules are not branded with invariant information

3. **Archive tree traversal:**
   - `spawn_child_state()` creates parent-child relationships
   - No invariant-class label on edges

**Implementation Details:**
```python
# From simulation.py (stabilization successor)
def topple_once(self, vertex: VertexId) -> "SandpileConfiguration":
    ...
    updated[neighbor] = updated.get(neighbor, 0) + multiplicity
    return SandpileConfiguration(model=self.model, chips=updated)
```

**What's Implemented Correctly:**
1. ✅ Multiple successor types (stabilization, rewrite, archive)
2. ✅ Stabilization follows sandpile physics correctly
3. ✅ Edge traversal records parent-child lineage

**What's Missing:**
1. No traversal-compatibility check (does successor preserve invariants?)
2. No class-transition documentation (e.g., "interior-valid → all-interior-invalid")
3. No forbidden-edge detection
4. No isogeny-edge representation
5. Successor edges not branded with invariant labels

**Impact:** Cannot verify that state transitions are valid under active interval rules; chains may silently violate hidden invariants

---

### 1.5 IFF Instruction

**SPEC.md Definition:**  
> Branches on global invariants (e.g. interior-valid vs all-interior-invalid, class membership via interval rules). Must not be reduced to a generic boolean without preserving which invariant is being tested.

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- No branching on invariants
- No "interior-invalid" or "interior-valid" classification
- No interval-dependency rules
- `SandpileConfiguration.is_stable()` checks stability (related but not iff-style):
  ```python
  def is_stable(self) -> bool:
      adjacency = self.model.graph.adjacency()
      for vertex in self.model.active_vertices:
          if self.chips.get(vertex, 0) >= sum(adjacency[vertex].values()):
              return False
      return True
  ```

**What's Missing:**
1. No invariant-classification system
2. No surface classification (interior-valid, mixed, all-interior-invalid)
3. No rule-based branching logic
4. No interval-dependency graph evaluation
5. No iff characterization records

**Impact:** Cannot branch on global semantic properties; all logic is procedural, not invariant-driven

---

## 2. HYPERGRAPH STRUCTURE ANALYSIS

### 2.1 Current Hypergraph Representation

**SPEC.md Definition:**  
> Nodes: state nodes, function nodes, glyph nodes  
> Edges: successor edges, function application edges, recursive edges  
> All computation is defined by hyperedges.

**Implementation Status:** ⚠️ PARTIALLY SKETCHED (NOT EXECUTABLE)

**Findings:**
- `dag.py` contains **provisional** hypergraph data structures:
  - `HyperedgeCandidateRecord`: edge_type, input_nodes, output_nodes, support_nodes
  - `HypergraphCandidateIndex`: list of candidate records
  - `UpdateEventRecord`: event-typed transformation steps
  - `CausalDependencyRecord`: cause-effect relation

**Code Example:**
```python
# From dag.py (INCOMPLETE)
@dataclass(frozen=True)
class HyperedgeCandidateRecord:
    edge_type: str
    input_nodes: list[str]
    output_nodes: list[str]
    support_nodes: list[str]
    metadata: dict[str, Any]
```

**What's Defined:**
1. ✅ Data structures for recording hyperedge candidates
2. ✅ Update event records with typed transformations
3. ✅ Causal dependency tracking framework

**What's Missing:**
1. ❌ No code that **populates** these structures
2. ❌ No hypergraph construction algorithm
3. ❌ No glyph-node concept
4. ❌ No function-node concept
5. ❌ No edge-type enumeration (only generic "str")
6. ❌ No hypergraph traversal or query functions
7. ❌ No hypergraph → program compilation

**Impact:** Hypergraph infrastructure is a skeleton; cannot construct or query hypergraphs from states

---

### 2.2 State Nodes

**Current Representation:**
- `ArchivedState`: state_id, signature, branch, directory, image_path
- `SandpileConfiguration`: model, chips dict
- States archived in `/state_tree/` with parent-child links

**Implementation Status:** ✅ PARTIALLY CORRECT
- State identity is well-defined (signature + state_id)
- Parentage tracked correctly
- Cannot link to hypergraph computations

---

## 3. INTERVAL/GLYPH MAPPING ANALYSIS

### 3.1 12-Glyph Interval Structure

**SPEC.md Definition:**  
```
4 bands × 3 elements each = 12 glyphs

Band 0: 64(@), 78(N), 92(\)
Band 1: 96(`), 113(q), 132(„)
Band 2: 133(…), 151(—), 166(¦)
Band 3: 169(©), 185(¹), 201(É)

Anchor values: [64,78,92,96,113,132,133,151,166,169,185,201]
Glyphs: ['@','N','\\','`','q','„','…','—','¦','©','¹','É']
```

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- No glyph constants defined anywhere
- No anchor-value lookup table
- No decode function
- No interval mapping

**What's Missing:**
1. ❌ Glyph constants
2. ❌ Anchor array
3. ❌ `decode(value) → glyph` function
4. ❌ Band structure
5. ❌ Distance metric for nearest-glyph selection

**Impact:** Cannot decode PGM pixel values to glyphs; pipeline from "pixel values → nearest anchor → 12-glyph alphabet → hypergraph instructions" is completely missing

**Code That Should Exist (but doesn't):**
```python
# MISSING from ternlsb.py or glyph.py
GLYPH_ANCHORS = [64, 78, 92, 96, 113, 132, 133, 151, 166, 169, 185, 201]
GLYPHS = ['@', 'N', '\\', '`', 'q', '„', '…', '—', '¦', '©', '¹', 'É']

def decode_glyph(value: int) -> str:
    """Return nearest glyph for pixel value."""
    idx = min(range(len(GLYPH_ANCHORS)),
              key=lambda i: abs(value - GLYPH_ANCHORS[i]))
    return GLYPHS[idx]

def pixel_to_glyph_slice(surface: ImageStateSurface) -> list[str]:
    """Convert all pixels to glyph stream."""
    flat = surface.flatten_pixels()
    return [decode_glyph(value) for value in flat]
```

---

### 3.2 Interval-Dependency Rules

**SPEC.md Definition:**  
> Given i ∈ I_a and j ∈ I_b, the result must land in the required I_c.  
> Interval representatives are canonical anchors for encoding/decoding.

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- `TernLSBProgram` uses a **3-symbol alphabet** ("ASN"), not the 12-glyph structure
- Ternary LSB encoding is orthogonal to interval semantics
- No interval algebra or rule enforcement

**Current TernLSB Implementation:**
```python
DEFAULT_TERNLSB_ALPHABET = "ASN"  # Add, Stabilize, Noop

@dataclass(frozen=True)
class TernLSBProgram:
    instructions: str
    alphabet: str = DEFAULT_TERNLSB_ALPHABET
    cell_size: int = 1
    capacity: int = 0
```

**Issues:**
1. ❌ "ASN" is semantic (add, stabilize, noop), not a glyph interval
2. ❌ No arithmetic on intervals
3. ❌ No result-landing verification
4. ❌ No dependency graph

**Impact:** Cannot enforce that computations respect interval boundaries; no semantic validation of instruction sequences

---

## 4. SANDPILE PHYSICS ANALYSIS

### 4.1 Height Function & Configuration

**SPEC.md Definition:**  
> A configuration is a function h: Z³ → Z≥0. Each recursion index z defines a 2D slice h_z.  
> Height 1 = input; Height ≥2 = internal state.

**Implementation Status:** ✅ PARTIALLY CORRECT

**Findings:**
1. **Configuration representation:**
   ```python
   @dataclass
   class SandpileConfiguration:
       model: SandpileModel
       chips: dict[VertexId, int]
   
       def total_chips(self) -> int:
           return sum(self.chips.values())
   ```

2. **Height function:** Chips value ↔ height at vertex

**What's Implemented Correctly:**
1. ✅ Configuration as vertex → height mapping
2. ✅ Non-negative integer heights
3. ✅ Chips (grain) count

**What's Missing:**
1. ❌ Z³ lattice explicitly (stored implicitly via grid)
2. ❌ Recursion axis (z-axis) not represented
3. ❌ Slice extraction (no hz function)
4. ❌ Height ≥2 vs. Height 1 distinction (no input/internal layering)
5. ❌ Period-8 checkpoint structure
6. ❌ Recursion depth tracking

**Impact:** Physics is 2D only; no z-axis recursion; no checkpoint markers every 8 steps

---

### 4.2 Stabilization & Toppling

**SPEC.md Definition:**  
> Stabilization is a semantic event, not merely a visual effect. Toppling rules are based on vertex degree.

**Implementation Status:** ✅ WELL IMPLEMENTED

**Code:**
```python
# From graph.py
def stabilize_configuration(configuration: SandpileConfiguration) -> StabilizationResult:
    adjacency = configuration.model.graph.adjacency()
    current = SandpileConfiguration(...)
    
    while True:
        unstable_vertices = [
            vertex for vertex in current.model.active_vertices
            if current.chips.get(vertex, 0) >= sum(adjacency[vertex].values())
        ]
        if not unstable_vertices:
            break
        
        vertex = unstable_vertices[0]
        degree = sum(adjacency[vertex].values())
        topple_count = current.chips.get(vertex, 0) // degree
        ...
    
    return StabilizationResult(...)
```

**What's Implemented Correctly:**
1. ✅ Degree-based toppling
2. ✅ Chip redistribution to neighbors
3. ✅ Sink chip loss
4. ✅ Topple record and count
5. ✅ Stability check (all vertices < degree)

**What's Missing:**
1. ⚠️ No explicit "semantic event" logging (just procedural execution)
2. ❌ No invariant-preservation verification
3. ❌ No boundary potential tracking (ϕ_z(u,v) = h_z(u) - h_z(v))
4. ❌ No "influence graph for next slice" concept

**Impact:** Stabilization works correctly for single slices but doesn't propagate boundary potentials to next recursion level

---

### 4.3 Boundary Potential

**SPEC.md Definition:**  
> ϕ_z(u,v) = h_z(u) - h_z(v) defines the influence graph for the next slice.  
> Only boundaries influence the next recursion step.

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- Boundary potential never computed
- No influence graph construction
- No z-slice recursion

**What's Missing:**
1. ❌ Potential function ϕ_z(u,v)
2. ❌ Boundary extraction (where does h change?)
3. ❌ Influence propagation to next z-slice
4. ❌ Recursion kernel (how does ϕ seed next level?)

**Impact:** Cannot model the z-axis recursion tree; each slice is independent

---

## 5. FILESYSTEM SEMANTICS ANALYSIS

### 5.1 /0x/ Tree as Self-Describing Glossary

**SPEC.md Definition:**  
> The embedded /0x/ tree is the glossary, the function table, the recursion lattice, the semantic address space.  
> The seed /0x/seed/0x80.pgm is the singularity.

**Implementation Status:** ⚠️ EXISTS BUT NOT INTEGRATED

**Findings:**
- `/0x/` tree is hardcoded in the repository but **never loaded or parsed**
- `SPEC.md` describes a rich directory structure:
  ```
  ./0x/
    0x10/          (checkpoints)
      0x01/
    seed/
      0x80.pgm     (singularity)
  ```
- No code reads or interprets this tree

**Current Workspace Structure:**
```python
# From simulation.py
class SimulationWorkspace:
    def create(cls, root: str | Path) -> "SimulationWorkspace":
        ...
        (workspace_root / "canonical_states").mkdir(exist_ok=True)
        (workspace_root / "states").mkdir(exist_ok=True)
        (workspace_root / "state_tree").mkdir(exist_ok=True)
        (workspace_root / "runs").mkdir(exist_ok=True)
```

**What's Implemented Correctly:**
1. ✅ State tree created and populated
2. ✅ Canonical state deduplication
3. ✅ State archive with branching metadata

**What's Missing:**
1. ❌ Reading the embedded /0x/ tree
2. ❌ Parsing tree structure as glossary
3. ❌ Extracting recursion families
4. ❌ Function table from tree
5. ❌ Address space semantics
6. ❌ Seed loading from /0x/seed/0x80.pgm

**Impact:** Tree is documentation only; not executable specification

---

### 5.2 Checkpoint & Periodic Structure

**SPEC.md Definition:**  
> Every 8 steps, the system reaches a checkpoint. Checkpoint states correspond to PGM representation, PNG+LSB representation, base64 identifier.

**Implementation Status:** ❌ NOT IMPLEMENTED

**Findings:**
- No period-8 checkpoint system
- No checkpoint markers or counters
- Archives are linear tree, not periodic

**What's Missing:**
1. ❌ Period-8 counter
2. ❌ Checkpoint detection
3. ❌ PNG+LSB representation format
4. ❌ Base64 identifier encoding
5. ❌ Checkpoint → recursive expansion rules

**Impact:** Cannot detect when recursion level changes; no period-8 structure observable

---

## 6. INVARIANT PRESERVATION ANALYSIS

### 6.1 Semantic Invariants (from INVARIANTS.md)

**Specification:**
- Graph semantics dominate image semantics
- Stabilization is a semantic event
- `scope singularity init` remains deterministic and scoped
- Sink is part of model (not optional metadata)
- Reduced Laplacian conventions explicit
- Edge multiplicity and degree preserved

**Implementation Status:**

| Invariant | Status | Notes |
|-----------|--------|-------|
| Graph semantics dominate | ✅ | SandpileModel is primary; image is projection |
| Sink is part of model | ✅ | SandpileModel requires sink; enforced in toppling |
| Reduced Laplacian explicit | ✅ | LaplacianData.reduced_vertex_order, reduced_matrix |
| Edge multiplicity preserved | ✅ | Edge.multiplicity stored and used in adjacency |
| Stabilization is semantic event | ⚠️ | Procedure is correct; event logging missing |
| Deterministic scope/init | ❌ | No scope construct; init not enforced scoped |

---

### 6.2 Interval & Surface Invariants

**Specification:**
- Every cell belongs to exactly one declared interval family
- Interval representatives are canonical anchors
- Interior validity / all-interior-invalid are iff characterizations
- Interval dependency rules must be respected

**Implementation Status:** ❌ NOT IMPLEMENTED (0% coverage)

**Missing:**
1. No interval classification of cells
2. No surface-level validity judgment
3. No iff rules
4. No dependency graph

---

### 6.3 Five-Instruction Semantic Closure

**Specification:**  
> Any valid program should be representable as:  
> `scope → singularity → init → (goto / iff)*`

**Implementation Status:** ❌ NOT ENSURED

**What's Missing:**
- No program synthesis or validation
- No instruction sequencing enforced
- No closure check

---

## 7. SUPERSINGULAR ISOGENY GRAPH (SPEC.md Section 14)

### 7.1 Current Implementation

**Implementation Status:** ✅ BASIC STRUCTURE, ❌ MISSING THEORY

**What's Implemented:**
```python
# From supersingular.py
def build_supersingular_isogeny_graph(
    prime: int,
    isogeny_degree: int,
    vertex_count: int | None = None,
) -> tuple[UndirectedGraph, dict[str, tuple[int, int]], SupersingularIsogenyGraphSpec]:
    # Synthetic circulant scaffold (NOT TRUE ISOGENY GRAPH)
    ...
    graph = UndirectedGraph(
        vertices=vertices,
        edges=edges,
        metadata={
            "is_true_isogeny_graph": False,  # ← Key admission
            ...
        },
    )
```

**What's Missing:**
1. ❌ True supersingular j-invariant computation
2. ❌ Isogeny walks (ℓ-adic Frobenius representation)
3. ❌ Jacobian torsion
4. ❌ Oxfoi field arithmetic (F_p with p = 0xffffffff00000001)
5. ❌ X-field lift (F_{p³} = F_p[X] / <X³ - X + 1>)
6. ❌ Galois representation structure
7. ❌ Seed 0x80 → 0x2a isogeny walk

**Impact:** Supersingular component is a mock graph, not real isogeny structure

---

## 8. DATA STRUCTURES & DAG ORCHESTRATION

### 8.1 DAG Nodes (Implemented)

**Status:** ✅ GOOD FOR SEQUENTIAL ORCHESTRATION

**What Works:**
1. ✅ `DagNode` protocol (inputs → outputs)
2. ✅ `Dag` sequential execution
3. ✅ Context threading (dict-based)
4. ✅ Typed node implementations:
   - `BuildSandpileModelNode`
   - `ComputeSandpileGroupNode`
   - `StabilizeConfigurationNode`
   - `ApplyTernLSBProgramNode`
   - etc.

**What's Missing:**
1. ❌ Hypergraph population nodes
2. ❌ Invariant-preservation verification nodes
3. ❌ Scope-transition nodes
4. ❌ Singularity-detection nodes
5. ❌ Iff-branch nodes

---

### 8.2 Production Pointer (Only Skeletal)

**Implementation Status:** ⚠️ MENTIONED BUT NOT IMPLEMENTED

**Code:**
```python
# From dag.py (INCOMPLETE)
@dataclass
class ProductionPointerRecord:
    pointer_id: str
    ray_id: str
    stem_path: str
    current_state_id: str
    canonical_path: str | None
    rewrite_rule: str
    recursion_depth: int
    recursion_limit: int
    can_descend: bool
    next_edge_types: list[str]
    allowed_outputs_ranked: list[dict[str, Any]]
    preferred_output: str | None
    safety_bounds: dict[str, Any]
    target_domain: str
    target_confidence: float
    metadata: dict[str, Any]
```

**Status:**
- Data structure defined ✅
- Never instantiated or used ❌
- No pointer creation, traversal, or serialization ❌

**Impact:** Cannot enforce recursion limits or scope boundaries via production pointers

---

## 9. MISSING CRITICAL FEATURES

### 9.1 Glyph Decoding Pipeline

**SPEC.md says no:**  
"PGM slice → pixel values → nearest rainbow anchor → 12-glyph alphabet → hypergraph instructions"

**Current state:** Only first step (read PGM) works. Missing steps 2-4.

---

### 9.2 Interval-Dependency Evaluation

**SPEC.md says:**  
"Interior-valid: all interior points satisfy interval-dependency rules"

**Current state:** No interior classification, no dependency rules, no evaluation function.

---

### 9.3 Hypergraph Compilation

**SPEC.md says:**  
"All computation is defined by hyperedges."

**Current state:** Computation is procedural (stabilization loops, rewrite rules). No hypergraph queries or execution.

---

### 9.4 Recursion Kernel (z-axis)

**SPEC.md says:**  
"Recursion axis is z-axis. Every 8 steps hits checkpoint. Boundary potential drives next slice."

**Current state:** No z-axis, no checkpoints, no recursion.

---

### 9.5 Oxfoi Field Arithmetic

**SPEC.md says:**  
"Base field is F_p with p = 0xffffffff00000001. Pixels are F_p grains."

**Current state:** Pixels are plain Python ints. No F_p enforcement or X-field support.

---

## 10. WHAT IS WORKING WELL

| Component | Status | Notes |
|-----------|--------|-------|
| Sandpile graph structure | ✅ | Vertices, edges, multiplicity |
| Stabilization algorithm | ✅ | Toppling, chip redistribution, sink loss |
| Reduced Laplacian computation | ✅ | Smith normal form, invariant factors |
| Sandpile group (critical group) | ✅ | Order, rank, Sylow decomposition |
| Configuration storage & archival | ✅ | State tree, deduplication, canonical paths |
| Netpbm I/O | ✅ | P1/P2 read/write |
| DAG-based orchestration | ✅ | Sequential pipeline execution |
| Ternary LSB steganography | ✅ | Encode/decode ASN-alphabet programs |
| Regular grid construction | ✅ | Centered grid with center vertex |
| Supersingular graph scaffold | ⚠️ | Synthetic circulant (not true isogeny graph) |

---

## 11. DETAILED GAP SUMMARY

### By Category

#### Semantic Instructions (5 / 5 missing)
- **scope:** ❌ Not implemented; no production pointer
- **singularity:** ⚠️ Partially implemented; ad hoc, not derived from context
- **init:** ⚠️ Partially implemented; lacks scope enforcement
- **goto:** ⚠️ Partially implemented; lacks compatibility checking
- **iff:** ❌ Not implemented; no invariant classification

#### Interval/Glyph (0/3 implemented)
- **12-glyph alphabet:** ❌ Missing constants, decode function
- **Interval bands:** ❌ No 4-band structure
- **Anchor-value lookup:** ❌ Not defined

#### Interval-Dependency Semantics (0/5)
- **Dependency rules:** ❌ None defined
- **Interior validity:** ❌ No classification
- **All-interior-invalid check:** ❌ Not implemented
- **Surface class membership:** ❌ No iff rules
- **Local computation validation:** ❌ No algebra

#### Hypergraph Structure (10% implemented)
- **Data structures:** ✅ Defined but empty
- **Construction algorithm:** ❌ Missing
- **Glyph nodes:** ❌ Not defined
- **Function nodes:** ❌ Not defined
- **Edge types:** ❌ Only generic "str"
- **Hypergraph queries:** ❌ None
- **Hypergraph execution:** ❌ Not compiled

#### Boundary Potential & Recursion (0% implemented)
- **Potential function ϕ_z(u,v):** ❌ Not computed
- **Influence graph:** ❌ Not extracted
- **Z-axis recursion:** ❌ No z-coordinate
- **Period-8 checkpoints:** ❌ Not tracked
- **Slice extraction:** ❌ No hz function

#### Filesystem Semantics (0% integrated)
- **/0x/ tree parsing:** ❌ Tree exists but unread
- **Glossary extraction:** ❌ Not done
- **Function table:** ❌ Not built
- **Recursion families:** ❌ Not identified
- **Seed 0x80 loading:** ❌ Hardcoded path only

#### Invariants from INVARIANTS.md

| Invariant Class | Coverage |
|------------------|----------|
| Semantic | 50% (graph semantics ✅, scope semantics ❌) |
| Interval / Surface | 0% |
| Five-instruction closure | 0% |
| Storage | 80% (archival works; manifest linkage weak) |
| DAG | 60% (nodes defined; hypergraph population missing) |
| Production-pointer | 5% (skeleton only) |
| Supersingular target | 10% (synthetic graph only; no isogeny theory) |
| Oxfoi/X-field | 0% |

#### Continuity & Self-Description
- Documentation talks about /0x/ but code doesn't read it
- Original model/config not connected to execution
- System is not self-describing from embedded tree

---

## 12. RECOMMENDED UNIFICATION & FIXES

### Phase 1: Enable Glyph Semantics (Quick Win)
1. Add glyph constants and decode function
2. Implement pixel-to-glyph-slice pipeline
3. Add interval classification to pixels
4. Implement interior-validity check

### Phase 2: Add Production Pointer & Scope
1. Implement `ProductionPointerRecord` creation and serialization
2. Add scope tracking to DagContext
3. Implement scope-transition nodes
4. Add scope bounds checking on all operations

### Phase 3: Implement Five Instructions as DAG Nodes
1. Create `ScopeNode`, `SingularityNode`, `InitNode`, `GotoNode`, `IffNode`
2. Each node validates invariant preservation
3. Connect to context recording for auditability
4. Implement iff branching on surface classification

### Phase 4: Build Hypergraph Layer
1. Populate `HypergraphCandidateIndex` from state transitions
2. Implement glyph-node and function-node construction
3. Add hypergraph traversal and query functions
4. Compile hypergraph to executable instructions

### Phase 5: Integrate /0x/ Tree
1. Parse embedded /0x/ directory as glossary
2. Extract recursion families from tree structure
3. Load seed 0x80 and track 0x80 → 0x2a mapping
4. Use tree to validate function calls

### Phase 6: Implement Recursion Kernel
1. Add z-coordinate to configurations
2. Implement boundary-potential computation
3. Build influence graph from boundaries
4. Implement z-axis recursion with period-8 checkpoints

### Phase 7: Add Oxfoi Field Arithmetic (Advanced)
1. Implement F_p arithmetic with p = 0xffffffff00000001
2. Replace plain int pixels with F_p elements
3. Add X-field lift when needed
4. Implement Galois representation layer

---

## 13. TESTING GAPS

### What Can Be Tested Now
- ✅ Sandpile stabilization (physics)
- ✅ Graph construction (grid, supersingular)
- ✅ Configuration archival and deduplication
- ✅ Laplacian and group-invariant computation

### What Cannot Be Tested
- ❌ Glyph decoding
- ❌ Scope enforcement
- ❌ Invariant-preservation
- ❌ Hypergraph queries
- ❌ Recursion with checkpoints
- ❌ Iff branching
- ❌ Singularity derivation

---

## 14. SPECIFICATION COVERAGE SCORECARD

| Aspect | Coverage | Status |
|--------|----------|--------|
| **Semantic Instructions** | 10% | Incomplete, ad hoc |
| **Hypergraph Structure** | 10% | Data structures only |
| **Interval/Glyph Mapping** | 0% | Not started |
| **12-Glyph Interval** | 0% | No constants |
| **Sandpile Physics** | 85% | Stabilization works; recursion missing |
| **Boundary Potential** | 0% | Not implemented |
| **Filesystem Semantics** | 0% | Tree unread |
| **Invariant Preservation** | 30% | Some enforced; most not audited |
| **Production Pointer** | 5% | Skeleton only |
| **Oxfoi Field** | 0% | Not started |
| **Overall** | **40%** | Physics layer solid; semantic layer needed |

---

## 15. CONCLUSION

The implementation is **a working physics engine** (sandpile stabilization on graphs) with **a storage and orchestration layer** (State archive, DAG execution). However, it lacks the **semantic instruction layer**, **interval semantics**, **hypergraph execution**, and **recursion kernel** that SPEC.md defines as fundamental.

### Key Synthesis Issue
- **Physics ✅**: Stabilization, toppling, group invariants computed correctly
- **Storage ✅**: States archived, deduplicated, reproducible
- **Semantics ❌**: No scope, singularity derivation, iff branching, invariant classes
- **Instructions ❌**: Five instructions not executable; no semantic closure guarantee
- **Recursion ❌**: No z-axis, no checkpoints, no boundary-potential propagation
- **Glyphs ❌**: No 12-symbol decoding; no interval dependency

### To Reach Full Specification
1. Implement the five semantic instructions as executable DAG nodes
2. Build the glyph-decoding and interval-classification pipeline
3. Add hypergraph construction and execution layer
4. Implement recursion kernel with boundary-potential propagation
5. Integrate the `/0x/` tree as executable glossary and function table
6. Add production-pointer tracking for scope safety
7. Implement Oxfoi field arithmetic (when required by domain shift)

The foundation is solid; the semantic superstructure is missing.

---

**Report generated:** March 22, 2026  
**Files analyzed:** simulation.py, dag.py, graph.py, regular.py, ternlsb.py, supersingular.py, INVARIANTS.md, ARCHITECTURE.md
