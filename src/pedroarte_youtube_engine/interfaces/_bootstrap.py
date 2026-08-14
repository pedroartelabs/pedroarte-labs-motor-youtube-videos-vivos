"""Bootstrap do motor — monta o `EngineContext` e o orquestrador.

Este módulo é a **cola** entre a configuração, os adaptadores e o orquestrador.
Ele cria tudo que o pipeline precisa para rodar, sem que nenhum agente precise
saber de onde veio cada dependência.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pedroarte_youtube_engine.adapters.analysis.heuristic import (
    HeuristicNarrativeAnalyzer,
)
from pedroarte_youtube_engine.adapters.providers.deterministic_llm import (
    DeterministicLLMProvider,
)
from pedroarte_youtube_engine.agents.base import EngineContext
from pedroarte_youtube_engine.agents.orchestrator import PipelineOrchestrator
from pedroarte_youtube_engine.domain.value_objects import ProjectId, RunId
from pedroarte_youtube_engine.infrastructure.artifacts import FilesystemArtifactAdapter
from pedroarte_youtube_engine.infrastructure.capabilities import YamlCapabilityRegistry
from pedroarte_youtube_engine.infrastructure.checkpoints import CheckpointStore
from pedroarte_youtube_engine.infrastructure.config_loader import ConfigurationLoader
from pedroarte_youtube_engine.observability.logging import RunLogger
from pedroarte_youtube_engine.observability.metrics import MetricsCollector
from pedroarte_youtube_engine.prompts import REGISTRY
from pedroarte_youtube_engine.rag.embedding import HashingEmbeddingProvider
from pedroarte_youtube_engine.rag.lexical import Bm25LexicalIndex
from pedroarte_youtube_engine.rag.pipeline import NarrativeRagPipeline
from pedroarte_youtube_engine.rag.reranker import HeuristicReranker
from pedroarte_youtube_engine.rag.vector_store import InMemoryVectorStore
from pedroarte_youtube_engine.shared.clock import SystemClock
from pedroarte_youtube_engine.shared.hashing import stable_short_id
from pedroarte_youtube_engine.shared.paths import PathPolicy

if TYPE_CHECKING:
    from pedroarte_youtube_engine.domain.configuration import ProjectConfiguration


def bootstrap(
    *,
    input_dir: Path,
    output_dir: Path | None = None,
    config_path: Path | None = None,
    verbose: bool = False,
) -> tuple[EngineContext, PipelineOrchestrator]:
    """Monta o contexto e o orquestrador prontos para `execute()`."""
    clock = SystemClock()
    timestamp = clock.now().isoformat()
    run_id = RunId.create(timestamp_iso=timestamp, seed=timestamp)

    configuration = _load_configuration(input_dir, config_path)
    slug = configuration.resolved_slug()
    project_id = ProjectId(
        value=slug
        if len(slug) >= 2
        else stable_short_id(str(input_dir), length=16)
    )

    logger = RunLogger(
        project_id=project_id.value,
        run_id=run_id.value,
        verbose=verbose,
    )
    metrics = MetricsCollector()

    resolved_input = input_dir.resolve()
    policy = PathPolicy.for_roots(resolved_input)

    effective_output = output_dir or (
        Path("outputs") / project_id.value / run_id.value
    )

    artifacts = FilesystemArtifactAdapter(root=effective_output)
    checkpoints = CheckpointStore(root=effective_output / ".checkpoints")

    cap_dir = Path("config/provider_capabilities")
    capabilities = (
        YamlCapabilityRegistry.from_directory(cap_dir)
        if cap_dir.is_dir()
        else YamlCapabilityRegistry()
    )

    rag = _build_rag(configuration)

    context = EngineContext(
        configuration=configuration,
        project_id=project_id,
        run_id=run_id,
        clock=clock,
        logger=logger,
        metrics=metrics,
        prompts=REGISTRY,
        analyzer=HeuristicNarrativeAnalyzer(),
        llm=DeterministicLLMProvider(),
        rag=rag,
        capabilities=capabilities,
        input_directory=str(input_dir),
    )

    orchestrator = PipelineOrchestrator(
        context=context,
        artifacts=artifacts,
        checkpoints=checkpoints,
        policy=policy,
    )

    return context, orchestrator


def _load_configuration(
    input_dir: Path, config_path: Path | None
) -> "ProjectConfiguration":
    loader = ConfigurationLoader()
    candidates: list[Path | None] = [config_path] if config_path else []
    candidates += [
        input_dir / "project.yaml",
        input_dir / "project.yml",
        Path("project.yaml"),
        Path("project.yml"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            loaded = loader.load(explicit_config_path=candidate)
            return loaded.configuration
    loaded = loader.load()
    return loaded.configuration


def _build_rag(configuration: "ProjectConfiguration") -> NarrativeRagPipeline:
    rag_config = configuration.rag
    embedding = HashingEmbeddingProvider(dimensions=rag_config.embedding_dimensions)
    vector_store = InMemoryVectorStore()
    lexical = Bm25LexicalIndex()
    reranker = HeuristicReranker()

    return NarrativeRagPipeline(
        embedding_provider=embedding,
        vector_store=vector_store,
        lexical_index=lexical,
        reranker=reranker,
        lexical_weight=rag_config.lexical_weight,
    )
