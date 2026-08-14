"""Adaptadores de provedor.

Nenhum deles faz rede no modo padrão. Os `Fake*` são determinísticos e existem
para testes e para o caminho `execute_generation: false`; os adaptadores reais
(ex.: ecossistema Gemini) só são carregados quando há credencial e aceite
explícito.
"""

from __future__ import annotations

from pedroarte_youtube_engine.adapters.providers.deterministic_llm import (
    DeterministicLLMProvider,
)
from pedroarte_youtube_engine.adapters.providers.fakes import (
    FakeEmbeddingProvider,
    FakeImageProvider,
    FakeLLMProvider,
    FakeMusicProvider,
    FakeVideoProvider,
    FakeVoiceProvider,
)

__all__ = [
    "DeterministicLLMProvider",
    "FakeEmbeddingProvider",
    "FakeImageProvider",
    "FakeLLMProvider",
    "FakeMusicProvider",
    "FakeVideoProvider",
    "FakeVoiceProvider",
]
