"""Catálogo de agentes — 31 agentes tipados com contratos explícitos.

Para registrar um agente novo: adicione a classe, registre no `CATALOG` e
crie o prompt correspondente em `prompts/definitions.py`.
"""

from __future__ import annotations

from pedroarte_youtube_engine.agents.audiovisual import (
    AudiovisualBibleAgent,
    MusicSupervisorAgent,
    VoiceCastingAgent,
)
from pedroarte_youtube_engine.agents.base import (
    Agent,
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
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
from pedroarte_youtube_engine.agents.editors import (
    ShortsEditorAgent,
    TrailerEditorAgent,
)
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
    CanonGuardianAgent,
    FinalQaAgent,
    QualityGateAgent,
    RepairPlannerAgent,
)

__all__ = [
    "CATALOG",
    "Agent",
    "AgentContract",
    "AgentResult",
    "AgentTool",
    "BaseAgent",
    "EngineContext",
    "MemoryScope",
]

#: Catálogo completo, na ordem de execução do pipeline feliz.
CATALOG: tuple[type[BaseAgent], ...] = (
    # -- Fase 1: Descoberta e ingestão
    InputDiscoveryAgent,
    BookIngestionAgent,
    # -- Fase 2: Extração de cânone
    CanonExtractorAgent,
    WorldBibleAgent,
    CharacterBibleAgent,
    # -- Fase 3: Bíblias audiovisuais
    AudiovisualBibleAgent,
    VoiceCastingAgent,
    MusicSupervisorAgent,
    # -- Fase 4: Planejamento
    FormatPlannerAgent,
    AdaptationArchitectAgent,
    SeasonArchitectAgent,
    EpisodeArchitectAgent,
    # -- Fase 5: Construção de segmentos
    SegmentBuilderAgent,
    ShortsEditorAgent,
    TrailerEditorAgent,
    # -- Fase 6: Compilação para provedor
    ProviderCapabilityAgent,
    MultimodalPromptCompilerAgent,
    # -- Fase 7: Validação
    QualityGateAgent,
    CanonGuardianAgent,
    RetentionAndHookAgent,
    FinalQaAgent,
    RepairPlannerAgent,
    # -- Fase 8: Empacotamento e exportação
    YouTubePackagingAgent,
    AccessibilityAgent,
    LegalAndRightsAgent,
    CostAndQuotaAgent,
)


def agent_manifest() -> list[dict[str, object]]:
    """Manifesto JSON de todos os agentes — usado em docs e no `manifest.json`."""
    return [cls._contract.as_manifest_entry() for cls in CATALOG]
