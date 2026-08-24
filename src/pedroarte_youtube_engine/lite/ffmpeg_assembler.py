"""FFmpeg é o renderer/assembler do Lite — não se constrói um renderer
próprio (docs/youtube-lite/SDD_SPDD.md §17). Versão mínima do Gate 2: uma
imagem + Ken Burns (zoompan) + narração muxada, sem música (adiada — Gate 3).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pedroarte_youtube_engine.lite.timeline import TimelineBeat
from pedroarte_youtube_engine.shared.errors import EngineError

if TYPE_CHECKING:
    from pedroarte_youtube_engine.lite.retention import RetentionSegment

_WINGET_LINKS = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"


def resolve_ffmpeg_binary(name: str = "ffmpeg") -> str:
    """Localiza o binário do FFmpeg sem presumir que o PATH da sessão atual
    já foi recarregado após a instalação via winget (§32 do relatório de
    implementação)."""
    found = shutil.which(name)
    if found:
        return found
    candidate = _WINGET_LINKS / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    raise EngineError(
        f"'{name}' não encontrado no PATH nem em {candidate}. "
        "FFmpeg é um pré-requisito de ambiente do Gate 2 (SDD_SPDD.md §17)."
    )


@dataclass(frozen=True, slots=True)
class AssemblyResult:
    output_path: Path
    render_time_seconds: float
    command: tuple[str, ...]


def assemble_single_beat_clip(
    *,
    beat: TimelineBeat,
    narration_path: Path,
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 25,
    zoom_per_frame: float = 0.0006,
    max_zoom: float = 1.12,
) -> AssemblyResult:
    """Monta um clipe de um único beat: imagem estática com Ken Burns +
    narração muxada. Generaliza para múltiplos beats no Gate 3 via
    concatenação — não implementado agora (sem consumidor no Gate 2)."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    width, height = resolution
    output_path.parent.mkdir(parents=True, exist_ok=True)

    zoompan = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='min(zoom+{zoom_per_frame},{max_zoom})':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
    )

    command = (
        ffmpeg,
        "-y",
        "-loop", "1",
        "-framerate", str(fps),
        "-i", beat.image_path,
        "-i", str(narration_path),
        "-filter_complex", f"[0:v]{zoompan}[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{beat.duration_seconds:.3f}",
        "-movflags", "+faststart",
        str(output_path),
    )

    start = time.monotonic()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    elapsed = time.monotonic() - start

    if completed.returncode != 0 or not output_path.exists():
        raise EngineError(
            "Falha na montagem FFmpeg do clipe.",
            command=" ".join(command),
            stdout=(completed.stdout or "")[-1500:],
            stderr=(completed.stderr or "")[-1500:],
            returncode=completed.returncode,
        )

    return AssemblyResult(output_path=output_path, render_time_seconds=elapsed, command=command)


def _run_ffmpeg(command: tuple[str, ...], *, timeout: int = 300) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    if completed.returncode != 0:
        raise EngineError(
            "Falha na chamada FFmpeg.",
            command=" ".join(command),
            stderr=(completed.stderr or "")[-1500:],
            returncode=completed.returncode,
        )
    return completed


def render_retention_clip(
    *,
    image_path: Path,
    segment: "RetentionSegment",
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 25,
) -> AssemblyResult:
    """Renderiza UM Retention Segment (Gate 3D.1 SLICE A/B).

    Causa raiz corrigida (docs/youtube-lite/GATE_3D_POSTMORTEM_AND_3D1_PLAN.md
    §6): entrada de UM único frame estático (`-loop 1 -i imagem`, sem
    `-framerate`), com `zoompan` controlando a progressão via `d=<frames
    totais>` — não `d=1` sobre um input já multiplicado em frames idênticos.
    Essa é exatamente a receita "clássica" que o postmortem provou produzir
    movimento real (YAVG≈25 vs. ≈0.01 da receita quebrada, mesmo teste).

    Pan é expresso como fração da MARGEM DE RECORTE disponível no zoom atual
    (nunca da largura do frame) — garante que o recorte nunca sai da imagem.
    """
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    width, height = resolution
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_frames = max(1, round(segment.duration_seconds * fps))
    z0, z1 = segment.start_scale, segment.end_scale
    # progresso linear 0..1 ao longo dos frames de saída deste segmento
    t = f"(on/{max(1, total_frames - 1)})"
    zoom_expr = f"({z0}+({z1}-{z0})*{t})" if z0 != z1 else f"{z0}"

    base_x = "(iw/2-(iw/zoom/2))"
    base_y = "(ih/2-(ih/zoom/2))"
    x_expr = base_x if segment.pan_dx_fraction == 0 else f"({base_x}*(1+({segment.pan_dx_fraction})*{t}))"
    y_expr = base_y if segment.pan_dy_fraction == 0 else f"({base_y}*(1+({segment.pan_dy_fraction})*{t}))"

    zoompan = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='{zoom_expr}':d={total_frames}:"
        f"x='{x_expr}':y='{y_expr}':s={width}x{height}:fps={fps}"
    )
    command = (
        ffmpeg, "-y",
        "-loop", "1", "-i", str(image_path),
        "-filter_complex", f"[0:v]{zoompan}[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", f"{segment.duration_seconds:.3f}",
        str(output_path),
    )
    start = time.monotonic()
    _run_ffmpeg(command, timeout=120)
    elapsed = time.monotonic() - start
    if not output_path.exists():
        raise EngineError("Segmento não foi criado.", output_path=str(output_path))
    return AssemblyResult(output_path=output_path, render_time_seconds=elapsed, command=command)


def render_silent_segment(
    *,
    image_path: Path,
    duration_seconds: float,
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 25,
) -> AssemblyResult:
    """Compatibilidade: um único Retention Segment cobrindo a duração
    inteira (plano de retenção padrão para durações curtas — ver
    `lite/retention.py::build_default_retention_plan`). Mantido para não
    quebrar chamadores existentes (Gate 2/Gate 3D) — agora usa a receita
    corrigida internamente."""
    from pedroarte_youtube_engine.lite.retention import RetentionKind, RetentionSegment, compute_zoom_delta

    delta = compute_zoom_delta(duration_seconds)
    segment = RetentionSegment(
        kind=RetentionKind.ZOOM_IN, duration_seconds=duration_seconds, start_scale=1.0, end_scale=1.0 + delta
    )
    return render_retention_clip(
        image_path=image_path, segment=segment, output_path=output_path, resolution=resolution, fps=fps
    )


def concat_segments(*, segment_paths: list[Path], output_path: Path) -> AssemblyResult:
    """Concatena segmentos (mesmo codec/resolução/fps) sem reencodar."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = output_path.with_suffix(".concat.txt")
    list_path.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in segment_paths) + "\n", encoding="utf-8"
    )
    command = (
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c", "copy", str(output_path),
    )
    start = time.monotonic()
    _run_ffmpeg(command, timeout=180)
    elapsed = time.monotonic() - start
    if not output_path.exists():
        raise EngineError("Concatenação não produziu arquivo.", output_path=str(output_path))
    return AssemblyResult(output_path=output_path, render_time_seconds=elapsed, command=command)


def mux_video_audio(*, video_path: Path, audio_path: Path, output_path: Path) -> AssemblyResult:
    """Mux do vídeo silencioso concatenado com a narração completa real."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = (
        ffmpeg, "-y",
        "-i", str(video_path), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(output_path),
    )
    start = time.monotonic()
    _run_ffmpeg(command, timeout=180)
    elapsed = time.monotonic() - start
    if not output_path.exists():
        raise EngineError("Mux não produziu arquivo final.", output_path=str(output_path))
    return AssemblyResult(output_path=output_path, render_time_seconds=elapsed, command=command)


def burn_captions(*, video_path: Path, ass_path: Path, output_path: Path) -> AssemblyResult:
    """Queima legendas .ass no vídeo via libass (Gate 3D.1 SLICE C) —
    confirmado disponível no build instalado (`ffmpeg -filters | grep ass`,
    ver GATE_3D1_IMPLEMENTATION_REPORT.md). Reencode necessário (o filtro
    `ass` opera sobre pixels), mas é a única etapa que reencoda — o resto do
    pipeline continua evitando reencodes desnecessários."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Caminho do .ass precisa ser escapado para a sintaxe de filtro do FFmpeg
    # (":" e "\" são especiais); mais simples e robusto: copiar para um nome
    # sem caracteres problemáticos não é necessário no Windows se usarmos
    # aspas simples ao redor do caminho inteiro dentro da string do filtro.
    ass_arg = str(ass_path).replace("\\", "/").replace(":", "\\:")
    command = (
        ffmpeg, "-y",
        "-i", str(video_path),
        "-vf", f"ass='{ass_arg}'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    )
    start = time.monotonic()
    _run_ffmpeg(command, timeout=1500)  # reencode de libx264 sobre ~650s pode passar de 600s (medido: Gate 3D.2 estourou 600s)
    elapsed = time.monotonic() - start
    if not output_path.exists():
        raise EngineError("Vídeo com legendas queimadas não foi criado.", output_path=str(output_path))
    return AssemblyResult(output_path=output_path, render_time_seconds=elapsed, command=command)


def render_thumbnail(*, image_path: Path, output_path: Path, resolution: tuple[int, int] = (1280, 720)) -> Path:
    """Recorta/normaliza uma imagem já existente (reuso, sem gerar nada
    novo) para as dimensões recomendadas de thumbnail do YouTube."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    width, height = resolution
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = (
        ffmpeg, "-y", "-i", str(image_path),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-frames:v", "1",
        str(output_path),
    )
    _run_ffmpeg(command, timeout=60)
    if not output_path.exists():
        raise EngineError("Thumbnail não foi criado.", output_path=str(output_path))
    return output_path
