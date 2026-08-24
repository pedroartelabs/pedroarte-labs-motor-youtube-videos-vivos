"""ImageGenerationPort — a engine pede uma imagem com características, nunca
"chame o provider X" (docs/youtube-lite/SDD_SPDD.md §13/§27, discovery Lite
§13-16).

`ImageGenerationRequest` é o contrato estável; a estratégia (nativa do
ambiente, API externa autorizada, ou local) é decidida fora do domínio, pelo
operador ativo (ver `select_strategy` em `lite/images/__init__.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    output_path: Path
    width: int = 1920
    height: int = 1080
    negative_constraints: str = ""
    style_prefix: str = ""


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    output_path: Path
    method: str
    provider: str | None = None
    model: str | None = None
    prompt: str = ""
    extra: dict[str, str] = field(default_factory=dict)


class ImageGenerationPort(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
