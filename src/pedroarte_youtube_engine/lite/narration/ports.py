"""NarrationPort — a engine pede "sintetize este texto", nunca "chame o SAPI".

Existe como Protocol porque há variação operacional real (docs/youtube-lite/
SDD_SPDD.md §16, §29): Gate 2 usa SAPI5 (custo zero, prova o cano); Gate 3+
exigirá uma estratégia de qualidade de publicação (candidato: `edge-tts`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NarrationRequest:
    text: str
    output_path: Path
    language: str = "pt-BR"
    voice: str | None = None


@dataclass(frozen=True, slots=True)
class NarrationResult:
    output_path: Path
    duration_seconds: float
    method: str
    voice: str | None = None
    generation_time_seconds: float = 0.0
    timing_data_available: bool = False


class NarrationPort(Protocol):
    def synthesize(self, request: NarrationRequest) -> NarrationResult: ...
