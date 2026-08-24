"""Estratégia local (GDI+) do `ImageGenerationPort` — só para Gate 2.

Escolhida deliberadamente (decisão humana explícita, ver
docs/youtube-lite/ARTIFACT_CONTRACT.md §6/provenance) para provar o cano
FFmpeg/Ken Burns/mux sem gastar em nenhuma API paga. Não é geração de imagem
por IA e não deve ser avaliada como estratégia de qualidade visual — isso é
Gate 3, com Visual Bible Lite e um provider real, mediante autorização de
custo.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from pedroarte_youtube_engine.lite.images.ports import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from pedroarte_youtube_engine.shared.errors import EngineError

_SCRIPT_PATH = Path(__file__).with_name("generate_gdi.ps1")


class LocalGdiImageStrategy:
    """Implementa `ImageGenerationPort` via System.Drawing (Windows, offline, custo zero)."""

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        title, _, subtitle = request.prompt.partition("\n")
        with tempfile.TemporaryDirectory() as tmp:
            title_path = Path(tmp) / "title.txt"
            title_path.write_text(f"{title.strip()}\n{subtitle.strip()}", encoding="utf-8")

            start = time.monotonic()
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(_SCRIPT_PATH),
                    "-TitlePath",
                    str(title_path),
                    "-OutputPath",
                    str(request.output_path),
                    "-Width",
                    str(request.width),
                    "-Height",
                    str(request.height),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            time.monotonic() - start

        if completed.returncode != 0 or not request.output_path.exists():
            raise EngineError(
                "Falha na geração local de imagem (GDI+).",
                stdout=(completed.stdout or "")[-800:],
                stderr=(completed.stderr or "")[-800:],
                returncode=completed.returncode,
            )

        return ImageGenerationResult(
            output_path=request.output_path,
            method="local:gdi_placeholder",
            provider=None,
            model=None,
            prompt=request.prompt,
        )
