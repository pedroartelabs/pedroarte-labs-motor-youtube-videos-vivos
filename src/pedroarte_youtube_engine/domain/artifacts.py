"""Artefatos exportados e metadados de publicação."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    ContentHash,
    Duration,
    ProductionVariant,
    Timecode,
)


class ArtifactKind(StrEnum):
    MANIFEST = "manifesto"
    CANON = "canone"
    AUDIOVISUAL_BIBLE = "biblia_audiovisual"
    PRODUCTION_MANIFEST = "manifesto_de_producao"
    SEGMENT_PROMPT = "prompt_de_segmento"
    PROMPT_PACKAGE = "pacote_de_prompts"
    SUBTITLE = "legenda"
    TRANSCRIPT = "transcricao"
    PACKAGING = "empacotamento"
    REPORT = "relatorio"
    PROVIDER_PACKAGE = "pacote_de_provedor"
    CHECKPOINT = "checkpoint"
    LOG = "log"


class Artifact(DomainEntity):
    """Um arquivo produzido pela execução, com hash e proveniência."""

    artifact_id: str = Field(min_length=3, max_length=160)
    kind: ArtifactKind
    relative_path: str = Field(min_length=1, max_length=512)
    content_hash: ContentHash
    size_bytes: int = Field(ge=0)
    variant: ProductionVariant | None = None
    episode_id: str | None = None
    produced_by: str = Field(default="", max_length=96)
    schema_id: str | None = None
    description: str = Field(default="", max_length=400)


class ChapterMarker(DomainEntity):
    """Marcador de capítulo do YouTube (timestamps da descrição)."""

    at: Timecode
    title: str = Field(min_length=1, max_length=120)

    def formatted(self) -> str:
        total = self.at.milliseconds // 1000
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        stamp = (
            f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
        )
        return f"{stamp} {self.title}"


class ThumbnailPrompt(DomainEntity):
    """Prompt de thumbnail ou frame de capa."""

    label: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=20, max_length=4000)
    negative_prompt: str = Field(default="", max_length=1500)
    aspect_ratio: str = Field(default="16:9", max_length=12)
    text_overlay: str = Field(default="", max_length=120)
    rationale: str = Field(default="", max_length=600)


class PublicationMetadata(DomainEntity):
    """Pacote de publicação do `YOUTUBE_PACKAGING_AGENT`.

    O motor prepara os metadados; a publicação em si permanece fora do escopo
    desta versão (ver roadmap).
    """

    variant: ProductionVariant
    episode_id: str | None = None
    primary_title: str = Field(min_length=1, max_length=100)
    alternative_titles: tuple[str, ...] = Field(default_factory=tuple)
    description: str = Field(min_length=1, max_length=5000)
    chapters: tuple[ChapterMarker, ...] = Field(default_factory=tuple)
    keywords: tuple[str, ...] = Field(default_factory=tuple)
    hashtags: tuple[str, ...] = Field(default_factory=tuple)
    thumbnail_prompts: tuple[ThumbnailPrompt, ...] = Field(default_factory=tuple)
    pinned_comment: str = Field(default="", max_length=1000)
    playlist: str = Field(default="", max_length=160)
    publication_order: int = Field(default=1, ge=1)
    linked_shorts: tuple[str, ...] = Field(default_factory=tuple)
    linked_long_form: str = Field(default="", max_length=160)
    duration: Duration | None = None

    def title_length_ok(self) -> bool:
        """O YouTube trunca títulos acima de 100 caracteres."""
        return len(self.primary_title) <= 100


class AccessibilityPackage(DomainEntity):
    """Saída do `ACCESSIBILITY_AGENT`."""

    variant: ProductionVariant
    episode_id: str | None = None
    srt_content: str = Field(default="")
    vtt_content: str = Field(default="")
    transcript: str = Field(default="")
    speaker_labels: tuple[str, ...] = Field(default_factory=tuple)
    important_sound_descriptions: tuple[str, ...] = Field(default_factory=tuple)
    audio_description_notes: tuple[str, ...] = Field(default_factory=tuple)
    plain_language_summary: str = Field(default="", max_length=2000)


class RightsRisk(DomainEntity):
    """Risco sinalizado pelo `LEGAL_AND_RIGHTS_AGENT` — nunca um parecer jurídico."""

    risk_id: str = Field(min_length=3, max_length=128)
    category: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=5, max_length=800)
    evidence: str = Field(default="", max_length=800)
    severity: str = Field(default="advertencia", max_length=32)
    recommendation: str = Field(default="", max_length=600)


class CostReport(DomainEntity):
    """Saída do `COST_AND_QUOTA_AGENT`."""

    total_segments: int = Field(ge=0)
    estimated_provider_calls: int = Field(ge=0)
    calls_by_variant: dict[str, int] = Field(default_factory=dict)
    models_used: tuple[str, ...] = Field(default_factory=tuple)
    currency: str = Field(default="USD", max_length=3)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    cost_table_configured: bool = False
    batches: tuple[str, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)
