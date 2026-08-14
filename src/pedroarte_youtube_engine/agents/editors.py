"""Editores de formato curto (9.21 e 9.22).

Shorts e trailers não são recortes do vídeo principal: eles reescrevem o
material com regra própria. Estes agentes operam **depois** da construção dos
segmentos, ajustando o que o formato exige — gancho imediato, fechamento,
controle de revelação — sem alterar o cânone.
"""

from __future__ import annotations

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import EpisodePromptSet, PromptPackage
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.services.format_adaptation import (
    FormatAdaptationService,
)
from pedroarte_youtube_engine.domain.validation import IssueCategory, ValidationIssue
from pedroarte_youtube_engine.domain.value_objects import (
    NarrativeFunction,
    ProductionVariant,
    Severity,
)


class ShortsEditorAgent(BaseAgent):
    """`SHORTS_EDITOR_AGENT` — garante verticalidade, gancho e autossuficiência."""

    _contract = AgentContract(
        name="SHORTS_EDITOR_AGENT",
        responsibility=(
            "Selecionar momentos, reformular para vertical, criar gancho imediato, "
            "garantir compreensão independente, controlar duração, criar legendas e "
            "fechamento não invasivo."
        ),
        phase="WRITING_SEGMENTS",
        input_type="PromptPackage",
        output_type="PromptPackage",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "Todo Short usa proporção vertical.",
            "O primeiro segmento tem função de gancho.",
            "O último segmento fecha com pergunta ou convite.",
            "Todo Short tem legendas.",
        ),
        failure_criteria=("Um Short foi produzido em proporção horizontal.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        issues: list[ValidationIssue] = []
        updated: list[PromptPackage] = []

        for package in packages:
            if package.variant is not ProductionVariant.SHORTS:
                updated.append(package)
                continue

            episodes: list[EpisodePromptSet] = []
            for episode in package.episodes:
                if not episode.segments:
                    episodes.append(episode)
                    continue
                segments = self._edit(episode.segments)
                issues.extend(self._audit(episode, segments))
                episodes.append(episode.model_copy(update={"segments": segments}))
            updated.append(package.model_copy(update={"episodes": tuple(episodes)}))

        self._log(context).info(
            "Shorts editados",
            shorts=sum(
                len(package.episodes)
                for package in updated
                if package.variant is ProductionVariant.SHORTS
            ),
            issues=len(issues),
        )
        return self._with_issues(tuple(issues), packages=tuple(updated))

    @staticmethod
    def _edit(segments: tuple[PromptSegment, ...]) -> tuple[PromptSegment, ...]:
        """Impõe a gramática do Short: gancho na abertura, convite no fecho."""
        edited: list[PromptSegment] = []
        last = len(segments) - 1

        for index, segment in enumerate(segments):
            narrative = segment.narrative
            if index == 0:
                narrative = narrative.model_copy(
                    update={
                        "function": NarrativeFunction.HOOK,
                        "purpose": (
                            "Gancho de abertura: o Short começa no meio da ação, sem "
                            "contexto prévio, e precisa ser compreendido por quem nunca "
                            "ouviu falar da obra. "
                            + narrative.purpose
                        )[:800],
                    }
                )
            elif index == last:
                narrative = narrative.model_copy(
                    update={
                        "function": NarrativeFunction.CALL_TO_ACTION,
                        "purpose": (
                            "Fechamento: deixa uma pergunta em aberto e convida ao vídeo "
                            "completo, sem chamada invasiva sobre a imagem. "
                            + narrative.purpose
                        )[:800],
                    }
                )
            edited.append(segment.model_copy(update={"narrative": narrative}))
        return tuple(edited)

    @staticmethod
    def _audit(
        episode: EpisodePromptSet, segments: tuple[PromptSegment, ...]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for segment in segments:
            if not segment.segment_format.aspect_ratio.is_vertical:
                issues.append(
                    make_issue(
                        category=IssueCategory.PROVIDER_INCOMPATIBILITY,
                        severity=Severity.ERROR,
                        message="Short produzido fora da proporção vertical.",
                        responsible_agent="SHORTS_EDITOR_AGENT",
                        variant=ProductionVariant.SHORTS,
                        episode_id=episode.episode_id.value,
                        segment_id=segment.segment_id,
                        field_path="segment_format.aspect_ratio",
                        observed=str(segment.segment_format.aspect_ratio),
                        expected="9:16",
                    )
                )
            if not segment.subtitles and segment.audio.has_spoken_words:
                issues.append(
                    make_issue(
                        category=IssueCategory.ACCESSIBILITY_GAP,
                        severity=Severity.WARNING,
                        message="Short com fala e sem legenda.",
                        responsible_agent="SHORTS_EDITOR_AGENT",
                        variant=ProductionVariant.SHORTS,
                        episode_id=episode.episode_id.value,
                        segment_id=segment.segment_id,
                        field_path="subtitles",
                        suggested_fix="Shorts são assistidos sem som; legenda é obrigatória.",
                    )
                )
        return issues


class TrailerEditorAgent(BaseAgent):
    """`TRAILER_EDITOR_AGENT` — controla revelação, escalada e assinatura final."""

    _contract = AgentContract(
        name="TRAILER_EDITOR_AGENT",
        responsibility=(
            "Selecionar cenas, controlar revelações, criar escalada e montagem, "
            "planejar textos de tela e música, e criar a assinatura final — sem "
            "reutilizar mecanicamente os mesmos segmentos de outros formatos."
        ),
        phase="WRITING_SEGMENTS",
        input_type="PromptPackage",
        output_type="PromptPackage",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "Nenhum trailer exibe clímax, resolução ou epílogo.",
            "Cada trailer tem escalada própria e assinatura final.",
        ),
        failure_criteria=("Um trailer revelou o desfecho da obra.",),
        blocking=False,
    )

    def __init__(self, *, adaptation: FormatAdaptationService | None = None) -> None:
        self._adaptation = adaptation or FormatAdaptationService()

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        forbidden = self._adaptation.forbidden_functions_for(ProductionVariant.TRAILERS)
        issues: list[ValidationIssue] = []
        updated: list[PromptPackage] = []

        for package in packages:
            if package.variant is not ProductionVariant.TRAILERS:
                updated.append(package)
                continue

            episodes: list[EpisodePromptSet] = []
            for episode in package.episodes:
                if not episode.segments:
                    episodes.append(episode)
                    continue
                segments = self._edit(episode.segments, forbidden)
                issues.extend(self._audit(episode, segments, forbidden))
                episodes.append(episode.model_copy(update={"segments": segments}))
            updated.append(package.model_copy(update={"episodes": tuple(episodes)}))

        self._log(context).info("Trailers editados", issues=len(issues))
        return self._with_issues(tuple(issues), packages=tuple(updated))

    @staticmethod
    def _edit(
        segments: tuple[PromptSegment, ...],
        forbidden: frozenset[NarrativeFunction],
    ) -> tuple[PromptSegment, ...]:
        """Escalada crescente, sem entregar o desfecho."""
        edited: list[PromptSegment] = []
        last = len(segments) - 1

        for index, segment in enumerate(segments):
            narrative = segment.narrative
            function = narrative.function

            if function in forbidden:
                # A promessa substitui a entrega.
                function = NarrativeFunction.RISING_ACTION

            if index == last:
                function = NarrativeFunction.CLIFFHANGER
                narrative = narrative.model_copy(
                    update={
                        "purpose": (
                            "Assinatura final: o último quadro corta antes da resposta. "
                            "A promessa é feita; a entrega fica para a obra. "
                            + narrative.purpose
                        )[:800],
                        "information_withheld": (
                            "o desfecho da obra",
                            "a identidade por trás da revelação central",
                            "o resultado do confronto final",
                        ),
                    }
                )

            narrative = narrative.model_copy(
                update={
                    "function": function,
                    "tension": min(10, narrative.tension + index),
                }
            )
            edited.append(segment.model_copy(update={"narrative": narrative}))
        return tuple(edited)

    @staticmethod
    def _audit(
        episode: EpisodePromptSet,
        segments: tuple[PromptSegment, ...],
        forbidden: frozenset[NarrativeFunction],
    ) -> list[ValidationIssue]:
        return [
            make_issue(
                category=IssueCategory.REPEATED_SCENE,
                severity=Severity.ERROR,
                message=(
                    f"Trailer exibe função narrativa proibida: "
                    f"{segment.narrative.function.value}."
                ),
                responsible_agent="TRAILER_EDITOR_AGENT",
                variant=ProductionVariant.TRAILERS,
                episode_id=episode.episode_id.value,
                segment_id=segment.segment_id,
                field_path="narrative.function",
                suggested_fix="Trailers prometem; não entregam o desfecho.",
            )
            for segment in segments
            if segment.narrative.function in forbidden
        ]
