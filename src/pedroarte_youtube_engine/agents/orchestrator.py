"""Orquestrador com máquina de estados explícita (seção 10).

O orquestrador é o **único ponto de mutação** do `EngineContext`. Os agentes
leem o contexto e devolvem um `AgentResult`; o orquestrador decide se aceita o
resultado, aplica-o ao estado compartilhado, registra o evento e avança o
pipeline — ou dispara o repair loop.

A máquina de estados segue `domain.state.ALLOWED_TRANSITIONS` e nunca pula
etapas. O repair loop é limitado a `quality.max_repair_iterations` rodadas;
depois disso, o pipeline falha em vez de iterar para sempre.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pedroarte_youtube_engine.adapters.parsers import ParserRegistry
from pedroarte_youtube_engine.agents.audiovisual import AudiovisualBibleAgent
from pedroarte_youtube_engine.agents.base import (
    AgentResult,
    BaseAgent,
    EngineContext,
)
from pedroarte_youtube_engine.agents.canon import (
    CanonExtractorAgent,
    CharacterBibleAgent,
    WorldBibleAgent,
)
from pedroarte_youtube_engine.agents.compilation import (
    MultimodalPromptCompilerAgent,
    ProviderCapabilityAgent,
)
from pedroarte_youtube_engine.agents.editors import ShortsEditorAgent, TrailerEditorAgent
from pedroarte_youtube_engine.agents.ingestion import (
    BookIngestionAgent,
    InputDiscoveryAgent,
)
from pedroarte_youtube_engine.agents.packaging import (
    AccessibilityAgent,
    CostAndQuotaAgent,
    LegalAndRightsAgent,
    RetentionAndHookAgent,
    YouTubePackagingAgent,
)
from pedroarte_youtube_engine.agents.planning import (
    AdaptationArchitectAgent,
    EpisodeArchitectAgent,
    FormatPlannerAgent,
    SeasonArchitectAgent,
)
from pedroarte_youtube_engine.agents.segments import SegmentBuilderAgent
from pedroarte_youtube_engine.agents.validation import (
    FinalQaAgent,
    QualityGateAgent,
    RepairPlannerAgent,
)
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType, EventLog
from pedroarte_youtube_engine.domain.state import (
    PipelineState,
    assert_transition,
    next_state,
    progress_ratio,
)
from pedroarte_youtube_engine.domain.validation import QualityAssessment
from pedroarte_youtube_engine.infrastructure.artifacts import FilesystemArtifactAdapter
from pedroarte_youtube_engine.infrastructure.checkpoints import CheckpointStore
from pedroarte_youtube_engine.observability.logging import RunLogger
from pedroarte_youtube_engine.shared.errors import (
    RepairLimitExceeded,
    StateTransitionError,
)
from pedroarte_youtube_engine.shared.paths import PathPolicy


@dataclass(slots=True)
class PipelineRun:
    """Estado mutável de uma execução do pipeline."""

    state: PipelineState = PipelineState.DISCOVERING_INPUT
    event_log: EventLog = field(default_factory=EventLog)
    results: dict[str, AgentResult] = field(default_factory=dict)
    repair_iterations: int = 0
    started_at: float = field(default_factory=time.monotonic)
    quality: QualityAssessment | None = None

    def transition(self, target: PipelineState) -> None:
        assert_transition(self.state, target)
        self.state = target

    def record(self, event: DomainEvent) -> None:
        self.event_log.append(event)

    def record_many(self, events: tuple[DomainEvent, ...]) -> None:
        for event in events:
            self.record(event)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at


class PipelineOrchestrator:
    """Executa o pipeline completo, com repair loop e checkpoints."""

    def __init__(
        self,
        *,
        context: EngineContext,
        artifacts: FilesystemArtifactAdapter | None = None,
        checkpoints: CheckpointStore | None = None,
        policy: PathPolicy | None = None,
    ) -> None:
        self._context = context
        self._artifacts = artifacts
        self._checkpoints = checkpoints
        self._policy = policy or PathPolicy()
        self._run = PipelineRun()
        self._log = context.logger.bind(component="orchestrator")

    @property
    def state(self) -> PipelineState:
        return self._run.state

    @property
    def progress(self) -> float:
        return progress_ratio(self._run.state)

    @property
    def quality(self) -> QualityAssessment | None:
        return self._run.quality

    def execute(self) -> PipelineRun:
        """Executa o pipeline feliz com repair loop."""
        self._log.info("Pipeline iniciado", project=self._context.project_id.value)
        self._run.record(
            DomainEvent(
                event_type=DomainEventType.RUN_STARTED,
                occurred_at=self._context.clock.now(),
                run_id=self._context.run_id.value,
                project_id=self._context.project_id.value,
                emitted_by="orchestrator",
                payload={"configuration_hash": ""},
            )
        )

        try:
            self._phase_discover()
            self._phase_ingest()
            self._phase_extract_canon()
            self._phase_build_bibles()
            self._phase_plan()
            self._phase_write_segments()
            self._phase_compile()
            self._phase_validate_with_repair()
            self._phase_export()
            self._finish()
        except Exception as exc:
            self._fail(exc)
            raise

        return self._run

    # -- fases -------------------------------------------------------------

    def _phase_discover(self) -> None:
        self._advance(PipelineState.DISCOVERING_INPUT)
        agent = InputDiscoveryAgent(policy=self._policy)
        result = self._run_agent(agent)
        self._context.scratch["documents"] = result.output("documents")

    def _phase_ingest(self) -> None:
        self._advance(PipelineState.INGESTING)
        result = self._run_agent(BookIngestionAgent())
        self._context.book = result.output("book")
        self._context.scratch["source_map"] = result.output("source_map")

    def _phase_extract_canon(self) -> None:
        self._advance(PipelineState.EXTRACTING_CANON)
        result = self._run_agent(CanonExtractorAgent())
        self._context.canon = result.output("canon")
        self._context.analysis = result.output("analysis")

    def _phase_build_bibles(self) -> None:
        self._advance(PipelineState.BUILDING_BIBLES)

        world_result = self._run_agent(WorldBibleAgent())
        self._context.scratch["world_bible"] = world_result.output("world_bible")

        char_result = self._run_agent(CharacterBibleAgent())
        if char_result.output("characters"):
            canon = self._context.require_canon()
            self._context.canon = canon.model_copy(
                update={"characters": char_result.output("characters")}
            )
        if char_result.output("questions"):
            canon = self._context.require_canon()
            existing = list(canon.unresolved_questions)
            existing.extend(char_result.output("questions"))
            self._context.canon = canon.model_copy(
                update={"unresolved_questions": tuple(existing)}
            )

        av_result = self._run_agent(AudiovisualBibleAgent())
        self._context.audiovisual_bible = av_result.output("audiovisual_bible")

    def _phase_plan(self) -> None:
        self._advance(PipelineState.PLANNING_FORMATS)
        format_result = self._run_agent(FormatPlannerAgent())
        self._context.scratch["profiles"] = format_result.output("profiles")

        self._advance(PipelineState.ADAPTING)
        adapt_result = self._run_agent(AdaptationArchitectAgent())
        self._context.scratch["decisions"] = adapt_result.output("decisions")
        self._context.scratch["adaptation_strategy"] = adapt_result.output(
            "adaptation_strategy"
        )

        self._advance(PipelineState.PLANNING_EPISODES)
        season_result = self._run_agent(SeasonArchitectAgent())
        self._context.scratch["seasons"] = season_result.output("seasons")

        episode_result = self._run_agent(EpisodeArchitectAgent())
        self._context.production_plan = episode_result.output("production_plan")

    def _phase_write_segments(self) -> None:
        self._advance(PipelineState.WRITING_SEGMENTS)
        result = self._run_agent(SegmentBuilderAgent())
        self._context.scratch["packages"] = result.output("packages")

        shorts_result = self._run_agent(ShortsEditorAgent())
        if shorts_result.output("packages"):
            self._context.scratch["packages"] = shorts_result.output("packages")

        trailer_result = self._run_agent(TrailerEditorAgent())
        if trailer_result.output("packages"):
            self._context.scratch["packages"] = trailer_result.output("packages")

    def _phase_compile(self) -> None:
        self._advance(PipelineState.COMPILING_PROMPTS)
        cap_result = self._run_agent(ProviderCapabilityAgent())
        self._context.scratch["video_capability"] = cap_result.output("video_capability")
        self._context.scratch["image_capability"] = cap_result.output("image_capability")
        self._context.scratch["voice_capability"] = cap_result.output("voice_capability")

        compile_result = self._run_agent(MultimodalPromptCompilerAgent())
        self._context.scratch["packages"] = compile_result.output("packages")
        self._context.scratch["provider_prompts"] = compile_result.output("provider_prompts")

    def _phase_validate_with_repair(self) -> None:
        max_repairs = self._context.configuration.quality.max_repair_iterations

        while True:
            self._advance(PipelineState.VALIDATING)
            gate_result = self._run_agent(QualityGateAgent())
            self._context.scratch["packages"] = gate_result.output("packages")
            self._context.scratch["reports"] = gate_result.output("reports")

            self._run_agent(RetentionAndHookAgent())

            qa_result = self._run_agent(FinalQaAgent())
            assessment: QualityAssessment = qa_result.output("quality")
            self._run.quality = assessment

            if assessment.approved:
                self._log.info(
                    "Pipeline aprovado",
                    score=round(assessment.score, 4),
                    repairs=self._run.repair_iterations,
                )
                break

            if self._run.repair_iterations >= max_repairs:
                self._log.warning(
                    "Limite de reparos atingido",
                    iterations=self._run.repair_iterations,
                    score=round(assessment.score, 4),
                )
                raise RepairLimitExceeded(
                    f"O pipeline não atingiu o score mínimo após "
                    f"{self._run.repair_iterations} iteração(ões) de reparo. "
                    f"Score: {assessment.score:.4f}, "
                    f"mínimo: {self._context.configuration.quality.minimum_approval_score}.",
                    iterations=self._run.repair_iterations,
                    score=assessment.score,
                )

            self._advance(PipelineState.REPAIRING)
            self._run.repair_iterations += 1
            self._context.scratch["repair_iterations"] = self._run.repair_iterations

            repair_result = self._run_agent(RepairPlannerAgent())
            agents_to_rerun = repair_result.output("issues_by_agent") or {}
            self._log.info(
                "Repair loop",
                iteration=self._run.repair_iterations,
                agents=sorted(agents_to_rerun),
            )

            if "SEGMENT_BUILDER_AGENT" in agents_to_rerun:
                self._run_agent(SegmentBuilderAgent())
            if "MULTIMODAL_PROMPT_COMPILER_AGENT" in agents_to_rerun:
                self._run_agent(MultimodalPromptCompilerAgent())

    def _phase_export(self) -> None:
        self._advance(PipelineState.EXPORTING)
        self._run_agent(YouTubePackagingAgent())
        self._run_agent(AccessibilityAgent())
        self._run_agent(LegalAndRightsAgent())
        self._run_agent(CostAndQuotaAgent())

        if self._artifacts:
            self._advance(PipelineState.EXPORTING)
            self._export_artifacts()

    def _finish(self) -> None:
        self._advance(PipelineState.COMPLETED)
        self._run.record(
            DomainEvent(
                event_type=DomainEventType.RUN_COMPLETED,
                occurred_at=self._context.clock.now(),
                run_id=self._context.run_id.value,
                project_id=self._context.project_id.value,
                emitted_by="orchestrator",
                payload={
                    "elapsed_seconds": round(self._run.elapsed, 2),
                    "state": self._run.state.value,
                    "repairs": self._run.repair_iterations,
                    "quality_score": (
                        round(self._run.quality.score, 4) if self._run.quality else None
                    ),
                },
            )
        )
        self._log.info(
            "Pipeline concluído",
            elapsed=f"{self._run.elapsed:.1f}s",
            state=self._run.state.value,
        )

    def _fail(self, exc: Exception) -> None:
        self._run.state = PipelineState.FAILED
        self._run.record(
            DomainEvent(
                event_type=DomainEventType.RUN_FAILED,
                occurred_at=self._context.clock.now(),
                run_id=self._context.run_id.value,
                project_id=self._context.project_id.value,
                emitted_by="orchestrator",
                payload={
                    "error": str(exc)[:800],
                    "state_at_failure": self._run.state.value,
                    "elapsed_seconds": round(self._run.elapsed, 2),
                },
            )
        )
        self._log.error("Pipeline falhou", error=str(exc)[:400])

    # -- execução de agente ------------------------------------------------

    def _run_agent(self, agent: BaseAgent) -> AgentResult:
        name = agent.contract.name
        self._log.debug("Executando agente", agent=name)

        start = time.monotonic()
        try:
            result = agent.run(self._context)
        except Exception as exc:
            elapsed = time.monotonic() - start
            self._context.metrics.record_agent_failure(name)
            self._log.error(
                "Agente falhou",
                agent=name,
                error=str(exc)[:400],
                elapsed=f"{elapsed:.2f}s",
            )
            raise

        result.elapsed_seconds = time.monotonic() - start
        self._run.results[name] = result
        self._run.record_many(result.events)
        self._context.metrics.record_timing(f"agent.{name}", result.elapsed_seconds)

        if result.blocking_issues:
            self._log.warning(
                "Agente concluído com problemas bloqueantes",
                agent=name,
                blocking=len(result.blocking_issues),
                elapsed=f"{result.elapsed_seconds:.2f}s",
            )
        else:
            self._log.debug(
                "Agente concluído",
                agent=name,
                elapsed=f"{result.elapsed_seconds:.2f}s",
            )

        if self._checkpoints:
            self._checkpoint(name)

        return result

    def _advance(self, target: PipelineState) -> None:
        try:
            self._run.transition(target)
        except StateTransitionError:
            if target == self._run.state:
                return
            raise
        self._log.info("Estado", state=target.value, progress=f"{self.progress:.0%}")

    # -- checkpoints -------------------------------------------------------

    def _checkpoint(self, label: str) -> None:
        if self._checkpoints is None:
            return
        snapshot = {
            "state": self._run.state.value,
            "label": label,
            "repair_iterations": self._run.repair_iterations,
            "elapsed": round(self._run.elapsed, 2),
            "agents_completed": sorted(self._run.results),
        }
        self._checkpoints.save(
            run_id=self._context.run_id.value,
            label=label,
            data=snapshot,
        )

    # -- exportação --------------------------------------------------------

    def _export_artifacts(self) -> None:
        if self._artifacts is None:
            return

        import json

        from pedroarte_youtube_engine.adapters.renderers import (
            render_audiovisual_bible,
            render_canon_bible,
            render_segment_markdown,
            render_shotlist_csv,
        )
        from pedroarte_youtube_engine.adapters.renderers.subtitles import render_transcript

        run_id = self._context.run_id.value
        canon = self._context.canon
        bible = self._context.audiovisual_bible
        packages: tuple = self._context.scratch.get("packages", ())

        if canon:
            self._artifacts.write_text(run_id, "canon_bible.md", render_canon_bible(canon))
        if bible:
            self._artifacts.write_text(
                run_id, "audiovisual_bible.md", render_audiovisual_bible(bible)
            )

        for package in packages:
            variant_dir = package.directory
            for episode in package.episodes:
                episode_dir = f"{variant_dir}/{episode.episode_id.value}"
                for segment in episode.segments:
                    self._artifacts.write_text(
                        run_id,
                        f"{episode_dir}/{segment.segment_id.value}.md",
                        render_segment_markdown(
                            segment,
                            project_title=self._context.configuration.project.title,
                        ),
                    )
                self._artifacts.write_text(
                    run_id,
                    f"{episode_dir}/shotlist.csv",
                    render_shotlist_csv(episode.segments),
                )
                self._artifacts.write_text(
                    run_id,
                    f"{episode_dir}/transcript.md",
                    render_transcript(episode.segments, title=episode.title),
                )

        manifest = {
            "project_id": self._context.project_id.value,
            "run_id": run_id,
            "state": self._run.state.value,
            "elapsed_seconds": round(self._run.elapsed, 2),
            "repair_iterations": self._run.repair_iterations,
            "quality_score": (
                round(self._run.quality.score, 4) if self._run.quality else None
            ),
            "agents": sorted(self._run.results),
            "events": len(self._run.event_log),
            "packages": [
                {
                    "variant": package.variant.value,
                    "episodes": len(package.episodes),
                    "segments": package.segment_count,
                }
                for package in packages
            ],
        }
        self._artifacts.write_json(run_id, "manifest.json", manifest)
        self._log.info("Artefatos exportados", run_id=run_id)
