"""Versionamento de artefatos e identidade de execução.

Regra 42.18: *não sobrescreva execuções anteriores*. O `run_id` é derivado do
instante de início e de um sufixo estável, e o serviço rejeita qualquer tentativa
de reutilizar um diretório de execução já existente.
"""

from __future__ import annotations

from datetime import datetime

from pedroarte_youtube_engine.domain.artifacts import Artifact, ArtifactKind
from pedroarte_youtube_engine.domain.value_objects import (
    ContentHash,
    ProductionVariant,
    ProjectId,
    RunId,
)
from pedroarte_youtube_engine.shared.errors import DomainRuleViolation
from pedroarte_youtube_engine.shared.hashing import content_hash


class ArtifactVersioningService:
    """Cria `run_id`s únicos e registra artefatos com hash."""

    def new_run_id(
        self, *, started_at: datetime, project_id: ProjectId, seed: str = ""
    ) -> RunId:
        """`run_id` contendo data, horário e identificador curto (seção 12)."""
        timestamp = started_at.isoformat(timespec="seconds")
        return RunId.create(
            timestamp_iso=timestamp,
            seed=f"{project_id.value}|{seed}",
        )

    def run_directory(self, *, project_id: ProjectId, run_id: RunId) -> str:
        return f"outputs/{project_id.value}/{run_id.value}"

    def assert_new_run(self, *, existing_run_ids: tuple[str, ...], run_id: RunId) -> None:
        """Impede sobrescrita silenciosa de uma execução anterior."""
        if run_id.value in existing_run_ids:
            raise DomainRuleViolation(
                "Já existe uma execução com este run_id; execuções nunca são sobrescritas.",
                run_id=run_id.value,
            )

    def register(
        self,
        *,
        kind: ArtifactKind,
        relative_path: str,
        content: str,
        produced_by: str,
        variant: ProductionVariant | None = None,
        episode_id: str | None = None,
        schema_id: str | None = None,
        description: str = "",
    ) -> Artifact:
        """Cria o registro de um artefato a partir do conteúdo gravado."""
        encoded = content.encode("utf-8")
        return Artifact(
            artifact_id=_artifact_id(relative_path),
            kind=kind,
            relative_path=relative_path,
            content_hash=ContentHash(value=content_hash(encoded)),
            size_bytes=len(encoded),
            variant=variant,
            episode_id=episode_id,
            produced_by=produced_by,
            schema_id=schema_id,
            description=description,
        )

    def diff(
        self, previous: tuple[Artifact, ...], current: tuple[Artifact, ...]
    ) -> dict[str, tuple[str, ...]]:
        """Compara duas execuções: o que foi adicionado, alterado e removido."""
        previous_map = {artifact.relative_path: artifact for artifact in previous}
        current_map = {artifact.relative_path: artifact for artifact in current}
        added = tuple(sorted(set(current_map) - set(previous_map)))
        removed = tuple(sorted(set(previous_map) - set(current_map)))
        changed = tuple(
            sorted(
                path
                for path in set(previous_map) & set(current_map)
                if previous_map[path].content_hash != current_map[path].content_hash
            )
        )
        return {"added": added, "changed": changed, "removed": removed}

    @staticmethod
    def total_bytes(artifacts: tuple[Artifact, ...]) -> int:
        return sum(artifact.size_bytes for artifact in artifacts)


def _artifact_id(relative_path: str) -> str:
    """Id legível e estável derivado do caminho relativo."""
    cleaned = relative_path.strip("/").replace("/", ".").replace("\\", ".")
    return cleaned[:160] if len(cleaned) >= 3 else f"artifact.{cleaned}"
