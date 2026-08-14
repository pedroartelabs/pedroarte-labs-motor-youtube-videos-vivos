"""Provedores falsos determinísticos.

Servem a dois propósitos:

1. **Testes sem rede e sem credencial** — a suíte inteira roda offline.
2. **Ensaio de execução real** — com `execute_generation: true` e provedor
   `fake`, o operador exercita o caminho completo (idempotência, retry, custo,
   manifesto) sem gastar um centavo.

Todos são determinísticos: a mesma entrada produz a mesma saída, sempre.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from pedroarte_youtube_engine.ports.llm import LLMRequest, LLMResponse
from pedroarte_youtube_engine.ports.media import GenerationRequest, GenerationResult
from pedroarte_youtube_engine.rag.embedding import HashingEmbeddingProvider
from pedroarte_youtube_engine.shared.hashing import content_hash, structural_hash


class FakeLLMProvider:
    """LLM falso: devolve respostas roteirizadas ou um eco determinístico."""

    def __init__(
        self,
        *,
        responses: dict[str, str] | None = None,
        available: bool = True,
        fail_on: Callable[[LLMRequest], bool] | None = None,
    ) -> None:
        self._responses = responses or {}
        self._available = available
        self._fail_on = fail_on
        self.calls: list[LLMRequest] = []

    @property
    def name(self) -> str:
        return "fake-llm"

    def is_available(self) -> bool:
        return self._available

    def complete(self, request: LLMRequest) -> LLMResponse:
        from pedroarte_youtube_engine.shared.errors import ProviderError

        self.calls.append(request)
        if self._fail_on is not None and self._fail_on(request):
            raise ProviderError("Falha simulada pelo FakeLLMProvider.", provider=self.name)

        scripted = self._responses.get(request.prompt_name)
        text = scripted if scripted is not None else self._echo(request)
        parsed = None
        if request.json_schema is not None:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"text": text}

        return LLMResponse(
            text=text,
            parsed=parsed,
            model=f"{self.name}/v1",
            input_tokens=len(request.user) // 4,
            output_tokens=len(text) // 4,
        )

    @staticmethod
    def _echo(request: LLMRequest) -> str:
        digest = structural_hash({"prompt": request.prompt_name, "user": request.user})
        return (
            f"[fake:{request.prompt_name}@{request.prompt_version}] "
            f"{request.user[:200]} ({digest[7:19]})"
        )


class _FakeMediaProvider:
    """Base dos geradores de mídia falsos."""

    kind = "media"

    def __init__(self, *, available: bool = True, cost_per_call: float = 0.0) -> None:
        self._available = available
        self._cost = cost_per_call
        self.requests: list[GenerationRequest] = []

    @property
    def name(self) -> str:
        return f"fake-{self.kind}"

    def is_available(self) -> bool:
        return self._available

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        digest = content_hash(request.prompt.prompt_text).split(":", 1)[1][:16]
        reference = (
            f"{request.output_directory.rstrip('/')}/"
            f"{request.prompt.segment_id}_{self.kind}_{digest}.{self._extension}"
        )
        return GenerationResult(
            succeeded=True,
            output_reference=reference,
            provider_job_id=f"{self.name}-{request.idempotency_key[:12]}",
            estimated_cost_usd=self._cost,
            duration_seconds=request.prompt.provider_duration_seconds,
            raw_response_digest=digest,
        )

    @property
    def _extension(self) -> str:
        return "bin"


class FakeVideoProvider(_FakeMediaProvider):
    kind = "video"

    def __init__(self, *, native_audio: bool = True, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._native_audio = native_audio

    def supports_native_audio(self) -> bool:
        return self._native_audio

    @property
    def _extension(self) -> str:
        return "mp4"


class FakeImageProvider(_FakeMediaProvider):
    kind = "image"

    def supports_reference_image(self) -> bool:
        return True

    @property
    def _extension(self) -> str:
        return "png"


class FakeVoiceProvider(_FakeMediaProvider):
    kind = "voice"

    def available_voices(self) -> tuple[str, ...]:
        return ("fake_voice_a", "fake_voice_b", "fake_voice_narrator")

    @property
    def _extension(self) -> str:
        return "wav"


class FakeMusicProvider(_FakeMediaProvider):
    kind = "music"

    def max_duration_seconds(self) -> float:
        return 600.0

    @property
    def _extension(self) -> str:
        return "wav"


class FakeEmbeddingProvider:
    """Embeddings falsos, mas úteis: reaproveitam o hashing local.

    Usar hashing real em vez de vetores aleatórios mantém a similaridade
    significativa nos testes de contrato do RAG.
    """

    def __init__(self, *, dimensions: int = 64) -> None:
        self._delegate = HashingEmbeddingProvider(dimensions=dimensions)
        self.calls = 0

    @property
    def name(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return self._delegate.dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls += 1
        return self._delegate.embed(text)

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += len(texts)
        return self._delegate.embed_batch(texts)
