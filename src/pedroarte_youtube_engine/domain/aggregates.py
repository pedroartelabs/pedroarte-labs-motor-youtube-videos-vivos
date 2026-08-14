"""Agregados do domínio (seção 7.1).

Cada agregado é uma fronteira de consistência: só ele pode alterar suas próprias
entidades internas. Agentes não se editam mutuamente — eles propõem mudanças e o
agregado decide se elas são válidas (regra da seção 8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pedroarte_youtube_engine.domain.artifacts import (
    AccessibilityPackage,
    Artifact,
    CostReport,
    PublicationMetadata,
    RightsRisk,
)
from pedroarte_youtube_engine.domain.audiovisual import (
    CharacterVisualProfile,
    ContinuityAnchor,
    LocationVisualProfile,
    MusicTheme,
    SoundMotif,
    VisualIdentity,
    VoiceProfile,
)
from pedroarte_youtube_engine.domain.canon import (
    CanonFact,
    Character,
    CharacterRelationship,
    Location,
    NarrativeBeat,
    Prop,
    TimelineEvent,
    UnresolvedQuestion,
)
from pedroarte_youtube_engine.domain.configuration import ProjectConfiguration
from pedroarte_youtube_engine.domain.events import DomainEvent, EventLog
from pedroarte_youtube_engine.domain.production import (
    AdaptationDecision,
    Episode,
    FormatProfile,
    RetentionAssessment,
    SeasonPlan,
)
from pedroarte_youtube_engine.domain.provider import (
    CostEstimate,
    GenerationStatus,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment, SubtitleCue
from pedroarte_youtube_engine.domain.source import BookSource
from pedroarte_youtube_engine.domain.state import PipelineState, assert_transition
from pedroarte_youtube_engine.domain.validation import QualityAssessment, ValidationReport
from pedroarte_youtube_engine.domain.value_objects import (
    CharacterId,
    ContentHash,
    Duration,
    EpisodeId,
    Language,
    LocationId,
    ProductionVariant,
    ProjectId,
    RunId,
    SegmentId,
)
from pedroarte_youtube_engine.shared.errors import DomainRuleViolation


class Aggregate(BaseModel):
    """Base dos agregados. Mutável, mas apenas por métodos que preservam invariantes."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# CanonBible
# ---------------------------------------------------------------------------


class CanonBible(Aggregate):
    """A verdade narrativa da obra."""

    project_id: ProjectId
    title: str = Field(default="", max_length=300)
    author: str = Field(default="", max_length=200)
    language: Language = Field(default_factory=Language.brazilian_portuguese)
    logline: str = Field(default="", max_length=600)
    thesis: str = Field(default="", max_length=1200)
    facts: tuple[CanonFact, ...] = Field(default_factory=tuple)
    characters: tuple[Character, ...] = Field(default_factory=tuple)
    relationships: tuple[CharacterRelationship, ...] = Field(default_factory=tuple)
    locations: tuple[Location, ...] = Field(default_factory=tuple)
    props: tuple[Prop, ...] = Field(default_factory=tuple)
    timeline: tuple[TimelineEvent, ...] = Field(default_factory=tuple)
    beats: tuple[NarrativeBeat, ...] = Field(default_factory=tuple)
    world_rules: tuple[str, ...] = Field(default_factory=tuple)
    prohibitions: tuple[str, ...] = Field(default_factory=tuple)
    mysteries: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_questions: tuple[UnresolvedQuestion, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        _assert_unique(
            [character.character_id.value for character in self.characters], "personagem"
        )
        _assert_unique([location.location_id.value for location in self.locations], "local")
        _assert_unique([prop.prop_id.value for prop in self.props], "objeto")
        _assert_unique([fact.fact_id for fact in self.facts], "fato canônico")
        _assert_unique([beat.beat_id for beat in self.beats], "beat narrativo")
        orders = [event.order for event in self.timeline]
        if orders != sorted(orders):
            raise ValueError("A cronologia deve estar em ordem crescente.")
        return self

    def character(self, character_id: CharacterId) -> Character | None:
        for candidate in self.characters:
            if candidate.character_id == character_id:
                return candidate
        return None

    def character_by_name(self, name: str) -> Character | None:
        needle = name.strip().casefold()
        for candidate in self.characters:
            if candidate.canonical_name.casefold() == needle:
                return candidate
            if any(alias.casefold() == needle for alias in candidate.aliases):
                return candidate
        return None

    def location(self, location_id: LocationId) -> Location | None:
        for candidate in self.locations:
            if candidate.location_id == location_id:
                return candidate
        return None

    def leads(self) -> tuple[Character, ...]:
        ranked = sorted(
            self.characters,
            key=lambda character: (-character.mention_count, character.canonical_name),
        )
        return tuple(ranked[:6])

    def beats_for_chapter(self, chapter_index: int) -> tuple[NarrativeBeat, ...]:
        return tuple(beat for beat in self.beats if beat.chapter_index == chapter_index)

    def uncertain_facts(self) -> tuple[CanonFact, ...]:
        return tuple(fact for fact in self.facts if fact.is_uncertain)

    @property
    def has_provenance(self) -> bool:
        """Todo fato relevante aponta para um trecho da obra."""
        return all(fact.references for fact in self.facts)


# ---------------------------------------------------------------------------
# AudiovisualBible
# ---------------------------------------------------------------------------


class AudiovisualBible(Aggregate):
    """A tradução do cânone para linguagem audiovisual."""

    project_id: ProjectId
    visual_identity: VisualIdentity
    character_profiles: tuple[CharacterVisualProfile, ...] = Field(default_factory=tuple)
    location_profiles: tuple[LocationVisualProfile, ...] = Field(default_factory=tuple)
    voices: tuple[VoiceProfile, ...] = Field(default_factory=tuple)
    music_themes: tuple[MusicTheme, ...] = Field(default_factory=tuple)
    sound_motifs: tuple[SoundMotif, ...] = Field(default_factory=tuple)
    continuity_anchors: tuple[ContinuityAnchor, ...] = Field(default_factory=tuple)
    transitions_doctrine: str = Field(default="", max_length=1200)
    restrictions: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_voice_uniqueness(self) -> Self:
        _assert_unique([voice.voice_id for voice in self.voices], "voz")
        narrators = [voice for voice in self.voices if voice.is_narrator]
        if len(narrators) > 1:
            raise ValueError("A Bíblia Audiovisual admite no máximo uma voz de narrador.")
        return self

    def voice_for_character(self, character_id: CharacterId) -> VoiceProfile | None:
        for voice in self.voices:
            if voice.character_id == character_id:
                return voice
        return None

    def narrator_voice(self) -> VoiceProfile | None:
        for voice in self.voices:
            if voice.is_narrator:
                return voice
        return None

    def visual_profile(self, character_id: CharacterId) -> CharacterVisualProfile | None:
        for profile in self.character_profiles:
            if profile.character_id == character_id:
                return profile
        return None

    def location_profile(self, location_id: LocationId) -> LocationVisualProfile | None:
        for profile in self.location_profiles:
            if profile.location_id == location_id:
                return profile
        return None

    def theme_for_role(self, role: str) -> MusicTheme | None:
        for theme in self.music_themes:
            if theme.role.value == role:
                return theme
        return None

    def pronunciation_dictionary(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for voice in self.voices:
            merged.update(voice.pronunciation_dictionary)
        return merged


# ---------------------------------------------------------------------------
# ProductionPlan
# ---------------------------------------------------------------------------


class ProductionPlan(Aggregate):
    """Os formatos que serão produzidos e como cada um foi adaptado."""

    project_id: ProjectId
    profiles: tuple[FormatProfile, ...] = Field(default_factory=tuple)
    episodes: tuple[Episode, ...] = Field(default_factory=tuple)
    seasons: tuple[SeasonPlan, ...] = Field(default_factory=tuple)
    decisions: tuple[AdaptationDecision, ...] = Field(default_factory=tuple)
    retention: tuple[RetentionAssessment, ...] = Field(default_factory=tuple)
    adaptation_strategy: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def _validate_profiles(self) -> Self:
        _assert_unique([profile.profile_id for profile in self.profiles], "perfil de formato")
        _assert_unique([episode.episode_id.value for episode in self.episodes], "episódio")
        for profile in self.profiles:
            if not profile.has_exact_segmentation:
                raise DomainRuleViolation(
                    f"O perfil {profile.profile_id} não fecha em segmentos inteiros.",
                    profile_id=profile.profile_id,
                )
        return self

    def profiles_for(self, variant: ProductionVariant) -> tuple[FormatProfile, ...]:
        return tuple(profile for profile in self.profiles if profile.variant is variant)

    def episodes_for(self, variant: ProductionVariant) -> tuple[Episode, ...]:
        return tuple(episode for episode in self.episodes if episode.variant is variant)

    def episode(self, episode_id: EpisodeId) -> Episode | None:
        for episode in self.episodes:
            if episode.episode_id == episode_id:
                return episode
        return None

    def profile(self, profile_id: str) -> FormatProfile | None:
        for candidate in self.profiles:
            if candidate.profile_id == profile_id:
                return candidate
        return None

    @property
    def enabled_variants(self) -> tuple[ProductionVariant, ...]:
        seen: list[ProductionVariant] = []
        for profile in self.profiles:
            if profile.variant not in seen:
                seen.append(profile.variant)
        return tuple(seen)

    @property
    def total_planned_duration(self) -> Duration:
        total = sum(profile.total_duration.milliseconds for profile in self.profiles)
        return Duration(milliseconds=total)

    @property
    def total_segment_count(self) -> int:
        return sum(profile.segment_count for profile in self.profiles)


# ---------------------------------------------------------------------------
# PromptPackage
# ---------------------------------------------------------------------------


class EpisodePromptSet(Aggregate):
    """Os segmentos de um episódio, com legendas e empacotamento."""

    episode_id: EpisodeId
    profile_id: str
    variant: ProductionVariant
    title: str = Field(default="", max_length=240)
    segments: tuple[PromptSegment, ...] = Field(default_factory=tuple)
    subtitles: tuple[SubtitleCue, ...] = Field(default_factory=tuple)
    publication: PublicationMetadata | None = None
    accessibility: AccessibilityPackage | None = None

    @model_validator(mode="after")
    def _validate_segment_chain(self) -> Self:
        numbers = [segment.segment_number for segment in self.segments]
        if numbers != sorted(numbers):
            raise ValueError("Os segmentos devem estar em ordem crescente de número.")
        _assert_unique([segment.segment_id.value for segment in self.segments], "segmento")
        for previous, current in zip(self.segments, self.segments[1:], strict=False):
            if previous.range.end.milliseconds != current.range.start.milliseconds:
                raise DomainRuleViolation(
                    "Segmentos consecutivos precisam ser contíguos no tempo.",
                    previous=str(previous.segment_id),
                    current=str(current.segment_id),
                    previous_end=str(previous.range.end),
                    current_start=str(current.range.start),
                )
        return self

    @property
    def total_duration(self) -> Duration:
        if not self.segments:
            return Duration(milliseconds=0)
        return self.segments[-1].range.end.minus(self.segments[0].range.start)

    @property
    def approved(self) -> bool:
        return bool(self.segments) and all(
            segment.validation.approved for segment in self.segments
        )

    def segment(self, segment_id: SegmentId) -> PromptSegment | None:
        for segment in self.segments:
            if segment.segment_id == segment_id:
                return segment
        return None


class PromptPackage(Aggregate):
    """O conjunto completo de prompts de uma produção (um `variant`)."""

    project_id: ProjectId
    variant: ProductionVariant
    directory: str
    episodes: tuple[EpisodePromptSet, ...] = Field(default_factory=tuple)
    adaptation_strategy: str = Field(default="", max_length=8000)
    validation: QualityAssessment | None = None

    @property
    def segment_count(self) -> int:
        return sum(len(episode.segments) for episode in self.episodes)

    @property
    def total_duration(self) -> Duration:
        total = sum(episode.total_duration.milliseconds for episode in self.episodes)
        return Duration(milliseconds=total)

    @property
    def approved(self) -> bool:
        if self.validation is not None:
            return self.validation.approved
        return all(episode.approved for episode in self.episodes)

    def all_segments(self) -> tuple[PromptSegment, ...]:
        return tuple(segment for episode in self.episodes for segment in episode.segments)

    def episode(self, episode_id: EpisodeId) -> EpisodePromptSet | None:
        for episode in self.episodes:
            if episode.episode_id == episode_id:
                return episode
        return None


# ---------------------------------------------------------------------------
# GenerationJob
# ---------------------------------------------------------------------------


class GenerationJob(Aggregate):
    """Uma geração opcional enviada a um provedor externo (seção 22)."""

    job_id: str = Field(min_length=3, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)
    segment_id: SegmentId
    prompt: ProviderPrompt
    status: GenerationStatus = GenerationStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    output_reference: str = Field(default="", max_length=512)
    error_code: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=1200)
    cost: CostEstimate = Field(default_factory=CostEstimate)

    def mark_submitted(self, when: datetime) -> None:
        if self.status.is_terminal:
            raise DomainRuleViolation(
                "Não é possível reenviar um job já finalizado.", job_id=self.job_id
            )
        self.status = GenerationStatus.SUBMITTED
        self.attempts += 1
        self.submitted_at = when

    def mark_completed(self, when: datetime, *, output_reference: str) -> None:
        self.status = GenerationStatus.COMPLETED
        self.completed_at = when
        self.output_reference = output_reference

    def mark_failed(self, when: datetime, *, code: str, message: str) -> None:
        self.status = GenerationStatus.FAILED
        self.completed_at = when
        self.error_code = code
        self.error_message = message


# ---------------------------------------------------------------------------
# AdaptationProject — raiz da execução
# ---------------------------------------------------------------------------


class AdaptationProject(Aggregate):
    """Uma execução completa do motor, do input ao export.

    É a raiz: nada é gravado em disco que não esteja registrado aqui.
    """

    project_id: ProjectId
    run_id: RunId
    configuration: ProjectConfiguration
    started_at: datetime
    state: PipelineState = PipelineState.DISCOVERING_INPUT
    book: BookSource | None = None
    canon: CanonBible | None = None
    audiovisual_bible: AudiovisualBible | None = None
    production_plan: ProductionPlan | None = None
    packages: tuple[PromptPackage, ...] = Field(default_factory=tuple)
    jobs: tuple[GenerationJob, ...] = Field(default_factory=tuple)
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    reports: tuple[ValidationReport, ...] = Field(default_factory=tuple)
    quality: QualityAssessment | None = None
    rights_risks: tuple[RightsRisk, ...] = Field(default_factory=tuple)
    cost_report: CostReport | None = None
    events: EventLog = Field(default_factory=EventLog)
    repair_iterations: int = Field(default=0, ge=0)
    finished_at: datetime | None = None
    failure_reason: str = Field(default="", max_length=1200)

    # -- máquina de estados ------------------------------------------------

    def transition_to(self, target: PipelineState) -> None:
        """Muda de estado respeitando o grafo de transições permitidas."""
        assert_transition(self.state, target)
        self.state = target

    def fail(self, reason: str, when: datetime) -> None:
        self.transition_to(PipelineState.FAILED)
        self.failure_reason = reason
        self.finished_at = when

    def complete(self, when: datetime) -> None:
        self.transition_to(PipelineState.COMPLETED)
        self.finished_at = when

    # -- eventos -----------------------------------------------------------

    def record(self, event: DomainEvent) -> None:
        self.events.append(event)

    # -- artefatos ---------------------------------------------------------

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts = (*self.artifacts, artifact)

    def add_report(self, report: ValidationReport) -> None:
        self.reports = (*self.reports, report)

    def set_packages(self, packages: tuple[PromptPackage, ...]) -> None:
        self.packages = packages

    def package_for(self, variant: ProductionVariant) -> PromptPackage | None:
        for package in self.packages:
            if package.variant is variant:
                return package
        return None

    # -- consultas ---------------------------------------------------------

    @property
    def output_directory(self) -> str:
        return f"outputs/{self.project_id.value}/{self.run_id.value}"

    @property
    def total_segments(self) -> int:
        return sum(package.segment_count for package in self.packages)

    @property
    def approved(self) -> bool:
        return bool(self.packages) and all(package.approved for package in self.packages)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def content_fingerprint(self) -> ContentHash | None:
        """Hash do material de origem, base do cache e da idempotência."""
        return self.book.canonical_hash if self.book else None


def _assert_unique(values: list[str], label: str) -> None:
    duplicates = {value for value in values if values.count(value) > 1}
    if duplicates:
        raise ValueError(f"Identificadores de {label} duplicados: {sorted(duplicates)}")
