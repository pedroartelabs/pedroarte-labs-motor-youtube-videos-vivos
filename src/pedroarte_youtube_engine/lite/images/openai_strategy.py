"""Estratégia OpenAI do `ImageGenerationPort` — usada só quando não há
geração nativa do ambiente de execução disponível, mediante autorização
humana explícita para a chamada específica (Gate 3C §26-28, discovery Lite
§25-27). `ANTHROPIC_API_KEY` nunca entra aqui — a Anthropic não oferece
geração de imagem via API (decisão já registrada em discoveries anteriores).

A chave é lida apenas do ambiente (variável `OPENAI_API_KEY`, carregada de
`.env` se presente) — nunca lida do código, nunca impressa, nunca registrada
em log ou proveniência.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from pedroarte_youtube_engine.lite.images.ports import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from pedroarte_youtube_engine.shared.errors import EngineError

DEFAULT_MODEL = "gpt-image-1"
DEFAULT_SIZE = "1536x1024"  # landscape mais próximo de 16:9 suportado pela API
DEFAULT_QUALITY = "medium"


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Carrega `.env` no ambiente do processo, se ainda não estiver definido.

    Não expõe nenhum valor — só popula `os.environ` quando a chave ainda não
    existe lá (nunca sobrescreve uma variável já definida no ambiente real).
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


class OpenAiImageStrategy:
    """Implementa `ImageGenerationPort` via OpenAI Images API (rede + custo real)."""

    def __init__(
        self, *, model: str = DEFAULT_MODEL, size: str = DEFAULT_SIZE, quality: str = DEFAULT_QUALITY
    ) -> None:
        self._model = model
        self._size = size
        self._quality = quality

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        _load_dotenv()
        if "OPENAI_API_KEY" not in os.environ:
            raise EngineError(
                "OPENAI_API_KEY não encontrada no ambiente/.env. Nenhuma chamada foi feita."
            )

        from openai import OpenAI

        client = OpenAI()  # lê OPENAI_API_KEY do ambiente internamente

        full_prompt = (
            f"{request.style_prefix}\n\n{request.prompt}\n\n"
            f"EVITAR: {request.negative_constraints}"
        )[:32000]

        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        start = time.monotonic()
        try:
            response = client.images.generate(
                model=self._model,
                prompt=full_prompt,
                size=self._size,
                quality=self._quality,
                n=1,
            )
        except Exception as exc:
            raise EngineError(
                "Falha na chamada à API de imagem da OpenAI.", error=str(exc)[:400]
            ) from exc
        elapsed = time.monotonic() - start

        item = response.data[0]
        if getattr(item, "b64_json", None):
            image_bytes = base64.b64decode(item.b64_json)
            request.output_path.write_bytes(image_bytes)
        elif getattr(item, "url", None):
            import urllib.request

            urllib.request.urlretrieve(item.url, request.output_path)
        else:
            raise EngineError("Resposta da OpenAI sem b64_json nem url.")

        if not request.output_path.exists() or request.output_path.stat().st_size == 0:
            raise EngineError("Imagem não foi escrita corretamente.")

        return ImageGenerationResult(
            output_path=request.output_path,
            method="external_api:openai",
            provider="openai",
            model=self._model,
            prompt=full_prompt,
            extra={
                "size_requested": self._size,
                "quality": self._quality,
                "generation_time_seconds": f"{elapsed:.2f}",
            },
        )
