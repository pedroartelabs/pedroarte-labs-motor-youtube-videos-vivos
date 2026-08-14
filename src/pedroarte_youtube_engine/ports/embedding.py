"""Porta de embeddings.

O adaptador padrão é local e determinístico (hashing + n-gramas). Nenhum
download de modelo é necessário para rodar os testes ou o exemplo.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProviderPort(Protocol):
    """Converte texto em vetores densos."""

    @property
    def name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> tuple[float, ...]:
        """Vetoriza um único texto."""
        ...

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Vetoriza vários textos preservando a ordem."""
        ...
