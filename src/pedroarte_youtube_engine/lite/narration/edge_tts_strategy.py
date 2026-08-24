"""Estratégia `edge-tts` do `NarrationPort` — candidata a qualidade de
publicação no Gate 3B (SDD_SPDD.md §39).

IMPORTANTE — `LOCAL_FIRST != OFFLINE_ONLY` (Gate 3B, regra 8): este candidato
roda a partir desta máquina, mas cada síntese é uma chamada de rede real ao
serviço de voz neural da Microsoft/Edge (`speech.platform.bing.com`), sem
API key, sem custo monetário observável, mas COM dependência de rede. Nunca
declarar `network_required=False` para esta estratégia.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest, NarrationResult
from pedroarte_youtube_engine.shared.errors import EngineError

DEFAULT_VOICE = "pt-BR-FranciscaNeural"


class EdgeTtsNarrationStrategy:
    """Implementa `NarrationPort` via `edge-tts` (rede necessária, custo zero)."""

    def __init__(self, *, voice: str = DEFAULT_VOICE) -> None:
        self._voice = voice

    def synthesize(self, request: NarrationRequest) -> NarrationResult:
        import edge_tts

        voice = request.voice or self._voice
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        boundaries: list[dict[str, object]] = []

        async def _run() -> None:
            communicate = edge_tts.Communicate(request.text, voice)
            with open(request.output_path, "wb") as handle:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        handle.write(chunk["data"])
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        boundaries.append(
                            {
                                "type": chunk["type"],
                                "offset_100ns": chunk.get("offset"),
                                "duration_100ns": chunk.get("duration"),
                                "text": chunk.get("text", ""),
                            }
                        )

        start = time.monotonic()
        try:
            asyncio.run(_run())
        except Exception as exc:  # rede indisponível, voz inválida, etc.
            raise EngineError(
                "Falha na síntese edge-tts (dependência de rede).",
                voice=voice,
                error=str(exc)[:400],
            ) from exc
        elapsed = time.monotonic() - start

        if not request.output_path.exists() or request.output_path.stat().st_size == 0:
            raise EngineError("edge-tts não produziu áudio.", voice=voice)

        if boundaries:
            timing_path = request.output_path.with_suffix(".timing.json")
            timing_path.write_text(
                json.dumps(boundaries, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        duration = _mp3_duration_seconds_via_boundaries(boundaries) or 0.0

        return NarrationResult(
            output_path=request.output_path,
            duration_seconds=duration,
            method="external_api:edge_tts",
            voice=voice,
            generation_time_seconds=elapsed,
            timing_data_available=bool(boundaries),
        )


def _mp3_duration_seconds_via_boundaries(boundaries: list[dict[str, object]]) -> float:
    """Estimativa rápida a partir do último boundary — a duração exata e
    confiável é medida depois via `ffprobe` (mesma fonte de verdade usada
    para todos os candidatos, ver `qa.py`), não aqui."""
    if not boundaries:
        return 0.0
    last = boundaries[-1]
    offset = float(last.get("offset_100ns") or 0)
    duration = float(last.get("duration_100ns") or 0)
    return (offset + duration) / 10_000_000.0
