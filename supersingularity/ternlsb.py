from __future__ import annotations

from dataclasses import dataclass

from .graph import add_chip, configuration_signature, SandpileConfiguration, stabilize_configuration
from .simulation import clone_surface, ImageStateSurface


DEFAULT_TERNLSB_ALPHABET = "ASN"


@dataclass(frozen=True)
class TernLSBProgram:
    instructions: str
    alphabet: str = DEFAULT_TERNLSB_ALPHABET
    cell_size: int = 1
    capacity: int = 0


@dataclass(frozen=True)
class TernLSBExecutionRecord:
    instructions: str
    initial_signature: str
    final_signature: str
    total_topples: int
    steps: list[dict[str, int | str]]
    metadata: dict[str, int | str]


def _logical_positions(total_values: int, cell_size: int) -> list[int]:
    if cell_size < 1:
        raise ValueError("cell_size must be positive")
    return list(range(0, total_values, cell_size))


def ternlsb_capacity(
    surface: ImageStateSurface,
    alphabet: str = DEFAULT_TERNLSB_ALPHABET,
    cell_size: int = 1,
) -> int:
    logical_positions = _logical_positions(len(surface.flatten_pixels()), cell_size)
    return max(0, len(logical_positions) - 1)


def decode_ternlsb_program(
    surface: ImageStateSurface,
    alphabet: str = DEFAULT_TERNLSB_ALPHABET,
    cell_size: int = 1,
) -> TernLSBProgram:
    flat = surface.flatten_pixels()
    logical_positions = _logical_positions(len(flat), cell_size)
    base = len(alphabet) + 1
    instructions: list[str] = []
    for index in logical_positions:
        residue = flat[index] % base
        if residue == len(alphabet):
            break
        instructions.append(alphabet[residue])
    return TernLSBProgram(
        instructions="".join(instructions),
        alphabet=alphabet,
        cell_size=cell_size,
        capacity=max(0, len(logical_positions) - 1),
    )


def encode_ternlsb_program(
    surface: ImageStateSurface,
    instructions: str,
    alphabet: str = DEFAULT_TERNLSB_ALPHABET,
    cell_size: int = 1,
) -> ImageStateSurface:
    normalized = "".join(symbol for symbol in instructions if symbol in alphabet)
    encoded = clone_surface(surface)
    flat = encoded.flatten_pixels()
    logical_positions = _logical_positions(len(flat), cell_size)
    capacity = max(0, len(logical_positions) - 1)
    if len(normalized) > capacity:
        raise ValueError(
            f"instruction string length {len(normalized)} exceeds carrier capacity {capacity}"
        )

    base = len(alphabet) + 1
    for instruction_index, symbol in enumerate(normalized):
        flat_index = logical_positions[instruction_index]
        symbol_index = alphabet.index(symbol)
        flat[flat_index] = flat[flat_index] - (flat[flat_index] % base) + symbol_index

    terminator_index = logical_positions[len(normalized)]
    flat[terminator_index] = flat[terminator_index] - (flat[terminator_index] % base) + len(alphabet)

    width = encoded.image.width
    for row_index in range(encoded.image.height):
        start = row_index * width
        encoded.image.pixels[row_index] = flat[start : start + width]
    encoded.image.max_value = max(max(flat, default=0), base - 1, 1)
    return encoded


def _default_target_vertex(configuration: SandpileConfiguration) -> str:
    graph_metadata = configuration.model.graph.metadata
    center_vertex = graph_metadata.get("center_vertex")
    if center_vertex is not None and center_vertex in configuration.model.active_vertices:
        return center_vertex
    active_vertices = configuration.model.active_vertices
    if not active_vertices:
        raise ValueError("cannot target an empty active vertex set")
    return active_vertices[0]


def apply_ternlsb_program(
    configuration: SandpileConfiguration,
    program: TernLSBProgram,
    target_vertex: str | None = None,
) -> tuple[SandpileConfiguration, TernLSBExecutionRecord]:
    current = configuration
    chosen_vertex = target_vertex or _default_target_vertex(configuration)
    steps: list[dict[str, int | str]] = []
    total_topples = 0
    for index, symbol in enumerate(program.instructions):
        if symbol == "A":
            current = add_chip(current, chosen_vertex, amount=1)
            steps.append({"index": index, "instruction": symbol, "vertex": chosen_vertex})
            continue
        if symbol == "S":
            result = stabilize_configuration(current)
            current = result.stabilized
            total_topples += result.total_topples
            steps.append(
                {
                    "index": index,
                    "instruction": symbol,
                    "topples": result.total_topples,
                }
            )
            continue
        if symbol == "N":
            steps.append({"index": index, "instruction": symbol})
            continue
        raise ValueError(f"unsupported ternLSB instruction: {symbol}")

    record = TernLSBExecutionRecord(
        instructions=program.instructions,
        initial_signature=configuration_signature(configuration),
        final_signature=configuration_signature(current),
        total_topples=total_topples,
        steps=steps,
        metadata={
            "alphabet": program.alphabet,
            "cell_size": program.cell_size,
            "capacity": program.capacity,
            "target_vertex": chosen_vertex,
        },
    )
    return current, record
