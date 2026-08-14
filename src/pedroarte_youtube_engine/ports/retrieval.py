"""Portas de recuperação lexical e de reranking."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class RetrievedChunk(BaseModel):
    """Trecho recuperado, com pontuação e proveniência."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    text: str
    score: float
    source_id: str = ""
    source_path: str = ""
    chapter: str = ""
    scene: str = ""
    characters: tuple[str, ...] = Field(default_factory=tuple)
    locations: tuple[str, ...] = Field(default_factory=tuple)
    content_type: str = ""
    start_offset: int = 0
    end_offset: int = 0
    lexical_score: float = 0.0
    vector_score: float = 0.0


@runtime_checkable
class LexicalIndexPort(Protocol):
    """Índice invertido para busca por termos."""

    def index(self, *, chunk_id: str, text: str, metadata: dict[str, str]) -> None: ...

    def search(
        self, *, query: str, top_k: int, filters: dict[str, str] | None = None
    ) -> tuple[RetrievedChunk, ...]: ...

    def count(self) -> int: ...

    def clear(self) -> None: ...


@runtime_checkable
class RerankerPort(Protocol):
    """Reordena candidatos combinando sinais lexicais, vetoriais e de metadados."""

    def rerank(
        self, *, query: str, candidates: tuple[RetrievedChunk, ...], top_k: int
    ) -> tuple[RetrievedChunk, ...]: ...
