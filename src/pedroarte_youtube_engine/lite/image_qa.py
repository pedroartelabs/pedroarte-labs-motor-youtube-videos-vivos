"""QA objetiva de imagens geradas (Gate 3C §34). Só verificações objetivas —
"beleza", "qualidade cinematográfica" e "consistência" são Human Gate, nunca
um algoritmo aqui. Reaproveita `ffprobe` (já usado para áudio/vídeo no Lite)
em vez de adicionar Pillow — `ffprobe` também lê metadados de imagem.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary
from pedroarte_youtube_engine.shared.errors import EngineError


@dataclass(slots=True)
class ImageQaResult:
    exists: bool
    opens: bool
    width: int
    height: int
    aspect_ratio: float
    format: str
    file_size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "exists": self.exists,
            "opens": self.opens,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": round(self.aspect_ratio, 3),
            "format": self.format,
            "file_size_bytes": self.file_size_bytes,
        }


def probe_image(path: Path) -> ImageQaResult:
    if not path.exists() or path.stat().st_size == 0:
        return ImageQaResult(False, False, 0, 0, 0.0, "", 0)

    ffprobe = resolve_ffmpeg_binary("ffprobe")
    completed = subprocess.run(
        [
            ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
            str(path),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if completed.returncode != 0:
        return ImageQaResult(True, False, 0, 0, 0.0, "", path.stat().st_size)

    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    if not streams:
        return ImageQaResult(True, False, 0, 0, 0.0, "", path.stat().st_size)

    stream = streams[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    aspect = width / height if height else 0.0
    fmt = str(payload.get("format", {}).get("format_name", ""))

    return ImageQaResult(
        exists=True, opens=True, width=width, height=height, aspect_ratio=aspect,
        format=fmt, file_size_bytes=path.stat().st_size,
    )


def aspect_ratio_acceptable(aspect: float, *, target: float = 16 / 9, tolerance: float = 0.15) -> bool:
    return abs(aspect - target) <= tolerance
