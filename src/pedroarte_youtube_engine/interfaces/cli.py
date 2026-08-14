"""CLI `living-video` — ponto de entrada principal (seção 34).

Uso:
    living-video run input/            # pipeline completo
    living-video run input/ --dry-run  # planeja sem executar
    living-video doctor                # verifica dependências
    living-video manifest              # lista agentes e prompts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pedroarte_youtube_engine.shared.clock import SystemClock

app = typer.Typer(
    name="living-video",
    help="PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE — transforma livros em vídeos vivos.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def run(
    input_dir: Path = typer.Argument(
        ...,
        help="Pasta com o material de entrada (livro, notas, fichas).",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Pasta de saída. Padrão: output/<project_id>/<run_id>/",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Arquivo project.yaml. Padrão: procura em input_dir e no cwd.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Planeja e valida sem gerar artefatos.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Logs detalhados no terminal.",
    ),
) -> None:
    """Executa o pipeline completo de adaptação audiovisual."""
    from pedroarte_youtube_engine.interfaces._bootstrap import bootstrap

    console.print(
        Panel.fit(
            "[bold]PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE[/bold]\n"
            f"Entrada: {input_dir}\n"
            f"Modo: {'planejamento (dry-run)' if dry_run else 'execução completa'}",
            border_style="blue",
        )
    )

    try:
        context, orchestrator = bootstrap(
            input_dir=input_dir,
            output_dir=output_dir,
            config_path=config,
            verbose=verbose,
        )
    except Exception as exc:
        console.print(f"[red]Erro na inicialização:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executando pipeline...", total=None)

        try:
            result = orchestrator.execute()
        except Exception as exc:
            progress.stop()
            console.print(f"\n[red]Pipeline falhou:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        progress.update(task, description="Concluído", completed=True)

    _print_summary(result, context)


@app.command()
def doctor() -> None:
    """Verifica dependências e configuração."""
    checks: list[tuple[str, bool, str]] = []

    def _check(name: str, fn: object) -> None:
        try:
            assert callable(fn)
            fn()
            checks.append((name, True, "ok"))
        except Exception as exc:
            checks.append((name, False, str(exc)[:120]))

    _check("Python >= 3.11", lambda: _assert_python())
    _check("pydantic v2", lambda: _assert_pydantic())
    _check("typer", lambda: __import__("typer"))
    _check("rich", lambda: __import__("rich"))
    _check("yaml", lambda: __import__("yaml"))
    _check("jinja2", lambda: __import__("jinja2"))

    table = Table(title="Diagnóstico do motor")
    table.add_column("Componente")
    table.add_column("Status")
    table.add_column("Detalhe")

    for name, ok, detail in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, detail)

    console.print(table)

    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        console.print(f"\n[red]{len(failed)} verificação(ões) falharam.[/red]")
        raise typer.Exit(code=1)
    console.print("\n[green]Todas as verificações passaram.[/green]")


@app.command()
def manifest() -> None:
    """Lista agentes e prompts registrados."""
    from pedroarte_youtube_engine.agents import CATALOG, agent_manifest
    from pedroarte_youtube_engine.prompts import REGISTRY

    table = Table(title="Catálogo de Agentes")
    table.add_column("Agente", style="cyan")
    table.add_column("Fase")
    table.add_column("Entrada")
    table.add_column("Saída")
    table.add_column("Bloqueante")

    for entry in agent_manifest():
        table.add_row(
            str(entry["name"]),
            str(entry["phase"]),
            str(entry["input"]),
            str(entry["output"]),
            "sim" if entry["blocking"] else "não",
        )
    console.print(table)

    prompt_table = Table(title=f"Registro de Prompts ({len(REGISTRY)} definições)")
    prompt_table.add_column("Nome", style="cyan")
    prompt_table.add_column("Agente")
    prompt_table.add_column("Versão")
    prompt_table.add_column("Hash")

    for definition in REGISTRY.all():
        prompt_table.add_row(
            definition.name,
            definition.agent,
            str(definition.version),
            definition.hash[:12],
        )
    console.print(prompt_table)


@app.command()
def version() -> None:
    """Mostra a versão do motor."""
    from importlib.metadata import version as pkg_version

    try:
        ver = pkg_version("pedroarte-youtube-engine")
    except Exception:
        ver = "0.1.0-dev"
    console.print(f"living-video {ver}")


# -- auxiliares ------------------------------------------------------------


def _print_summary(result: object, context: object) -> None:
    from pedroarte_youtube_engine.agents.orchestrator import PipelineRun

    assert isinstance(result, PipelineRun)
    quality = result.quality

    table = Table(title="Resumo da Execução")
    table.add_column("Campo", style="bold")
    table.add_column("Valor")

    table.add_row("Estado final", result.state.value)
    table.add_row("Tempo", f"{result.elapsed:.1f}s")
    table.add_row("Agentes executados", str(len(result.results)))
    table.add_row("Eventos registrados", str(len(result.event_log)))
    table.add_row("Iterações de reparo", str(result.repair_iterations))

    if quality:
        verdict_color = "green" if quality.approved else "red"
        table.add_row(
            "Veredito",
            f"[{verdict_color}]{quality.verdict.value}[/{verdict_color}]",
        )
        table.add_row("Score", f"{quality.score:.4f}")
        table.add_row("Problemas bloqueantes", str(len(quality.blocking_issues)))
        table.add_row("Advertências", str(len(quality.warnings)))

    console.print(table)


def _assert_python() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError(f"Python {sys.version} < 3.11")


def _assert_pydantic() -> None:
    import pydantic

    major = int(pydantic.__version__.split(".")[0])
    if major < 2:
        raise RuntimeError(f"Pydantic {pydantic.__version__} < 2.0")


def main() -> None:
    app()
