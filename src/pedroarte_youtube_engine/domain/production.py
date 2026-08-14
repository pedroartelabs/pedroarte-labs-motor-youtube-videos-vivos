"""Entidades de produção: do perfil de formato até a cena.

A hierarquia é `FormatProfile → Episode → Sequence → Scene → PromptSegment`.
Um vídeo avulso (o principal de 10 minutos, um Short, um trailer) é modelado
como um episódio único, o que mantém um único caminho de código para todos os
formatos.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    CharacterId,
    Duration,
    EmotionalTone,
    EpisodeId,
    FrameRate,
    Language,
    LocationId,
    NarrativeFunction,
    ProductionVariant,
    Resolution,
    SceneId,
    SequenceId,
    SourceReference,
    TimeRange,
    Timecode,
)


class FormatProfile(DomainEntity):
    """Especificação técnica e narrativa de um produto audiovisual."""

    profile_id: str = Field(min_length=3, max_length=96)
    variant: ProductionVariant
    label: str = Field(min_length=1, max_length=160)
    directory: str = Field(min_length=1, max_length=160)
    total_duration: Duration
    segment_duration: Duration
    aspect_ratio: AspectRatio
    resolution: Resolution
    frame_rate: FrameRate
    language: Language
    narration_enabled: bool = True
    dialogue_enabled: bool = True
    music_enabled: bool = True
    ambient_sound_enabled: bool = True
    sound_effects_enabled: bool = True
    minimum_duration: Duration | None = None
    strategy_note: str = Field(default="", max_length=800)

    @model_validator(mode="after")
    def _validate_durations(self) -> Self:
        if self.segment_duration.milliseconds <= 0:
            raise ValueError("A duração do segmento deve ser positiva.")
        if self.total_duration.milliseconds < self.segment_duration.milliseconds:
            raise ValueError("A duração total não pode ser menor que a de um segmento.")
        if (
            self.minimum_duration is not None
            and self.total_duration.milliseconds < self.minimum_duration.milliseconds
        ):
            raise ValueError(
                f"Duração total ({self.total_duration}) abaixo do mínimo exigido "
                f"({self.minimum_duration}) para {self.variant.value}."
            )
        return self

    @property
    def segment_count(self) -> int:
        """Quantos segmentos cobrem exatamente a duração total.

        A divisão é exata por construção: `DurationPlanningService` só cria
        perfis cuja duração total é múltipla da duração de segmento.
        """
        return self.total_duration.milliseconds // self.segment_duration.milliseconds

    @property
    def has_exact_segmentation(self) -> bool:
        return self.total_duration.milliseconds % self.segment_duration.milliseconds == 0


class SceneKind(StrEnum):
    DIALOGUE = "dialogo"
    ACTION = "acao"
    TRANSITION = "transicao"
    REVELATION = "revelacao"
    BREATHING = "respiro"
    MONTAGE = "montagem"
    ESTABLISHING = "estabelecimento"


class Scene(DomainEntity):
    """Ocorrência contínua de espaço, tempo e ação."""

    scene_id: SceneId
    sequence_id: SequenceId
    order: int = Field(ge=0)
    kind: SceneKind = SceneKind.DIALOGUE
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=3, max_length=1200)
    location_id: LocationId | None = None
    location_name: str = Field(default="", max_length=160)
    time_of_day: str = Field(default="indefinido", max_length=64)
    weather: str = Field(default="indefinido", max_length=120)
    participants: tuple[CharacterId, ...] = Field(default_factory=tuple)
    beat_ids: tuple[str, ...] = Field(default_factory=tuple)
    range: TimeRange
    tone_start: EmotionalTone = EmotionalTone.NEUTRAL
    tone_end: EmotionalTone = EmotionalTone.NEUTRAL
    dramatic_function: NarrativeFunction = NarrativeFunction.RISING_ACTION
    dialogue_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)

    @property
    def duration(self) -> Duration:
        return self.range.duration

    @property
    def changes_location_from(self) -> LocationId | None:
        return self.location_id


class Sequence(DomainEntity):
    """Conjunto de cenas com uma função dramática única."""

    sequence_id: SequenceId
    episode_id: EpisodeId
    order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=240)
    dramatic_function: NarrativeFunction
    summary: str = Field(default="", max_length=1200)
    scenes: tuple[Scene, ...] = Field(default_factory=tuple)
    range: TimeRange

    @model_validator(mode="after")
    def _validate_scene_order(self) -> Self:
        orders = [scene.order for scene in self.scenes]
        if orders != sorted(orders):
            raise ValueError("As cenas de uma sequência devem estar em ordem crescente.")
        for previous, current in zip(self.scenes, self.scenes[1:], strict=False):
            if previous.range.end.milliseconds != current.range.start.milliseconds:
                raise ValueError(
                    "As cenas de uma sequência devem ser contíguas: "
                    f"{previous.range.end} ≠ {current.range.start}."
                )
        return self

    @property
    def duration(self) -> Duration:
        return self.range.duration


class Episode(DomainEntity):
    """Unidade narrativa publicável.

    Um vídeo único também é um episódio (`number = 1`), o que evita duplicar o
    pipeline para formatos avulsos.
    """

    episode_id: EpisodeId
    variant: ProductionVariant
    season_number: int = Field(default=1, ge=1)
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    logline: str = Field(default="", max_length=600)
    synopsis: str = Field(default="", max_length=2400)
    covered_chapters: tuple[int, ...] = Field(default_factory=tuple)
    sequences: tuple[Sequence, ...] = Field(default_factory=tuple)
    total_duration: Duration
    hook: str = Field(default="", max_length=600)
    cliffhanger: str = Field(default="", max_length=600)
    recap_needed: bool = False
    opening_note: str = Field(default="", max_length=400)
    closing_note: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def _validate_sequence_continuity(self) -> Self:
        orders = [sequence.order for sequence in self.sequences]
        if orders != sorted(orders):
            raise ValueError("As sequências devem estar em ordem crescente.")
        for previous, current in zip(self.sequences, self.sequences[1:], strict=False):
            if previous.range.end.milliseconds != current.range.start.milliseconds:
                raise ValueError(
                    "As sequências de um episódio devem ser contíguas: "
                    f"{previous.range.end} ≠ {current.range.start}."
                )
        if self.sequences:
            measured = self.sequences[-1].range.end.milliseconds
            if measured != self.total_duration.milliseconds:
                raise ValueError(
                    f"A soma das sequências ({measured} ms) diverge da duração "
                    f"declarada do episódio ({self.total_duration.milliseconds} ms)."
                )
        return self

    @property
    def slug(self) -> str:
        return f"episodio_{self.number:02d}"

    def all_scenes(self) -> tuple[Scene, ...]:
        return tuple(scene for sequence in self.sequences for scene in sequence.scenes)

    def scene_at(self, moment: Timecode) -> Scene | None:
        for scene in self.all_scenes():
            if scene.range.contains(moment):
                return scene
        return None


class SeasonPlan(DomainEntity):
    """Plano de temporada para os formatos episódicos."""

    season_number: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=240)
    logline: str = Field(default="", max_length=600)
    episode_count: int = Field(ge=1)
    arc_summary: str = Field(default="", max_length=2400)
    arcs: tuple[str, ...] = Field(default_factory=tuple)
    chapter_distribution: dict[str, tuple[int, ...]] = Field(default_factory=dict)
    progression_note: str = Field(default="", max_length=1200)


class AdaptationDecision(DomainEntity):
    """Registro auditável de uma escolha de adaptação (seção 9.8)."""

    decision_id: str = Field(min_length=3, max_length=128)
    kind: str = Field(min_length=2, max_length=48)
    subject: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=3, max_length=1200)
    affects_variants: tuple[ProductionVariant, ...] = Field(default_factory=tuple)
    preserves_thesis: bool = True
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)


class RetentionAssessment(DomainEntity):
    """Avaliação de retenção emitida pelo `RETENTION_AND_HOOK_AGENT`."""

    variant: ProductionVariant
    episode_id: EpisodeId | None = None
    opening_promise: str = Field(min_length=3, max_length=600)
    first_seconds_score: float = Field(ge=0.0, le=1.0)
    pacing_score: float = Field(ge=0.0, le=1.0)
    low_energy_segments: tuple[str, ...] = Field(default_factory=tuple)
    recommendations: tuple[str, ...] = Field(default_factory=tuple)
    clickbait_risk: bool = False
