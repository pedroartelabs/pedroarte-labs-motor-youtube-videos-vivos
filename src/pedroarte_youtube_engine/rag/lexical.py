"""Índice lexical BM25.

BM25 é implementado aqui em vez de importado porque a alternativa seria uma
dependência inteira para trinta linhas de aritmética — e porque o motor precisa
ser determinístico e auditável, inclusive na pontuação.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from pedroarte_youtube_engine.ports.retrieval import RetrievedChunk
from pedroarte_youtube_engine.shared.text import strip_accents

_TOKEN = re.compile(r"[\wÀ-ÿ]+")

#: Palavras funcionais do português que não discriminam documentos.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "do", "da",
        "dos", "das", "em", "no", "na", "nos", "nas", "por", "para", "com",
        "sem", "sob", "sobre", "ao", "aos", "e", "ou", "mas", "que", "se",
        "ja", "nao", "sim", "ele", "ela", "eles", "elas", "eu", "tu", "voce",
        "nos", "vos", "meu", "minha", "seu", "sua", "dele", "dela", "isso",
        "isto", "aquilo", "este", "esta", "esse", "essa", "aquele", "aquela",
        "foi", "era", "ser", "estar", "ter", "havia", "muito", "mais", "menos",
        "quando", "onde", "como", "porque", "entao", "ainda", "depois", "antes",
    }
)

_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    """Tokenização determinística: minúsculas, sem acento, sem palavras vazias."""
    normalized = strip_accents(text).lower()
    return [
        token
        for token in _TOKEN.findall(normalized)
        if len(token) > 1 and token not in _STOPWORDS
    ]


@dataclass(slots=True)
class _Document:
    chunk_id: str
    text: str
    metadata: dict[str, str]
    frequencies: Counter[str] = field(default_factory=Counter)
    length: int = 0


class Bm25LexicalIndex:
    """Índice invertido com pontuação BM25 (Okapi)."""

    def __init__(self) -> None:
        self._documents: dict[str, _Document] = {}
        self._document_frequency: Counter[str] = Counter()
        self._total_length = 0

    # -- construção --------------------------------------------------------

    def index(self, *, chunk_id: str, text: str, metadata: dict[str, str]) -> None:
        if chunk_id in self._documents:
            self._remove(chunk_id)
        tokens = tokenize(text)
        document = _Document(
            chunk_id=chunk_id,
            text=text,
            metadata=dict(metadata),
            frequencies=Counter(tokens),
            length=len(tokens),
        )
        self._documents[chunk_id] = document
        self._total_length += document.length
        for term in document.frequencies:
            self._document_frequency[term] += 1

    def _remove(self, chunk_id: str) -> None:
        document = self._documents.pop(chunk_id)
        self._total_length -= document.length
        for term in document.frequencies:
            self._document_frequency[term] -= 1
            if self._document_frequency[term] <= 0:
                del self._document_frequency[term]

    def clear(self) -> None:
        self._documents.clear()
        self._document_frequency.clear()
        self._total_length = 0

    def count(self) -> int:
        return len(self._documents)

    # -- consulta ----------------------------------------------------------

    def search(
        self, *, query: str, top_k: int, filters: dict[str, str] | None = None
    ) -> tuple[RetrievedChunk, ...]:
        if not self._documents or top_k <= 0:
            return ()

        terms = tokenize(query)
        if not terms:
            return ()

        candidates = [
            document
            for document in self._documents.values()
            if _matches(document.metadata, filters)
        ]
        if not candidates:
            return ()

        average_length = self._total_length / max(1, len(self._documents))
        scored: list[tuple[float, _Document]] = []

        for document in candidates:
            score = 0.0
            for term in terms:
                frequency = document.frequencies.get(term, 0)
                if frequency == 0:
                    continue
                score += self._idf(term) * self._term_score(
                    frequency, document.length, average_length
                )
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        best = scored[0][0] if scored else 1.0

        return tuple(
            _to_chunk(document, score=score / best, lexical_score=score / best)
            for score, document in scored[:top_k]
        )

    def _idf(self, term: str) -> float:
        total = len(self._documents)
        frequency = self._document_frequency.get(term, 0)
        # Variante suavizada: sempre positiva, mesmo para termos ubíquos.
        return math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))

    @staticmethod
    def _term_score(frequency: int, length: int, average_length: float) -> float:
        numerator = frequency * (_K1 + 1)
        denominator = frequency + _K1 * (1 - _B + _B * length / max(1e-9, average_length))
        return numerator / denominator


def _matches(metadata: dict[str, str], filters: dict[str, str] | None) -> bool:
    """Filtro por metadados; listas separadas por `|` casam por pertencimento."""
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


def _to_chunk(
    document: _Document, *, score: float, lexical_score: float = 0.0, vector_score: float = 0.0
) -> RetrievedChunk:
    metadata = document.metadata
    return RetrievedChunk(
        chunk_id=document.chunk_id,
        text=document.text,
        score=round(score, 6),
        source_id=metadata.get("source_id", ""),
        source_path=metadata.get("source_path", ""),
        chapter=metadata.get("chapter", ""),
        scene=metadata.get("scene", ""),
        characters=tuple(filter(None, metadata.get("characters", "").split("|"))),
        locations=tuple(filter(None, metadata.get("locations", "").split("|"))),
        content_type=metadata.get("content_type", ""),
        start_offset=int(metadata.get("start_offset", "0") or 0),
        end_offset=int(metadata.get("end_offset", "0") or 0),
        lexical_score=round(lexical_score, 6),
        vector_score=round(vector_score, 6),
    )
