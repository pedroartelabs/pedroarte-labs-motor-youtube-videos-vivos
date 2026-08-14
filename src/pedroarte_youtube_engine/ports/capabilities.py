"""Porta do registro de capacidades de provedor.

As capacidades vêm de configuração (`config/provider_capabilities/*.yaml`),
nunca de constantes no domínio: elas mudam a cada release de um modelo.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pedroarte_youtube_engine.domain.provider import ProviderCapability, ProviderModality


@runtime_checkable
class CapabilityRegistryPort(Protocol):
    """Fornece as capacidades declaradas de cada par provedor/modelo."""

    def get(
        self, *, provider: str, modality: ProviderModality, model: str | None = None
    ) -> ProviderCapability | None: ...

    def require(
        self, *, provider: str, modality: ProviderModality, model: str | None = None
    ) -> ProviderCapability: ...

    def list_all(self) -> tuple[ProviderCapability, ...]: ...
