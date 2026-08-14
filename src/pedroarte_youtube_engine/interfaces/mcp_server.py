"""MCP Server (seção 34.3).

Expõe o motor como servidor MCP para que um LLM possa orquestrar a adaptação
audiovisual conversacionalmente. Cada tool corresponde a uma operação do
pipeline.

O servidor NÃO executa geração por padrão — ele só prepara os prompts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_mcp_tools() -> list[dict[str, Any]]:
    """Retorna as definições de tools para um servidor MCP."""
    return [
        {
            "name": "living_video_run",
            "description": (
                "Executa o pipeline completo de adaptação audiovisual. "
                "Recebe o caminho da pasta de entrada e retorna o manifesto "
                "da execução com score de qualidade e artefatos."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input_dir": {
                        "type": "string",
                        "description": "Caminho absoluto da pasta com o material de entrada.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Caminho da pasta de saída (opcional).",
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Caminho do project.yaml (opcional).",
                    },
                },
                "required": ["input_dir"],
            },
        },
        {
            "name": "living_video_status",
            "description": "Retorna o estado da execução mais recente.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "ID da execução.",
                    },
                },
                "required": ["run_id"],
            },
        },
        {
            "name": "living_video_manifest",
            "description": "Lista os agentes e prompts registrados no motor.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "living_video_doctor",
            "description": "Verifica dependências e configuração do motor.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


def handle_mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Despacha uma chamada MCP para a operação correspondente."""
    if tool_name == "living_video_run":
        return _handle_run(arguments)
    if tool_name == "living_video_manifest":
        return _handle_manifest()
    if tool_name == "living_video_doctor":
        return _handle_doctor()
    return {"error": f"Tool desconhecida: {tool_name}"}


def _handle_run(arguments: dict[str, Any]) -> dict[str, Any]:
    from pedroarte_youtube_engine.interfaces._bootstrap import bootstrap

    input_dir = Path(arguments["input_dir"])
    if not input_dir.is_dir():
        return {"error": f"Pasta não encontrada: {arguments['input_dir']}"}

    try:
        context, orchestrator = bootstrap(
            input_dir=input_dir,
            output_dir=Path(arguments["output_dir"]) if arguments.get("output_dir") else None,
            config_path=(
                Path(arguments["config_path"]) if arguments.get("config_path") else None
            ),
        )
        result = orchestrator.execute()
        return {
            "run_id": context.run_id.value,
            "state": result.state.value,
            "elapsed_seconds": round(result.elapsed, 2),
            "repairs": result.repair_iterations,
            "quality_score": (
                round(result.quality.score, 4) if result.quality else None
            ),
            "agents_completed": sorted(result.results),
            "events": len(result.event_log),
        }
    except Exception as exc:
        return {"error": str(exc)[:800]}


def _handle_manifest() -> dict[str, Any]:
    from pedroarte_youtube_engine.agents import agent_manifest
    from pedroarte_youtube_engine.prompts import REGISTRY

    return {
        "agents": agent_manifest(),
        "prompts": REGISTRY.manifest(),
    }


def _handle_doctor() -> dict[str, Any]:
    import sys

    checks: dict[str, str] = {}

    checks["python"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )

    try:
        import pydantic

        checks["pydantic"] = pydantic.__version__
    except ImportError:
        checks["pydantic"] = "não instalado"

    for name in ("typer", "rich", "yaml", "jinja2"):
        try:
            __import__(name)
            checks[name] = "ok"
        except ImportError:
            checks[name] = "não instalado"

    return {"checks": checks}


def serve_stdio() -> None:
    """Loop stdio simples para testes locais do MCP server."""
    import sys

    tools = build_mcp_tools()
    sys.stdout.write(json.dumps({"tools": tools}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            tool_name = request.get("tool", "")
            arguments = request.get("arguments", {})
            response = handle_mcp_call(tool_name, arguments)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"error": "JSON inválido"}) + "\n")
            sys.stdout.flush()
