"""Unified engine: reads the 0x/ tree as ground truth, maps workspace scopes
into it, and builds the hypergraph from both."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from .netpbm import NetpbmImage, read_netpbm
except ImportError:  # allow standalone execution
    from netpbm import NetpbmImage, read_netpbm  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# PGM node: a state in either tree
# ---------------------------------------------------------------------------

class NodeClass(Enum):
    COLLAPSED = "collapsed"    # 1x1, boundary/sink probe
    LEAF = "leaf"              # full surface, no successors
    EXPLORABLE = "explorable"  # full surface, has successors
    SPINE = "spine"            # accumulation step on init path
    SEED = "seed"              # singularity
    CHECKPOINT = "checkpoint"  # period-boundary state
    GLYPH = "glyph"            # decoded glyph node


@dataclass(frozen=True)
class StateNode:
    """A single state in the filesystem tree."""
    address: str               # hex label, e.g. "0x08"
    path: Path                 # path to the .pgm file
    directory: Path            # containing directory
    width: int
    height: int
    max_value: int
    total_chips: int
    nonzero_cells: int
    node_class: NodeClass
    children: tuple[str, ...]  # addresses of successor directories
    signature: str             # flattened pixel string for identity


@dataclass
class TreeIndex:
    """Complete index of a filesystem state tree."""
    root: Path
    nodes: dict[str, StateNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    spine: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    """Derived scope: period length and seed chip count."""
    period: int          # = seed_chips / root_label
    seed_chips: int      # total chips in singularity
    root_label: int      # hex value of root directory name
    singularity: str     # path to seed pgm


# ---------------------------------------------------------------------------
# IFF classification
# ---------------------------------------------------------------------------

class IffClass(Enum):
    COLLAPSED = "collapsed"          # 1x1 → boundary probe
    ABSORBED = "absorbed"            # full surface, stable leaf
    EXPLORABLE = "explorable"        # full surface, has successors


@dataclass(frozen=True)
class IffResult:
    """Classification of a child node at a checkpoint."""
    address: str
    iff_class: IffClass
    successor: str | None    # address of successor, if any
    chips: int
    dimensions: tuple[int, int]


# ---------------------------------------------------------------------------
# Hypergraph
# ---------------------------------------------------------------------------

# Five primitive instructions (SPEC §8):
#   scope, singularity, init, goto, iff
# These define hypergraph structure, not execution.

class Instruction(Enum):
    SCOPE = "scope"              # select interval family, bound production pointer
    SINGULARITY = "singularity"  # identify distinguished fixed point / seed
    INIT = "init"                # materialize surface from seed under scope
    GOTO = "goto"                # traverse successor edges
    IFF = "iff"                  # branch on global invariants


@dataclass(frozen=True)
class InstructionRecord:
    """A single compositional instruction applied to the hypergraph.
    
    These records define structure: which instruction produced which
    hyperedges and under what context. They are the semantic atoms
    from which the hypergraph is built.
    """
    instruction: Instruction
    context: dict[str, Any]    # instruction-specific parameters
    produced_edges: tuple[int, ...]  # indices into Hypergraph.edges


class EdgeKind(Enum):
    INIT = "init"              # spine accumulation
    GOTO = "goto"              # real branching at checkpoint
    IFF = "iff"                # classification edge
    CROSS_SCOPE = "cross"      # workspace→0x mapping
    GLYPH_DECODE = "glyph"     # pixel → glyph decoding
    BOUNDARY = "boundary"      # boundary potential edge
    FUNCTION_APP = "func"      # function application edge


@dataclass(frozen=True)
class HyperedgeRecord:
    """A typed edge in the hypergraph."""
    kind: EdgeKind
    source_nodes: tuple[str, ...]
    target_nodes: tuple[str, ...]
    rule: str                  # which rule produced this edge
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypergraph:
    """The unified hypergraph connecting 0x/ and workspace/ trees."""
    nodes: dict[str, StateNode] = field(default_factory=dict)
    edges: list[HyperedgeRecord] = field(default_factory=list)
    scope: Scope | None = None
    iff_results: list[IffResult] = field(default_factory=list)
    cross_scope_map: dict[str, str] = field(default_factory=dict)
    glyph_nodes: dict[str, GlyphNode] = field(default_factory=dict)
    boundary_edges: list[BoundaryEdge] = field(default_factory=list)
    instruction_log: list[InstructionRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tree parser
# ---------------------------------------------------------------------------

def _read_pgm_stats(path: Path) -> tuple[int, int, int, int, int, str]:
    """Return (width, height, max_value, total_chips, nonzero_cells, signature).

    Uses the package NetpbmImage reader.
    """
    img = read_netpbm(path)
    flat = [v for row in img.pixels for v in row]
    total = sum(flat)
    nonzero = sum(1 for v in flat if v > 0)
    sig = "".join(str(v) for v in flat)
    return img.width, img.height, img.max_value, total, nonzero, sig


def _classify_node(
    width: int,
    height: int,
    total_chips: int,
    children: list[str],
    depth: int,
    is_seed: bool,
) -> NodeClass:
    if is_seed:
        return NodeClass.SEED
    if width == 1 and height == 1:
        return NodeClass.COLLAPSED
    if not children:
        return NodeClass.LEAF
    if len(children) > 2:
        return NodeClass.CHECKPOINT
    return NodeClass.SPINE


def parse_ox_tree(root: Path) -> TreeIndex:
    """Parse the 0x/ filesystem tree into a TreeIndex."""
    index = TreeIndex(root=root)

    def walk(directory: Path, parent_addr: str | None, depth: int) -> None:
        subdirs = sorted([
            d for d in directory.iterdir()
            if d.is_dir() and d.name.startswith("0x")
        ])
        pgm_files = sorted(directory.glob("*.pgm"))

        for pgm in pgm_files:
            addr = pgm.stem  # e.g. "0x08"
            child_dirs = sorted([
                d for d in directory.iterdir()
                if d.is_dir() and d.name.startswith("0x") and d.name != addr
            ])
            child_addrs = [d.name for d in child_dirs]

            w, h, mv, total, nz, sig = _read_pgm_stats(pgm)
            is_seed = directory.name == "seed"
            nc = _classify_node(w, h, total, child_addrs, depth, is_seed)

            node = StateNode(
                address=addr,
                path=pgm,
                directory=directory,
                width=w,
                height=h,
                max_value=mv,
                total_chips=total,
                nonzero_cells=nz,
                node_class=nc,
                children=tuple(child_addrs),
                signature=sig,
            )
            # Use full relative path as key to avoid collisions
            key = str(pgm.relative_to(root))
            index.nodes[key] = node

            if parent_addr is not None:
                index.edges.append((parent_addr, key))

        for subdir in subdirs:
            # Find the pgm in this directory to use as parent
            parent_key = None
            for pgm in pgm_files:
                parent_key = str(pgm.relative_to(root))
                break
            walk(subdir, parent_key, depth + 1)

    walk(root, None, 0)
    return index


def find_spine(index: TreeIndex) -> list[str]:
    """Extract the linear init spine from the tree."""
    spine = []
    for key, node in sorted(index.nodes.items()):
        if node.node_class in (NodeClass.SEED, NodeClass.SPINE, NodeClass.CHECKPOINT):
            spine.append(key)
    return spine


# ---------------------------------------------------------------------------
# Scope derivation
# ---------------------------------------------------------------------------

def derive_scope(ox_root: Path) -> Scope:
    """Derive scope from the 0x/ tree: period = seed_chips / root_label."""
    seed_path = ox_root / "seed" / "0x80.pgm"
    root_dir = None
    for d in ox_root.iterdir():
        if d.is_dir() and d.name.startswith("0x") and d.name != "seed":
            root_dir = d
            break

    if root_dir is None or not seed_path.exists():
        raise ValueError("cannot derive scope: missing seed or root directory")

    _, _, _, seed_chips, _, _ = _read_pgm_stats(seed_path)
    root_label = int(root_dir.name, 16)
    period = seed_chips // root_label if root_label else 0

    return Scope(
        period=period,
        seed_chips=seed_chips,
        root_label=root_label,
        singularity=str(seed_path),
    )


# ---------------------------------------------------------------------------
# IFF classification at checkpoint
# ---------------------------------------------------------------------------

def classify_checkpoint_children(index: TreeIndex) -> list[IffResult]:
    """Classify all children at the first checkpoint (branching node)."""
    results = []
    for key, node in index.nodes.items():
        if node.node_class != NodeClass.CHECKPOINT:
            continue
        # This is the checkpoint; classify its children
        checkpoint_dir = node.directory
        for child_name in sorted(checkpoint_dir.iterdir()):
            if not child_name.is_dir() or not child_name.name.startswith("0x"):
                continue
            if child_name.name == node.address:
                continue  # skip self-reference
            child_pgm = child_name / f"{child_name.name}.pgm"
            if not child_pgm.exists():
                continue
            w, h, _, chips, _, _ = _read_pgm_stats(child_pgm)

            # Find successor
            successor_dirs = sorted([
                d for d in child_name.iterdir()
                if d.is_dir() and d.name.startswith("0x")
            ])
            successor = successor_dirs[0].name if successor_dirs else None

            if w == 1 and h == 1:
                cls = IffClass.COLLAPSED
            elif successor:
                cls = IffClass.EXPLORABLE
            else:
                cls = IffClass.ABSORBED

            results.append(IffResult(
                address=child_name.name,
                iff_class=cls,
                successor=successor,
                chips=chips,
                dimensions=(w, h),
            ))
    return results


# ---------------------------------------------------------------------------
# 12-Glyph interval structure (SPEC §4)
# ---------------------------------------------------------------------------

GLYPH_ANCHORS = (64, 78, 92, 96, 113, 132, 133, 151, 166, 169, 185, 201)
GLYPH_SYMBOLS = ('@', 'N', '\\', '`', 'q', '\u201e', '\u2026', '\u2014',
                 '\u00a6', '\u00a9', '\u00b9', '\u00c9')
GLYPH_BANDS = (
    (0, 1, 2),    # Band 0: @  N  \
    (3, 4, 5),    # Band 1: `  q  „
    (6, 7, 8),    # Band 2: …  —  ¦
    (9, 10, 11),  # Band 3: ©  ¹  É
)


def decode_glyph(value: int) -> int:
    """Map a grayscale pixel value to the nearest glyph index (0-11)."""
    best = 0
    best_dist = abs(value - GLYPH_ANCHORS[0])
    for i in range(1, 12):
        d = abs(value - GLYPH_ANCHORS[i])
        if d < best_dist:
            best = i
            best_dist = d
    return best


def decode_glyph_symbol(value: int) -> str:
    """Map a grayscale pixel value to its glyph character."""
    return GLYPH_SYMBOLS[decode_glyph(value)]


def glyph_band(index: int) -> int:
    """Return the band number (0-3) for a glyph index (0-11)."""
    return index // 3


@dataclass(frozen=True)
class GlyphNode:
    """A decoded glyph from a checkpoint PGM."""
    state_key: str             # key of the state node this was decoded from
    position: tuple[int, int]  # (x, y) in the surface
    pixel_value: int           # raw grayscale value
    glyph_index: int           # 0-11
    glyph_symbol: str          # the character
    band: int                  # 0-3


def decode_surface_glyphs(
    state_key: str,
    img: NetpbmImage,
) -> list[GlyphNode]:
    """Decode all non-zero pixels in a surface to glyph nodes."""
    nodes: list[GlyphNode] = []
    for y, row in enumerate(img.pixels):
        for x, val in enumerate(row):
            if val == 0:
                continue
            idx = decode_glyph(val)
            nodes.append(GlyphNode(
                state_key=state_key,
                position=(x, y),
                pixel_value=val,
                glyph_index=idx,
                glyph_symbol=GLYPH_SYMBOLS[idx],
                band=glyph_band(idx),
            ))
    return nodes


# ---------------------------------------------------------------------------
# Boundary potential (SPEC §5): ϕ_z(u,v) = h_z(u) - h_z(v)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundaryEdge:
    """A directed boundary-potential edge between adjacent cells."""
    state_key: str
    u: tuple[int, int]         # source cell (x, y)
    v: tuple[int, int]         # neighbor cell (x, y)
    potential: int             # h(u) - h(v)


def extract_boundary_potential(
    state_key: str,
    img: NetpbmImage,
) -> list[BoundaryEdge]:
    """Extract boundary-potential edges where adjacent cells differ.

    Only non-zero potentials are returned — these define the influence
    graph for the next recursion step (SPEC §5).
    """
    edges: list[BoundaryEdge] = []
    w, h = img.width, img.height
    for y in range(h):
        for x in range(w):
            hu = img.pixels[y][x]
            # 4-connected neighbors (degree-4 grid)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    hv = img.pixels[ny][nx]
                    phi = hu - hv
                    if phi != 0:
                        edges.append(BoundaryEdge(
                            state_key=state_key,
                            u=(x, y),
                            v=(nx, ny),
                            potential=phi,
                        ))
    return edges


# ---------------------------------------------------------------------------
# PGM comment metadata read-back
# ---------------------------------------------------------------------------

def parse_pgm_comments(img: NetpbmImage) -> dict[str, str]:
    """Extract key=value metadata from PGM comment lines.

    Comment lines are expected to look like:
        # scope_depth=8
        # state_id=0x100
    Returns a dict of {key: value} pairs.
    """
    meta: dict[str, str] = {}
    if not img.comments:
        return meta
    for line in img.comments:
        text = line.lstrip("# ").strip()
        if "=" in text:
            key, _, value = text.partition("=")
            meta[key.strip()] = value.strip()
    return meta


# ---------------------------------------------------------------------------
# Workspace scope group parser
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkspaceScope:
    """A scope from the workspace tree: a child of the root with its subtree."""
    address: str               # e.g. "0x01", "0x0a"
    total_chips: int
    dimensions: tuple[int, int]
    child_count: int
    has_ref: bool
    node_class: NodeClass
    signature: str


def parse_workspace_scopes(workspace_root: Path) -> list[WorkspaceScope]:
    """Parse the workspace state tree and extract each scope."""
    state_tree = workspace_root / "state_tree" / "sandpile_state0x10"
    if not state_tree.exists():
        return []

    scopes = []
    for child_dir in sorted(state_tree.iterdir()):
        if not child_dir.is_dir():
            continue
        name = child_dir.name  # e.g. "sandpile_state0x01"
        addr = name.removeprefix("sandpile_state")
        pgm = child_dir / f"{name}.pgm"
        ref = child_dir / f"{name}.pgm.ref"

        if not pgm.exists():
            continue

        grandchildren = [
            d for d in child_dir.iterdir()
            if d.is_dir() and d.name.startswith("sandpile_state")
        ]

        # Check if pgm is a reference or actual state
        is_ref = ref.exists()

        if pgm.stat().st_size < 20:
            # Likely a ref pointer, read dimensions from the ref
            w, h, chips, nz = 1, 1, 0, 0
            sig = "0"
        else:
            try:
                w, h, _, chips, nz, sig = _read_pgm_stats(pgm)
            except Exception:
                w, h, chips, nz, sig = 1, 1, 0, 0, "0"

        if w == 1 and h == 1:
            nc = NodeClass.COLLAPSED
        elif len(grandchildren) == 0:
            nc = NodeClass.LEAF
        elif len(grandchildren) > 2:
            nc = NodeClass.EXPLORABLE
        else:
            nc = NodeClass.SPINE

        scopes.append(WorkspaceScope(
            address=addr,
            total_chips=chips,
            dimensions=(w, h),
            child_count=len(grandchildren),
            has_ref=is_ref,
            node_class=nc,
            signature=sig,
        ))

    return scopes


# ---------------------------------------------------------------------------
# Cross-scope mapping: initial scope → workspace scope group
# ---------------------------------------------------------------------------

def map_scopes(
    ox_index: TreeIndex,
    ws_scopes: list[WorkspaceScope],
    iff_results: list[IffResult],
) -> dict[str, list[str]]:
    """Map 0x/ checkpoint children to workspace scopes by address match.

    Returns {ox_child_address: [ws_scope_addresses]} for each match.
    Both trees share the same address space under 0x10, so addresses
    that appear in both trees represent the same vertex probe.
    """
    ox_addresses = {r.address for r in iff_results}
    ws_by_addr: dict[str, list[str]] = {}

    for ws in ws_scopes:
        ws_by_addr.setdefault(ws.address, []).append(ws.address)

    mapping: dict[str, list[str]] = {}
    for ox_addr in sorted(ox_addresses):
        matched = ws_by_addr.get(ox_addr, [])
        if matched:
            mapping[ox_addr] = matched
        else:
            # Check if workspace has explored further from this address
            # Workspace children are named sandpile_state{addr}
            # and their children carry the exploration forward
            pass

    return mapping


# ---------------------------------------------------------------------------
# Hypergraph builder
# ---------------------------------------------------------------------------

def build_hypergraph(
    ox_root: Path,
    workspace_root: Path,
) -> Hypergraph:
    """Build the unified hypergraph from both trees.

    The five primitive instructions (SPEC §8) each contribute a
    set of hyperedges. They define structure, not execution:

      1. scope      — derives period, bounds the recursion axis
      2. singularity — identifies the seed as distinguished fixed point
      3. init       — materializes init edges along the spine
      4. goto       — traverses successor edges at checkpoint
      5. iff        — classifies children by global invariants
    """
    hg = Hypergraph()

    def _log(instr: Instruction, ctx: dict[str, Any], start: int) -> None:
        produced = tuple(range(start, len(hg.edges)))
        hg.instruction_log.append(InstructionRecord(
            instruction=instr, context=ctx, produced_edges=produced,
        ))

    # ── Instruction 1: SCOPE ──────────────────────────────────────────
    hg.scope = derive_scope(ox_root)
    _log(Instruction.SCOPE, {
        "period": hg.scope.period,
        "seed_chips": hg.scope.seed_chips,
        "root_label": hg.scope.root_label,
    }, len(hg.edges))

    # ── Instruction 2: SINGULARITY ────────────────────────────────────
    ox_index = parse_ox_tree(ox_root)
    spine = find_spine(ox_index)
    hg.nodes.update(ox_index.nodes)
    # The seed node itself is the singularity
    seed_keys = [k for k, n in ox_index.nodes.items()
                 if n.node_class == NodeClass.SEED]
    _log(Instruction.SINGULARITY, {
        "seed_keys": seed_keys,
        "singularity_path": hg.scope.singularity,
    }, len(hg.edges))

    # ── Instruction 3: INIT ───────────────────────────────────────────
    init_start = len(hg.edges)
    for i in range(len(spine) - 1):
        hg.edges.append(HyperedgeRecord(
            kind=EdgeKind.INIT,
            source_nodes=(spine[i],),
            target_nodes=(spine[i + 1],),
            rule="add_seed_stabilize",
            metadata={"step": i + 1, "period": hg.scope.period},
        ))
    _log(Instruction.INIT, {
        "spine_length": len(spine),
        "period": hg.scope.period,
    }, init_start)

    # ── Instruction 4: GOTO ───────────────────────────────────────────
    goto_start = len(hg.edges)
    hg.iff_results = classify_checkpoint_children(ox_index)
    checkpoint_keys = [k for k, n in ox_index.nodes.items()
                       if n.node_class == NodeClass.CHECKPOINT]
    for result in hg.iff_results:
        for ck in checkpoint_keys:
            child_keys = [k for k, n in ox_index.nodes.items()
                         if n.address == result.address
                         and n.directory.parent == ox_index.nodes[ck].directory]
            for child_key in child_keys:
                hg.edges.append(HyperedgeRecord(
                    kind=EdgeKind.GOTO,
                    source_nodes=(ck,),
                    target_nodes=(child_key,),
                    rule="vertex_probe",
                    metadata={
                        "vertex": result.address,
                        "iff_class": result.iff_class.value,
                    },
                ))
    _log(Instruction.GOTO, {
        "checkpoint_count": len(checkpoint_keys),
        "children": len(hg.iff_results),
    }, goto_start)

    # ── Instruction 5: IFF ────────────────────────────────────────────
    iff_start = len(hg.edges)
    for result in hg.iff_results:
        hg.edges.append(HyperedgeRecord(
            kind=EdgeKind.IFF,
            source_nodes=(result.address,),
            target_nodes=(result.successor,) if result.successor else (),
            rule="classify",
            metadata={
                "class": result.iff_class.value,
                "chips": result.chips,
                "dimensions": result.dimensions,
            },
        ))
    _log(Instruction.IFF, {
        "collapsed": sum(1 for r in hg.iff_results if r.iff_class == IffClass.COLLAPSED),
        "absorbed": sum(1 for r in hg.iff_results if r.iff_class == IffClass.ABSORBED),
        "explorable": sum(1 for r in hg.iff_results if r.iff_class == IffClass.EXPLORABLE),
    }, iff_start)

    # ── Cross-scope mapping (workspace extension) ─────────────────────
    ws_scopes = parse_workspace_scopes(workspace_root)
    cross_map = map_scopes(ox_index, ws_scopes, hg.iff_results)
    hg.cross_scope_map = {k: v[0] if v else "" for k, v in cross_map.items()}

    for ox_addr, ws_addrs in cross_map.items():
        for ws_addr in ws_addrs:
            ws_scope = next((s for s in ws_scopes if s.address == ws_addr), None)
            if ws_scope and ws_scope.child_count > 0:
                hg.edges.append(HyperedgeRecord(
                    kind=EdgeKind.CROSS_SCOPE,
                    source_nodes=(ox_addr,),
                    target_nodes=(f"ws:{ws_addr}",),
                    rule="workspace_rule",
                    metadata={
                        "ws_children": ws_scope.child_count,
                        "ws_chips": ws_scope.total_chips,
                        "ws_class": ws_scope.node_class.value,
                    },
                ))

    # ── Glyph decoding + boundary potential (SPEC §4, §5) ────────────
    for key, node in ox_index.nodes.items():
        if node.node_class not in (NodeClass.CHECKPOINT, NodeClass.SPINE):
            continue
        if node.width == 1 and node.height == 1:
            continue
        img = read_netpbm(node.path)

        glyphs = decode_surface_glyphs(key, img)
        for g in glyphs:
            glyph_id = f"g:{key}:{g.position[0]},{g.position[1]}"
            hg.glyph_nodes[glyph_id] = g
            hg.edges.append(HyperedgeRecord(
                kind=EdgeKind.GLYPH_DECODE,
                source_nodes=(key,),
                target_nodes=(glyph_id,),
                rule="nearest_anchor",
                metadata={
                    "pixel": g.pixel_value,
                    "index": g.glyph_index,
                    "symbol": g.glyph_symbol,
                    "band": g.band,
                },
            ))

        boundaries = extract_boundary_potential(key, img)
        hg.boundary_edges.extend(boundaries)
        if boundaries:
            hg.edges.append(HyperedgeRecord(
                kind=EdgeKind.BOUNDARY,
                source_nodes=(key,),
                target_nodes=(),
                rule="boundary_potential",
                metadata={
                    "nonzero_edges": len(boundaries),
                    "max_potential": max(abs(b.potential) for b in boundaries),
                },
            ))

        meta = parse_pgm_comments(img)
        if meta:
            node_meta_key = f"meta:{key}"
            hg.edges.append(HyperedgeRecord(
                kind=EdgeKind.FUNCTION_APP,
                source_nodes=(key,),
                target_nodes=(node_meta_key,),
                rule="comment_metadata",
                metadata=meta,
            ))

    return hg


# ---------------------------------------------------------------------------
# Summary / introspection
# ---------------------------------------------------------------------------

def summarize_hypergraph(hg: Hypergraph) -> dict[str, Any]:
    """Return a summary dict for inspection."""
    edge_counts: dict[str, int] = {}
    for e in hg.edges:
        edge_counts[e.kind.value] = edge_counts.get(e.kind.value, 0) + 1

    iff_counts: dict[str, int] = {}
    for r in hg.iff_results:
        iff_counts[r.iff_class.value] = iff_counts.get(r.iff_class.value, 0) + 1

    # Glyph band distribution
    band_counts = [0, 0, 0, 0]
    for g in hg.glyph_nodes.values():
        band_counts[g.band] += 1

    return {
        "scope": {
            "period": hg.scope.period if hg.scope else None,
            "seed_chips": hg.scope.seed_chips if hg.scope else None,
            "root_label": hg.scope.root_label if hg.scope else None,
            "singularity": hg.scope.singularity if hg.scope else None,
        },
        "nodes": {
            "state": len(hg.nodes),
            "glyph": len(hg.glyph_nodes),
            "total": len(hg.nodes) + len(hg.glyph_nodes),
        },
        "edges": edge_counts,
        "iff_classification": iff_counts,
        "cross_scope_mappings": len(hg.cross_scope_map),
        "glyph_bands": {
            "band_0": band_counts[0],
            "band_1": band_counts[1],
            "band_2": band_counts[2],
            "band_3": band_counts[3],
        },
        "boundary": {
            "edges": len(hg.boundary_edges),
            "max_potential": max((abs(b.potential) for b in hg.boundary_edges), default=0),
        },
        "instructions": {
            "scope": hg.scope.period if hg.scope else None,
            "singularity": hg.scope.singularity if hg.scope else None,
            "init": f"{len([e for e in hg.edges if e.kind == EdgeKind.INIT])} spine steps",
            "goto": f"{len([e for e in hg.edges if e.kind == EdgeKind.GOTO])} branch edges",
            "iff": f"{len(hg.iff_results)} classifications",
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import json

    project_root = Path(__file__).parent
    ox_root = project_root / "0x"
    workspace_root = project_root / "workspace"

    hg = build_hypergraph(ox_root, workspace_root)
    summary = summarize_hypergraph(hg)
    print(json.dumps(summary, indent=2, default=str))

    print(f"\n--- IFF Classification ---")
    for r in sorted(hg.iff_results, key=lambda r: r.address):
        succ_str = f" → {r.successor}" if r.successor else ""
        print(f"  {r.address}: {r.iff_class.value} ({r.dimensions[0]}x{r.dimensions[1]}, {r.chips} chips){succ_str}")

    print(f"\n--- Cross-Scope Mappings ---")
    for ox_addr, ws_addr in sorted(hg.cross_scope_map.items()):
        ws_scope = next((s for s in parse_workspace_scopes(workspace_root) if s.address == ws_addr), None)
        if ws_scope:
            print(f"  0x/{ox_addr} → ws:{ws_addr} ({ws_scope.child_count} children, {ws_scope.total_chips} chips, {ws_scope.node_class.value})")

    print(f"\n--- Hyperedges ---")
    for kind in EdgeKind:
        edges = [e for e in hg.edges if e.kind == kind]
        if edges:
            print(f"  {kind.value}: {len(edges)} edges")
            for e in edges[:5]:
                print(f"    {e.source_nodes} → {e.target_nodes} [{e.rule}]")
            if len(edges) > 5:
                print(f"    ... and {len(edges) - 5} more")


if __name__ == "__main__":
    main()
