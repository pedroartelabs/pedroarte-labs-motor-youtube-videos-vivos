"""Porta de armazenamento vetorial.

Nenhum banco vetorial externo é obrigatório: a implementação padrão é em
memória, e os testes unitários jamais dependem de um serviço rodando.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class VectorMatch(BaseModel):
    """Um resultado de busca vetorial."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    score: float
    metadata: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class VectorStorePort(Protocol):
    """Armazena e recupera vetores por similaridade."""

    @property
    def name(self) -> str: ...

    def upsert(
        self,
        *,
        chunk_id: str,
        vector: tuple[float, ...],
        metadata: dict[str, str],
    ) -> None: ...

    def search(
        self,
        *,
        vector: tuple[float, ...],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> tuple[VectorMatch, ...]: ...

    def count(self) -> int: ...

    def clear(self) -> None: ...
