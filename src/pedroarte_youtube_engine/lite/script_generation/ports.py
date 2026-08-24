"""ScriptGenerationPort — LLM CREATES, CODE VALIDATES, HUMAN JUDGES
(SDD_SPDD.md §38.3).

O código nunca tenta escrever criatividade. Este port só existe porque há uma
estratégia real por trás dela (`OperatorAuthoredScriptStrategy`) — não é uma
abstração especulativa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pedroarte_youtube_engine.lite.video_spec import VideoSpecification


@dataclass(frozen=True, slots=True)
class ScriptGenerationRequest:
    specification: VideoSpecification
    reference_text: str = ""


@dataclass(frozen=True, slots=True)
class ScriptGenerationResult:
    script_text: str
    method: str
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    extra: dict[str, str] = field(default_factory=dict)


class ScriptGenerationPort(Protocol):
    def generate(self, request: ScriptGenerationRequest) -> ScriptGenerationResult: ...
