"""Porta de fila de jobs.

Opcional: o motor roda em processo único por padrão. A porta existe para que
uma execução distribuída possa ser plugada sem alterar a orquestração.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pedroarte_youtube_engine.domain.aggregates import GenerationJob


@runtime_checkable
class JobQueuePort(Protocol):
    """Enfileira e consome jobs de geração de mídia."""

    def enqueue(self, job: GenerationJob) -> str: ...

    def dequeue(self) -> GenerationJob | None: ...

    def pending_count(self) -> int: ...

    def mark_done(self, job_id: str) -> None: ...
