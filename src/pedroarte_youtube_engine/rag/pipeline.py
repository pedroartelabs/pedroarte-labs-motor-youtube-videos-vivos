"""Pipeline RAG completo (seção 19.1).

    Source Discovery → Parsing → Structural Chunking → Semantic Enrichment
    → Metadata Assignment → Embedding → Lexical Index → Vector Index
    → Hybrid Retrieval → Reranking → Context Assembly → Citation & Provenance

O passo final é o que justifica o resto: toda recuperação devolve a citação
junto com o texto, e é essa citação que viaja até o prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pedroarte_youtube_engine.domain.value_objects import (
    ChunkId,
    ConfidenceScore,
    SourceId,
    SourceReference,
)
from pedroarte_youtube_engine.ports.embedding import EmbeddingProviderPort
from pedroarte_youtube_engine.ports.retrieval import RerankerPort, RetrievedChunk
from pedroarte_youtube_engine.ports.vector_store import VectorStorePort
from pedroarte_youtube_engine.rag.chunking import NarrativeChunk
from pedroarte_youtube_engine.rag.embedding import HashingEmbeddingProvider
from pedroarte_youtube_engine.rag.lexical import Bm25LexicalIndex, _to_chunk
from pedroarte_youtube_engine.rag.reranker import HeuristicReranker
from pedroarte_youtube_engine.rag.vector_store import InMemoryVectorStore
from pedroarte_youtube_engine.shared.text import excerpt


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Contexto montado, pronto para virar proveniência."""

    query: str
    chunks: tuple[RetrievedChunk, ...]
    mode: str

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    def context_text(self, *, max_chars: int = 6000) -> str:
        """Contexto concatenado, com o cabeçalho de origem de cada trecho."""
        parts: list[str] = []
        budget = max_chars
        for chunk in self.chunks:
            header = f"[{chunk.chunk_id} · {chunk.chapter or chunk.source_path}]"
            body = chunk.text[: max(0, budget - len(header) - 2)]
            if not body:
                break
            parts.append(f"{header}\n{body}")
            budget -= len(header) + len(body) + 2
            if budget <= 0:
                break
        return "\n\n".join(parts)

    def references(self, *, confidence: float | None = None) -> tuple[SourceReference, ...]:
        """Converte os trechos recuperados em referências de proveniência."""
        references: list[SourceReference] = []
        for chunk in self.chunks:
            score = confidence if confidence is not None else min(1.0, max(0.0, chunk.score))
            references.append(
                SourceReference(
                    source_id=SourceId(value=chunk.source_id or "fonte-desconhecida"),
                    source_path=chunk.source_path or chunk.chunk_id,
                    chapter=chunk.chapter or None,
                    chunk_id=ChunkId(value=_safe_chunk_id(chunk.chunk_id)),
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    excerpt=excerpt(chunk.text, max_chars=220),
                    confidence=ConfidenceScore(value=round(score, 4)),
                )
            )
        return tuple(references)


@dataclass(slots=True)
class NarrativeRagPipeline:
    """Orquestra chunking, indexação e recuperação híbrida."""

    embedding_provider: EmbeddingProviderPort = field(
        default_factory=lambda: HashingEmbeddingProvider(dimensions=256)
    )
    vector_store: VectorStorePort = field(default_factory=InMemoryVectorStore)
    lexical_index: Bm25LexicalIndex = field(default_factory=Bm25LexicalIndex)
    reranker: RerankerPort = field(default_factory=HeuristicReranker)
    lexical_weight: float = 0.5
    mode: str = "hybrid"
    _chunks: dict[str, NarrativeChunk] = field(default_factory=dict, init=False)

    # -- indexação ---------------------------------------------------------

    def index(self, chunks: tuple[NarrativeChunk, ...]) -> int:
        """Indexa os chunks nos dois índices. Devolve quantos foram indexados."""
        for chunk in chunks:
            metadata = chunk.metadata()
            self._chunks[chunk.chunk_id] = chunk
            self.lexical_index.index(
                chunk_id=chunk.chunk_id, text=chunk.text, metadata=metadata
            )
            self.vector_store.upsert(
                chunk_id=chunk.chunk_id,
                vector=self.embedding_provider.embed(chunk.text),
                metadata=metadata,
            )
        return len(chunks)

    def clear(self) -> None:
        self._chunks.clear()
        self.lexical_index.clear()
        self.vector_store.clear()

    @property
    def indexed_count(self) -> int:
        return len(self._chunks)

    # -- recuperação -------------------------------------------------------

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 8,
        filters: dict[str, str] | None = None,
        rerank: bool = True,
    ) -> RetrievalResult:
        """Recuperação híbrida com fusão ponderada e reranking."""
        if not query.strip() or not self._chunks:
            return RetrievalResult(query=query, chunks=(), mode=self.mode)

        pool = max(top_k * 3, top_k + 5)
        lexical = (
            self.lexical_index.search(query=query, top_k=pool, filters=filters)
            if self.mode in {"hybrid", "lexical"}
            else ()
        )
        vector = self._vector_search(query, top_k=pool, filters=filters)

        fused = self._fuse(lexical, vector)
        if rerank and fused:
            fused = self.reranker.rerank(query=query, candidates=fused, top_k=top_k)
        else:
            fused = fused[:top_k]

        return RetrievalResult(query=query, chunks=fused, mode=self.mode)

    def _vector_search(
        self, query: str, *, top_k: int, filters: dict[str, str] | None
    ) -> tuple[RetrievedChunk, ...]:
        if self.mode not in {"hybrid", "vector"}:
            return ()
        matches = self.vector_store.search(
            vector=self.embedding_provider.embed(query), top_k=top_k, filters=filters
        )
        results: list[RetrievedChunk] = []
        for match in matches:
            chunk = self._chunks.get(match.chunk_id)
            if chunk is None:
                continue
            results.append(
                _to_chunk(
                    _AsDocument(chunk),  # type: ignore[arg-type]
                    score=match.score,
                    vector_score=match.score,
                )
            )
        return tuple(results)

    def _fuse(
        self,
        lexical: tuple[RetrievedChunk, ...],
        vector: tuple[RetrievedChunk, ...],
    ) -> tuple[RetrievedChunk, ...]:
        """Combina os dois rankings por soma ponderada dos scores normalizados."""
        if not lexical:
            return vector
        if not vector:
            return lexical

        merged: dict[str, RetrievedChunk] = {}
        lexical_scores = {chunk.chunk_id: chunk.score for chunk in lexical}
        vector_scores = {chunk.chunk_id: chunk.score for chunk in vector}

        for chunk in (*lexical, *vector):
            merged.setdefault(chunk.chunk_id, chunk)

        weight = self.lexical_weight
        fused = [
            chunk.model_copy(
                update={
                    "score": round(
                        weight * lexical_scores.get(chunk.chunk_id, 0.0)
                        + (1 - weight) * vector_scores.get(chunk.chunk_id, 0.0),
                        6,
                    ),
                    "lexical_score": round(lexical_scores.get(chunk.chunk_id, 0.0), 6),
                    "vector_score": round(vector_scores.get(chunk.chunk_id, 0.0), 6),
                }
            )
            for chunk in merged.values()
        ]
        fused.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        return tuple(fused)

    # -- consultas de conveniência ----------------------------------------

    def about_character(self, name: str, *, top_k: int = 5) -> RetrievalResult:
        return self.retrieve(
            f"{name} aparência rosto olhos cabelo roupa voz gesto", top_k=top_k
        )

    def about_location(self, name: str, *, top_k: int = 4) -> RetrievalResult:
        return self.retrieve(f"{name} lugar ambiente luz som cheiro textura", top_k=top_k)

    def about_scene(self, summary: str, *, top_k: int = 6) -> RetrievalResult:
        return self.retrieve(summary, top_k=top_k)


class _AsDocument:
    """Adapta um `NarrativeChunk` à forma que `_to_chunk` espera.

    Evita duplicar a montagem de `RetrievedChunk` entre o índice lexical e o
    vetorial, que produzem o mesmo tipo a partir de fontes diferentes.
    """

    __slots__ = ("chunk_id", "metadata", "text")

    def __init__(self, chunk: NarrativeChunk) -> None:
        self.chunk_id = chunk.chunk_id
        self.text = chunk.text
        self.metadata = chunk.metadata()


def _safe_chunk_id(raw: str) -> str:
    """Ajusta o id do chunk às regras do `Identifier` do domínio."""
    cleaned = raw.strip().lower().replace("/", ".").replace("\\", ".")
    cleaned = "".join(char if char.isalnum() or char in "_-." else "-" for char in cleaned)
    cleaned = cleaned.strip("-.")
    if len(cleaned) < 2:
        cleaned = f"chunk-{cleaned or '0'}"
    return cleaned[:128]
