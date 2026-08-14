"""Registro de prompts versionados (seção 35).

Nenhum prompt de agente vive como string solta no meio do código. Cada um tem
nome, versão, objetivo, esquema de entrada e saída, modelo recomendado,
temperatura, critérios de avaliação e hash — para que uma mudança de prompt seja
tão rastreável quanto uma mudança de código.
"""

from __future__ import annotations

from pedroarte_youtube_engine.prompts.definitions import ALL_PROMPTS
from pedroarte_youtube_engine.prompts.registry import PromptDefinition, PromptRegistry

#: Registro global, pronto para uso pelos agentes.
REGISTRY = PromptRegistry(ALL_PROMPTS)

__all__ = ["ALL_PROMPTS", "REGISTRY", "PromptDefinition", "PromptRegistry"]
