from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class CompiledWorkspaceIndex:
    workspace_root: str
    raw_state_images: int
    reference_backed_images: int
    canonical_images: int
    state_tree_images: int
    max_lineage_depth: int
    branching_directories: int
    leaf_directories: int
    unique_signatures: int


@dataclass(frozen=True)
class CompiledCarrierCapacity:
    image_path: str
    width: int
    height: int
    max_value: int
    cell_size: int
    alphabet: str
    total_values: int
    logical_cells: int
    instruction_capacity: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _compiled_binary() -> Path | None:
    repo_root = _repo_root()
    for candidate in (
        repo_root / "target" / "release" / "supersingularity_compile",
        repo_root / "target" / "debug" / "supersingularity_compile",
    ):
        if candidate.exists():
            return candidate
    return None


def _run_compiled_helper(*args: str) -> dict[str, object]:
    binary = _compiled_binary()
    if binary is not None:
        command = [str(binary), *args]
    else:
        command = [
            "cargo",
            "run",
            "--quiet",
            "--bin",
            "supersingularity_compile",
            "--",
            *args,
        ]
    completed = subprocess.run(
        command,
        cwd=_repo_root(),
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def build_compiled_workspace_index(workspace_root: str | Path) -> CompiledWorkspaceIndex:
    payload = _run_compiled_helper("workspace-index", str(workspace_root))
    return CompiledWorkspaceIndex(
        workspace_root=str(payload["workspace_root"]),
        raw_state_images=int(payload["raw_state_images"]),
        reference_backed_images=int(payload["reference_backed_images"]),
        canonical_images=int(payload["canonical_images"]),
        state_tree_images=int(payload["state_tree_images"]),
        max_lineage_depth=int(payload["max_lineage_depth"]),
        branching_directories=int(payload["branching_directories"]),
        leaf_directories=int(payload["leaf_directories"]),
        unique_signatures=int(payload["unique_signatures"]),
    )


def inspect_compiled_ternlsb_capacity(
    image_path: str | Path,
    cell_size: int = 1,
    alphabet: str = "ASN",
) -> CompiledCarrierCapacity:
    payload = _run_compiled_helper(
        "ternlsb-capacity",
        str(image_path),
        str(cell_size),
        alphabet,
    )
    return CompiledCarrierCapacity(
        image_path=str(payload["image_path"]),
        width=int(payload["width"]),
        height=int(payload["height"]),
        max_value=int(payload["max_value"]),
        cell_size=int(payload["cell_size"]),
        alphabet=str(payload["alphabet"]),
        total_values=int(payload["total_values"]),
        logical_cells=int(payload["logical_cells"]),
        instruction_capacity=int(payload["instruction_capacity"]),
    )
