from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrimitiveInputRecord:
    raw_text: str
    canonical_name: str
    arity: int
    metadata: dict[str, object]


def parse_primitive_input(text: str) -> PrimitiveInputRecord:
    raw = text.strip()
    lowered = raw.lower()
    if lowered in {"", "s", "succ", "successor"}:
        return PrimitiveInputRecord(
            raw_text=text,
            canonical_name="successor",
            arity=1,
            metadata={
                "projection_family": "primitive_recursion_base",
                "accepts_blank_enter": True,
            },
        )
    raise ValueError(f"unsupported primitive input: {text!r}")
