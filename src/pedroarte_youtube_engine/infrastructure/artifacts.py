"""Gravação de artefatos em disco.

Toda escrita passa pela `PathPolicy`: nada é gravado fora de
`outputs/<project_slug>/<run_id>/`, e execuções anteriores nunca são
sobrescritas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pedroarte_youtube_engine.domain.artifacts import Artifact, ArtifactKind
from pedroarte_youtube_engine.domain.services.artifact_versioning import (
    ArtifactVersioningService,
)
from pedroarte_youtube_engine.domain.value_objects import ProductionVariant
from pedroarte_youtube_engine.shared.errors import DomainRuleViolation
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic


class FilesystemArtifactAdapter:
    """Implementação do `ArtifactWriterPort` sobre o sistema de arquivos."""

    def __init__(
        self,
        *,
        run_directory: Path,
        policy: PathPolicy,
        pretty_json: bool = True,
        allow_existing: bool = False,
    ) -> None:
        self._run_directory = policy.resolve_within(run_directory)
        if self._run_directory.exists() and any(self._run_directory.iterdir()):
            if not allow_existing:
                raise DomainRuleViolation(
                    "O diretório da execução já existe e não está vazio. "
                    "Execuções nunca são sobrescritas.",
                    run_directory=str(self._run_directory),
                )
        self._run_directory.mkdir(parents=True, exist_ok=True)
        self._policy = policy
        self._pretty = pretty_json
        self._versioning = ArtifactVersioningService()
        self._artifacts: list[Artifact] = []

    @property
    def run_directory(self) -> str:
        return str(self._run_directory)

    @property
    def run_path(self) -> Path:
        return self._run_directory

    # -- escrita -----------------------------------------------------------

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
    ) -> Artifact:
        target = self._run_directory / relative_path
        write_text_atomic(target, content, self._policy)
        artifact = self._versioning.register(
            kind=kind,
            relative_path=relative_path.replace("\\", "/"),
            content=content,
            produced_by=produced_by,
            variant=variant,
            episode_id=episode_id,
            schema_id=schema_id,
            description=description,
        )
        self._artifacts.append(artifact)
        return artifact

    def write_json(
        self,
        *,
        relative_path: str,
        payload: Any,
        kind: ArtifactKind,
        produced_by: str,
        variant: ProductionVariant | None = None,
        episode_id: str | None = None,
        schema_id: str | None = None,
        description: str = "",
    ) -> Artifact:
        content = json.dumps(
            _jsonable(payload),
            ensure_ascii=False,
            indent=2 if self._pretty else None,
            sort_keys=False,
        )
        return self.write_text(
            relative_path=relative_path,
            content=content + "\n",
            kind=kind,
            produced_by=produced_by,
            variant=variant,
            episode_id=episode_id,
            schema_id=schema_id,
            description=description,
        )

    def write_jsonl(
        self,
        *,
        relative_path: str,
        rows: tuple[Any, ...],
        kind: ArtifactKind,
        produced_by: str,
        variant: ProductionVariant | None = None,
        description: str = "",
    ) -> Artifact:
        lines = [
            json.dumps(_jsonable(row), ensure_ascii=False, sort_keys=False) for row in rows
        ]
        return self.write_text(
            relative_path=relative_path,
            content="\n".join(lines) + ("\n" if lines else ""),
            kind=kind,
            produced_by=produced_by,
            variant=variant,
            description=description,
        )

    def artifacts(self) -> tuple[Artifact, ...]:
        return tuple(self._artifacts)

    @property
    def total_bytes(self) -> int:
        return sum(artifact.size_bytes for artifact in self._artifacts)


def _jsonable(value: Any) -> Any:
    """Converte modelos Pydantic e tipos do domínio em estruturas serializáveis."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
