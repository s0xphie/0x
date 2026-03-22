from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_MAGIC = {"P1", "P2"}


@dataclass
class NetpbmImage:
    magic: str
    width: int
    height: int
    pixels: list[list[int]]
    max_value: int = 1
    comments: list[str] | None = None  # optional comment lines

    def __post_init__(self) -> None:
        if self.magic not in SUPPORTED_MAGIC:
            raise ValueError(f"unsupported Netpbm magic: {self.magic}")
        if self.height != len(self.pixels):
            raise ValueError("height does not match pixel rows")
        if self.height and self.width != len(self.pixels[0]):
            raise ValueError("width does not match pixel columns")


def read_netpbm(path: str | Path) -> NetpbmImage:
    content = Path(path).read_text(encoding="utf-8")
    comments = []
    for line in content.splitlines():
        if line.strip().startswith("#"):
            comments.append(line.strip())
    
    tokens = _tokenize(content)
    if not tokens:
        raise ValueError("empty Netpbm file")

    magic = tokens.pop(0)
    if magic not in SUPPORTED_MAGIC:
        raise ValueError(f"unsupported Netpbm format: {magic}")

    width = int(tokens.pop(0))
    height = int(tokens.pop(0))
    max_value = 1 if magic == "P1" else int(tokens.pop(0))

    expected = width * height
    if len(tokens) != expected:
        raise ValueError(f"expected {expected} pixels, found {len(tokens)}")

    values = [int(token) for token in tokens]
    pixels = [
        values[row_start:row_start + width]
        for row_start in range(0, expected, width)
    ]
    return NetpbmImage(
        magic=magic,
        width=width,
        height=height,
        pixels=pixels,
        max_value=max_value,
        comments=comments if comments else None,
    )


def write_netpbm(image: NetpbmImage, path: str | Path) -> None:
    lines = []
    if image.comments:
        lines.extend(image.comments)
    lines.extend([image.magic, f"{image.width} {image.height}"])
    if image.magic == "P2":
        lines.append(str(image.max_value))
    lines.extend(" ".join(str(value) for value in row) for row in image.pixels)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tokenize(raw_text: str) -> list[str]:
    tokens: list[str] = []
    for line in raw_text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            tokens.extend(line.split())
    return tokens
