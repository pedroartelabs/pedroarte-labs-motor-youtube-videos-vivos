"""Registro de compiladores de prompt.

Adicionar um provedor novo é registrar um compilador aqui e declarar as
capacidades dele em `config/provider_capabilities/`. Nada no domínio muda.
"""

from __future__ import annotations

from typing import Protocol

from pedroarte_youtube_engine.adapters.prompt_compilers.gemini import (
    GeminiImagePromptAdapter,
    GeminiVideoPromptAdapter,
)
from pedroarte_youtube_engine.adapters.prompt_compilers.generic import (
    GenericImagePromptAdapter,
    GenericVideoPromptAdapter,
    GenericVoicePromptAdapter,
)
from pedroarte_youtube_engine.domain.provider import (
    ProviderCapability,
    ProviderModality,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.shared.errors import CapabilityError


class PromptCompiler(Protocol):
    """Contrato mínimo de um compilador de prompt."""

    @property
    def name(self) -> str: ...

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]: ...


class PromptCompilerRegistry:
    """Resolve o compilador para um par provedor/modalidade."""

    def __init__(self) -> None:
        self._compilers: dict[tuple[str, ProviderModality], PromptCompiler] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("generic", ProviderModality.VIDEO, GenericVideoPromptAdapter())
        self.register("generic", ProviderModality.IMAGE, GenericImagePromptAdapter())
        self.register("generic", ProviderModality.VOICE, GenericVoicePromptAdapter())
        self.register("gemini", ProviderModality.VIDEO, GeminiVideoPromptAdapter())
        self.register("gemini", ProviderModality.IMAGE, GeminiImagePromptAdapter())
        self.register("gemini", ProviderModality.VOICE, GenericVoicePromptAdapter())

    def register(
        self, provider: str, modality: ProviderModality, compiler: PromptCompiler
    ) -> None:
        self._compilers[(provider, modality)] = compiler

    def get(self, provider: str, modality: ProviderModality) -> PromptCompiler | None:
        compiler = self._compilers.get((provider, modality))
        if compiler is None:
            # Um provedor desconhecido recai no alvo genérico da mesma modalidade,
            # que produz um prompt completo em vez de nenhum prompt.
            compiler = self._compilers.get(("generic", modality))
        return compiler

    def require(self, provider: str, modality: ProviderModality) -> PromptCompiler:
        compiler = self.get(provider, modality)
        if compiler is None:
            raise CapabilityError(
                f"Nenhum compilador registrado para {provider}/{modality.value}.",
                provider=provider,
                modality=modality.value,
                registered=[f"{key[0]}/{key[1].value}" for key in self._compilers],
            )
        return compiler

    def registered(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                f"{provider}/{modality.value} → {compiler.name}"
                for (provider, modality), compiler in self._compilers.items()
            )
        )
