"""Planejamento de duração e segmentação.

Este serviço é responsável pela promessa mais concreta da Definition of Done:
*o vídeo principal possui exatamente a duração configurada*. Ele nunca aproxima
— ou a duração fecha em segmentos inteiros, ou o perfil é rejeitado.
"""

from __future__ import annotations

from dataclasses import dataclass

from pedroarte_youtube_engine.domain.configuration import ProjectConfiguration
from pedroarte_youtube_engine.domain.production import FormatProfile
from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    Duration,
    FrameRate,
    Language,
    ProductionVariant,
    Resolution,
    TimeRange,
    Timecode,
)
from pedroarte_youtube_engine.shared.errors import DomainRuleViolation


@dataclass(frozen=True, slots=True)
class EpisodeSlot:
    """Uma fatia de tempo reservada para um episódio dentro de um formato."""

    number: int
    duration: Duration
    segment_count: int


class DurationPlanningService:
    """Converte a configuração em perfis de formato coerentes."""

    def build_profiles(self, configuration: ProjectConfiguration) -> tuple[FormatProfile, ...]:
        """Constrói todos os perfis habilitados na configuração."""
        segment = configuration.segmentation.segment_duration
        language = configuration.project.output_language
        enabled = configuration.formats.enabled_variants()
        profiles: list[FormatProfile] = []

        if ProductionVariant.MAIN_10_MINUTES in enabled:
            profiles.append(self._main_profile(configuration, segment, language))
        if ProductionVariant.SHORTS in enabled and configuration.shorts.enabled:
            profiles.extend(self._shorts_profiles(configuration, segment, language))
        if ProductionVariant.LONG_FORM in enabled and configuration.long_form.enabled:
            profiles.append(self._long_form_profile(configuration, segment, language))
        if ProductionVariant.SERIES in enabled and configuration.series.enabled:
            profiles.append(self._series_profile(configuration, segment, language))
        if ProductionVariant.MINI_NOVELA in enabled and configuration.mini_novela.enabled:
            profiles.append(self._mini_novela_profile(configuration, segment, language))
        if ProductionVariant.TRAILERS in enabled and configuration.trailers.enabled:
            profiles.extend(self._trailer_profiles(configuration, segment, language))

        return tuple(profiles)

    # -- perfis por formato ------------------------------------------------

    def _main_profile(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> FormatProfile:
        section = configuration.main_video
        return FormatProfile(
            profile_id="main10",
            variant=ProductionVariant.MAIN_10_MINUTES,
            label="Vídeo principal de 10 minutos",
            directory=ProductionVariant.MAIN_10_MINUTES.directory,
            total_duration=section.duration,
            segment_duration=segment,
            aspect_ratio=section.aspect_ratio,
            resolution=section.resolution.oriented(section.aspect_ratio),
            frame_rate=FrameRate(fps=section.frame_rate),
            language=language,
            narration_enabled=configuration.audio.narration_enabled,
            dialogue_enabled=configuration.audio.dialogue_enabled,
            music_enabled=configuration.audio.music_enabled,
            ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
            sound_effects_enabled=configuration.audio.sound_effects_enabled,
            strategy_note=(
                "História condensada e autossuficiente: porta de entrada do universo da obra."
            ),
        )

    def _shorts_profiles(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> list[FormatProfile]:
        section = configuration.shorts
        profiles: list[FormatProfile] = []
        for index in range(section.quantity):
            seconds = section.duration_profiles[index % len(section.duration_profiles)]
            short_kind = section.profiles[index % len(section.profiles)]
            profiles.append(
                FormatProfile(
                    profile_id=f"short_{index + 1:02d}_{short_kind}",
                    variant=ProductionVariant.SHORTS,
                    label=f"Short {index + 1:02d} — {short_kind.replace('_', ' ')} ({seconds}s)",
                    directory=ProductionVariant.SHORTS.directory,
                    total_duration=Duration.from_seconds(seconds),
                    segment_duration=segment,
                    aspect_ratio=section.aspect_ratio,
                    resolution=section.resolution.oriented(section.aspect_ratio),
                    frame_rate=FrameRate(fps=section.frame_rate),
                    language=language,
                    narration_enabled=configuration.audio.narration_enabled,
                    dialogue_enabled=configuration.audio.dialogue_enabled,
                    music_enabled=configuration.audio.music_enabled,
                    ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
                    sound_effects_enabled=configuration.audio.sound_effects_enabled,
                    strategy_note=(
                        f"Perfil '{short_kind.replace('_', ' ')}': gancho imediato, "
                        "compreensão independente e fechamento com pergunta ou convite."
                    ),
                )
            )
        return profiles

    def _long_form_profile(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> FormatProfile:
        section = configuration.long_form
        return FormatProfile(
            profile_id="long36",
            variant=ProductionVariant.LONG_FORM,
            label=f"Vídeo longo de {section.target_duration_minutes:.0f} minutos",
            directory=ProductionVariant.LONG_FORM.directory,
            total_duration=section.target_duration,
            minimum_duration=section.minimum_duration,
            segment_duration=segment,
            aspect_ratio=section.aspect_ratio,
            resolution=section.resolution.oriented(section.aspect_ratio),
            frame_rate=FrameRate(fps=section.frame_rate),
            language=language,
            narration_enabled=configuration.audio.narration_enabled,
            dialogue_enabled=configuration.audio.dialogue_enabled,
            music_enabled=configuration.audio.music_enabled,
            ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
            sound_effects_enabled=configuration.audio.sound_effects_enabled,
            strategy_note=(
                "Adaptação longa com atos, subtramas, cenas de respiro e epílogo próprios — "
                "nunca uma versão esticada do vídeo de dez minutos."
            ),
        )

    def _series_profile(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> FormatProfile:
        section = configuration.series
        return FormatProfile(
            profile_id="series",
            variant=ProductionVariant.SERIES,
            label=f"Série — episódios de {section.episode_duration_minutes:.0f} minutos",
            directory=ProductionVariant.SERIES.directory,
            total_duration=section.episode_duration,
            segment_duration=segment,
            aspect_ratio=section.aspect_ratio,
            resolution=section.resolution.oriented(section.aspect_ratio),
            frame_rate=FrameRate(fps=section.frame_rate),
            language=language,
            narration_enabled=configuration.audio.narration_enabled,
            dialogue_enabled=configuration.audio.dialogue_enabled,
            music_enabled=configuration.audio.music_enabled,
            ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
            sound_effects_enabled=configuration.audio.sound_effects_enabled,
            strategy_note="Temporada com arcos, ganchos e progressão entre episódios.",
        )

    def _mini_novela_profile(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> FormatProfile:
        section = configuration.mini_novela
        return FormatProfile(
            profile_id="mininovela",
            variant=ProductionVariant.MINI_NOVELA,
            label=f"Mini-novela — capítulos de {section.episode_duration_minutes:.0f} minutos",
            directory=ProductionVariant.MINI_NOVELA.directory,
            total_duration=section.episode_duration,
            segment_duration=segment,
            aspect_ratio=section.aspect_ratio,
            resolution=section.resolution.oriented(section.aspect_ratio),
            frame_rate=FrameRate(fps=section.frame_rate),
            language=language,
            narration_enabled=configuration.audio.narration_enabled,
            dialogue_enabled=configuration.audio.dialogue_enabled,
            music_enabled=configuration.audio.music_enabled,
            ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
            sound_effects_enabled=configuration.audio.sound_effects_enabled,
            strategy_note=(
                "Ênfase em personagens, relações e revelações; estrutura dramática mínima "
                "em seis passos por capítulo."
            ),
        )

    def _trailer_profiles(
        self, configuration: ProjectConfiguration, segment: Duration, language: Language
    ) -> list[FormatProfile]:
        section = configuration.trailers
        profiles: list[FormatProfile] = []
        for spec in section.specs:
            profiles.append(
                FormatProfile(
                    profile_id=f"trailer_{spec.slug}",
                    variant=ProductionVariant.TRAILERS,
                    label=spec.label,
                    directory=f"{ProductionVariant.TRAILERS.directory}/{spec.slug}",
                    total_duration=Duration.from_seconds(spec.duration_seconds),
                    segment_duration=segment,
                    aspect_ratio=spec.aspect_ratio,
                    resolution=section.resolution.oriented(spec.aspect_ratio),
                    frame_rate=FrameRate(fps=section.frame_rate),
                    language=language,
                    narration_enabled=configuration.audio.narration_enabled,
                    dialogue_enabled=configuration.audio.dialogue_enabled,
                    music_enabled=configuration.audio.music_enabled,
                    ambient_sound_enabled=configuration.audio.ambient_sound_enabled,
                    sound_effects_enabled=configuration.audio.sound_effects_enabled,
                    strategy_note=spec.strategy,
                )
            )
        return profiles

    # -- distribuição em episódios ----------------------------------------

    def plan_episode_slots(
        self,
        *,
        profile: FormatProfile,
        episode_count: int,
    ) -> tuple[EpisodeSlot, ...]:
        """Distribui um formato episódico em episódios de duração igual."""
        if episode_count < 1:
            raise DomainRuleViolation("Um formato episódico exige ao menos um episódio.")
        return tuple(
            EpisodeSlot(
                number=number,
                duration=profile.total_duration,
                segment_count=profile.segment_count,
            )
            for number in range(1, episode_count + 1)
        )

    def choose_episode_count(
        self,
        *,
        beat_count: int,
        minimum: int,
        maximum: int,
        beats_per_episode: int = 6,
    ) -> int:
        """Escolhe quantos episódios a obra comporta, dentro dos limites.

        A regra evita dois defeitos opostos: episódios vazios (poucos beats
        esticados) e episódios atropelados (muitos beats comprimidos).
        """
        if minimum > maximum:
            raise DomainRuleViolation("O mínimo de episódios excede o máximo configurado.")
        natural = max(1, round(beat_count / max(1, beats_per_episode)))
        return max(minimum, min(maximum, natural))

    # -- segmentação -------------------------------------------------------

    def segment_ranges(self, profile: FormatProfile) -> tuple[TimeRange, ...]:
        """Divide a duração total em intervalos contíguos e exatos.

        A soma dos intervalos é idêntica à duração total — não aproximadamente
        idêntica. É esta função que sustenta o teste de propriedade
        `test_segment_ranges_sum_to_total`.
        """
        if not profile.has_exact_segmentation:
            raise DomainRuleViolation(
                f"O perfil {profile.profile_id} não fecha em segmentos inteiros.",
                total_ms=profile.total_duration.milliseconds,
                segment_ms=profile.segment_duration.milliseconds,
            )
        step = profile.segment_duration.milliseconds
        return tuple(
            TimeRange(
                start=Timecode(milliseconds=offset),
                end=Timecode(milliseconds=offset + step),
            )
            for offset in range(0, profile.total_duration.milliseconds, step)
        )

    def offset_ranges(self, ranges: tuple[TimeRange, ...], offset: Duration) -> tuple[TimeRange, ...]:
        """Desloca um conjunto de intervalos, preservando durações."""
        return tuple(
            TimeRange(
                start=Timecode(milliseconds=item.start.milliseconds + offset.milliseconds),
                end=Timecode(milliseconds=item.end.milliseconds + offset.milliseconds),
            )
            for item in ranges
        )

    @staticmethod
    def describe(profile: FormatProfile) -> str:
        return (
            f"{profile.label}: {profile.total_duration.human()} em "
            f"{profile.segment_count} segmentos de {profile.segment_duration.human()} "
            f"({profile.aspect_ratio}, {profile.resolution})"
        )

    @staticmethod
    def oriented_resolution(resolution: Resolution, aspect: AspectRatio) -> Resolution:
        return resolution.oriented(aspect)
