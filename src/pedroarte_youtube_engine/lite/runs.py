"""Filesystem como fonte de verdade da execução (docs/youtube-lite/ARTIFACT_CONTRACT.md).

Nenhuma dependência do `bootstrap()`/`EngineContext` legacy. Um `run_id` só
precisa de um relógio e um slug — não precisa de `RunId`/`ProjectId` do
domínio legacy, que carregam mais invariantes do que o Lite usa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic
from pedroarte_youtube_engine.shared.text import safe_slug

DEFAULT_RUNS_ROOT = Path("runs")


class RunStatus(StrEnum):
    """Status linear do run Lite — não reutiliza a máquina de estados legacy de 15 fases."""

    STARTED = "started"
    SCRIPT_READY = "script_ready"
    NARRATION_READY = "narration_ready"
    IMAGES_READY = "images_ready"
    ASSEMBLED = "assembled"
    QA_PASSED = "qa_passed"
    QA_FAILED = "qa_failed"
    FAILED = "failed"


def new_run_id(label: str, *, now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{safe_slug(label)}"


@dataclass(slots=True)
class RunPaths:
    run_id: str
    root: Path
    input_dir: Path
    working_dir: Path
    assets_dir: Path
    images_dir: Path
    output_dir: Path
    manifest_path: Path
    pending_tasks_path: Path


def create_run(run_id: str, *, runs_root: Path = DEFAULT_RUNS_ROOT) -> RunPaths:
    """Cria a árvore de diretórios de uma execução e devolve os caminhos.

    A allowlist da `PathPolicy` é a própria `runs_root` (resolvida) — o Lite
    nunca escreve fora dela.
    """
    runs_root = runs_root.resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    policy = PathPolicy.for_roots(runs_root)

    root = runs_root / run_id
    paths = RunPaths(
        run_id=run_id,
        root=root,
        input_dir=root / "input",
        working_dir=root / "working",
        assets_dir=root / "assets",
        images_dir=root / "assets" / "images",
        output_dir=root / "output",
        manifest_path=root / "run_manifest.json",
        pending_tasks_path=root / "pending_tasks.json",
    )
    for directory in (
        paths.input_dir,
        paths.working_dir,
        paths.assets_dir,
        paths.images_dir,
        paths.output_dir,
    ):
        ensure_directory(directory, policy)
    return paths


def write_manifest(paths: RunPaths, manifest: dict[str, Any]) -> Path:
    policy = PathPolicy.for_roots(paths.root)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    return write_text_atomic(
        paths.manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        policy,
    )


def read_manifest(paths: RunPaths) -> dict[str, Any]:
    return json.loads(paths.manifest_path.read_text(encoding="utf-8"))


def write_pending_tasks(paths: RunPaths, tasks: list[dict[str, str]]) -> Path:
    policy = PathPolicy.for_roots(paths.root)
    payload = {"run_id": paths.run_id, "tasks": tasks}
    return write_text_atomic(
        paths.pending_tasks_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        policy,
    )


def new_manifest(
    *,
    run_id: str,
    gate: str,
    owner: str,
    briefing_source: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "run_id": run_id,
        "gate": gate,
        "owner": owner,
        "status": RunStatus.STARTED.value,
        "created_at": now,
        "updated_at": now,
        "briefing_source": briefing_source,
        "artifacts": [],
        "provenance": {},
        "economics": {
            "external_api_cost": 0.0,
            "generation_time_seconds": 0.0,
            "human_review_time_seconds": None,
            "asset_count": 0,
            "render_time_seconds": 0.0,
            "retry_count": 0,
            "execution_environment": "claude_code",
            "generation_method": "local_first",
        },
        "qa": {"automated": {}, "human": None},
    }
