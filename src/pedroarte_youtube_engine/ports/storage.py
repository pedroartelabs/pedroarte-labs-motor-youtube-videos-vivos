"""Portas de armazenamento de artefatos e de objetos."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pedroarte_youtube_engine.domain.artifacts import Artifact, ArtifactKind
from pedroarte_youtube_engine.domain.value_objects import ProductionVariant


@runtime_checkable
class ArtifactWriterPort(Protocol):
    """Grava artefatos textuais da execução e devolve o registro com hash."""

    @property
    def run_directory(self) -> str: ...

    def write_text(
        self,
        *,
        relative_path: str,
        content: str,
        kind: ArtifactKind,
        produced_by: str,
        variant: ProductionVariant | None = None,
        episode_id: str | None = None,
        schema_id: str | None = None,
        description: str = "",
    ) -> Artifact: ...

    def write_json(
        self,
        *,
        relative_path: str,
        payload: object,
        kind: ArtifactKind,
        produced_by: str,
        variant: ProductionVariant | None = None,
        episode_id: str | None = None,
        schema_id: str | None = None,
        description: str = "",
    ) -> Artifact: ...

    def write_jsonl(
        self,
        *,
        relative_path: str,
        rows: tuple[object, ...],
        kind: ArtifactKind,
        produced_by: str,
        variant: ProductionVariant | None = None,
        description: str = "",
    ) -> Artifact: ...

    def artifacts(self) -> tuple[Artifact, ...]: ...


@runtime_checkable
class ObjectStoragePort(Protocol):
    """Armazena binários grandes (mídia gerada), fora do diretório de artefatos."""

    def put(self, *, key: str, data: bytes, content_type: str) -> str: ...

    def get(self, *, key: str) -> bytes | None: ...

    def exists(self, *, key: str) -> bool: ...
