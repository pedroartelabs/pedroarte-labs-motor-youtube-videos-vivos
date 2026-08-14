"""Configuração do projeto (seção 11.2).

A configuração é parte do contrato de domínio: ela decide durações, formatos e
portões de qualidade. Por isso o *shape* vive aqui, tipado e validado. A leitura
de YAML e a mesclagem de arquivos ficam na camada de aplicação.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    Duration,
    Language,
    ProductionVariant,
    Resolution,
)


class ConfigModel(BaseModel):
    """Base das seções de configuração: estrita e imutável."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ProjectSection(ConfigModel):
    title: str = Field(default="", max_length=300)
    author: str = Field(default="", max_length=200)
    language: Language = Field(default_factory=Language.brazilian_portuguese)
    output_language: Language = Field(default_factory=Language.brazilian_portuguese)
    project_slug: str = Field(default="", max_length=120)


class RightsSection(ConfigModel):
    """O operador declara possuir direitos de adaptação. O motor apenas registra."""

    user_confirms_adaptation_rights: bool = False
    rights_holder: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=800)


class FormatsSection(ConfigModel):
    main_10_minutes: bool = True
    shorts: bool = True
    long_form: bool = True
    series: bool = True
    mini_novela: bool = True
    trailers: bool = True

    def enabled_variants(self) -> tuple[ProductionVariant, ...]:
        mapping = (
            (self.main_10_minutes, ProductionVariant.MAIN_10_MINUTES),
            (self.shorts, ProductionVariant.SHORTS),
            (self.long_form, ProductionVariant.LONG_FORM),
            (self.series, ProductionVariant.SERIES),
            (self.mini_novela, ProductionVariant.MINI_NOVELA),
            (self.trailers, ProductionVariant.TRAILERS),
        )
        return tuple(variant for enabled, variant in mapping if enabled)


class SegmentationSection(ConfigModel):
    target_segment_seconds: float = Field(default=10.0, gt=0, le=120)
    allow_provider_recompilation: bool = True

    @property
    def segment_duration(self) -> Duration:
        return Duration.from_seconds(self.target_segment_seconds)


class MainVideoSection(ConfigModel):
    duration_minutes: float = Field(default=10.0, gt=0, le=600)
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.landscape)
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=24, ge=12, le=120)

    @property
    def duration(self) -> Duration:
        return Duration.from_minutes(self.duration_minutes)


class ShortsSection(ConfigModel):
    enabled: bool = True
    quantity: int = Field(default=6, ge=1, le=50)
    duration_profiles: tuple[int, ...] = Field(default=(30, 60))
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.vertical)
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=30, ge=12, le=120)
    profiles: tuple[str, ...] = Field(
        default=(
            "short_de_impacto",
            "short_de_misterio",
            "short_de_personagem",
            "short_de_dialogo",
            "short_de_revelacao",
            "short_de_atmosfera",
            "short_de_convite",
        )
    )

    @model_validator(mode="after")
    def _validate_durations(self) -> Self:
        if not self.duration_profiles:
            raise ValueError("Shorts exigem ao menos um perfil de duração.")
        for seconds in self.duration_profiles:
            if not 5 <= seconds <= 180:
                raise ValueError(f"Duração de Short fora do intervalo aceito: {seconds}s.")
        return self


class LongFormSection(ConfigModel):
    enabled: bool = True
    target_duration_minutes: float = Field(default=36.0, gt=0, le=600)
    minimum_duration_minutes: float = Field(default=31.0, gt=0, le=600)
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.landscape)
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=24, ge=12, le=120)

    @model_validator(mode="after")
    def _validate_minimum(self) -> Self:
        if self.target_duration_minutes < self.minimum_duration_minutes:
            raise ValueError(
                "A duração alvo do formato longo não pode ser menor que o mínimo exigido."
            )
        return self

    @property
    def target_duration(self) -> Duration:
        return Duration.from_minutes(self.target_duration_minutes)

    @property
    def minimum_duration(self) -> Duration:
        return Duration.from_minutes(self.minimum_duration_minutes)


class SeriesSection(ConfigModel):
    enabled: bool = True
    episode_duration_minutes: float = Field(default=8.0, gt=0, le=180)
    min_episodes: int = Field(default=6, ge=1, le=100)
    max_episodes: int = Field(default=12, ge=1, le=100)
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.landscape)
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=24, ge=12, le=120)

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.max_episodes < self.min_episodes:
            raise ValueError("max_episodes não pode ser menor que min_episodes.")
        return self

    @property
    def episode_duration(self) -> Duration:
        return Duration.from_minutes(self.episode_duration_minutes)


class MiniNovelaSection(ConfigModel):
    enabled: bool = True
    episode_duration_minutes: float = Field(default=6.0, gt=0, le=120)
    min_episodes: int = Field(default=5, ge=1, le=100)
    max_episodes: int = Field(default=10, ge=1, le=100)
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.landscape)
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=24, ge=12, le=120)

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.max_episodes < self.min_episodes:
            raise ValueError("max_episodes não pode ser menor que min_episodes.")
        return self

    @property
    def episode_duration(self) -> Duration:
        return Duration.from_minutes(self.episode_duration_minutes)


class TrailerSpec(ConfigModel):
    slug: str = Field(min_length=3, max_length=64)
    label: str = Field(min_length=3, max_length=120)
    duration_seconds: int = Field(ge=5, le=300)
    strategy: str = Field(min_length=3, max_length=400)
    aspect_ratio: AspectRatio = Field(default_factory=AspectRatio.landscape)


DEFAULT_TRAILERS: tuple[TrailerSpec, ...] = (
    TrailerSpec(
        slug="teaser_20_segundos",
        label="Teaser de 20 segundos",
        duration_seconds=20,
        strategy="Uma única imagem-conceito, uma pergunta e nenhuma resposta.",
    ),
    TrailerSpec(
        slug="trailer_60_segundos",
        label="Trailer de 60 segundos",
        duration_seconds=60,
        strategy="Premissa, conflito e escalada, cortando antes da revelação central.",
    ),
    TrailerSpec(
        slug="trailer_120_segundos",
        label="Trailer de 120 segundos",
        duration_seconds=120,
        strategy="Três atos comprimidos com respiro no meio e assinatura sonora final.",
    ),
    TrailerSpec(
        slug="trailer_personagem",
        label="Trailer de personagem",
        duration_seconds=60,
        strategy="Retrato de um único protagonista pelo que ele teme perder.",
    ),
    TrailerSpec(
        slug="trailer_atmosferico",
        label="Trailer atmosférico",
        duration_seconds=40,
        strategy="Ambiente, textura e som; quase sem enredo explícito.",
    ),
    TrailerSpec(
        slug="trailer_historia",
        label="Trailer de história",
        duration_seconds=90,
        strategy="Linha narrativa clara, do incidente incitante à promessa do clímax.",
    ),
)


class TrailersSection(ConfigModel):
    enabled: bool = True
    specs: tuple[TrailerSpec, ...] = DEFAULT_TRAILERS
    resolution: Resolution = Field(default_factory=lambda: Resolution.parse("1080p"))
    frame_rate: int = Field(default=24, ge=12, le=120)


class AudioSection(ConfigModel):
    spoken_language: Language = Field(default_factory=Language.brazilian_portuguese)
    narration_enabled: bool = True
    dialogue_enabled: bool = True
    music_enabled: bool = True
    ambient_sound_enabled: bool = True
    sound_effects_enabled: bool = True
    speech_rate_wpm: float = Field(default=150.0, gt=60, le=280)


class ProvidersSection(ConfigModel):
    prompt_target: str = Field(default="generic", max_length=64)
    video_provider: str | None = None
    image_provider: str | None = None
    audio_provider: str | None = None
    execute_generation: bool = False
    max_budget_usd: float = Field(default=0.0, ge=0.0)
    allowed_models: tuple[str, ...] = Field(default_factory=tuple)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=2.0, ge=0.0, le=120.0)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def _validate_execution_preconditions(self) -> Self:
        """A execução real exige orçamento e allowlist de modelos (seção 22)."""
        if self.execute_generation:
            if self.max_budget_usd <= 0:
                raise ValueError(
                    "execute_generation exige max_budget_usd maior que zero."
                )
            if not self.allowed_models:
                raise ValueError(
                    "execute_generation exige uma allowlist explícita em allowed_models."
                )
        return self


class QualitySection(ConfigModel):
    max_repair_iterations: int = Field(default=3, ge=0, le=10)
    fail_on_critical_issue: bool = True
    minimum_approval_score: float = Field(default=0.90, ge=0.0, le=1.0)


class RagSection(ConfigModel):
    enabled: bool = True
    retrieval_mode: str = Field(default="hybrid", pattern=r"^(hybrid|lexical|vector)$")
    top_k: int = Field(default=8, ge=1, le=100)
    chunk_target_words: int = Field(default=280, ge=50, le=2000)
    chunk_overlap_words: int = Field(default=40, ge=0, le=500)
    embedding_dimensions: int = Field(default=256, ge=32, le=4096)
    lexical_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class McpSection(ConfigModel):
    enabled: bool = True
    allowed_roots: tuple[str, ...] = Field(default=("./input", "./outputs", "./examples"))
    max_payload_bytes: int = Field(default=1_048_576, ge=1024)


class OutputSection(ConfigModel):
    write_segment_directories: bool = True
    write_jsonl: bool = True
    write_shotlist_csv: bool = True
    write_subtitles: bool = True
    pretty_json: bool = True


class ProjectConfiguration(ConfigModel):
    """Configuração completa de uma execução."""

    project: ProjectSection = Field(default_factory=ProjectSection)
    rights: RightsSection = Field(default_factory=RightsSection)
    formats: FormatsSection = Field(default_factory=FormatsSection)
    segmentation: SegmentationSection = Field(default_factory=SegmentationSection)
    main_video: MainVideoSection = Field(default_factory=MainVideoSection)
    shorts: ShortsSection = Field(default_factory=ShortsSection)
    long_form: LongFormSection = Field(default_factory=LongFormSection)
    series: SeriesSection = Field(default_factory=SeriesSection)
    mini_novela: MiniNovelaSection = Field(default_factory=MiniNovelaSection)
    trailers: TrailersSection = Field(default_factory=TrailersSection)
    audio: AudioSection = Field(default_factory=AudioSection)
    providers: ProvidersSection = Field(default_factory=ProvidersSection)
    quality: QualitySection = Field(default_factory=QualitySection)
    rag: RagSection = Field(default_factory=RagSection)
    mcp: McpSection = Field(default_factory=McpSection)
    output: OutputSection = Field(default_factory=OutputSection)

    @model_validator(mode="after")
    def _validate_segmentation_fits(self) -> Self:
        """Toda duração alvo tem de ser múltipla da duração de segmento.

        Sem isso o vídeo principal não fecharia *exatamente* nos 600 segundos
        exigidos pela Definition of Done.
        """
        segment_ms = self.segmentation.segment_duration.milliseconds
        checks: list[tuple[str, int]] = [
            ("main_video.duration_minutes", self.main_video.duration.milliseconds),
            ("long_form.target_duration_minutes", self.long_form.target_duration.milliseconds),
            ("series.episode_duration_minutes", self.series.episode_duration.milliseconds),
            (
                "mini_novela.episode_duration_minutes",
                self.mini_novela.episode_duration.milliseconds,
            ),
        ]
        for label, total_ms in checks:
            if total_ms % segment_ms != 0:
                raise ValueError(
                    f"{label} ({total_ms / 1000:.1f}s) não é múltiplo da duração de segmento "
                    f"({segment_ms / 1000:.1f}s). Ajuste a duração ou "
                    "segmentation.target_segment_seconds."
                )
        for seconds in self.shorts.duration_profiles:
            if (seconds * 1000) % segment_ms != 0:
                raise ValueError(
                    f"Perfil de Short de {seconds}s não é múltiplo da duração de segmento."
                )
        for spec in self.trailers.specs:
            if (spec.duration_seconds * 1000) % segment_ms != 0:
                raise ValueError(
                    f"Trailer {spec.slug} ({spec.duration_seconds}s) não é múltiplo da "
                    "duração de segmento."
                )
        return self

    def resolved_slug(self) -> str:
        from pedroarte_youtube_engine.shared.text import safe_slug

        if self.project.project_slug:
            return safe_slug(self.project.project_slug)
        if self.project.title:
            return safe_slug(self.project.title)
        return "projeto-sem-titulo"
