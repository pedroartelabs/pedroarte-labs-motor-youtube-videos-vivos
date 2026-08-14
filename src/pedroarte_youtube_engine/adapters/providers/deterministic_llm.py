"""LLM determinístico local — o adaptador padrão.

O motor **não depende de um LLM**. Onde um sistema convencional chamaria um
modelo, este adaptador aplica a regra correspondente de forma explícita e
auditável, e declara `is_available() == True` sem credencial nenhuma.

Isso não é um placeholder: é uma escolha de arquitetura. O trabalho pesado de
compreensão narrativa está no `HeuristicNarrativeAnalyzer` e nos serviços de
domínio, que são testáveis e reproduzíveis. Um LLM real pode ser plugado pela
mesma porta quando houver credencial e orçamento — e aí ele *melhora* o
resultado, em vez de ser condição para existir resultado.
"""

from __future__ import annotations

from pedroarte_youtube_engine.ports.llm import LLMRequest, LLMResponse
from pedroarte_youtube_engine.shared.hashing import structural_hash


class DeterministicLLMProvider:
    """Provedor local que não faz rede e não consome quota."""

    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    @property
    def name(self) -> str:
        return "deterministic-local"

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Devolve o próprio conteúdo estruturado da requisição.

        Os agentes deste motor montam o texto que precisam a partir do domínio;
        quando chamam esta porta, é para registrar a decisão de forma
        rastreável, não para pedir criatividade a um modelo.
        """
        self.calls.append(request)
        digest = structural_hash(
            {
                "prompt": request.prompt_name,
                "version": request.prompt_version,
                "user": request.user,
            }
        )
        return LLMResponse(
            text=request.user,
            parsed=None,
            model=f"{self.name}/{request.prompt_name}@{request.prompt_version}",
            input_tokens=len(request.user) // 4,
            output_tokens=len(request.user) // 4,
            finish_reason="deterministic",
            cached=True,
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)
