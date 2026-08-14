"""Director of Living Video (seção 9.1).

O diretor não executa nenhum passo criativo: ele decide **quais** agentes rodam,
em **que ordem**, e com **quais gates**. A execução real é do orquestrador.
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
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.state import HAPPY_PATH, PipelineState


class DirectorAgent(BaseAgent):
    """`DIRECTOR_OF_LIVING_VIDEO` — planeja e supervisiona a execução."""

    _contract = AgentContract(
        name="DIRECTOR_OF_LIVING_VIDEO",
        responsibility=(
            "Selecionar o fluxo de execução, ordenar os agentes, definir os gates "
            "de qualidade que bloqueiam publicação, monitorar o progresso e emitir "
            "o relatório final com evidências."
        ),
        phase="PLANNING_EXECUTION",
        input_type="ProjectConfiguration",
        output_type="ExecutionPlan",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.FULL,
        prompt_name="director.plan_run",
        completion_criteria=(
            "A sequência cobre da descoberta até a exportação.",
            "Nenhum gate obrigatório é omitido.",
            "Artefatos reprovados nunca são exportados como aprovados.",
        ),
        failure_criteria=("A configuração não está disponível.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        configuration = context.configuration
        log = self._log(context)

        enabled = configuration.formats.enabled_variants()
        stages = [state.value for state in HAPPY_PATH]

        gates = [
            "audio_completeness",
            "prompt_completeness",
            "canon_consistency",
            "visual_continuity",
            "character_continuity",
            "voice_continuity",
            "timeline_consistency",
            "narrative_coverage",
            "provider_compatibility",
        ]

        plan = {
            "stages": stages,
            "gates": gates,
            "enabled_variants": [variant.value for variant in enabled],
            "segment_duration_seconds": configuration.segmentation.segment_duration_seconds,
            "max_repair_iterations": configuration.quality.max_repair_iterations,
            "minimum_approval_score": configuration.quality.minimum_approval_score,
            "execute_generation": configuration.providers.execute_generation,
            "rag_enabled": configuration.rag.enabled,
        }

        log.info(
            "Plano de execução definido",
            stages=len(stages),
            gates=len(gates),
            variants=len(enabled),
        )

        return AgentResult(
            agent=self.name,
            outputs={"execution_plan": plan},
            events=(
                DomainEvent(
                    event_type=DomainEventType.RUN_STARTED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload=plan,
                ),
            ),
        )
