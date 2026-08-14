"""Reranking heurístico.

Combina os sinais que o BM25 e o cosseno não veem sozinhos: cobertura dos termos
da consulta, densidade do trecho e presença de entidades citadas na pergunta.
"""

from __future__ import annotations

from pedroarte_youtube_engine.ports.retrieval import RetrievedChunk
from pedroarte_youtube_engine.rag.lexical import tokenize


class HeuristicReranker:
    """Reordena candidatos por relevância composta."""

    def __init__(
        self,
        *,
        coverage_weight: float = 0.45,
        base_weight: float = 0.40,
        entity_weight: float = 0.15,
        ideal_words: int = 220,
    ) -> None:
        self._coverage_weight = coverage_weight
        self._base_weight = base_weight
        self._entity_weight = entity_weight
        self._ideal_words = ideal_words

    def rerank(
        self, *, query: str, candidates: tuple[RetrievedChunk, ...], top_k: int
    ) -> tuple[RetrievedChunk, ...]:
        if not candidates:
            return ()

        query_terms = set(tokenize(query))
        if not query_terms:
            return candidates[:top_k]

        scored: list[tuple[float, RetrievedChunk]] = []
        for candidate in candidates:
            coverage = self._coverage(query_terms, candidate.text)
            entity_bonus = self._entity_bonus(query, candidate)
            length_penalty = self._length_penalty(candidate.text)
            final = (
                self._coverage_weight * coverage
                + self._base_weight * candidate.score
                + self._entity_weight * entity_bonus
            ) * length_penalty
            scored.append((final, candidate))

        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return tuple(
            candidate.model_copy(update={"score": round(score, 6)})
            for score, candidate in scored[:top_k]
        )

    @staticmethod
    def _coverage(query_terms: set[str], text: str) -> float:
        """Fração dos termos da consulta presentes no trecho."""
        text_terms = set(tokenize(text))
        if not query_terms:
            return 0.0
        return len(query_terms & text_terms) / len(query_terms)

    @staticmethod
    def _entity_bonus(query: str, candidate: RetrievedChunk) -> float:
        """Bônus quando o trecho contém entidades nomeadas na consulta."""
        lowered = query.lower()
        entities = (*candidate.characters, *candidate.locations)
        if not entities:
            return 0.0
        hits = sum(1 for entity in entities if entity.split()[0].lower() in lowered)
        return min(1.0, hits / max(1, len(entities)))

    def _length_penalty(self, text: str) -> float:
        """Penaliza trechos muito curtos, que respondem pela metade.

        Trechos longos não são penalizados: o custo deles é de contexto, não de
        precisão, e o `top_k` já limita o volume.
        """
        words = len(tokenize(text))
        if words >= self._ideal_words * 0.35:
            return 1.0
        return max(0.5, words / (self._ideal_words * 0.35))
