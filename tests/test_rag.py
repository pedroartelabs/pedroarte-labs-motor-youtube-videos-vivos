"""Testes unitários do RAG."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.rag.embedding import HashingEmbeddingProvider
from pedroarte_youtube_engine.rag.lexical import Bm25LexicalIndex
from pedroarte_youtube_engine.rag.reranker import HeuristicReranker
from pedroarte_youtube_engine.rag.vector_store import InMemoryVectorStore

pytestmark = pytest.mark.unit


class TestHashingEmbedding:
    def test_deterministic(self) -> None:
        provider = HashingEmbeddingProvider(dimensions=64)
        a = provider.embed("teste")
        b = provider.embed("teste")
        assert a == b

    def test_correct_dimensions(self) -> None:
        provider = HashingEmbeddingProvider(dimensions=64)
        vec = provider.embed("qualquer texto")
        assert len(vec) == 64

    def test_different_texts_differ(self) -> None:
        provider = HashingEmbeddingProvider(dimensions=64)
        a = provider.embed("texto um")
        b = provider.embed("texto dois")
        assert a != b

    def test_min_dimensions_enforced(self) -> None:
        with pytest.raises(ValueError):
            HashingEmbeddingProvider(dimensions=8)


class TestInMemoryVectorStore:
    def test_upsert_and_search(self) -> None:
        store = InMemoryVectorStore()
        provider = HashingEmbeddingProvider(dimensions=64)
        vec = provider.embed("hello world test")
        store.upsert(chunk_id="doc1", vector=vec, metadata={})
        results = store.search(vector=vec, top_k=1)
        assert len(results) >= 1
        assert results[0].chunk_id == "doc1"

    def test_empty_search(self) -> None:
        store = InMemoryVectorStore()
        provider = HashingEmbeddingProvider(dimensions=64)
        vec = provider.embed("nada")
        results = store.search(vector=vec, top_k=5)
        assert results == ()

    def test_count(self) -> None:
        store = InMemoryVectorStore()
        assert store.count() == 0
        provider = HashingEmbeddingProvider(dimensions=64)
        store.upsert(chunk_id="d1", vector=provider.embed("x"), metadata={})
        assert store.count() == 1


class TestBm25LexicalIndex:
    def test_index_and_search(self) -> None:
        index = Bm25LexicalIndex()
        index.index(chunk_id="d1", text="o gato sentou no tapete", metadata={})
        index.index(chunk_id="d2", text="o cachorro correu no parque", metadata={})
        results = index.search(query="gato tapete", top_k=1)
        assert len(results) >= 1
        assert results[0].chunk_id == "d1"

    def test_empty_search(self) -> None:
        index = Bm25LexicalIndex()
        results = index.search(query="nada", top_k=5)
        assert results == ()

    def test_count(self) -> None:
        index = Bm25LexicalIndex()
        assert index.count() == 0
        index.index(chunk_id="d1", text="texto", metadata={})
        assert index.count() == 1


class TestHeuristicReranker:
    def test_rerank_preserves_top_k(self) -> None:
        reranker = HeuristicReranker()
        index = Bm25LexicalIndex()
        index.index(chunk_id="d1", text="primeiro documento sobre gatos", metadata={})
        index.index(chunk_id="d2", text="segundo documento sobre cães", metadata={})
        index.index(chunk_id="d3", text="terceiro documento sobre gatos e cães", metadata={})
        candidates = index.search(query="gatos", top_k=3)
        result = reranker.rerank(query="gatos", candidates=candidates, top_k=2)
        assert len(result) <= 2
