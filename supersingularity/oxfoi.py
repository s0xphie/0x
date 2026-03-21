from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .dag import InitializationVectorRecord, ProductionPointerRecord


OXFOI_PRIME = 2**64 - 2**32 + 1
OXFOI_EXTENSION_DEGREE = 3
OXFOI_SHAH_POLYNOMIAL = "X^3 - X + 1"

OxfoiFieldDomain = Literal["B", "X"]
TritonInstructionKind = Literal["add", "push", "custom"]


def _oxfoi_digest(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class OxfoiExpressionRecord:
    expression_id: str
    payload: str
    field_domain: OxfoiFieldDomain
    instruction_width_words: int
    single_use: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class OxfoiStateRecord:
    state_id: str
    init_origin: str
    field_domain: OxfoiFieldDomain
    instruction_pointer_words: int
    consumed_expression_ids: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class OxfoiTransitionRecord:
    transition_id: str
    input_state_id: str
    output_state_id: str
    expression_id: str
    field_domain: OxfoiFieldDomain
    instruction_width_words: int
    displacement_kind: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class OxfoiEvaluationRecord:
    expression: OxfoiExpressionRecord
    input_state: OxfoiStateRecord
    output_state: OxfoiStateRecord
    transition: OxfoiTransitionRecord


@dataclass(frozen=True)
class TritonOxfoiStateRecord:
    state_id: str
    field_domain: OxfoiFieldDomain
    instruction_pointer_words: int
    operand_stack: tuple[int, ...]
    ram: dict[int, int]
    program_memory: tuple[str, ...]
    data_interface_mode: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TritonOxfoiInstructionRecord:
    instruction_id: str
    instruction_kind: TritonInstructionKind
    instruction_width_words: int
    argument: int | None
    field_domain: OxfoiFieldDomain
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TritonOxfoiExecutionRecord:
    instruction: TritonOxfoiInstructionRecord
    input_state: TritonOxfoiStateRecord
    output_state: TritonOxfoiStateRecord
    metadata: dict[str, Any]


def build_oxfoi_expression(
    payload: str,
    *,
    field_domain: OxfoiFieldDomain = "B",
    instruction_width_words: int = 1,
    single_use: bool = True,
    metadata: dict[str, Any] | None = None,
) -> OxfoiExpressionRecord:
    width = max(1, int(instruction_width_words))
    expression_id = f"oxexpr_{_oxfoi_digest(payload, field_domain, width, single_use)}"
    return OxfoiExpressionRecord(
        expression_id=expression_id,
        payload=payload,
        field_domain=field_domain,
        instruction_width_words=width,
        single_use=bool(single_use),
        metadata=dict(metadata or {}),
    )


def build_oxfoi_state(
    initialization: "InitializationVectorRecord",
    *,
    field_domain: OxfoiFieldDomain = "B",
    instruction_pointer_words: int = 0,
    consumed_expression_ids: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> OxfoiStateRecord:
    init_origin = initialization.prefix
    state_id = f"oxstate_{_oxfoi_digest(init_origin, field_domain, instruction_pointer_words, consumed_expression_ids)}"
    return OxfoiStateRecord(
        state_id=state_id,
        init_origin=init_origin,
        field_domain=field_domain,
        instruction_pointer_words=max(0, int(instruction_pointer_words)),
        consumed_expression_ids=tuple(consumed_expression_ids),
        metadata={
            "seed_path": initialization.seed_path,
            "global_recursive_limit": initialization.global_recursive_limit,
            "materialized_recursive_steps": initialization.materialized_recursive_steps,
            "checkpoint_interval_steps": initialization.checkpoint_interval_steps,
            **dict(metadata or {}),
        },
    )


def evaluate_oxfoi_expression(
    initialization: "InitializationVectorRecord",
    expression: OxfoiExpressionRecord,
    *,
    pointer: "ProductionPointerRecord" | None = None,
    input_state: OxfoiStateRecord | None = None,
) -> OxfoiEvaluationRecord:
    current_state = input_state or build_oxfoi_state(
        initialization,
        field_domain=expression.field_domain,
    )
    next_ip = current_state.instruction_pointer_words + expression.instruction_width_words
    consumed_expression_ids = current_state.consumed_expression_ids + (expression.expression_id,)
    output_state = build_oxfoi_state(
        initialization,
        field_domain=expression.field_domain,
        instruction_pointer_words=next_ip,
        consumed_expression_ids=consumed_expression_ids,
        metadata={
            "source_state_id": current_state.state_id,
            "single_use_expression": expression.single_use,
            "pointer_id": pointer.pointer_id if pointer is not None else None,
        },
    )
    displacement_kind = "sideways_identity_shift" if expression.field_domain == "B" else "extension_field_lift"
    transition = OxfoiTransitionRecord(
        transition_id=f"oxtr_{_oxfoi_digest(current_state.state_id, output_state.state_id, expression.expression_id)}",
        input_state_id=current_state.state_id,
        output_state_id=output_state.state_id,
        expression_id=expression.expression_id,
        field_domain=expression.field_domain,
        instruction_width_words=expression.instruction_width_words,
        displacement_kind=displacement_kind,
        metadata={
            "payload": expression.payload,
            "single_use": expression.single_use,
            "pointer_preferred_output": pointer.preferred_output if pointer is not None else None,
            "pointer_target_domain": pointer.target_domain if pointer is not None else None,
            "oxfoi_prime": OXFOI_PRIME,
            "extension_degree": OXFOI_EXTENSION_DEGREE,
            "shah_polynomial": OXFOI_SHAH_POLYNOMIAL,
        },
    )
    return OxfoiEvaluationRecord(
        expression=expression,
        input_state=current_state,
        output_state=output_state,
        transition=transition,
    )


def build_triton_instruction(
    instruction_kind: TritonInstructionKind,
    *,
    argument: int | None = None,
    field_domain: OxfoiFieldDomain = "B",
    metadata: dict[str, Any] | None = None,
) -> TritonOxfoiInstructionRecord:
    width = 2 if instruction_kind == "push" else 1
    instruction_id = f"triton_instr_{_oxfoi_digest(instruction_kind, argument, field_domain, width)}"
    return TritonOxfoiInstructionRecord(
        instruction_id=instruction_id,
        instruction_kind=instruction_kind,
        instruction_width_words=width,
        argument=argument,
        field_domain=field_domain,
        metadata=dict(metadata or {}),
    )


def build_triton_state(
    initialization: "InitializationVectorRecord",
    *,
    field_domain: OxfoiFieldDomain = "B",
    instruction_pointer_words: int = 0,
    operand_stack: tuple[int, ...] = (),
    ram: dict[int, int] | None = None,
    program_memory: tuple[str, ...] = (),
    data_interface_mode: str = "public",
    metadata: dict[str, Any] | None = None,
) -> TritonOxfoiStateRecord:
    ram_map = dict(ram or {})
    state_id = f"triton_oxstate_{_oxfoi_digest(initialization.prefix, field_domain, instruction_pointer_words, operand_stack, tuple(sorted(ram_map.items())))}"
    return TritonOxfoiStateRecord(
        state_id=state_id,
        field_domain=field_domain,
        instruction_pointer_words=max(0, int(instruction_pointer_words)),
        operand_stack=tuple(int(value) % OXFOI_PRIME for value in operand_stack),
        ram={int(address): int(value) % OXFOI_PRIME for address, value in ram_map.items()},
        program_memory=tuple(program_memory),
        data_interface_mode=data_interface_mode,
        metadata={
            "init_origin": initialization.prefix,
            "seed_path": initialization.seed_path,
            "global_recursive_limit": initialization.global_recursive_limit,
            "harvard_architecture": True,
            "stack_machine": True,
            **dict(metadata or {}),
        },
    )


def execute_triton_instruction(
    initialization: "InitializationVectorRecord",
    instruction: TritonOxfoiInstructionRecord,
    *,
    input_state: TritonOxfoiStateRecord | None = None,
) -> TritonOxfoiExecutionRecord:
    current_state = input_state or build_triton_state(
        initialization,
        field_domain=instruction.field_domain,
    )
    stack = list(current_state.operand_stack)
    ram = dict(current_state.ram)
    if instruction.instruction_kind == "push":
        stack.append(int(instruction.argument or 0) % OXFOI_PRIME)
    elif instruction.instruction_kind == "add":
        right = stack.pop() if stack else 0
        left = stack.pop() if stack else 0
        stack.append((left + right) % OXFOI_PRIME)
    elif instruction.instruction_kind == "custom":
        if instruction.argument is not None:
            ram[current_state.instruction_pointer_words] = int(instruction.argument) % OXFOI_PRIME

    output_state = build_triton_state(
        initialization,
        field_domain=instruction.field_domain,
        instruction_pointer_words=current_state.instruction_pointer_words + instruction.instruction_width_words,
        operand_stack=tuple(stack),
        ram=ram,
        program_memory=current_state.program_memory + (instruction.instruction_kind,),
        data_interface_mode=current_state.data_interface_mode,
        metadata={
            "source_state_id": current_state.state_id,
            "instruction_id": instruction.instruction_id,
        },
    )
    return TritonOxfoiExecutionRecord(
        instruction=instruction,
        input_state=current_state,
        output_state=output_state,
        metadata={
            "harvard_architecture": True,
            "stack_machine": True,
            "instruction_width_words": instruction.instruction_width_words,
            "field_domain": instruction.field_domain,
        },
    )
