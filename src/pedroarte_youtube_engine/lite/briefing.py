"""BriefingSchema — o menor contrato necessário (SDD_SPDD.md §38.1).

Reaproveita o padrão `frozen=True, extra="forbid"` do legacy
(`domain/configuration.py::ConfigModel`) sem importar a classe: o padrão é
uma linha, e importar `domain.configuration` arrastaria dependências do
domínio de 6 formatos que o Lite não usa.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactualityMode(StrEnum):
    """Registrado no manifesto — nunca decidido implicitamente pelo texto do roteiro."""

    CREATIVE = "creative"
    GENERAL_KNOWLEDGE = "general_knowledge"
    FACT_SENSITIVE = "fact_sensitive"


class BriefingSchema(BaseModel):
    """Contrato de entrada do Gate 3A. Estrito: campos desconhecidos são rejeitados."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    topic: str = Field(min_length=3, max_length=300)
    objective: str = Field(min_length=3, max_length=600)
    audience: str = Field(default="", max_length=300)
    language: str = Field(default="pt-BR", max_length=16)
    tone: str = Field(default="", max_length=200)
    target_min_minutes: float = Field(default=10.0, gt=0, le=60)
    target_max_minutes: float = Field(default=15.0, gt=0, le=60)
    must_include: tuple[str, ...] = Field(default_factory=tuple)
    must_avoid: tuple[str, ...] = Field(default_factory=tuple)
    references: tuple[str, ...] = Field(default_factory=tuple)
    additional_context: str = Field(default="", max_length=4000)
    visual_direction: str = Field(default="", max_length=800)
    factuality_mode: FactualityMode = FactualityMode.GENERAL_KNOWLEDGE

    @model_validator(mode="after")
    def _validate_duration_range(self) -> "BriefingSchema":
        if self.target_max_minutes < self.target_min_minutes:
            raise ValueError(
                "target_max_minutes não pode ser menor que target_min_minutes."
            )
        return self
