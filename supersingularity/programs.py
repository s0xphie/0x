from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .ternlsb import TernLSBExecutionRecord, TernLSBProgram


def _program_signature(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ProgramDescription:
    signature: str
    program_type: str
    trace: tuple[str, ...]
    instruction_text: str = ""
    initial_signature: str = ""
    final_signature: str = ""
    total_topples: int = 0
    mnemonic: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.trace)

    def to_dict(self) -> dict[str, object]:
        return {
            "signature": self.signature,
            "program_type": self.program_type,
            "trace": list(self.trace),
            "instruction_text": self.instruction_text,
            "initial_signature": self.initial_signature,
            "final_signature": self.final_signature,
            "total_topples": self.total_topples,
            "length": self.length,
            "mnemonic": self.mnemonic,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ProgramDescription":
        trace = tuple(str(item) for item in data.get("trace", []))
        metadata = dict(data.get("metadata", {}))
        signature = str(data.get("signature", "")) or _program_signature(
            {
                "program_type": str(data.get("program_type", "unknown")),
                "trace": list(trace),
                "instruction_text": str(data.get("instruction_text", "")),
                "initial_signature": str(data.get("initial_signature", "")),
                "final_signature": str(data.get("final_signature", "")),
            }
        )
        return cls(
            signature=signature,
            program_type=str(data.get("program_type", "unknown")),
            trace=trace,
            instruction_text=str(data.get("instruction_text", "")),
            initial_signature=str(data.get("initial_signature", "")),
            final_signature=str(data.get("final_signature", "")),
            total_topples=int(data.get("total_topples", 0)),
            mnemonic=str(data.get("mnemonic", "")),
            metadata=metadata,
        )

    def is_recursive(self, min_cycle_length: int = 2) -> bool:
        if len(self.trace) < min_cycle_length * 2:
            return False
        for cycle_len in range(min_cycle_length, len(self.trace) // 2 + 1):
            for offset in range(len(self.trace) - cycle_len * 2 + 1):
                if self.trace[offset : offset + cycle_len] == self.trace[offset + cycle_len : offset + cycle_len * 2]:
                    return True
        repeated_tokens = {token for token in self.trace if self.trace.count(token) > 1}
        return len(repeated_tokens) >= max(2, min_cycle_length)

    def similarity(self, other: "ProgramDescription", method: str = "jaccard") -> float:
        if method == "jaccard":
            set_a = set(self.trace)
            set_b = set(other.trace)
            if not set_a and not set_b:
                return 1.0
            union = len(set_a | set_b)
            return len(set_a & set_b) / union if union else 0.0
        if method == "lcs":
            max_len = max(len(self.trace), len(other.trace))
            if max_len == 0:
                return 1.0
            return _lcs_length(self.trace, other.trace) / max_len
        raise ValueError(f"unsupported similarity method: {method}")


def _lcs_length(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    rows = len(left) + 1
    cols = len(right) + 1
    dp = [[0] * cols for _ in range(rows)]
    for row in range(1, rows):
        for col in range(1, cols):
            if left[row - 1] == right[col - 1]:
                dp[row][col] = dp[row - 1][col - 1] + 1
            else:
                dp[row][col] = max(dp[row - 1][col], dp[row][col - 1])
    return dp[-1][-1]


@dataclass
class ProgramCatalog:
    filepath: Path
    programs: dict[str, ProgramDescription] = field(default_factory=dict)

    def __init__(self, filepath: str | Path = "program_catalog.json"):
        self.filepath = Path(filepath)
        self.programs = {}
        self.load()

    def add(self, program: ProgramDescription) -> bool:
        if program.signature in self.programs:
            return False
        self.programs[program.signature] = program
        return True

    def find_recursive(self) -> list[ProgramDescription]:
        return [program for program in self.programs.values() if program.is_recursive()]

    def find_similar(
        self,
        program: ProgramDescription,
        threshold: float = 0.7,
        method: str = "jaccard",
    ) -> list[ProgramDescription]:
        similar: list[ProgramDescription] = []
        for candidate in self.programs.values():
            if program.similarity(candidate, method=method) >= threshold:
                similar.append(candidate)
        return sorted(
            similar,
            key=lambda candidate: program.similarity(candidate, method=method),
            reverse=True,
        )

    def save(self) -> None:
        payload = {
            "count": len(self.programs),
            "programs": [program.to_dict() for program in self.programs.values()],
        }
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.filepath.parent),
            prefix=f"{self.filepath.name}.",
            suffix=".tmp",
            text=True,
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self.filepath)

    def load(self) -> None:
        if not self.filepath.exists():
            return
        with open(self.filepath, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload.get("programs", []):
            program = ProgramDescription.from_dict(item)
            self.programs[program.signature] = program


def describe_ternlsb_execution(
    program: TernLSBProgram,
    execution: TernLSBExecutionRecord,
) -> ProgramDescription:
    trace: list[str] = []
    for step in execution.steps:
        instruction = str(step.get("instruction", ""))
        if instruction == "A":
            trace.append(f"A@{step.get('vertex', execution.metadata.get('target_vertex', ''))}")
        elif instruction == "S":
            trace.append(f"S#{int(step.get('topples', 0))}")
        elif instruction == "N":
            trace.append("N")
        else:
            trace.append(instruction or "?")

    metadata = dict(execution.metadata)
    metadata["instruction_symbols"] = list(program.instructions)
    signature = _program_signature(
        {
            "program_type": "ternlsb",
            "trace": trace,
            "instruction_text": program.instructions,
            "initial_signature": execution.initial_signature,
            "final_signature": execution.final_signature,
        }
    )
    return ProgramDescription(
        signature=signature,
        program_type="ternlsb",
        trace=tuple(trace),
        instruction_text=program.instructions,
        initial_signature=execution.initial_signature,
        final_signature=execution.final_signature,
        total_topples=execution.total_topples,
        metadata=metadata,
    )
