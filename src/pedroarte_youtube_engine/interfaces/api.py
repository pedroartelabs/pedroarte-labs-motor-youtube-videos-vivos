"""FastAPI opcional (seção 34.2).

Endpoints:
    POST /run          — dispara o pipeline
    GET  /status/{id}  — estado da execução
    GET  /health       — liveness
    GET  /manifest     — catálogo de agentes e prompts
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pedroarte_youtube_engine.shared.clock import SystemClock

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise ImportError(
        "FastAPI não está instalado. Instale com: pip install pedroarte-youtube-engine[api]"
    ) from exc


app = FastAPI(
    title="PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE",
    version="0.1.0",
    description="API REST para o motor de adaptação audiovisual.",
)

_runs: dict[str, dict[str, Any]] = {}


class RunRequest(BaseModel):
    input_dir: str = Field(..., min_length=1)
    output_dir: str | None = None
    config_path: str | None = None


class RunResponse(BaseModel):
    run_id: str
    status: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "living-video"}


@app.get("/manifest")
def manifest() -> dict[str, Any]:
    from pedroarte_youtube_engine.agents import agent_manifest
    from pedroarte_youtube_engine.prompts import REGISTRY

    return {
        "agents": agent_manifest(),
        "prompts": REGISTRY.manifest(),
    }


@app.post("/run", response_model=RunResponse)
def start_run(request: RunRequest, background: BackgroundTasks) -> RunResponse:
    """Dispara o pipeline em background."""
    from pedroarte_youtube_engine.interfaces._bootstrap import bootstrap

    input_path = Path(request.input_dir)
    if not input_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Pasta não encontrada: {request.input_dir}")

    try:
        context, orchestrator = bootstrap(
            input_dir=input_path,
            output_dir=Path(request.output_dir) if request.output_dir else None,
            config_path=Path(request.config_path) if request.config_path else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:800]) from exc

    run_id = context.run_id.value
    _runs[run_id] = {"status": "running", "progress": 0.0}

    def _execute() -> None:
        try:
            result = orchestrator.execute()
            _runs[run_id] = {
                "status": "completed",
                "state": result.state.value,
                "elapsed": round(result.elapsed, 2),
                "repairs": result.repair_iterations,
                "quality_score": (
                    round(result.quality.score, 4) if result.quality else None
                ),
            }
        except Exception as exc:
            _runs[run_id] = {"status": "failed", "error": str(exc)[:800]}

    background.add_task(_execute)
    return RunResponse(run_id=run_id, status="running")


@app.get("/status/{run_id}")
def get_status(run_id: str) -> dict[str, Any]:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return {"run_id": run_id, **_runs[run_id]}
