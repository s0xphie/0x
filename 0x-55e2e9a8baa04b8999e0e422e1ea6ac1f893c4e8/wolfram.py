"""Wolfram Language bridge for the 0x hypergraph engine.

Exports the unified hypergraph, sandpile states, glyph structure, boundary
potentials, and recursive-function semantics into Wolfram Language expressions.

The bridge targets three Wolfram surfaces:
  1. Direct WL code generation (pasteable into a notebook)
  2. .wl script files (batch-evaluable)
  3. Structured workbook outline (.nb cell expressions)

Wolfram Function Repository functions referenced:
  - SandpileTopple          (sandpile stabilization)
  - HypergraphPlot          (hyperedge visualization)
  - AdjacencyTensor         (hypergraph adjacency)
  - KirchhoffTensor         (hypergraph Laplacian)
  - RecursiveFunctionCallGraph  (recursive function traces)
  - WolframModel / WolframModelPlot (Wolfram Physics hypergraph evolution)
  - MultiwaySystem          (multiway rewriting)

Theory alignment (the Universal Argument):
  Recursive_Functions.pdf establishes:
    Zero, Successor, Projection → Composition, Primitive Recursion → μ-recursion
  Our five instructions map:
    singularity ↔ Zero       (the constant seed)
    init        ↔ Successor  (add-seed-stabilize along spine)
    scope       ↔ Projection (selects the recursion axis / period)
    goto        ↔ Composition (branch traversal composes states)
    iff         ↔ Primitive Recursion (classifies by invariant predicate)
  ASM_TC.pdf confirms: Abelian sandpiles on Z³ are Turing-complete.
  SPEC §10 diagonal function D(x) = F_x(x) + 1 closes universality.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine import (
    BoundaryEdge,
    EdgeKind,
    GlyphNode,
    Hypergraph,
    HyperedgeRecord,
    IffClass,
    Instruction,
    InstructionRecord,
    NodeClass,
    Scope,
    StateNode,
    build_hypergraph,
    summarize_hypergraph,
    GLYPH_ANCHORS,
    GLYPH_SYMBOLS,
)
from netpbm import read_netpbm


# ── WL Serialization Helpers ─────────────────────────────────────────

def _wl_list(items: list[str]) -> str:
    return "{" + ", ".join(items) + "}"


def _wl_string(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _wl_rule(key: str, value: str) -> str:
    return f'{_wl_string(key)} -> {value}'


def _wl_assoc(pairs: list[tuple[str, str]]) -> str:
    rules = ", ".join(_wl_rule(k, v) for k, v in pairs)
    return "<|" + rules + "|>"


# ── Surface Export: PGM → Wolfram Matrix ─────────────────────────────

def pgm_to_wl_matrix(pgm_path: Path) -> str:
    """Convert a PGM file to a Wolfram 2D list (matrix)."""
    img = read_netpbm(pgm_path)
    rows = []
    for row in img.pixels:
        rows.append(_wl_list([str(v) for v in row]))
    return _wl_list(rows)


# ── Sandpile Stabilization via SandpileTopple ────────────────────────

def wl_sandpile_topple(pgm_path: Path) -> str:
    """Generate WL code that loads a PGM surface and topples it.

    Uses ResourceFunction["SandpileTopple"] from the Wolfram Function Repository.
    """
    matrix = pgm_to_wl_matrix(pgm_path)
    return (
        f'(* Sandpile surface from {pgm_path.name} *)\n'
        f'surface = {matrix};\n'
        f'graph = GridGraph[Dimensions[surface]];\n'
        f'ResourceFunction["SandpileTopple"][graph, Flatten[surface]]'
    )


# ── Hypergraph → Wolfram Hypergraph ─────────────────────────────────

def hypergraph_to_wl(hg: Hypergraph) -> str:
    """Export the unified hypergraph as WL Hypergraph expression.

    Generates code using ResourceFunction["HypergraphPlot"] for visualization
    and ResourceFunction["AdjacencyTensor"] / ResourceFunction["KirchhoffTensor"]
    for algebraic analysis.
    """
    lines: list[str] = []

    # Node list
    node_keys = sorted(hg.nodes.keys())
    lines.append(f'(* {len(node_keys)} state nodes, {len(hg.glyph_nodes)} glyph nodes *)')
    lines.append(f'stateNodes = {_wl_list([_wl_string(k) for k in node_keys])};')

    # Hyperedges grouped by kind
    edges_by_kind: dict[str, list[HyperedgeRecord]] = {}
    for e in hg.edges:
        edges_by_kind.setdefault(e.kind.value, []).append(e)

    hyperedges: list[str] = []
    for e in hg.edges:
        sources = _wl_list([_wl_string(s) for s in e.source_nodes])
        targets = _wl_list([_wl_string(t) for t in e.target_nodes])
        hyperedges.append(f'{sources} -> {targets}')

    lines.append(f'hyperedges = {_wl_list(hyperedges)};')
    lines.append('')

    # Edge kind counts for annotation
    for kind, edges in sorted(edges_by_kind.items()):
        lines.append(f'(* {kind}: {len(edges)} edges *)')

    lines.append('')
    lines.append('(* Visualize with HypergraphPlot *)')
    lines.append('ResourceFunction["HypergraphPlot"][hyperedges]')
    lines.append('')
    lines.append('(* Adjacency tensor *)')
    lines.append('ResourceFunction["AdjacencyTensor"][hyperedges]')
    lines.append('')
    lines.append('(* Kirchhoff tensor (hypergraph Laplacian) *)')
    lines.append('ResourceFunction["KirchhoffTensor"][hyperedges]')

    return "\n".join(lines)


# ── Glyph Alphabet → Wolfram Association ─────────────────────────────

def glyph_alphabet_to_wl() -> str:
    """Export the 12-glyph interval structure as a WL association."""
    pairs = []
    for i, (anchor, symbol) in enumerate(zip(GLYPH_ANCHORS, GLYPH_SYMBOLS)):
        pairs.append(f'{anchor} -> {_wl_string(symbol)}')
    lines = [
        '(* 12-Glyph Interval Structure (SPEC §4) *)',
        '(* 4 bands × 3 elements, nearest-anchor decoding *)',
        f'glyphAnchors = {_wl_list([str(a) for a in GLYPH_ANCHORS])};',
        f'glyphSymbols = {_wl_list([_wl_string(s) for s in GLYPH_SYMBOLS])};',
        f'glyphMap = Association[{_wl_list(pairs)}];',
        '',
        '(* Decode a pixel value to its nearest glyph *)',
        'decodeGlyph[v_Integer] := glyphSymbols[[',
        '  First@Ordering[Abs[glyphAnchors - v], 1]',
        ']];',
    ]
    return "\n".join(lines)


# ── Boundary Potential → Wolfram Graph ───────────────────────────────

def boundary_edges_to_wl(edges: list[BoundaryEdge]) -> str:
    """Export boundary potential edges as a WL weighted directed graph."""
    if not edges:
        return '(* No boundary edges *)\nboundaryGraph = Graph[{}];'

    wl_edges = []
    for be in edges:
        u_label = f'"({be.u[0]},{be.u[1]})"'
        v_label = f'"({be.v[0]},{be.v[1]})"'
        wl_edges.append(f'DirectedEdge[{u_label}, {v_label}]')
    weights = [str(be.potential) for be in edges]

    lines = [
        f'(* Boundary potential: {len(edges)} directed edges *)',
        '(* ϕ_z(u,v) = h_z(u) - h_z(v), SPEC §5 *)',
        f'boundaryEdges = {_wl_list(wl_edges)};',
        f'boundaryWeights = {_wl_list(weights)};',
        'boundaryGraph = Graph[boundaryEdges,',
        '  EdgeWeight -> boundaryWeights,',
        '  EdgeLabels -> "EdgeWeight",',
        '  GraphLayout -> "SpringElectricalEmbedding"',
        '];',
    ]
    return "\n".join(lines)


# ── Recursive Function Correspondence ────────────────────────────────

def recursive_function_correspondence_to_wl(hg: Hypergraph) -> str:
    """Map the five instructions to μ-recursive function theory in WL.

    This implements the Universal Argument:
      Zero        ↔ singularity  (constant seed)
      Successor   ↔ init         (add-seed-stabilize)
      Projection  ↔ scope        (period extraction)
      Composition ↔ goto         (branch traversal)
      PrimRec     ↔ iff          (classification by invariant)

    The recursive function call graph can be visualized with
    ResourceFunction["RecursiveFunctionCallGraph"].
    """
    log = hg.instruction_log
    scope_rec = next((r for r in log if r.instruction == Instruction.SCOPE), None)
    sing_rec = next((r for r in log if r.instruction == Instruction.SINGULARITY), None)
    init_rec = next((r for r in log if r.instruction == Instruction.INIT), None)
    goto_rec = next((r for r in log if r.instruction == Instruction.GOTO), None)
    iff_rec = next((r for r in log if r.instruction == Instruction.IFF), None)

    period = scope_rec.context.get("period", 8) if scope_rec else 8

    lines = [
        '(* ══════════════════════════════════════════════════════════════ *)',
        '(* THE UNIVERSAL ARGUMENT                                        *)',
        '(* μ-recursive functions ↔ five primitive instructions            *)',
        '(* Recursive_Functions.pdf + ASM_TC.pdf + SPEC §8,§10           *)',
        '(* ══════════════════════════════════════════════════════════════ *)',
        '',
        '(* ── Base Functions (Primitive Recursive) ────────────────────── *)',
        '',
        '(* Zero ↔ singularity: the constant seed state *)',
        f'zero = ConstantArray[0, {{{period}, {period}}}];',
        f'(* Seed chips: {sing_rec.context.get("singularity_path", "?")} *)',
        '',
        '(* Successor ↔ init: add seed and stabilize *)',
        f'(* {len(init_rec.produced_edges)} init edges along spine *)' if init_rec else '',
        'successor[state_] := Module[{sum, tmp},',
        '  sum = state + seed;',
        '  While[Max[sum] > 3,',
        '    sum = ArrayPad[sum, 1, 0];',
        '    tmp = Quotient[sum, 4];',
        '    sum -= 4 tmp;',
        '    sum += RotateLeft[tmp, {0, 1}] + RotateLeft[tmp, {1, 0}]',
        '         + RotateLeft[tmp, {0, -1}] + RotateLeft[tmp, {-1, 0}];',
        '    sum = ArrayPad[sum, -1];',
        '  ];',
        '  sum',
        '];',
        '',
        '(* Projection ↔ scope: extract recursion period *)',
        f'scopePeriod = {period};',
        'projection[stateHistory_, z_] := stateHistory[[Mod[z, scopePeriod] + 1]];',
        '',
        '(* ── Operations ──────────────────────────────────────────────── *)',
        '',
        '(* Composition ↔ goto: branch traversal *)',
        f'(* {len(goto_rec.produced_edges)} goto edges *)' if goto_rec else '',
        'composition[f_, g_][x_] := f[g[x]];',
        '',
        '(* Primitive Recursion ↔ iff: classify by invariant *)',
        f'(* {len(iff_rec.produced_edges)} iff classifications *)' if iff_rec else '',
        'primitiveRecursion[base_, step_][x_, 0] := base[x];',
        'primitiveRecursion[base_, step_][x_, n_] := ',
        '  step[x, n - 1, primitiveRecursion[base, step][x, n - 1]];',
        '',
        '(* ── Unbounded Minimization (μ-operator) ────────────────────── *)',
        '(* Sandpiles on Z³ are Turing-complete (ASM_TC.pdf, Cairns 2021) *)',
        '(* μ-recursion closes the gap to full T-computability *)',
        'mu[predicate_][x_] := Module[{y = 0},',
        '  While[!predicate[x, y], y++];',
        '  y',
        '];',
        '',
        '(* ── Diagonal Function (SPEC §10, Universality) ─────────────── *)',
        '(* D(x) = F_x(x) + 1 establishes universality *)',
        'diagonal[functionTable_][x_] := functionTable[[x]][x] + 1;',
        '',
        '(* ── Instruction Log Visualization ───────────────────────────── *)',
        '(* Trace the five instructions as a recursive call graph *)',
        'instructionGraph = Graph[{',
        '  DirectedEdge["scope", "singularity"],',
        '  DirectedEdge["singularity", "init"],',
        '  DirectedEdge["init", "goto"],',
        '  DirectedEdge["goto", "iff"],',
        '  DirectedEdge["iff", "init"]  (* recursion *)',
        '}, VertexLabels -> "Name", GraphLayout -> "LayeredDigraphEmbedding"];',
    ]
    return "\n".join(lines)


# ── Wolfram Multiway Graph Bridge ────────────────────────────────────

def _short_label(path_key: str) -> str:
    """Compress 0x10/0x01/.../0x08.pgm → 10.01...08 for readable labels."""
    parts = path_key.replace(".pgm", "").split("/")
    hexes = [p.replace("0x", "") for p in parts if p.startswith("0x")]
    return ".".join(hexes) if hexes else path_key


def multiway_rules_to_wl(hg: Hypergraph) -> str:
    """Extract the full rewriting rule system from the hypergraph.

    Produces four rule sets that together define the multiway evolution:
      - initRules:  deterministic spine transitions (add-seed-stabilize)
      - gotoRules:  nondeterministic checkpoint→child branching
      - iffRules:   classification edges (explorable/collapsed/absorbed)
      - crossRules: scope-crossing edges into workspace

    Uses short hex labels for readability.
    """
    lines = [
        '(* ── Multiway Rewriting Rules ────────────────────────────────── *)',
        '(* Extracted from the 0x unified hypergraph                      *)',
        '(* init = deterministic spine, goto = nondeterministic branch    *)',
        '(* iff = classification, cross = scope extension                 *)',
        '',
    ]

    def _rules_for_kind(kind: EdgeKind) -> list[HyperedgeRecord]:
        return [e for e in hg.edges if e.kind == kind]

    # Init rules (deterministic)
    init_edges = _rules_for_kind(EdgeKind.INIT)
    if init_edges:
        rules = []
        for e in init_edges:
            s = _short_label(e.source_nodes[0])
            t = _short_label(e.target_nodes[0])
            rules.append(f'{_wl_string(s)} -> {_wl_string(t)}')
        lines.append(f'(* Init: {len(init_edges)} deterministic spine steps *)')
        lines.append(f'initRules = {_wl_list(rules)};')
        lines.append('')

    # Goto rules (nondeterministic — this is the multiway fork)
    goto_edges = _rules_for_kind(EdgeKind.GOTO)
    if goto_edges:
        rules = []
        for e in goto_edges:
            s = _short_label(e.source_nodes[0])
            t = _short_label(e.target_nodes[0])
            rules.append(f'{_wl_string(s)} -> {_wl_string(t)}')
        lines.append(f'(* Goto: {len(goto_edges)} nondeterministic branches *)')
        lines.append(f'gotoRules = {_wl_list(rules)};')
        lines.append('')

    # Iff classification rules
    iff_edges = _rules_for_kind(EdgeKind.IFF)
    if iff_edges:
        rules = []
        for e in iff_edges:
            s = e.source_nodes[0]
            t = e.target_nodes[0] if e.target_nodes else "sink"
            cls = e.metadata.get("class", "?")
            rules.append(f'{_wl_string(s)} -> {_wl_string(t)}')
        lines.append(f'(* Iff: {len(iff_edges)} classifications *)')
        lines.append(f'iffRules = {_wl_list(rules)};')
        lines.append('')

    # Cross-scope rules
    cross_edges = _rules_for_kind(EdgeKind.CROSS_SCOPE)
    if cross_edges:
        rules = []
        for e in cross_edges:
            s = e.source_nodes[0]
            t = e.target_nodes[0] if e.target_nodes else "?"
            rules.append(f'{_wl_string(s)} -> {_wl_string(t)}')
        lines.append(f'(* Cross: {len(cross_edges)} scope extensions *)')
        lines.append(f'crossRules = {_wl_list(rules)};')
        lines.append('')

    # Combined rule system
    all_rule_vars = []
    if init_edges:
        all_rule_vars.append("initRules")
    if goto_edges:
        all_rule_vars.append("gotoRules")
    if iff_edges:
        all_rule_vars.append("iffRules")
    if cross_edges:
        all_rule_vars.append("crossRules")

    lines.append(f'allRules = Join[{", ".join(all_rule_vars)}];')
    lines.append('')

    return "\n".join(lines)


def multiway_states_graph_to_wl(hg: Hypergraph) -> str:
    """Generate the MultiwaySystem StatesGraph visualization.

    The states graph shows all reachable states connected by rule
    applications. Nondeterministic goto rules produce branching —
    the same checkpoint can evolve to multiple children simultaneously.
    """
    lines = [
        '(* ── Multiway States Graph ───────────────────────────────────── *)',
        '(* All reachable states from the singularity (seed)              *)',
        '(* Goto rules at checkpoints produce branching paths             *)',
        '',
    ]

    # Determine root state
    seed_key = hg.scope.singularity if hg.scope else "0x/seed/0x80.pgm"
    spine_init = [e for e in hg.edges if e.kind == EdgeKind.INIT]
    root = _short_label(spine_init[0].source_nodes[0]) if spine_init else _short_label(seed_key)

    lines.append(f'multiwayRoot = {_wl_string(root)};')
    lines.append('')

    # States graph: all rules applied from root, N steps
    n_steps = max(3, len(spine_init))
    lines.append(f'(* MultiwaySystem: exploring {n_steps} steps from singularity *)')
    lines.append(f'statesGraph = ResourceFunction["MultiwaySystem"][')
    lines.append(f'  Join[initRules, gotoRules], multiwayRoot, {n_steps},')
    lines.append(f'  "StatesGraph",')
    lines.append(f'  VertexSize -> 0.5,')
    lines.append(f'  GraphLayout -> "LayeredDigraphEmbedding"')
    lines.append(f'];')
    lines.append('')
    lines.append('(* Annotate with iff classification coloring *)')
    lines.append('statesGraphColored = HighlightGraph[statesGraph,')

    # Build highlight groups from iff results
    explorable = [r.address for r in hg.iff_results if r.iff_class == IffClass.EXPLORABLE]
    collapsed = [r.address for r in hg.iff_results if r.iff_class == IffClass.COLLAPSED]
    absorbed = [r.address for r in hg.iff_results if r.iff_class == IffClass.ABSORBED]

    if explorable:
        lines.append(f'  Style[{_wl_list([_wl_string(a) for a in explorable])}, Green],')
    if collapsed:
        lines.append(f'  Style[{_wl_list([_wl_string(a) for a in collapsed])}, Gray],')
    if absorbed:
        lines.append(f'  Style[{_wl_list([_wl_string(a) for a in absorbed])}, Orange],')

    # Remove trailing comma from last Style line
    if lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]

    lines.append('];')
    lines.append('')

    return "\n".join(lines)


def multiway_branchial_graph_to_wl(hg: Hypergraph) -> str:
    """Generate the MultiwaySystem BranchialGraph visualization.

    The branchial graph connects states that are "spacelike separated" —
    states reachable at the same recursion depth but through different
    branching paths. This is the key structure that shows which
    checkpoint children are simultaneously explorable.

    In the sandpile context:
      - States at the same depth from root are on the same branchial slice
      - The branchial graph's connected components = independent exploration fronts
      - Cliques in the branchial graph = states arising from the same checkpoint
    """
    spine_init = [e for e in hg.edges if e.kind == EdgeKind.INIT]
    root = _short_label(spine_init[0].source_nodes[0]) if spine_init else "10.01"
    n_steps = max(3, len(spine_init))

    lines = [
        '(* ── Multiway Branchial Graph ────────────────────────────────── *)',
        '(* Spacelike-separated states at each recursion depth             *)',
        '(* Connected components = independent exploration fronts          *)',
        '(* Cliques = children of the same checkpoint                     *)',
        '',
        f'branchialGraph = ResourceFunction["MultiwaySystem"][',
        f'  Join[initRules, gotoRules], {_wl_string(root)}, {n_steps},',
        f'  "BranchialGraph",',
        f'  GraphLayout -> "SpringElectricalEmbedding"',
        f'];',
        '',
    ]

    return "\n".join(lines)


def multiway_causal_graph_to_wl(hg: Hypergraph) -> str:
    """Generate the MultiwaySystem evolution causal graph.

    The causal graph shows which rule applications causally influence
    which later applications. In the sandpile context:
      - Init steps form a causal chain (each depends on the prior)
      - Goto branches from a checkpoint are causally independent
      - Iff classifications causally depend on their parent state

    This directly corresponds to the DAG causal layer from dag.py.
    """
    spine_init = [e for e in hg.edges if e.kind == EdgeKind.INIT]
    root = _short_label(spine_init[0].source_nodes[0]) if spine_init else "10.01"
    n_steps = max(3, len(spine_init))

    lines = [
        '(* ── Multiway Evolution Causal Graph ─────────────────────────── *)',
        '(* Causal dependencies between rule applications                  *)',
        '(* Init = causal chain, Goto = causally independent branches     *)',
        '',
        f'causalGraph = ResourceFunction["MultiwaySystem"][',
        f'  Join[initRules, gotoRules], {_wl_string(root)}, {n_steps},',
        f'  "EvolutionCausalGraph",',
        f'  GraphLayout -> "LayeredDigraphEmbedding"',
        f'];',
        '',
    ]

    return "\n".join(lines)


def multiway_wolfram_model_to_wl(hg: Hypergraph) -> str:
    """Express the hypergraph as WolframModel evolution rules.

    WolframModel operates on hypergraphs directly — each rule rewrites
    a set of hyperedges into another set. This is the deepest connection:
    the 0x engine's hypergraph IS a WolframModel state, and each
    instruction (init, goto, iff) IS a rewriting rule.

    The init rule: {{a, b}} -> {{b, c}} (deterministic successor)
    The goto rule: {{cp}} -> {{c1}, {c2}, ...} (nondeterministic branch)
    The iff rule:  {{addr, class}} -> {{addr, succ}} | {} (conditional)
    """
    lines = [
        '(* ── WolframModel Hypergraph Evolution ──────────────────────── *)',
        '(* The 0x hypergraph as a WolframModel rewriting system         *)',
        '(* Each instruction = a rewriting rule on hyperedges            *)',
        '',
    ]

    # Build abstract WolframModel rules from the five instructions
    lines.append('(* Abstract rules derived from the five instructions *)')
    lines.append('(* Rule 1: init (Successor) — deterministic chain *)')
    lines.append('initWMRule = {{x, y}} -> {{y, z}};')
    lines.append('')
    lines.append('(* Rule 2: goto (Composition) — vertex probe branching *)')
    lines.append('gotoWMRule = {{x, y}} -> {{x, y1}, {x, y2}};')
    lines.append('')

    # Concrete init hyperedges from the spine
    init_edges = [e for e in hg.edges if e.kind == EdgeKind.INIT]
    if init_edges:
        hyper = []
        for e in init_edges:
            s = _short_label(e.source_nodes[0])
            t = _short_label(e.target_nodes[0])
            hyper.append(_wl_list([_wl_string(s), _wl_string(t)]))
        lines.append(f'(* Concrete spine as WolframModel initial state *)')
        lines.append(f'initHyperedges = {_wl_list(hyper)};')
        lines.append('')

    # Goto branching hyperedges from checkpoints
    goto_edges = [e for e in hg.edges if e.kind == EdgeKind.GOTO]
    if goto_edges:
        hyper = []
        for e in goto_edges:
            s = _short_label(e.source_nodes[0])
            t = _short_label(e.target_nodes[0])
            hyper.append(_wl_list([_wl_string(s), _wl_string(t)]))
        lines.append(f'(* Goto branching hyperedges *)')
        lines.append(f'gotoHyperedges = {_wl_list(hyper)};')
        lines.append('')

    # Cross-scope hyperedges
    cross_edges = [e for e in hg.edges if e.kind == EdgeKind.CROSS_SCOPE]
    if cross_edges:
        hyper = []
        for e in cross_edges:
            nodes = list(e.source_nodes) + list(e.target_nodes)
            hyper.append(_wl_list([_wl_string(n) for n in nodes]))
        lines.append(f'(* Cross-scope hyperedges *)')
        lines.append(f'crossHyperedges = {_wl_list(hyper)};')
        lines.append('')

    # Combined initial condition for WolframModel
    lines.append('(* Full initial hypergraph state *)')
    parts = []
    if init_edges:
        parts.append("initHyperedges")
    if goto_edges:
        parts.append("gotoHyperedges")
    if cross_edges:
        parts.append("crossHyperedges")
    lines.append(f'fullHypergraph = Join[{", ".join(parts)}];')
    lines.append('')

    # WolframModel evolution
    lines.append('(* WolframModel evolution — apply init rule *)')
    lines.append('wmEvolution = ResourceFunction["WolframModel"][')
    lines.append('  initWMRule, initHyperedges, 4];')
    lines.append('wmEvolution["FinalStatePlot"]')
    lines.append('')

    # WolframModelPlot of the full state
    lines.append('(* Full hypergraph visualization *)')
    lines.append('ResourceFunction["WolframModelPlot"][fullHypergraph,')
    lines.append('  VertexLabels -> Automatic]')

    return "\n".join(lines)


def multiway_all_views_to_wl(hg: Hypergraph) -> str:
    """Generate the complete multiway section combining all views.

    This is the master function that produces:
      1. The rewriting rule system
      2. States graph (all reachable states)
      3. Branchial graph (spacelike structure)
      4. Evolution causal graph (timelike structure)
      5. WolframModel hypergraph evolution
      6. Comparative analysis (branchial width, causal depth, etc.)
    """
    sections = [
        multiway_rules_to_wl(hg),
        '',
        multiway_states_graph_to_wl(hg),
        '',
        multiway_branchial_graph_to_wl(hg),
        '',
        multiway_causal_graph_to_wl(hg),
        '',
        multiway_wolfram_model_to_wl(hg),
        '',
        '(* ── Multiway Comparative Analysis ───────────────────────────── *)',
        '(* Structural properties of the multiway system                  *)',
        '',
        '(* Branchial width at each step (# of simultaneously live states) *)',
        'branchialWidths = ResourceFunction["MultiwaySystem"][',
        '  Join[initRules, gotoRules], multiwayRoot,',
        f'  {max(3, len([e for e in hg.edges if e.kind == EdgeKind.INIT]))},',
        '  "StateCount"',
        '];',
        'ListLinePlot[branchialWidths,',
        '  PlotLabel -> "Multiway Branchial Width",',
        '  AxesLabel -> {"Recursion Depth", "# Live States"},',
        '  PlotTheme -> "Scientific"]',
        '',
        '(* States graph properties *)',
        'Print["States graph vertices: ", VertexCount[statesGraph]];',
        'Print["States graph edges: ", EdgeCount[statesGraph]];',
        '',
        '(* Branchial graph properties *)',
        'Print["Branchial graph vertices: ", VertexCount[branchialGraph]];',
        'Print["Branchial graph edges: ", EdgeCount[branchialGraph]];',
        'Print["Branchial components: ", Length@ConnectedComponents[UndirectedGraph[branchialGraph]]];',
        '',
        '(* Causal graph depth (= recursion depth of the longest path) *)',
        'Print["Causal graph depth: ", GraphDiameter[causalGraph]];',
        '',
    ]

    return "\n".join(sections)


# ── Full Workbook Generation ─────────────────────────────────────────

def generate_workbook(
    hg: Hypergraph,
    ox_root: Path,
    output_path: Path,
) -> str:
    """Generate a complete Wolfram Language workbook (.wl) file.

    The workbook is structured as a self-contained evaluation that covers:
      §1  Sandpile Foundations (grid construction, stabilization)
      §2  The Embedded Tree (0x/ structure, scope derivation)
      §3  12-Glyph Interval Decoder (SPEC §4)
      §4  Boundary Potential (SPEC §5)
      §5  Hypergraph Language (SPEC §6)
      §6  The Universal Argument (Recursive Functions → five instructions)
      §7  Multiway System (states/branchial/causal graphs + WolframModel)
      §8  Invariant Extraction & Verification
    """
    summary = summarize_hypergraph(hg)
    seed_path = ox_root / "seed" / "0x80.pgm"

    sections: list[str] = []

    # ── §1 Sandpile Foundations ───────────────────────────────────────
    sections.append(
        '(* ================================================================ *)\n'
        '(* §1  SANDPILE FOUNDATIONS                                          *)\n'
        '(* Abelian sandpile on regular grid, degree-4, boundary sinks       *)\n'
        '(* Reference: Numberphile/Wolfram Community implementation           *)\n'
        '(* ================================================================ *)\n'
        '\n'
        '(* Grid construction *)\n'
        'n = 32;  (* grid dimension *)\n'
        'maxHeight = 3;  (* max grains before toppling *)\n'
        'grid = GridGraph[{n, n}];\n'
        '\n'
        '(* Sandpile stabilization (Wolfram Language native) *)\n'
        'stabilize[state_List] := Module[{s = state, tmp},\n'
        '  While[Max[s] > maxHeight,\n'
        '    s = ArrayPad[s, 1, 0];\n'
        '    tmp = Quotient[s, 4];\n'
        '    s -= 4 tmp;\n'
        '    s += RotateLeft[tmp, {0, 1}] + RotateLeft[tmp, {1, 0}]\n'
        '       + RotateLeft[tmp, {0, -1}] + RotateLeft[tmp, {-1, 0}];\n'
        '    s = ArrayPad[s, -1];\n'
        '  ];\n'
        '  s\n'
        '];\n'
        '\n'
        '(* Visualize a sandpile state *)\n'
        'sandpileColors = {0 -> Black, 1 -> RGBColor[0, 0.5, 1],\n'
        '  2 -> RGBColor[1, 0.8, 0], 3 -> RGBColor[1, 0, 0]};\n'
        'showSandpile[state_] := ArrayPlot[state /. sandpileColors,\n'
        '  Frame -> False, ImageSize -> 300];\n'
        '\n'
        '(* ResourceFunction bridge *)\n'
        'sandpileTopple[g_, config_] := ResourceFunction["SandpileTopple"][g, config];\n'
    )

    # ── §2 The Embedded Tree ──────────────────────────────────────────
    spine_len = summary.get("edges", {}).get("init", 0)
    scope_info = summary.get("scope", {})
    sections.append(
        '(* ================================================================ *)\n'
        '(* §2  THE EMBEDDED TREE (0x/ structure)                            *)\n'
        '(* SPEC §7: the filesystem IS the glossary, the function table,    *)\n'
        '(*          the recursion lattice, the semantic address space       *)\n'
        '(* ================================================================ *)\n'
        '\n'
        f'(* Scope: period={scope_info.get("period", "?")}, '
        f'seed_chips={scope_info.get("seed_chips", "?")}, '
        f'root_label={scope_info.get("root_label", "?")} *)\n'
        f'(* Singularity: {scope_info.get("singularity", "?")} *)\n'
        f'(* Spine length: {spine_len + 1} nodes, {spine_len} init edges *)\n'
        '\n'
        f'scopePeriod = {scope_info.get("period", 8)};\n'
        f'seedChips = {scope_info.get("seed_chips", 128)};\n'
        f'rootLabel = {scope_info.get("root_label", 16)};\n'
        '\n'
        '(* Seed surface *)\n'
    )
    if seed_path.exists():
        sections.append(f'seed = {pgm_to_wl_matrix(seed_path)};\n')
    else:
        sections.append(f'seed = ConstantArray[0, {{n, n}}];\n'
                        f'seed[[n/2, n/2]] = seedChips;\n')

    sections.append(
        '\n'
        '(* Generate spine by repeated add-seed-stabilize *)\n'
        'spine = NestList[stabilize[# + seed] &, ConstantArray[0, {n, n}], scopePeriod];\n'
        'Grid[{showSandpile /@ spine}]\n'
    )

    # ── §3 12-Glyph Interval Decoder ─────────────────────────────────
    sections.append(
        '\n(* ================================================================ *)\n'
        '(* §3  12-GLYPH INTERVAL DECODER (SPEC §4)                         *)\n'
        '(* 4 bands × 3 elements, nearest-anchor decoding                   *)\n'
        '(* ================================================================ *)\n'
        '\n'
    )
    sections.append(glyph_alphabet_to_wl())
    sections.append(
        '\n\n'
        '(* Decode an entire surface to glyph matrix *)\n'
        'decodeSurface[mat_] := Map[decodeGlyph, mat, {2}];\n'
        '\n'
        '(* Band assignment *)\n'
        'glyphBands = {0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3};\n'
        'bandOfGlyph[idx_] := glyphBands[[idx]];\n'
    )

    # ── §4 Boundary Potential ─────────────────────────────────────────
    boundary_info = summary.get("boundary", {})
    sections.append(
        '\n(* ================================================================ *)\n'
        '(* §4  BOUNDARY POTENTIAL (SPEC §5)                                *)\n'
        '(* ϕ_z(u,v) = h_z(u) - h_z(v)                                     *)\n'
        '(* Only non-zero potentials define the influence graph              *)\n'
        '(* ================================================================ *)\n'
        '\n'
        f'(* {boundary_info.get("edges", 0)} boundary edges, '
        f'max potential = {boundary_info.get("max_potential", 0)} *)\n'
        '\n'
        'boundaryPotential[mat_] := Module[{h = mat, edges = {}},\n'
        '  Do[\n'
        '    If[h[[r, c]] != h[[r, c + 1]],\n'
        '      AppendTo[edges, {r, c} -> {r, c + 1}]];\n'
        '    If[h[[r, c]] != h[[r + 1, c]],\n'
        '      AppendTo[edges, {r, c} -> {r + 1, c}]];\n'
        '  , {r, Length[h] - 1}, {c, Length[h[[1]]] - 1}];\n'
        '  edges\n'
        '];\n'
        '\n'
        '(* Influence graph from boundary *)\n'
        'influenceGraph[mat_] := Graph[\n'
        '  DirectedEdge @@@ boundaryPotential[mat],\n'
        '  GraphLayout -> "SpringElectricalEmbedding"\n'
        '];\n'
    )

    # ── §5 Hypergraph Language ────────────────────────────────────────
    sections.append(
        '\n(* ================================================================ *)\n'
        '(* §5  HYPERGRAPH LANGUAGE (SPEC §6)                               *)\n'
        '(* "All computation is defined by hyperedges.                      *)\n'
        '(*  Everything else is a projection."                               *)\n'
        '(* ================================================================ *)\n'
        '\n'
    )
    sections.append(hypergraph_to_wl(hg))

    # ── §6 The Universal Argument ─────────────────────────────────────
    sections.append(
        '\n\n(* ================================================================ *)\n'
        '(* §6  THE UNIVERSAL ARGUMENT                                       *)\n'
        '(* Recursive_Functions.pdf: Zero, Succ, Proj → Comp, PrimRec → μ  *)\n'
        '(* ASM_TC.pdf: sandpiles on Z³ are Turing-complete (Cairns 2021)  *)\n'
        '(* SPEC §10: D(x) = F_x(x) + 1 establishes universality          *)\n'
        '(* ================================================================ *)\n'
        '\n'
    )
    sections.append(recursive_function_correspondence_to_wl(hg))

    # ── §7 Multiway System ─────────────────────────────────────────────
    sections.append(
        '\n\n(* ================================================================ *)\n'
        '(* §7  MULTIWAY SYSTEM                                              *)\n'
        '(* The 0x/ tree IS a multiway graph.                               *)\n'
        '(* Spine = deterministic backbone, checkpoints = branch points     *)\n'
        '(* iff classifies which branches survive (explorable/collapsed)    *)\n'
        '(* States graph: all reachable states                              *)\n'
        '(* Branchial graph: spacelike separation (simultaneous fronts)    *)\n'
        '(* Causal graph: timelike dependencies between rule applications   *)\n'
        '(* WolframModel: hypergraph rewriting from the five instructions   *)\n'
        '(* ================================================================ *)\n'
        '\n'
    )
    sections.append(multiway_all_views_to_wl(hg))

    # ── §8 Invariant Extraction & Verification ────────────────────────
    iff_info = summary.get("iff_classification", {})
    sections.append(
        '\n\n(* ================================================================ *)\n'
        '(* §8  INVARIANT EXTRACTION & VERIFICATION                          *)\n'
        '(* SPEC §12: recursion families, interval/glyph structure,         *)\n'
        '(*   boundary potentials, periodic groups, global sink,            *)\n'
        '(*   supersingular invariants                                       *)\n'
        '(* ================================================================ *)\n'
        '\n'
        f'(* IFF classification: collapsed={iff_info.get("collapsed", 0)}, '
        f'absorbed={iff_info.get("absorbed", 0)}, '
        f'explorable={iff_info.get("explorable", 0)} *)\n'
        '\n'
        '(* Verify period-8 recurrence *)\n'
        'verifyRecurrence[spineStates_] := Module[{diffs},\n'
        '  diffs = Table[\n'
        '    Total[Abs[spineStates[[i]] - spineStates[[i + scopePeriod]]], 2],\n'
        '    {i, Length[spineStates] - scopePeriod}\n'
        '  ];\n'
        '  AllTrue[diffs, # == 0 &]\n'
        '];\n'
        '\n'
        '(* Laplacian of the grid graph (sandpile group structure) *)\n'
        'laplacian = KirchhoffMatrix[grid];\n'
        '(* Sandpile group order = Det[reduced Laplacian] *)\n'
        'reducedLaplacian = Delete[laplacian, {{1}, {-1}}];\n'
        'reducedLaplacian = Delete[#, {{1}}] & /@ reducedLaplacian;\n'
        'sandpileGroupOrder = Det[reducedLaplacian];\n'
        'Print["Sandpile group order: ", sandpileGroupOrder];\n'
        '\n'
        '(* Supersingular correspondence stub (SPEC §14) *)\n'
        '(* p = 0xffffffff00000001 = 2^64 - 2^32 + 1 *)\n'
        'supersingularPrime = 2^64 - 2^32 + 1;\n'
        'Print["Supersingular prime: ", supersingularPrime];\n'
        'Print["Is prime: ", PrimeQ[supersingularPrime]];\n'
        '\n'
        '(* RecursiveFunctionCallGraph for the five instructions *)\n'
        'ResourceFunction["RecursiveFunctionCallGraph"][\n'
        '  primitiveRecursion[Function[x, zero], \n'
        '    Function[{x, n, prev}, successor[prev]]][#, 4] &,\n'
        '  ConstantArray[0, {n, n}]\n'
        ']\n'
    )

    content = "\n".join(sections)
    output_path.write_text(content, encoding="utf-8")
    return content


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    import sys

    ox_root = Path("0x")
    workspace_root = Path("workspace")
    output = Path("workbook.wl")

    if len(sys.argv) > 1:
        output = Path(sys.argv[1])

    print(f"Building hypergraph from {ox_root}/ and {workspace_root}/ ...")
    hg = build_hypergraph(ox_root, workspace_root)
    summary = summarize_hypergraph(hg)

    print(f"  {summary['nodes']['total']} nodes, {len(hg.edges)} edges")
    print(f"  {len(hg.instruction_log)} instruction records")
    print(f"  {summary['boundary']['edges']} boundary edges")

    print(f"Generating workbook → {output} ...")
    generate_workbook(hg, ox_root, output)
    print(f"  Written {output.stat().st_size} bytes")
    print("Done. Open in Wolfram Mathematica or evaluate with wolframscript.")


if __name__ == "__main__":
    main()
