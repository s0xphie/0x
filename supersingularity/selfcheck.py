from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from .eisenstein import (
    EISENSTEIN_NEIGHBOR_OFFSETS,
    centered_configuration as centered_eisenstein_configuration,
    configuration_from_program_text as eisenstein_configuration_from_program_text,
    eisenstein_vertex,
    make_eisenstein_graph,
)
from .graph import SandpileModel
from .regular import centered_configuration, grid_vertex, make_grid_graph
from .simulation import ImageStateSurface, SimulationWorkspace
from .ternlsb import encode_ternlsb_program
from .dag import StegoSandpileCyclePipeline


@dataclass(frozen=True)
class SelfCheckReport:
    ok: bool
    checks: dict[str, bool]
    details: dict[str, object]


def run_selfcheck() -> SelfCheckReport:
    from .viewer import build_chain_frame

    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="supersingularity_selfcheck_") as root:
        workspace = SimulationWorkspace.create(Path(root) / "workspace")

        graph, layout = make_grid_graph(5, 5)
        model = SandpileModel(graph=graph, sink=grid_vertex(0, 0))
        configuration = centered_configuration(model, grain=0)

        carrier_path = workspace.initialize_surface(
            "carrier",
            width=5,
            height=5,
            fill=0,
            magic="P2",
            max_value=9,
        )
        carrier = ImageStateSurface.from_path(carrier_path)
        carrier = encode_ternlsb_program(carrier, "AASN")
        workspace.snapshot("carrier", carrier)

        stego_context = {
            "workspace": workspace,
            "carrier_surface": carrier,
            "configuration": configuration,
            "grid_rows": 5,
            "grid_cols": 5,
            "layout": layout,
            "vertex_layout": layout,
        }
        stego_result = StegoSandpileCyclePipeline().run(stego_context)
        description = stego_result["ternlsb_program_description"]
        archived_state = stego_result["archived_state"]
        frame = build_chain_frame(archived_state.image_path)

        checks["ternlsb_program_description"] = (
            description.program_type == "ternlsb"
            and description.instruction_text == "AASN"
            and len(description.trace) == 4
        )
        checks["stego_event_index"] = [record.event_type for record in stego_result["stego_update_event_index"].records] == [
            "ternlsb_decode",
            "ternlsb_apply",
            "ternlsb_project",
            "ternlsb_encode",
        ]
        checks["viewer_frame_render"] = "ws:" in frame and archived_state.state_id in frame

        eisenstein_graph, _ = make_eisenstein_graph(5)
        eisenstein_model = SandpileModel(graph=eisenstein_graph, sink=eisenstein_vertex(0, 0))
        eisenstein_center = centered_eisenstein_configuration(eisenstein_model, grain=3)
        eisenstein_program = eisenstein_configuration_from_program_text(
            eisenstein_model,
            "123456 654321",
        )
        checks["eisenstein_geometry"] = (
            eisenstein_graph.metadata.get("graph_family") == "eisenstein"
            and len(EISENSTEIN_NEIGHBOR_OFFSETS) == 6
            and eisenstein_center.chips[eisenstein_vertex(2, 2)] == 3
            and sum(eisenstein_program.chips.values()) == 42
        )

        details["program_trace"] = list(description.trace)
        details["viewer_footer"] = frame.splitlines()[-1] if frame.splitlines() else ""
        details["viewer_frame_lines"] = len(frame.splitlines())
        details["eisenstein_total_grains"] = sum(eisenstein_program.chips.values())

    return SelfCheckReport(
        ok=all(checks.values()),
        checks=checks,
        details=details,
    )
