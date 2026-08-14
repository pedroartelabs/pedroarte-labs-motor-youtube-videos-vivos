"""Vector store em memória.

Busca exaustiva por cosseno. Para o volume de um livro — alguns milhares de
chunks — a busca linear é rápida o bastante e evita a dependência de um serviço
externo, que a especificação proíbe tornar obrigatório.
"""

from __future__ import annotations

from dataclasses import dataclass

from pedroarte_youtube_engine.ports.vector_store import VectorMatch
from pedroarte_youtube_engine.rag.embedding import cosine_similarity


@dataclass(slots=True)
class _Entry:
    chunk_id: str
    vector: tuple[float, ...]
    metadata: dict[str, str]


class InMemoryVectorStore:
    """Implementação de referência do `VectorStorePort`."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    @property
    def name(self) -> str:
        return "in_memory_cosine_v1"

    def upsert(
        self, *, chunk_id: str, vector: tuple[float, ...], metadata: dict[str, str]
    ) -> None:
        self._entries[chunk_id] = _Entry(
            chunk_id=chunk_id, vector=vector, metadata=dict(metadata)
        )

    def search(
        self,
        *,
        vector: tuple[float, ...],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> tuple[VectorMatch, ...]:
        if not self._entries or top_k <= 0:
            return ()

        scored: list[tuple[float, _Entry]] = []
        for entry in self._entries.values():
            if not _matches(entry.metadata, filters):
                continue
            if len(entry.vector) != len(vector):
                continue
            scored.append((cosine_similarity(vector, entry.vector), entry))

        # Desempate pelo chunk_id garante ordenação estável entre execuções.
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return tuple(
            VectorMatch(
                chunk_id=entry.chunk_id,
                score=round(score, 6),
                metadata=entry.metadata,
            )
            for score, entry in scored[:top_k]
            if score > 0
        )

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()


def _matches(metadata: dict[str, str], filters: dict[str, str] | None) -> bool:
    if not filters:
        return True
    for key, wanted in filters.items():
        value = metadata.get(key, "")
        if "|" in value:
            if wanted not in value.split("|"):
                return False
        elif value != wanted:
            return False
    return True
