"""Estratégia SAPI5 do `NarrationPort` — só para Gate 2 (prova de pipeline).

GATE_2_TTS != GATE_3_TTS (docs/youtube-lite/SDD_SPDD.md §29): esta estratégia
não é avaliada como solução final de qualidade de publicação — só prova que
existe um caminho 100% local e gratuito para colocar áudio real dentro do
MP4. Zero dependência Python nova: chama o PowerShell/`System.Speech` do
próprio Windows via subprocess, texto passado por arquivo (nunca por
interpolação de string em linha de comando).
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest, NarrationResult
from pedroarte_youtube_engine.shared.errors import EngineError

_SCRIPT_PATH = Path(__file__).with_name("synthesize_sapi.ps1")
DEFAULT_VOICE = "Microsoft Maria Desktop"


class Sapi5NarrationStrategy:
    """Implementa `NarrationPort` via SAPI5 (Windows, offline, custo zero)."""

    def __init__(self, *, voice: str = DEFAULT_VOICE) -> None:
        self._voice = voice

    def synthesize(self, request: NarrationRequest) -> NarrationResult:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            text_path = Path(tmp) / "narration_text.txt"
            text_path.write_text(request.text, encoding="utf-8")

            start = time.monotonic()
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(_SCRIPT_PATH),
                    "-TextPath",
                    str(text_path),
                    "-OutputPath",
                    str(request.output_path),
                    "-VoiceName",
                    self._voice,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            elapsed = time.monotonic() - start

        if completed.returncode != 0 or not request.output_path.exists():
            raise EngineError(
                "Falha na síntese SAPI5.",
                stdout=(completed.stdout or "")[-800:],
                stderr=(completed.stderr or "")[-800:],
                returncode=completed.returncode,
            )

        duration = _wav_duration_seconds(request.output_path)
        return NarrationResult(
            output_path=request.output_path,
            duration_seconds=duration,
            method="local:sapi5",
            voice=self._voice,
            generation_time_seconds=elapsed,
            timing_data_available=False,
        )


def _wav_duration_seconds(path: Path) -> float:
    """Duração real do WAV, lida do próprio cabeçalho — sem depender do FFmpeg aqui."""
    import wave

    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        return frames / float(rate) if rate else 0.0
