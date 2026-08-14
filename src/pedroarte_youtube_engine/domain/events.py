"""Eventos de domínio (seção 7.5).

Os eventos são o registro imutável do que aconteceu numa execução. Eles
alimentam os logs estruturados, o `manifest.json` e a retomada — o motor
reconstrói o que já foi feito a partir dos eventos, não de inferência.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.shared.hashing import structural_hash


class DomainEventType(StrEnum):
    BOOK_INGESTED = "BookIngested"
    CANON_EXTRACTED = "CanonExtracted"
    AUDIOVISUAL_BIBLE_CREATED = "AudiovisualBibleCreated"
    PRODUCTION_PLANNED = "ProductionPlanned"
    EPISODE_PLANNED = "EpisodePlanned"
    SCENE_DECOMPOSED = "SceneDecomposed"
    SEGMENT_CREATED = "SegmentCreated"
    PROMPT_COMPILED = "PromptCompiled"
    CONTINUITY_VIOLATION_DETECTED = "ContinuityViolationDetected"
    PROMPT_PACKAGE_APPROVED = "PromptPackageApproved"
    PROVIDER_JOB_SUBMITTED = "ProviderJobSubmitted"
    PROVIDER_JOB_COMPLETED = "ProviderJobCompleted"
    PROVIDER_JOB_FAILED = "ProviderJobFailed"
    ARTIFACTS_EXPORTED = "ArtifactsExported"
    # Eventos operacionais, além dos exigidos pela especificação.
    INPUT_DISCOVERED = "InputDiscovered"
    INDEX_BUILT = "IndexBuilt"
    STATE_CHANGED = "StateChanged"
    REPAIR_STARTED = "RepairStarted"
    REPAIR_COMPLETED = "RepairCompleted"
    QUALITY_GATE_EVALUATED = "QualityGateEvaluated"
    RUN_PAUSED = "RunPaused"
    RUN_RESUMED = "RunResumed"
    RUN_FAILED = "RunFailed"


class DomainEvent(BaseModel):
    """Evento imutável, carimbado no tempo e correlacionável."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: DomainEventType
    occurred_at: datetime
    run_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(default="", max_length=64)
    emitted_by: str = Field(default="", max_length=96)
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def event_hash(self) -> str:
        return structural_hash(
            {
                "type": self.event_type.value,
                "run": self.run_id,
                "project": self.project_id,
                "payload": self.payload,
            }
        )

    def describe(self) -> str:
        return f"[{self.occurred_at.isoformat()}] {self.event_type.value} ({self.emitted_by})"


class EventLog(BaseModel):
    """Sequência ordenada de eventos de uma execução."""

    model_config = ConfigDict(extra="forbid")

    events: list[DomainEvent] = Field(default_factory=list)

    def append(self, event: DomainEvent) -> None:
        self.events.append(event)

    def of_type(self, event_type: DomainEventType) -> list[DomainEvent]:
        return [event for event in self.events if event.event_type is event_type]

    def last_of_type(self, event_type: DomainEventType) -> DomainEvent | None:
        matches = self.of_type(event_type)
        return matches[-1] if matches else None

    def count_of(self, event_type: DomainEventType) -> int:
        return len(self.of_type(event_type))

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self) -> Any:  # noqa: D105 - iteração transparente sobre os eventos
        return iter(self.events)
