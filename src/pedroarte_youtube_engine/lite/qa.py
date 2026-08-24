"""MediaQA — checks automatizados do Gate 2 sobre o `.mp4` real (SDD_SPDD.md
§34/discovery Lite §32). Usa `ffprobe`; não reimplementa nenhum parser de
container — FFmpeg já resolve isso.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary
from pedroarte_youtube_engine.shared.errors import EngineError


@dataclass(slots=True)
class QaCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class QaReport:
    checks: list[QaCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def _ffprobe_json(path: Path) -> dict:
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
            "ffprobe não conseguiu abrir o arquivo.",
            stderr=(completed.stderr or "")[-800:],
            returncode=completed.returncode,
        )
    return json.loads(completed.stdout)


def _volume_stats(path: Path) -> tuple[float | None, float | None]:
    """`mean_volume`/`max_volume` em dB via o filtro `volumedetect`.

    Proxy barato de "áudio audível, sem clipping óbvio" (max < 0 dB e mean
    não extremamente baixo) — não é medição de loudness EBU R128 completa,
    que fica para o Gate 3 (SDD_SPDD.md §5 do discovery, item de qualidade).
    """
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


def run_gate2_qa(
    path: Path,
    *,
    min_duration_seconds: float = 20.0,
    expected_width: int = 1920,
    expected_height: int = 1080,
) -> QaReport:
    report = QaReport()

    exists = path.exists() and path.stat().st_size > 0
    report.checks.append(QaCheck("file_exists_and_nonempty", exists, str(path)))
    if not exists:
        return report

    try:
        probe = _ffprobe_json(path)
    except EngineError as exc:
        report.checks.append(QaCheck("ffprobe_opens_file", False, str(exc)))
        return report
    report.checks.append(QaCheck("ffprobe_opens_file", True))

    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    duration = float(fmt.get("duration", 0.0))
    report.checks.append(
        QaCheck(
            "duration_at_least_minimum",
            duration >= min_duration_seconds,
            f"duration={duration:.2f}s min={min_duration_seconds}s",
        )
    )

    report.checks.append(QaCheck("has_video_stream", bool(video_streams)))
    report.checks.append(QaCheck("has_audio_stream", bool(audio_streams)))

    if video_streams:
        vstream = video_streams[0]
        width = int(vstream.get("width", 0))
        height = int(vstream.get("height", 0))
        report.checks.append(
            QaCheck(
                "resolution_matches_expected",
                (width, height) == (expected_width, expected_height),
                f"got={width}x{height} expected={expected_width}x{expected_height}",
            )
        )
        codec = vstream.get("codec_name", "")
        report.checks.append(QaCheck("video_codec_is_h264", codec == "h264", f"codec={codec}"))

    if audio_streams:
        acodec = audio_streams[0].get("codec_name", "")
        report.checks.append(QaCheck("audio_codec_is_aac", acodec == "aac", f"codec={acodec}"))

    mean_db, max_db = _volume_stats(path)
    audible = mean_db is not None and mean_db > -40.0
    report.checks.append(
        QaCheck("audio_audible", audible, f"mean_volume={mean_db}dB")
    )
    no_clipping = max_db is not None and max_db <= 0.0
    report.checks.append(
        QaCheck("no_obvious_clipping", no_clipping, f"max_volume={max_db}dB")
    )

    return report
