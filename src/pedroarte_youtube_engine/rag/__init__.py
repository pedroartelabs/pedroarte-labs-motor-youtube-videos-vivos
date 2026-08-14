"""RAG narrativo.

O objetivo do RAG aqui não é responder perguntas: é **reduzir alucinação na
adaptação**. Quando um agente precisa saber a cor dos olhos de um personagem,
ele recupera o trecho do livro que diz isso — e a citação viaja junto com o
fato, até o prompt final.

Nenhum banco vetorial externo é obrigatório. O pipeline completo roda em
memória, de forma determinística.
"""

from __future__ import annotations

from pedroarte_youtube_engine.rag.chunking import NarrativeChunk, StructuralChunker
from pedroarte_youtube_engine.rag.embedding import HashingEmbeddingProvider
from pedroarte_youtube_engine.rag.lexical import Bm25LexicalIndex
from pedroarte_youtube_engine.rag.pipeline import NarrativeRagPipeline, RetrievalResult
from pedroarte_youtube_engine.rag.reranker import HeuristicReranker
from pedroarte_youtube_engine.rag.vector_store import InMemoryVectorStore

__all__ = [
    "Bm25LexicalIndex",
    "HashingEmbeddingProvider",
    "HeuristicReranker",
    "InMemoryVectorStore",
    "NarrativeChunk",
    "NarrativeRagPipeline",
    "RetrievalResult",
    "StructuralChunker",
]
