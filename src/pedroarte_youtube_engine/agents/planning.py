"""Agentes de planejamento (9.8 a 9.12).

Aqui a obra vira estrutura: perfis de formato, temporadas, episódios, sequências
e cenas — todos fechando exatamente na duração configurada.
"""

from __future__ import annotations

import math

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import CanonBible, ProductionPlan
from pedroarte_youtube_engine.domain.canon import NarrativeBeat
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.production import (
    AdaptationDecision,
    Episode,
    FormatProfile,
    Scene,
    SceneKind,
    SeasonPlan,
    Sequence,
)
from pedroarte_youtube_engine.domain.services.duration_planning import (
    DurationPlanningService,
)
from pedroarte_youtube_engine.domain.services.format_adaptation import (
    FormatAdaptationService,
)
from pedroarte_youtube_engine.domain.value_objects import (
    EmotionalTone,
    EpisodeId,
    NarrativeFunction,
    ProductionVariant,
    SceneId,
    SequenceId,
    TimeRange,
)
from pedroarte_youtube_engine.shared.errors import DomainRuleViolation
from pedroarte_youtube_engine.shared.text import first_sentence, safe_slug

#: Quantos segmentos, em média, uma cena ocupa em cada formato.
_SEGMENTS_PER_SCENE: dict[ProductionVariant, int] = {
    ProductionVariant.MAIN_10_MINUTES: 4,
    ProductionVariant.LONG_FORM: 6,
    ProductionVariant.SERIES: 4,
    ProductionVariant.MINI_NOVELA: 3,
    ProductionVariant.SHORTS: 1,
    ProductionVariant.TRAILERS: 1,
}

#: Estrutura de atos por formato: função dramática de cada sequência.
_ACT_STRUCTURES: dict[ProductionVariant, tuple[NarrativeFunction, ...]] = {
    ProductionVariant.MAIN_10_MINUTES: (
        NarrativeFunction.HOOK,
        NarrativeFunction.SETUP,
        NarrativeFunction.RISING_ACTION,
        NarrativeFunction.CONFRONTATION,
        NarrativeFunction.CLIMAX,
        NarrativeFunction.RESOLUTION,
    ),
    ProductionVariant.LONG_FORM: (
        NarrativeFunction.HOOK,
        NarrativeFunction.SETUP,
        NarrativeFunction.INCITING_INCIDENT,
        NarrativeFunction.RISING_ACTION,
        NarrativeFunction.COMPLICATION,
        NarrativeFunction.BREATHING,
        NarrativeFunction.CONFRONTATION,
        NarrativeFunction.REVELATION,
        NarrativeFunction.CLIMAX,
        NarrativeFunction.FALLING_ACTION,
        NarrativeFunction.RESOLUTION,
        NarrativeFunction.EPILOGUE,
    ),
    ProductionVariant.SERIES: (
        NarrativeFunction.HOOK,
        NarrativeFunction.SETUP,
        NarrativeFunction.RISING_ACTION,
        NarrativeFunction.CONFRONTATION,
        NarrativeFunction.CLIFFHANGER,
    ),
    ProductionVariant.MINI_NOVELA: (
        NarrativeFunction.HOOK,
        NarrativeFunction.SETUP,
        NarrativeFunction.COMPLICATION,
        NarrativeFunction.CONFRONTATION,
        NarrativeFunction.REVERSAL,
        NarrativeFunction.CLIFFHANGER,
    ),
    ProductionVariant.SHORTS: (
        NarrativeFunction.HOOK,
        NarrativeFunction.RISING_ACTION,
        NarrativeFunction.REVELATION,
        NarrativeFunction.CALL_TO_ACTION,
    ),
    ProductionVariant.TRAILERS: (
        NarrativeFunction.HOOK,
        NarrativeFunction.RISING_ACTION,
        NarrativeFunction.CLIFFHANGER,
    ),
}


class FormatPlannerAgent(BaseAgent):
    """`FORMAT_PLANNER_AGENT` — calcula durações, segmentos e formato de tela."""

    _contract = AgentContract(
        name="FORMAT_PLANNER_AGENT",
        responsibility=(
            "Planejar vídeo principal, Shorts, vídeo longo, série, mini-novela e "
            "trailers: duração, quantidade de segmentos, proporção, resolução e idioma."
        ),
        phase="PLANNING_FORMATS",
        input_type="ProjectConfiguration",
        output_type="tuple[FormatProfile, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        prompt_name="planning.formats",
        completion_criteria=(
            "Toda duração é múltipla exata da duração de segmento.",
            "Ao menos um formato foi habilitado.",
        ),
        failure_criteria=("Nenhum formato foi habilitado na configuração.",),
    )

    def __init__(self, *, planning: DurationPlanningService | None = None) -> None:
        self._planning = planning or DurationPlanningService()

    def run(self, context: EngineContext) -> AgentResult:
        profiles = self._planning.build_profiles(context.configuration)
        if not profiles:
            raise DomainRuleViolation(
                "Nenhum formato habilitado. Ative ao menos um em `formats:`."
            )

        log = self._log(context)
        for profile in profiles:
            log.debug("Perfil planejado", profile=self._planning.describe(profile))

        log.info(
            "Formatos planejados",
            profiles=len(profiles),
            total_segments=sum(profile.segment_count for profile in profiles),
        )
        return self._ok(profiles=profiles)


class AdaptationArchitectAgent(BaseAgent):
    """`ADAPTATION_ARCHITECT_AGENT` — decide o que preservar, condensar e reorganizar."""

    _contract = AgentContract(
        name="ADAPTATION_ARCHITECT_AGENT",
        responsibility=(
            "Determinar o que preservar, condensar e reorganizar; impedir a perda da "
            "tese central; criar estratégia específica para cada formato e documentar "
            "todas as mudanças relevantes."
        ),
        phase="ADAPTING",
        input_type="CanonBible",
        output_type="tuple[AdaptationDecision, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.CANON,
        prompt_name="adaptation.strategy",
        completion_criteria=(
            "Cada formato tem estratégia distinta e justificada.",
            "A tese central aparece em todas as estratégias.",
        ),
        failure_criteria=("Nenhuma decisão de adaptação foi registrada.",),
    )

    def __init__(self, *, adaptation: FormatAdaptationService | None = None) -> None:
        self._adaptation = adaptation or FormatAdaptationService()

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        profiles: tuple[FormatProfile, ...] = context.scratch["profiles"]
        variants = tuple(dict.fromkeys(profile.variant for profile in profiles))

        decisions: list[AdaptationDecision] = []
        narrative: list[str] = [
            f"# Estratégia de adaptação — «{canon.title}»",
            "",
            f"**Tese central.** {canon.thesis or 'não declarada explicitamente pela obra'}",
            "",
            (
                "Cada formato abaixo recebe uma estratégia própria de seleção de beats. "
                "Nenhum deles é derivado mecanicamente de outro: o vídeo longo não é o "
                "vídeo de dez minutos esticado, e os trailers não reutilizam os mesmos "
                "segmentos do vídeo principal."
            ),
            "",
        ]

        for variant in variants:
            strategy = self._adaptation.strategy_for(variant)
            narrative.append(self._adaptation.describe(variant))
            narrative.append("")
            decisions.append(
                AdaptationDecision(
                    decision_id=f"decision_{safe_slug(variant.value, max_length=60)}",
                    kind="estrategia_de_formato",
                    subject=variant.value,
                    rationale=strategy.rationale,
                    affects_variants=(variant,),
                    preserves_thesis=True,
                )
            )

        forbidden = self._adaptation.forbidden_functions_for(ProductionVariant.TRAILERS)
        if ProductionVariant.TRAILERS in variants:
            decisions.append(
                AdaptationDecision(
                    decision_id="decision_trailer_spoiler_guard",
                    kind="restricao_de_revelacao",
                    subject="trailers",
                    rationale=(
                        "Trailers não exibem "
                        + ", ".join(function.value for function in sorted(forbidden))
                        + ". A promessa é feita sem entregar o desfecho."
                    ),
                    affects_variants=(ProductionVariant.TRAILERS,),
                )
            )

        self._log(context).info("Estratégia de adaptação definida", decisions=len(decisions))
        return self._ok(
            decisions=tuple(decisions), adaptation_strategy="\n".join(narrative)
        )


class SeasonArchitectAgent(BaseAgent):
    """`SEASON_ARCHITECT_AGENT` — divide a obra em episódios com progressão."""

    _contract = AgentContract(
        name="SEASON_ARCHITECT_AGENT",
        responsibility=(
            "Criar a temporada, dividir capítulos, distribuir arcos, criar ganchos e "
            "progressão, evitar episódios redundantes e manter a continuidade."
        ),
        phase="PLANNING_EPISODES",
        input_type="CanonBible",
        output_type="tuple[SeasonPlan, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.CANON,
        prompt_name="planning.season",
        completion_criteria=(
            "A quantidade de episódios respeita os limites configurados.",
            "Cada episódio cobre um trecho distinto da obra.",
        ),
        failure_criteria=("O cânone não tem beats suficientes para uma temporada.",),
        blocking=False,
    )

    def __init__(self, *, planning: DurationPlanningService | None = None) -> None:
        self._planning = planning or DurationPlanningService()

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        configuration = context.configuration
        profiles: tuple[FormatProfile, ...] = context.scratch["profiles"]
        seasons: list[SeasonPlan] = []

        for variant, section in (
            (ProductionVariant.SERIES, configuration.series),
            (ProductionVariant.MINI_NOVELA, configuration.mini_novela),
        ):
            if not any(profile.variant is variant for profile in profiles):
                continue

            episode_count = self._planning.choose_episode_count(
                beat_count=len(canon.beats),
                minimum=section.min_episodes,
                maximum=section.max_episodes,
                beats_per_episode=6 if variant is ProductionVariant.SERIES else 4,
            )
            seasons.append(
                SeasonPlan(
                    season_number=1,
                    title=f"{canon.title} — {_variant_label(variant)}, temporada 1",
                    logline=canon.logline,
                    episode_count=episode_count,
                    arc_summary=self._arc_summary(canon, variant, episode_count),
                    arcs=self._arcs(canon),
                    chapter_distribution=self._distribute(canon, episode_count),
                    progression_note=(
                        "Cada episódio cobre um trecho contíguo da obra e termina em "
                        "gancho. Nenhum episódio repete o conteúdo de outro."
                    ),
                )
            )

        self._log(context).info("Temporadas planejadas", seasons=len(seasons))
        return self._ok(seasons=tuple(seasons))

    @staticmethod
    def _arc_summary(
        canon: CanonBible, variant: ProductionVariant, episode_count: int
    ) -> str:
        leads = ", ".join(character.canonical_name for character in canon.leads()[:3])
        return (
            f"Temporada de {episode_count} episódios centrada em {leads or 'a obra'}. "
            f"O formato {_variant_label(variant)} organiza a progressão por "
            + (
                "escalada de conflito, com cliffhanger ao fim de cada episódio."
                if variant is ProductionVariant.SERIES
                else "relações e revelações, com mudança de estado a cada capítulo."
            )
        )

    @staticmethod
    def _arcs(canon: CanonBible) -> tuple[str, ...]:
        return tuple(
            f"Arco de {character.canonical_name}: {character.arc or 'a definir pela adaptação'}"
            for character in canon.leads()[:4]
        )

    @staticmethod
    def _distribute(canon: CanonBible, episode_count: int) -> dict[str, tuple[int, ...]]:
        chapters = sorted({beat.chapter_index for beat in canon.beats})
        if not chapters:
            return {}
        per_episode = max(1, math.ceil(len(chapters) / episode_count))
        distribution: dict[str, tuple[int, ...]] = {}
        for number in range(1, episode_count + 1):
            start = (number - 1) * per_episode
            distribution[f"episodio_{number:02d}"] = tuple(
                chapters[start : start + per_episode]
            )
        return distribution


class EpisodeArchitectAgent(BaseAgent):
    """`EPISODE_ARCHITECT_AGENT` + `SCENE_DECOMPOSER_AGENT`.

    Constrói episódios completos: sequências com função dramática, cenas
    contíguas e a grade de segmentos que o `SEGMENT_BUILDER` vai preencher.
    """

    _contract = AgentContract(
        name="EPISODE_ARCHITECT_AGENT",
        responsibility=(
            "Criar a estrutura de cada episódio — começo, meio e fim —, organizar os "
            "beats em sequências e cenas contíguas, controlar a duração e criar o "
            "cliffhanger, mantendo a função de cada cena."
        ),
        phase="PLANNING_EPISODES",
        input_type="tuple[FormatProfile, ...]",
        output_type="tuple[Episode, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.CANON,
        prompt_name="planning.episode",
        completion_criteria=(
            "As sequências são contíguas e somam a duração exata do episódio.",
            "Cada cena tem função dramática e beats atribuídos.",
        ),
        failure_criteria=("Um perfil não fecha em segmentos inteiros.",),
    )

    def __init__(
        self,
        *,
        planning: DurationPlanningService | None = None,
        adaptation: FormatAdaptationService | None = None,
    ) -> None:
        self._planning = planning or DurationPlanningService()
        self._adaptation = adaptation or FormatAdaptationService()

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        profiles: tuple[FormatProfile, ...] = context.scratch["profiles"]
        seasons: tuple[SeasonPlan, ...] = context.scratch.get("seasons", ())
        decisions = context.scratch.get("decisions", ())
        strategy_text = context.scratch.get("adaptation_strategy", "")

        by_variant = {season.title.split("—")[0].strip(): season for season in seasons}
        episodes: list[Episode] = []

        for profile in profiles:
            count = self._episode_count_for(profile, seasons)
            for number in range(1, count + 1):
                episodes.append(
                    self._build_episode(
                        canon=canon, profile=profile, number=number, total=count
                    )
                )

        plan = ProductionPlan(
            project_id=context.project_id,
            profiles=profiles,
            episodes=tuple(episodes),
            seasons=seasons,
            decisions=decisions,
            adaptation_strategy=strategy_text,
        )

        self._log(context).info(
            "Episódios planejados",
            episodes=len(episodes),
            profiles=len(profiles),
            segments=plan.total_segment_count,
            seasons=len(by_variant),
        )

        return AgentResult(
            agent=self.name,
            outputs={"production_plan": plan},
            events=(
                DomainEvent(
                    event_type=DomainEventType.PRODUCTION_PLANNED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "profiles": len(profiles),
                        "episodes": len(episodes),
                        "variants": [variant.value for variant in plan.enabled_variants],
                    },
                ),
            ),
        )

    # -- construção --------------------------------------------------------

    @staticmethod
    def _episode_count_for(
        profile: FormatProfile, seasons: tuple[SeasonPlan, ...]
    ) -> int:
        """Formatos episódicos usam o plano de temporada; os demais têm um episódio."""
        if profile.variant is ProductionVariant.SERIES:
            for season in seasons:
                if "Série" in season.title:
                    return season.episode_count
        if profile.variant is ProductionVariant.MINI_NOVELA:
            for season in seasons:
                if "Mini-novela" in season.title:
                    return season.episode_count
        return 1

    def _build_episode(
        self, *, canon: CanonBible, profile: FormatProfile, number: int, total: int
    ) -> Episode:
        ranges = self._planning.segment_ranges(profile)
        scene_span = _SEGMENTS_PER_SCENE.get(profile.variant, 4)
        scene_count = max(1, math.ceil(len(ranges) / scene_span))

        beats = self._adaptation.select_beats(
            canon.beats,
            variant=profile.variant,
            wanted=scene_count,
            offset=self._offset_for(profile, number),
        )
        if not beats:
            beats = canon.beats[:scene_count] or ()

        episode_id = EpisodeId(
            value=f"{safe_slug(profile.profile_id, max_length=90)}_ep{number:02d}"
        )
        functions = _ACT_STRUCTURES.get(
            profile.variant, _ACT_STRUCTURES[ProductionVariant.MAIN_10_MINUTES]
        )

        scenes = self._build_scenes(
            canon=canon,
            profile=profile,
            episode_id=episode_id,
            ranges=ranges,
            beats=beats,
            scene_count=scene_count,
            functions=functions,
        )
        sequences = self._group_sequences(episode_id, scenes, functions)

        covered = tuple(sorted({beat.chapter_index for beat in beats}))
        return Episode(
            episode_id=episode_id,
            variant=profile.variant,
            season_number=1,
            number=number,
            title=self._title(canon, profile, number, total, beats),
            logline=canon.logline[:600],
            synopsis=self._synopsis(beats),
            covered_chapters=covered,
            sequences=sequences,
            total_duration=profile.total_duration,
            hook=first_sentence(beats[0].summary, fallback=beats[0].summary)[:600]
            if beats
            else "",
            cliffhanger=(
                first_sentence(beats[-1].summary, fallback=beats[-1].summary)[:600]
                if beats and profile.variant
                in {ProductionVariant.SERIES, ProductionVariant.MINI_NOVELA}
                else ""
            ),
            recap_needed=number > 1
            and profile.variant in {ProductionVariant.SERIES, ProductionVariant.MINI_NOVELA},
            opening_note=(
                "Abertura de cinco segundos com o motivo sonoro principal."
                if profile.variant in {ProductionVariant.SERIES, ProductionVariant.MINI_NOVELA}
                else ""
            ),
            closing_note=(
                "Encerramento com o tema invertido e chamada para o próximo episódio."
                if profile.variant in {ProductionVariant.SERIES, ProductionVariant.MINI_NOVELA}
                else ""
            ),
        )

    @staticmethod
    def _offset_for(profile: FormatProfile, number: int) -> int:
        """Deslocamento na seleção de beats.

        É o que garante que o Short nº 3 e o Short nº 4 contem momentos
        diferentes, e que o episódio 2 não repita o episódio 1.
        """
        if profile.variant is ProductionVariant.SHORTS:
            # O sufixo numérico do profile_id (`short_03_...`) determina a janela.
            parts = profile.profile_id.split("_")
            return int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() else 0
        if profile.variant is ProductionVariant.TRAILERS:
            return abs(hash(profile.profile_id)) % 5
        return number - 1

    def _build_scenes(
        self,
        *,
        canon: CanonBible,
        profile: FormatProfile,
        episode_id: EpisodeId,
        ranges: tuple[TimeRange, ...],
        beats: tuple[NarrativeBeat, ...],
        scene_count: int,
        functions: tuple[NarrativeFunction, ...],
    ) -> tuple[Scene, ...]:
        """Distribui os segmentos entre cenas contíguas, sem sobra nem lacuna."""
        base = len(ranges) // scene_count
        remainder = len(ranges) % scene_count

        scenes: list[Scene] = []
        cursor = 0
        for index in range(scene_count):
            span = base + (1 if index < remainder else 0)
            if span == 0:
                continue
            block = ranges[cursor : cursor + span]
            cursor += span

            beat = beats[index % len(beats)] if beats else None
            location = canon.location(beat.location_id) if beat and beat.location_id else None
            function = functions[min(index * len(functions) // scene_count, len(functions) - 1)]

            scenes.append(
                Scene(
                    scene_id=SceneId(value=f"{episode_id.value}_scene_{index + 1:03d}"),
                    sequence_id=SequenceId(
                        value=f"{episode_id.value}_seq_{_sequence_index(index, scene_count, functions):02d}"
                    ),
                    order=index,
                    kind=_scene_kind(beat),
                    title=(
                        first_sentence(beat.summary, fallback=beat.summary)[:200]
                        if beat
                        else f"Cena {index + 1}"
                    ),
                    summary=beat.summary if beat else "Cena de transição narrativa.",
                    location_id=beat.location_id if beat else None,
                    location_name=location.canonical_name if location else "",
                    time_of_day=location.default_time_of_day if location else "indefinido",
                    weather=location.default_weather if location else "indefinido",
                    participants=beat.participants if beat else (),
                    beat_ids=(beat.beat_id,) if beat else (),
                    range=TimeRange(start=block[0].start, end=block[-1].end),
                    tone_start=beat.tone_start if beat else EmotionalTone.NEUTRAL,
                    tone_end=beat.tone_end if beat else EmotionalTone.NEUTRAL,
                    dramatic_function=function,
                    dialogue_excerpts=beat.dialogue_excerpts if beat else (),
                    references=beat.references if beat else (),
                )
            )
        return tuple(scenes)

    @staticmethod
    def _group_sequences(
        episode_id: EpisodeId,
        scenes: tuple[Scene, ...],
        functions: tuple[NarrativeFunction, ...],
    ) -> tuple[Sequence, ...]:
        """Agrupa cenas contíguas que compartilham o mesmo `sequence_id`."""
        grouped: dict[str, list[Scene]] = {}
        for scene in scenes:
            grouped.setdefault(scene.sequence_id.value, []).append(scene)

        sequences: list[Sequence] = []
        for order, (sequence_key, members) in enumerate(sorted(grouped.items())):
            renumbered = tuple(
                scene.model_copy(update={"order": position})
                for position, scene in enumerate(members)
            )
            function = renumbered[0].dramatic_function
            sequences.append(
                Sequence(
                    sequence_id=SequenceId(value=sequence_key),
                    episode_id=episode_id,
                    order=order,
                    title=f"{function.value.replace('_', ' ').capitalize()}",
                    dramatic_function=function,
                    summary=renumbered[0].summary,
                    scenes=renumbered,
                    range=TimeRange(
                        start=renumbered[0].range.start, end=renumbered[-1].range.end
                    ),
                )
            )
        return tuple(sequences)

    @staticmethod
    def _title(
        canon: CanonBible,
        profile: FormatProfile,
        number: int,
        total: int,
        beats: tuple[NarrativeBeat, ...],
    ) -> str:
        if total > 1:
            return f"{canon.title} — Episódio {number:02d}"
        if profile.variant is ProductionVariant.SHORTS:
            return f"{canon.title} — {profile.label}"
        if profile.variant is ProductionVariant.TRAILERS:
            return f"{canon.title} — {profile.label}"
        return f"{canon.title} — {profile.label}"

    @staticmethod
    def _synopsis(beats: tuple[NarrativeBeat, ...]) -> str:
        return " ".join(
            first_sentence(beat.summary, fallback=beat.summary) for beat in beats[:6]
        )[:2400]


def _sequence_index(
    scene_index: int, scene_count: int, functions: tuple[NarrativeFunction, ...]
) -> int:
    """Mapeia uma cena para a sequência (ato) correspondente."""
    return min(scene_index * len(functions) // max(1, scene_count), len(functions) - 1)


def _scene_kind(beat: NarrativeBeat | None) -> SceneKind:
    if beat is None:
        return SceneKind.TRANSITION
    if beat.dialogue_excerpts:
        return SceneKind.DIALOGUE
    if beat.information_revealed:
        return SceneKind.REVELATION
    if beat.tension >= 5:
        return SceneKind.ACTION
    if beat.tension == 0:
        return SceneKind.BREATHING
    return SceneKind.ESTABLISHING


def _variant_label(variant: ProductionVariant) -> str:
    return {
        ProductionVariant.SERIES: "Série",
        ProductionVariant.MINI_NOVELA: "Mini-novela",
    }.get(variant, variant.value)
