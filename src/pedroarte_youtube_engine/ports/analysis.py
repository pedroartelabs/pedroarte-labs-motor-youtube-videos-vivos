"""Porta de análise narrativa.

Esta é a porta que torna o motor executável sem credenciais. O
`CANON_EXTRACTOR_AGENT` não fala com um LLM: ele fala com um
`NarrativeAnalyzerPort`. O adaptador padrão é heurístico e determinístico —
lê o português, separa capítulos, detecta personagens por atribuição de fala e
frequência, encontra locais por preposição e extrai diálogos por travessão e
aspas. Um adaptador baseado em LLM pode substituí-lo sem tocar no agente.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class DetectedCharacter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    mentions: int = Field(ge=0)
    dialogue_lines: int = Field(default=0, ge=0)
    first_chapter_index: int = Field(default=0, ge=0)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    descriptive_sentences: tuple[str, ...] = Field(default_factory=tuple)
    co_occurring: tuple[str, ...] = Field(default_factory=tuple)


class DetectedLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    mentions: int = Field(ge=0)
    interior: bool = True
    descriptive_sentences: tuple[str, ...] = Field(default_factory=tuple)


class DetectedProp(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    mentions: int = Field(ge=0)
    descriptive_sentences: tuple[str, ...] = Field(default_factory=tuple)


class DetectedDialogue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    speaker: str = ""
    text: str
    chapter_index: int = Field(default=0, ge=0)
    offset: int = Field(default=0, ge=0)


class DetectedBeat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int = Field(ge=0)
    chapter_index: int = Field(default=0, ge=0)
    summary: str
    participants: tuple[str, ...] = Field(default_factory=tuple)
    location: str = ""
    tension: int = Field(default=0, ge=0, le=10)
    tone: str = "neutro"
    dialogue_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    information_revealed: tuple[str, ...] = Field(default_factory=tuple)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)
    weight: float = Field(default=1.0, gt=0.0, le=10.0)


class NarrativeAnalysis(BaseModel):
    """Resultado completo da leitura estruturada de uma obra."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = ""
    author: str = ""
    logline: str = ""
    thesis: str = ""
    characters: tuple[DetectedCharacter, ...] = Field(default_factory=tuple)
    locations: tuple[DetectedLocation, ...] = Field(default_factory=tuple)
    props: tuple[DetectedProp, ...] = Field(default_factory=tuple)
    dialogues: tuple[DetectedDialogue, ...] = Field(default_factory=tuple)
    beats: tuple[DetectedBeat, ...] = Field(default_factory=tuple)
    world_rules: tuple[str, ...] = Field(default_factory=tuple)
    mysteries: tuple[str, ...] = Field(default_factory=tuple)
    prohibitions: tuple[str, ...] = Field(default_factory=tuple)
    themes: tuple[str, ...] = Field(default_factory=tuple)
    uncertainties: tuple[str, ...] = Field(default_factory=tuple)
    analyzer_name: str = "unknown"


@runtime_checkable
class NarrativeAnalyzerPort(Protocol):
    """Extrai estrutura narrativa de um texto canônico."""

    @property
    def name(self) -> str: ...

    def analyze(
        self,
        *,
        text: str,
        chapters: tuple[tuple[int, str, str], ...],
        language: str,
    ) -> NarrativeAnalysis:
        """Analisa o texto.

        `chapters` é uma tupla de `(índice, título, texto)` já normalizada pela
        ingestão, para que o analisador não precise reimplementar a separação.
        """
        ...
