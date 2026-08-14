"""Base do sistema multiagente.

Cada agente tem responsabilidade delimitada, entrada tipada, saída tipada,
contrato, critérios de conclusão e de falha, ferramentas autorizadas, memória
permitida, versão de prompt, testes e rastreabilidade (seção 8).

**Nenhum agente altera diretamente o trabalho de outro.** Os agentes leem o
`EngineContext` e devolvem um `AgentResult`; só o orquestrador aplica o
resultado ao estado compartilhado, e só depois de validá-lo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.domain.aggregates import (
    AudiovisualBible,
    CanonBible,
    ProductionPlan,
    PromptPackage,
)
from pedroarte_youtube_engine.domain.configuration import ProjectConfiguration
from pedroarte_youtube_engine.domain.events import DomainEvent
from pedroarte_youtube_engine.domain.source import BookSource
from pedroarte_youtube_engine.domain.validation import ValidationIssue
from pedroarte_youtube_engine.domain.value_objects import ProjectId, RunId
from pedroarte_youtube_engine.infrastructure.capabilities import YamlCapabilityRegistry
from pedroarte_youtube_engine.observability.logging import RunLogger
from pedroarte_youtube_engine.observability.metrics import MetricsCollector
from pedroarte_youtube_engine.ports.analysis import NarrativeAnalysis, NarrativeAnalyzerPort
from pedroarte_youtube_engine.ports.llm import LLMProviderPort
from pedroarte_youtube_engine.prompts.registry import PromptRegistry
from pedroarte_youtube_engine.rag.pipeline import NarrativeRagPipeline
from pedroarte_youtube_engine.shared.clock import Clock


class MemoryScope(StrEnum):
    """Memória que um agente pode acessar."""

    NONE = "nenhuma"
    RUN = "execucao"
    CANON = "canone"
    CONTINUITY = "continuidade"
    FULL = "completa"


class AgentTool(StrEnum):
    """Ferramentas que um agente pode ser autorizado a usar."""

    FILESYSTEM_READ = "leitura_de_arquivos"
    ARTIFACT_WRITE = "escrita_de_artefatos"
    RAG_RETRIEVAL = "recuperacao_rag"
    NARRATIVE_ANALYSIS = "analise_narrativa"
    LLM = "modelo_de_linguagem"
    CAPABILITY_REGISTRY = "registro_de_capacidades"
    PROMPT_COMPILER = "compilador_de_prompt"
    MEDIA_GENERATION = "geracao_de_midia"
    DOMAIN_SERVICES = "servicos_de_dominio"


class AgentContract(BaseModel):
    """O contrato público de um agente."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3, max_length=96)
    responsibility: str = Field(min_length=10, max_length=1200)
    phase: str = Field(min_length=3, max_length=64)
    input_type: str = Field(min_length=3, max_length=128)
    output_type: str = Field(min_length=3, max_length=128)
    authorized_tools: tuple[AgentTool, ...] = Field(default_factory=tuple)
    memory: MemoryScope = MemoryScope.RUN
    prompt_name: str | None = None
    prompt_version: str = "1.0.0"
    completion_criteria: tuple[str, ...] = Field(min_length=1)
    failure_criteria: tuple[str, ...] = Field(min_length=1)
    blocking: bool = True

    def as_manifest_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "phase": self.phase,
            "input": self.input_type,
            "output": self.output_type,
            "tools": [tool.value for tool in self.authorized_tools],
            "memory": self.memory.value,
            "prompt": f"{self.prompt_name}@{self.prompt_version}" if self.prompt_name else None,
            "blocking": self.blocking,
        }


@dataclass(slots=True)
class EngineContext:
    """Estado compartilhado da execução.

    Os agentes **leem** livremente e **escrevem** apenas através do
    `AgentResult` que devolvem — o orquestrador é o único ponto de mutação.
    """

    configuration: ProjectConfiguration
    project_id: ProjectId
    run_id: RunId
    clock: Clock
    logger: RunLogger
    metrics: MetricsCollector
    prompts: PromptRegistry
    analyzer: NarrativeAnalyzerPort
    llm: LLMProviderPort
    rag: NarrativeRagPipeline
    capabilities: YamlCapabilityRegistry
    input_directory: str = ""
    book: BookSource | None = None
    analysis: NarrativeAnalysis | None = None
    canon: CanonBible | None = None
    audiovisual_bible: AudiovisualBible | None = None
    production_plan: ProductionPlan | None = None
    packages: tuple[PromptPackage, ...] = field(default_factory=tuple)
    scratch: dict[str, Any] = field(default_factory=dict)

    # -- acessos que exigem a etapa anterior concluída ---------------------

    def require_book(self) -> BookSource:
        if self.book is None:
            raise _missing("BookSource", "BOOK_INGESTION_AGENT")
        return self.book

    def require_analysis(self) -> NarrativeAnalysis:
        if self.analysis is None:
            raise _missing("NarrativeAnalysis", "CANON_EXTRACTOR_AGENT")
        return self.analysis

    def require_canon(self) -> CanonBible:
        if self.canon is None:
            raise _missing("CanonBible", "CANON_EXTRACTOR_AGENT")
        return self.canon

    def require_bible(self) -> AudiovisualBible:
        if self.audiovisual_bible is None:
            raise _missing("AudiovisualBible", "AUDIOVISUAL_BIBLE_AGENT")
        return self.audiovisual_bible

    def require_plan(self) -> ProductionPlan:
        if self.production_plan is None:
            raise _missing("ProductionPlan", "FORMAT_PLANNER_AGENT")
        return self.production_plan


@dataclass(slots=True)
class AgentResult:
    """O que um agente devolve ao orquestrador."""

    agent: str
    succeeded: bool = True
    outputs: dict[str, Any] = field(default_factory=dict)
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    events: tuple[DomainEvent, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    elapsed_seconds: float = 0.0

    @property
    def blocking_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocks_approval)

    def output(self, key: str) -> Any:
        return self.outputs.get(key)

    @classmethod
    def failure(
        cls, agent: str, *, issues: tuple[ValidationIssue, ...], notes: tuple[str, ...] = ()
    ) -> "AgentResult":
        return cls(agent=agent, succeeded=False, issues=issues, notes=notes)


@runtime_checkable
class Agent(Protocol):
    """Todo agente do catálogo implementa esta interface."""

    @property
    def contract(self) -> AgentContract: ...

    def run(self, context: EngineContext) -> AgentResult: ...


class BaseAgent:
    """Implementação comum: expõe o contrato e registra o próprio nome."""

    _contract: AgentContract

    @property
    def contract(self) -> AgentContract:
        return self._contract

    @property
    def name(self) -> str:
        return self._contract.name

    def run(self, context: EngineContext) -> AgentResult:  # pragma: no cover - abstrato
        raise NotImplementedError(
            f"{type(self).__name__} não implementa run(). "
            "Todo agente do catálogo precisa de uma implementação executável."
        )

    # -- utilidades para as subclasses ------------------------------------

    def _ok(self, **outputs: Any) -> AgentResult:
        return AgentResult(agent=self.name, succeeded=True, outputs=outputs)

    def _with_issues(
        self, issues: tuple[ValidationIssue, ...], **outputs: Any
    ) -> AgentResult:
        blocking = any(issue.blocks_approval for issue in issues)
        return AgentResult(
            agent=self.name,
            succeeded=not blocking,
            outputs=outputs,
            issues=issues,
        )

    def _log(self, context: EngineContext) -> RunLogger:
        return context.logger.bind(agent=self.name)


def _missing(what: str, producer: str) -> RuntimeError:
    from pedroarte_youtube_engine.shared.errors import StateTransitionError

    return StateTransitionError(
        f"{what} ainda não foi produzido. Execute {producer} antes desta etapa.",
        missing=what,
        producer=producer,
    )
