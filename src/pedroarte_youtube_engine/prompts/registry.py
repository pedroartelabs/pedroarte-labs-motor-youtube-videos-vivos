"""Estrutura do registro de prompts."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.domain.value_objects import PromptVersion
from pedroarte_youtube_engine.shared.errors import ConfigurationError
from pedroarte_youtube_engine.shared.hashing import content_hash


class PromptDefinition(BaseModel):
    """Um prompt versionado do catálogo de agentes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3, max_length=128)
    version: PromptVersion
    agent: str = Field(min_length=3, max_length=96)
    objective: str = Field(min_length=10, max_length=1200)
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    template: str = Field(min_length=20)
    changed_at: date
    recommended_model: str = Field(default="deterministic-local", max_length=128)
    recommended_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    evaluation_criteria: tuple[str, ...] = Field(min_length=1)
    notes: str = Field(default="", max_length=1200)

    @property
    def hash(self) -> str:
        """Hash do conteúdo — muda sempre que o template muda."""
        return content_hash(f"{self.name}@{self.version}\n{self.template}")

    @property
    def qualified_name(self) -> str:
        return f"{self.name}@{self.version}"

    def render(self, **variables: object) -> str:
        """Preenche o template com as variáveis informadas.

        Uma variável faltando é erro, não string vazia: um prompt incompleto
        produziria um artefato incompleto sem que ninguém percebesse.
        """
        try:
            return self.template.format(**variables)
        except KeyError as exc:
            raise ConfigurationError(
                f"Variável ausente no prompt {self.qualified_name}: {exc}",
                prompt=self.qualified_name,
                missing=str(exc),
            ) from exc


class PromptRegistry:
    """Coleção imutável de prompts, indexada por nome."""

    def __init__(self, definitions: tuple[PromptDefinition, ...]) -> None:
        self._by_name: dict[str, PromptDefinition] = {}
        for definition in definitions:
            if definition.name in self._by_name:
                raise ConfigurationError(
                    f"Prompt duplicado no registro: {definition.name}",
                    name=definition.name,
                )
            self._by_name[definition.name] = definition

    def get(self, name: str) -> PromptDefinition | None:
        return self._by_name.get(name)

    def require(self, name: str) -> PromptDefinition:
        definition = self.get(name)
        if definition is None:
            raise ConfigurationError(
                f"Prompt não registrado: {name}",
                name=name,
                available=sorted(self._by_name),
            )
        return definition

    def for_agent(self, agent: str) -> tuple[PromptDefinition, ...]:
        return tuple(
            definition
            for definition in self._by_name.values()
            if definition.agent == agent
        )

    def all(self) -> tuple[PromptDefinition, ...]:
        return tuple(self._by_name[name] for name in sorted(self._by_name))

    def manifest(self) -> list[dict[str, str]]:
        """Inventário para o `manifest.json` da execução."""
        return [
            {
                "name": definition.name,
                "version": str(definition.version),
                "agent": definition.agent,
                "hash": definition.hash,
                "changed_at": definition.changed_at.isoformat(),
                "model": definition.recommended_model,
            }
            for definition in self.all()
        ]

    def __len__(self) -> int:
        return len(self._by_name)

    def __contains__(self, name: object) -> bool:
        return name in self._by_name
