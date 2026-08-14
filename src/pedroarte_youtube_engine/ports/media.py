"""Portas de geração de mídia.

Quatro portas distintas — vídeo, imagem, voz e música. Elas não compartilham
assinatura porque não compartilham capacidade: um gerador de imagem não tem
duração, um gerador de voz não tem enquadramento.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.domain.provider import ProviderPrompt


class GenerationRequest(BaseModel):
    """Pedido de geração real de mídia."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: ProviderPrompt
    idempotency_key: str = Field(min_length=8, max_length=128)
    output_directory: str = Field(min_length=1, max_length=512)
    max_budget_usd: float = Field(default=0.0, ge=0.0)
    timeout_seconds: float = Field(default=300.0, gt=0)
    correlation_id: str = Field(default="", max_length=64)


class GenerationResult(BaseModel):
    """Resultado de uma geração real."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    succeeded: bool
    output_reference: str = Field(default="", max_length=512)
    provider_job_id: str = Field(default="", max_length=128)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    error_code: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=1200)
    raw_response_digest: str = Field(default="", max_length=128)


@runtime_checkable
class MediaGenerationPort(Protocol):
    """Comportamento comum a todos os geradores de mídia."""

    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...

    def generate(self, request: GenerationRequest) -> GenerationResult: ...


@runtime_checkable
class VideoGenerationProviderPort(MediaGenerationPort, Protocol):
    """Gera vídeo a partir de um `ProviderPrompt` de modalidade `video`."""

    def supports_native_audio(self) -> bool:
        """Informa se o provedor produz a trilha sonora junto com a imagem."""
        ...


@runtime_checkable
class ImageGenerationProviderPort(MediaGenerationPort, Protocol):
    """Gera imagens fixas — quadros-chave, thumbnails, capas de Short."""

    def supports_reference_image(self) -> bool: ...


@runtime_checkable
class VoiceGenerationProviderPort(MediaGenerationPort, Protocol):
    """Sintetiza voz a partir de um plano vocal."""

    def available_voices(self) -> tuple[str, ...]: ...


@runtime_checkable
class MusicGenerationProviderPort(MediaGenerationPort, Protocol):
    """Gera música original a partir da descrição de um tema."""

    def max_duration_seconds(self) -> float: ...
