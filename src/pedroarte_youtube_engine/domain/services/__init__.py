"""Serviços de domínio (seção 7.4).

Lógica que não pertence a uma única entidade: planejamento de duração,
consistência de cânone, continuidade, completude de áudio, compatibilidade de
provedor e versionamento de artefatos.

Todos são funções puras sobre o domínio — sem I/O, sem rede, sem relógio. É o
que permite testá-los exaustivamente com Hypothesis.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.services.artifact_versioning import (
    ArtifactVersioningService,
)
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
from pedroarte_youtube_engine.domain.services.duration_planning import (
    DurationPlanningService,
)
from pedroarte_youtube_engine.domain.services.format_adaptation import (
    FormatAdaptationService,
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
from pedroarte_youtube_engine.domain.services.segment_compilation import (
    SegmentCompilationService,
)
from pedroarte_youtube_engine.domain.services.timeline_consistency import (
    TimelineConsistencyService,
)

__all__ = [
    "ArtifactVersioningService",
    "AudioCompletenessService",
    "CanonConsistencyService",
    "CharacterContinuityService",
    "DurationPlanningService",
    "FormatAdaptationService",
    "NarrativeCoverageService",
    "PromptCompletenessService",
    "ProviderCapabilityMatchingService",
    "SegmentCompilationService",
    "TimelineConsistencyService",
    "VisualContinuityService",
    "VoiceContinuityService",
]
