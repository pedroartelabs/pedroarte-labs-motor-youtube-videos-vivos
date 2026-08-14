"""Capacidades de provedor e prompts compilados.

Capacidades são **dados de configuração**, nunca constantes de código: elas
mudam a cada release de um modelo de vídeo, e o domínio não pode envelhecer
junto com uma API (regra da seção 9.23).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    Duration,
    ModelName,
    ProviderName,
    SegmentId,
)


class ProviderModality(StrEnum):
    """Imagem e vídeo são capacidades distintas — nunca a mesma coisa."""

    VIDEO = "video"
    IMAGE = "imagem"
    VOICE = "voz"
    MUSIC = "musica"
    SOUND_EFFECT = "efeito_sonoro"
    TEXT = "texto"
    EMBEDDING = "embedding"


class ProviderCapability(DomainEntity):
    """Registro declarativo do que um modelo aceita (seção 21.1)."""

    provider: ProviderName
    model: ModelName
    modality: ProviderModality
    min_duration_seconds: float = Field(default=1.0, gt=0)
    max_duration_seconds: float = Field(default=10.0, gt=0)
    duration_granularity_seconds: float = Field(default=1.0, gt=0)
    supported_aspect_ratios: tuple[str, ...] = Field(default=("16:9", "9:16"))
    supported_resolutions: tuple[str, ...] = Field(default=("720p", "1080p"))
    native_audio: bool = False
    dialogue_support: bool = False
    first_frame_reference: bool = False
    last_frame_reference: bool = False
    image_reference: bool = False
    video_extension: bool = False
    max_prompt_characters: int = Field(default=8000, gt=0)
    max_negative_prompt_characters: int = Field(default=1500, ge=0)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.max_duration_seconds < self.min_duration_seconds:
            raise ValueError("max_duration_seconds não pode ser menor que min_duration_seconds.")
        return self

    def supports_aspect_ratio(self, aspect: AspectRatio) -> bool:
        return str(aspect) in self.supported_aspect_ratios

    def supports_resolution(self, label: str) -> bool:
        return label in self.supported_resolutions

    def supports_duration(self, duration: Duration) -> bool:
        seconds = duration.seconds
        return self.min_duration_seconds <= seconds <= self.max_duration_seconds

    def best_fit_duration(self, target: Duration) -> Duration:
        """Maior duração aceita pelo provedor que não ultrapassa o alvo.

        Quando nem o mínimo cabe no alvo, devolve o mínimo — cabe ao compilador
        decidir entre estender a cena ou sobrepor segmentos.
        """
        seconds = min(target.seconds, self.max_duration_seconds)
        if seconds < self.min_duration_seconds:
            return Duration.from_seconds(self.min_duration_seconds)
        granularity = self.duration_granularity_seconds
        snapped = (int(seconds / granularity)) * granularity
        if snapped < self.min_duration_seconds:
            snapped = self.min_duration_seconds
        return Duration.from_seconds(snapped)

    def calls_needed_for(self, target: Duration) -> int:
        """Quantas chamadas cobrem a duração narrativa alvo."""
        chunk = self.best_fit_duration(target)
        if chunk.milliseconds <= 0:
            raise ValueError("Duração de chamada inválida para este provedor.")
        calls = -(-target.milliseconds // chunk.milliseconds)  # teto da divisão
        return max(1, calls)


class CompilationStrategy(StrEnum):
    """Como um segmento de 10 s vira uma ou mais chamadas de provedor."""

    DIRECT = "direto"
    SUBDIVIDE = "subdividir"
    EXTEND = "estender"
    OVERLAP = "sobrepor"
    FIRST_LAST_FRAME = "primeiro_e_ultimo_quadro"
    CONTINUITY_FRAME = "quadro_de_continuidade"
    MULTI_CALL = "multiplas_chamadas"


class ProviderPrompt(DomainEntity):
    """Prompt pronto para envio a um provedor concreto."""

    segment_id: SegmentId
    provider: ProviderName
    model: ModelName
    modality: ProviderModality
    call_index: int = Field(default=1, ge=1)
    call_total: int = Field(default=1, ge=1)
    strategy: CompilationStrategy = CompilationStrategy.DIRECT
    narrative_timecode_start: str = Field(min_length=8, max_length=16)
    narrative_timecode_end: str = Field(min_length=8, max_length=16)
    provider_duration_seconds: float = Field(gt=0)
    prompt_text: str = Field(min_length=20)
    negative_prompt: str = Field(default="")
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    reference_frames: tuple[str, ...] = Field(default_factory=tuple)
    audio_prompt: str = Field(default="")
    decision_log: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_calls(self) -> Self:
        if self.call_index > self.call_total:
            raise ValueError("call_index não pode exceder call_total.")
        return self

    @property
    def is_split(self) -> bool:
        return self.call_total > 1


class GenerationStatus(StrEnum):
    PENDING = "pendente"
    SUBMITTED = "enviado"
    RUNNING = "executando"
    COMPLETED = "concluido"
    FAILED = "falhou"
    SKIPPED = "ignorado"
    CANCELLED = "cancelado"

    @property
    def is_terminal(self) -> bool:
        return self in {
            GenerationStatus.COMPLETED,
            GenerationStatus.FAILED,
            GenerationStatus.SKIPPED,
            GenerationStatus.CANCELLED,
        }


class CostEstimate(DomainEntity):
    """Estimativa de custo. Só é preenchida quando há tabela configurada."""

    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount: float = Field(default=0.0, ge=0.0)
    basis: str = Field(default="tabela não configurada", max_length=200)
    is_estimated: bool = True

    def plus(self, other: "CostEstimate") -> "CostEstimate":
        if self.currency != other.currency:
            raise ValueError("Não é possível somar custos em moedas diferentes.")
        return self.model_copy(update={"amount": self.amount + other.amount})
