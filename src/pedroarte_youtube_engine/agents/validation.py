"""Agentes de validação e portões de qualidade (9.16, 9.25, 9.26, 9.31)."""

from __future__ import annotations

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import PromptPackage
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.production import FormatProfile
from pedroarte_youtube_engine.domain.provider import ProviderCapability
from pedroarte_youtube_engine.domain.segment import PromptSegment, SegmentValidationFlags
from pedroarte_youtube_engine.domain.services.audio_completeness import (
    AudioCompletenessService,
)
from pedroarte_youtube_engine.domain.services.canon_consistency import (
    CanonConsistencyService,
)
from pedroarte_youtube_engine.domain.services.continuity import (
    CharacterContinuityService,
    VisualContinuityService,
    VoiceContinuityService,
)
from pedroarte_youtube_engine.domain.services.narrative_coverage import (
    NarrativeCoverageService,
)
from pedroarte_youtube_engine.domain.services.prompt_completeness import (
    PromptCompletenessService,
)
from pedroarte_youtube_engine.domain.services.provider_capability import (
    ProviderCapabilityMatchingService,
)
from pedroarte_youtube_engine.domain.services.timeline_consistency import (
    TimelineConsistencyService,
)
from pedroarte_youtube_engine.domain.validation import (
    QualityAssessment,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Severity


class QualityGateAgent(BaseAgent):
    """Executa todos os gates de qualidade e marca cada segmento.

    Reúne `CANON_GUARDIAN_AGENT`, `AUDIOVISUAL_QUALITY_GUARDIAN_AGENT` e
    `VISUAL_CONTINUITY_AGENT` numa única passagem sobre os pacotes, porque os
    três precisam ver exatamente o mesmo estado — rodá-los em momentos
    diferentes permitiria que um validasse um artefato que o outro já mudou.
    """

    _contract = AgentContract(
        name="AUDIOVISUAL_QUALITY_GUARDIAN_AGENT",
        responsibility=(
            "Verificar completude visual e sonora, voz, câmera, iluminação, "
            "continuidade, duração, transição, ausência de placeholders, aderência ao "
            "cânone e compatibilidade com o provedor."
        ),
        phase="VALIDATING",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[ValidationReport, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.FULL,
        prompt_name="validation.audiovisual_quality",
        completion_criteria=(
            "Todos os gates foram executados sobre todos os segmentos.",
            "Cada segmento recebeu marcação de validação.",
        ),
        failure_criteria=("Um gate não pôde ser executado por falta de estado.",),
    )

    def __init__(self, *, speech_rate_wpm: float = 150.0) -> None:
        self._audio = AudioCompletenessService(speech_rate_wpm=speech_rate_wpm)
        self._prompt = PromptCompletenessService()
        self._timeline = TimelineConsistencyService()
        self._visual = VisualContinuityService()
        self._character = CharacterContinuityService()
        self._voice = VoiceContinuityService()
        self._canon = CanonConsistencyService()
        self._coverage = NarrativeCoverageService()
        self._provider = ProviderCapabilityMatchingService()

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        canon = context.require_canon()
        bible = context.require_bible()
        plan = context.require_plan()
        capability: ProviderCapability = context.scratch["video_capability"]
        log = self._log(context)

        reports: list[ValidationReport] = []
        marked_packages: list[PromptPackage] = []

        for package in packages:
            all_segments = package.all_segments()

            package_reports = [
                self._audio.validate_many(all_segments),
                self._prompt.validate_many(all_segments),
                self._character.validate(all_segments, canon),
                self._voice.validate(all_segments, bible),
                self._canon.validate(all_segments, canon),
                self._provider.validate_many(all_segments, capability),
                self._coverage.validate(all_segments, canon, variant=package.variant),
            ]

            for episode in package.episodes:
                profile = plan.profile(episode.profile_id)
                if profile is not None:
                    package_reports.append(
                        self._timeline.validate(
                            episode.segments,
                            profile=profile,
                            episode_id=episode.episode_id.value,
                        )
                    )
                package_reports.append(self._visual.validate_chain(episode.segments))

            reports.extend(package_reports)
            marked_packages.append(
                self._mark_segments(package, package_reports, plan.profile)
            )

        blocking = sum(len(report.blocking_issues) for report in reports)
        log.info(
            "Gates de qualidade executados",
            gates=len(reports),
            blocking_issues=blocking,
            warnings=sum(len(report.warnings) for report in reports),
        )
        context.metrics.increment("validation_issues", blocking)

        events: list[DomainEvent] = [
            DomainEvent(
                event_type=DomainEventType.QUALITY_GATE_EVALUATED,
                occurred_at=context.clock.now(),
                run_id=context.run_id.value,
                project_id=context.project_id.value,
                emitted_by=self.name,
                payload={"gates": len(reports), "blocking_issues": blocking},
            )
        ]
        if blocking:
            events.append(
                DomainEvent(
                    event_type=DomainEventType.CONTINUITY_VIOLATION_DETECTED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={"issues": blocking},
                )
            )

        return AgentResult(
            agent=self.name,
            succeeded=True,
            outputs={"packages": tuple(marked_packages), "reports": tuple(reports)},
            issues=tuple(issue for report in reports for issue in report.issues),
            events=tuple(events),
        )

    def _mark_segments(
        self,
        package: PromptPackage,
        reports: list[ValidationReport],
        profile_lookup: object,
    ) -> PromptPackage:
        """Anota em cada segmento o resultado dos gates que o mencionam."""
        by_segment: dict[str, list[ValidationIssue]] = {}
        global_blocking = False

        for report in reports:
            for issue in report.issues:
                if issue.segment_id is None:
                    if issue.blocks_approval:
                        global_blocking = True
                    continue
                by_segment.setdefault(issue.segment_id.value, []).append(issue)

        episodes = []
        for episode in package.episodes:
            segments = []
            for segment in episode.segments:
                issues = by_segment.get(segment.segment_id.value, [])
                segments.append(
                    segment.with_validation(
                        self._flags_for(segment, issues, global_blocking)
                    )
                )
            episodes.append(episode.model_copy(update={"segments": tuple(segments)}))
        return package.model_copy(update={"episodes": tuple(episodes)})

    @staticmethod
    def _flags_for(
        segment: PromptSegment,
        issues: list[ValidationIssue],
        global_blocking: bool,
    ) -> SegmentValidationFlags:
        blocking = [issue for issue in issues if issue.blocks_approval]
        categories = {issue.category.value for issue in blocking}

        audio_bad = any(
            "audio" in category or "voz" in category or "fala" in category
            for category in categories
        )
        video_bad = any(
            category
            in {
                "campo_visual_ausente",
                "prompt_abstrato_demais",
                "uso_de_placeholder",
                "camera_impossivel",
                "personagem_sem_identidade",
            }
            for category in categories
        )
        canon_bad = "contradicao_com_o_livro" in categories
        continuity_bad = any(
            category
            in {
                "quebra_de_continuidade",
                "mudanca_fisica_nao_explicada",
                "objeto_desaparecendo",
                "mudanca_de_ambiente_sem_transicao",
                "luz_incompativel",
            }
            for category in categories
        )
        duration_bad = any(
            category in {"timecode_inconsistente", "duracao_total_incorreta"}
            for category in categories
        )

        flags = SegmentValidationFlags(
            audio_complete=not audio_bad,
            video_complete=not video_bad,
            canon_valid=not canon_bad,
            continuity_valid=not continuity_bad,
            duration_valid=not duration_bad and not global_blocking,
        )
        return flags.approve()


class FinalQaAgent(BaseAgent):
    """`FINAL_QA_AGENT` — consolida os gates e emite o veredito."""

    _contract = AgentContract(
        name="FINAL_QA_AGENT",
        responsibility=(
            "Consolidar as validações, bloquear artefatos incompletos, emitir score, "
            "lista de erros e lista de advertências, e aprovar ou rejeitar o pacote."
        ),
        phase="VALIDATING",
        input_type="tuple[ValidationReport, ...]",
        output_type="QualityAssessment",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.FULL,
        prompt_name="validation.final_qa",
        completion_criteria=(
            "Um veredito foi emitido.",
            "Um problema crítico sempre reprova o pacote.",
        ),
        failure_criteria=("Nenhum relatório foi produzido pelos gates.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        reports: tuple[ValidationReport, ...] = context.scratch["reports"]
        quality = context.configuration.quality
        repairs = int(context.scratch.get("repair_iterations", 0))

        assessment = QualityAssessment.from_reports(
            reports,
            minimum_required=quality.minimum_approval_score,
            repair_iterations=repairs,
            fail_on_critical=quality.fail_on_critical_issue,
        )

        log = self._log(context)
        log.info(
            "Veredito final",
            verdict=assessment.verdict.value,
            score=round(assessment.score, 4),
            minimum=quality.minimum_approval_score,
            blocking=len(assessment.blocking_issues),
            warnings=len(assessment.warnings),
        )

        events: tuple[DomainEvent, ...] = ()
        if assessment.approved:
            events = (
                DomainEvent(
                    event_type=DomainEventType.PROMPT_PACKAGE_APPROVED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "verdict": assessment.verdict.value,
                        "score": assessment.score,
                    },
                ),
            )

        return AgentResult(
            agent=self.name,
            succeeded=True,
            outputs={"quality": assessment},
            issues=assessment.blocking_issues,
            events=events,
        )


class RepairPlannerAgent(BaseAgent):
    """Planeja reparos a partir dos problemas estruturados (seção 10.1).

    O repair loop não reexecuta o pipeline inteiro: ele identifica o agente
    responsável por cada problema reparável e devolve o conjunto mínimo de
    etapas a repetir.
    """

    _contract = AgentContract(
        name="REPAIR_PLANNER_AGENT",
        responsibility=(
            "Converter problemas de validação em um plano de reparo mínimo, "
            "identificando o agente responsável e as etapas a reexecutar."
        ),
        phase="REPAIRING",
        input_type="tuple[ValidationIssue, ...]",
        output_type="RepairPlan",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.FULL,
        completion_criteria=(
            "Todo problema reparável foi atribuído a um agente responsável.",
            "O plano nunca excede o limite de iterações configurado.",
        ),
        failure_criteria=("Um problema bloqueante não é reparável por nenhum agente.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        reports: tuple[ValidationReport, ...] = context.scratch["reports"]
        issues = tuple(
            issue
            for report in reports
            for issue in report.issues
            if issue.blocks_approval
        )

        repairable = tuple(issue for issue in issues if issue.repairable)
        unrepairable = tuple(issue for issue in issues if not issue.repairable)

        by_agent: dict[str, int] = {}
        for issue in repairable:
            by_agent[issue.responsible_agent] = by_agent.get(issue.responsible_agent, 0) + 1

        self._log(context).info(
            "Plano de reparo",
            repairable=len(repairable),
            unrepairable=len(unrepairable),
            agents=sorted(by_agent),
        )

        return AgentResult(
            agent=self.name,
            outputs={
                "repairable_issues": repairable,
                "unrepairable_issues": unrepairable,
                "issues_by_agent": by_agent,
            },
            issues=unrepairable,
            notes=tuple(
                f"{agent}: {count} problema(s) a reparar"
                for agent, count in sorted(by_agent.items())
            ),
        )


class CanonGuardianAgent(BaseAgent):
    """`CANON_GUARDIAN_AGENT` — executável isoladamente para auditoria."""

    _contract = AgentContract(
        name="CANON_GUARDIAN_AGENT",
        responsibility=(
            "Comparar os prompts com a obra, detectar invenções indevidas e "
            "contradições, verificar personagens, cronologia e regras do mundo, e "
            "bloquear violações graves."
        ),
        phase="VALIDATING",
        input_type="tuple[PromptSegment, ...]",
        output_type="ValidationReport",
        authorized_tools=(AgentTool.DOMAIN_SERVICES, AgentTool.RAG_RETRIEVAL),
        memory=MemoryScope.CANON,
        prompt_name="validation.canon_guardian",
        completion_criteria=(
            "Todo personagem em cena existe no cânone.",
            "Nenhuma proibição do universo é violada.",
        ),
        failure_criteria=("O cânone não está disponível.",),
    )

    def __init__(self) -> None:
        self._service = CanonConsistencyService()

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        segments = tuple(
            segment for package in packages for segment in package.all_segments()
        )
        report = self._service.validate(segments, canon)

        self._log(context).info(
            "Auditoria de cânone",
            segments=len(segments),
            issues=len(report.issues),
            blocking=len(report.blocking_issues),
        )
        return self._with_issues(report.issues, report=report)


def summarize_issues(issues: tuple[ValidationIssue, ...]) -> dict[str, int]:
    """Contagem por severidade — usada em relatórios e no `manifest.json`."""
    counts = {severity.value: 0 for severity in Severity}
    for issue in issues:
        counts[issue.severity.value] += 1
    return counts
