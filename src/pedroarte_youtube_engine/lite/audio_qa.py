"""QA objetiva de amostras de áudio (Gate 3B, SDD_SPDD §15 do briefing do
gate). Métricas mensuráveis apenas — nenhum "quality score" algorítmico
inventado. A escolha da voz é sempre humana (§16 do briefing do gate).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary
from pedroarte_youtube_engine.shared.errors import EngineError


@dataclass(slots=True)
class AudioQaMetrics:
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    file_size_bytes: int
    mean_volume_db: float | None
    max_volume_db: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "duration_seconds": round(self.duration_seconds, 2),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "codec": self.codec,
            "file_size_bytes": self.file_size_bytes,
            "mean_volume_db": self.mean_volume_db,
            "max_volume_db": self.max_volume_db,
        }


def probe_audio(path: Path) -> AudioQaMetrics:
    ffprobe = resolve_ffmpeg_binary("ffprobe")
    completed = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if completed.returncode != 0:
        raise EngineError(
            "ffprobe não conseguiu abrir a amostra de áudio.",
            stderr=(completed.stderr or "")[-800:],
        )
    payload = json.loads(completed.stdout)
    fmt = payload.get("format", {})
    audio_streams = [s for s in payload.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise EngineError("Amostra não contém stream de áudio.", path=str(path))
    stream = audio_streams[0]

    mean_db, max_db = _volume_stats(path)

    return AudioQaMetrics(
        duration_seconds=float(fmt.get("duration", 0.0)),
        sample_rate=int(stream.get("sample_rate", 0)),
        channels=int(stream.get("channels", 0)),
        codec=str(stream.get("codec_name", "")),
        file_size_bytes=int(fmt.get("size", 0)),
        mean_volume_db=mean_db,
        max_volume_db=max_db,
    )


def _volume_stats(path: Path) -> tuple[float | None, float | None]:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    completed = subprocess.run(
        [ffmpeg, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    stderr = completed.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?)\s*dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+(\.\d+)?)\s*dB", stderr)
    mean_db = float(mean_match.group(1)) if mean_match else None
    max_db = float(max_match.group(1)) if max_match else None
    return mean_db, max_db
