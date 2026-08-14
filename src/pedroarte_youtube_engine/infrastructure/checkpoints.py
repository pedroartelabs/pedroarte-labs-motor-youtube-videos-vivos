"""Checkpoints e retomada.

Regra da seção 28: *uma falha no segmento 147 não deve exigir refazer os 146
anteriores*. Cada etapa concluída grava um checkpoint com o hash da entrada; ao
retomar, o motor pula tudo que já foi feito sobre exatamente o mesmo material.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.domain.state import PipelineState
from pedroarte_youtube_engine.shared.errors import EngineError
from pedroarte_youtube_engine.shared.hashing import structural_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic


class Checkpoint(BaseModel):
    """Marco de progresso de uma execução."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: PipelineState
    created_at: datetime
    input_fingerprint: str = Field(default="", max_length=128)
    config_fingerprint: str = Field(default="", max_length=128)
    completed_stages: tuple[str, ...] = Field(default_factory=tuple)
    segment_counts: dict[str, int] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=1200)

    def is_compatible_with(self, *, input_fingerprint: str, config_fingerprint: str) -> bool:
        """Um checkpoint só é reutilizável se entrada e configuração não mudaram."""
        return (
            self.input_fingerprint == input_fingerprint
            and self.config_fingerprint == config_fingerprint
        )


class CheckpointStore:
    """Persiste checkpoints em `checkpoints/` dentro do diretório da execução."""

    FILENAME = "checkpoint.json"

    def __init__(self, *, run_directory: Path, policy: PathPolicy) -> None:
        self._directory = policy.resolve_within(run_directory) / "checkpoints"
        self._policy = policy

    @property
    def path(self) -> Path:
        return self._directory / self.FILENAME

    def save(self, checkpoint: Checkpoint) -> Path:
        payload = checkpoint.model_dump(mode="json")
        write_text_atomic(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            self._policy,
        )
        return self.path

    def load(self) -> Checkpoint | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EngineError(
                f"Checkpoint corrompido: {exc}", path=str(self.path)
            ) from exc
        return Checkpoint.model_validate(payload)

    def stage_path(self, stage: str) -> Path:
        return self._directory / f"stage_{stage.lower()}.json"

    def save_stage(self, stage: str, payload: Any) -> Path:
        target = self.stage_path(stage)
        write_text_atomic(
            target,
            json.dumps(_jsonable(payload), ensure_ascii=False, indent=2) + "\n",
            self._policy,
        )
        return target

    def load_stage(self, stage: str) -> Any | None:
        target = self.stage_path(stage)
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def has_stage(self, stage: str) -> bool:
        return self.stage_path(stage).exists()


def fingerprint(payload: Any) -> str:
    """Impressão digital estável de uma estrutura, para comparar execuções."""
    return structural_hash(_jsonable(payload)).split(":", 1)[1][:32]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
