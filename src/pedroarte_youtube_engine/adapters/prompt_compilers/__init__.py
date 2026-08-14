"""Compiladores de prompt por provedor (Anti-Corruption Layer).

Cada adaptador traduz o segmento canônico para a sintaxe de um provedor. A
tradução nunca perde informação obrigatória: se um provedor não aceita algum
campo, o compilador o move para outra seção ou registra a perda no log de
decisões — jamais o descarta em silêncio.
"""

from __future__ import annotations

from pedroarte_youtube_engine.adapters.prompt_compilers.gemini import (
    GeminiImagePromptAdapter,
    GeminiVideoPromptAdapter,
)
from pedroarte_youtube_engine.adapters.prompt_compilers.generic import (
    GenericImagePromptAdapter,
    GenericVideoPromptAdapter,
    GenericVoicePromptAdapter,
)
from pedroarte_youtube_engine.adapters.prompt_compilers.registry import (
    PromptCompilerRegistry,
)

__all__ = [
    "GeminiImagePromptAdapter",
    "GeminiVideoPromptAdapter",
    "GenericImagePromptAdapter",
    "GenericVideoPromptAdapter",
    "GenericVoicePromptAdapter",
    "PromptCompilerRegistry",
]
