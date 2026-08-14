"""Portas (interfaces) do hexágono.

Cada porta é um `Protocol` estrutural. O domínio e a aplicação dependem apenas
destas assinaturas; nenhuma implementação concreta é importada aqui.

Imagem e vídeo são portas **distintas** por decisão explícita (seção 21): tratá-las
como a mesma capacidade foi o erro que a especificação pede para evitar.
"""

from __future__ import annotations

from pedroarte_youtube_engine.ports.analysis import NarrativeAnalyzerPort
from pedroarte_youtube_engine.ports.capabilities import CapabilityRegistryPort
from pedroarte_youtube_engine.ports.embedding import EmbeddingProviderPort
from pedroarte_youtube_engine.ports.llm import LLMProviderPort, LLMRequest, LLMResponse
from pedroarte_youtube_engine.ports.media import (
    GenerationRequest,
    GenerationResult,
    ImageGenerationProviderPort,
    MusicGenerationProviderPort,
    VideoGenerationProviderPort,
    VoiceGenerationProviderPort,
)
from pedroarte_youtube_engine.ports.parsing import DocumentParserPort, ParsedDocument
from pedroarte_youtube_engine.ports.queue import JobQueuePort
from pedroarte_youtube_engine.ports.retrieval import (
    LexicalIndexPort,
    RerankerPort,
    RetrievedChunk,
)
from pedroarte_youtube_engine.ports.storage import ArtifactWriterPort, ObjectStoragePort
from pedroarte_youtube_engine.ports.vector_store import VectorMatch, VectorStorePort

__all__ = [
    "ArtifactWriterPort",
    "CapabilityRegistryPort",
    "DocumentParserPort",
    "EmbeddingProviderPort",
    "GenerationRequest",
    "GenerationResult",
    "ImageGenerationProviderPort",
    "JobQueuePort",
    "LLMProviderPort",
    "LLMRequest",
    "LLMResponse",
    "LexicalIndexPort",
    "MusicGenerationProviderPort",
    "NarrativeAnalyzerPort",
    "ObjectStoragePort",
    "ParsedDocument",
    "RerankerPort",
    "RetrievedChunk",
    "VectorMatch",
    "VectorStorePort",
    "VideoGenerationProviderPort",
    "VoiceGenerationProviderPort",
]
