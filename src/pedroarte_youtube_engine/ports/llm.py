"""Porta de modelo de linguagem.

O motor **não exige** um LLM para funcionar: o adaptador padrão é determinístico
e local. Esta porta existe para que um LLM possa ser plugado quando houver
credencial e orçamento, sem que nada no domínio mude.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class LLMRequest(BaseModel):
    """Requisição tipada a um modelo de linguagem."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_name: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=32)
    system: str = Field(default="")
    user: str = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, gt=0)
    json_schema: dict[str, object] | None = None
    correlation_id: str = Field(default="", max_length=64)


class LLMResponse(BaseModel):
    """Resposta de um modelo de linguagem."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(default="")
    parsed: dict[str, object] | None = None
    model: str = Field(default="")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    finish_reason: str = Field(default="stop", max_length=64)
    cached: bool = False


@runtime_checkable
class LLMProviderPort(Protocol):
    """Gera texto (ou JSON estruturado) a partir de um prompt versionado."""

    @property
    def name(self) -> str:
        """Identificador do provedor, usado em logs e no manifesto."""
        ...

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Executa a requisição e devolve a resposta."""
        ...

    def is_available(self) -> bool:
        """Informa se o provedor pode ser usado (credencial, quota, circuito)."""
        ...
