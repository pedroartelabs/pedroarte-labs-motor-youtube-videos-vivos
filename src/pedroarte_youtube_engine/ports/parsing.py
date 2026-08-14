"""Porta de leitura de documentos de entrada."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ParsedDocument(BaseModel):
    """Texto extraído de um arquivo, com a estrutura que ele revelou."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(default="")
    title: str = Field(default="", max_length=300)
    author: str = Field(default="", max_length=200)
    encoding: str = Field(default="utf-8", max_length=32)
    #: Pares `(título, texto)` quando o formato expõe capítulos explicitamente.
    sections: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    #: Dados estruturados, quando a entrada é JSON ou YAML.
    structured: dict[str, object] | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)


@runtime_checkable
class DocumentParserPort(Protocol):
    """Converte um arquivo de entrada em texto normalizado."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Extensões que este parser sabe ler, em minúsculas e com ponto."""
        ...

    def can_parse(self, path: Path) -> bool: ...

    def parse(self, path: Path) -> ParsedDocument: ...
