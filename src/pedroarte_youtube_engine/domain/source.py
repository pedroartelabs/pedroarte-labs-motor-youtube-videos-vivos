"""Entidades de origem: o material bruto colocado em `input/`.

Estas entidades preservam a rastreabilidade entre cada afirmação do cânone e o
texto que a originou. Nenhum artefato sai do motor sem essa cadeia.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pedroarte_youtube_engine.domain.value_objects import ContentHash, Language, SourceId
from pedroarte_youtube_engine.shared.text import count_words, excerpt


class DomainEntity(BaseModel):
    """Base das entidades: estrita, serializável e imutável por padrão.

    Mutações acontecem por cópia funcional (`model_copy(update=...)`), o que
    mantém o histórico do pipeline auditável e evita que um agente altere em
    silêncio o objeto de outro (regra da seção 8).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class SourceKind(StrEnum):
    """Natureza do documento, decidida pelo `INPUT_DISCOVERY_AGENT`."""

    BOOK = "livro"
    NOVEL = "romance"
    SHORT_STORY = "conto"
    SCREENPLAY = "roteiro"
    EXPANDED_SYNOPSIS = "sinopse_expandida"
    UNIVERSE_BIBLE = "biblia_de_universo"
    CHAPTER_COLLECTION = "colecao_de_capitulos"
    LITERARY_SERIES = "serie_literaria"
    NARRATIVE_NOTES = "notas_narrativas"
    CHARACTER_DOCUMENT = "documento_de_personagens"
    CANON_AUXILIARY = "documento_auxiliar_de_canone"
    PROJECT_CONFIG = "configuracao_de_projeto"
    UNKNOWN = "desconhecido"

    @property
    def is_narrative(self) -> bool:
        """Documentos narrativos alimentam a adaptação; os demais só o cânone."""
        return self in {
            SourceKind.BOOK,
            SourceKind.NOVEL,
            SourceKind.SHORT_STORY,
            SourceKind.SCREENPLAY,
            SourceKind.EXPANDED_SYNOPSIS,
            SourceKind.CHAPTER_COLLECTION,
            SourceKind.LITERARY_SERIES,
        }


class SourceFormat(StrEnum):
    MARKDOWN = "md"
    PLAIN_TEXT = "txt"
    DOCX = "docx"
    PDF = "pdf"
    EPUB = "epub"
    JSON = "json"
    YAML = "yaml"

    @classmethod
    def from_suffix(cls, suffix: str) -> "SourceFormat":
        normalized = suffix.lower().lstrip(".")
        if normalized == "yml":
            return cls.YAML
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Formato de entrada não suportado: {suffix!r}") from exc


class SourceDocument(DomainEntity):
    """Um arquivo descoberto em `input/`, já lido e normalizado."""

    source_id: SourceId
    relative_path: str = Field(min_length=1, max_length=512)
    kind: SourceKind
    source_format: SourceFormat
    content_hash: ContentHash
    size_bytes: int = Field(ge=0)
    encoding: str = Field(default="utf-8", max_length=32)
    title: str = Field(default="", max_length=300)
    text: str = Field(default="")
    #: Pares `(título, corpo)` quando o formato de origem expôs capítulos.
    #: Guardar aqui evita reprocessar o arquivo — e evita que a estrutura se
    #: perca entre a descoberta e a ingestão.
    sections: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    is_primary: bool = False
    detection_reason: str = Field(default="", max_length=400)

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    def preview(self) -> str:
        return excerpt(self.text, max_chars=240)


class Chapter(DomainEntity):
    """Capítulo preservado com ordem, título e deslocamentos no texto canônico."""

    source_id: SourceId
    index: int = Field(ge=0)
    number: str = Field(default="", max_length=32)
    title: str = Field(default="", max_length=300)
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_offsets(self) -> Self:
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset não pode preceder start_offset em um capítulo.")
        return self

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    @property
    def label(self) -> str:
        if self.title and self.number:
            return f"{self.number} — {self.title}"
        return self.title or self.number or f"Capítulo {self.index + 1}"


class BookSource(DomainEntity):
    """Documento canônico consolidado, com todos os capítulos em ordem.

    É o resultado do `BOOK_INGESTION_AGENT`: um único texto normalizado, o mapa
    de capítulos e o rastro de todos os documentos que contribuíram.
    """

    primary_source_id: SourceId
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(default="", max_length=200)
    language: Language
    documents: tuple[SourceDocument, ...] = Field(default_factory=tuple)
    chapters: tuple[Chapter, ...] = Field(default_factory=tuple)
    canonical_text: str = Field(default="")
    canonical_hash: ContentHash

    @model_validator(mode="after")
    def _validate_chapter_order(self) -> Self:
        indices = [chapter.index for chapter in self.chapters]
        if indices != sorted(indices):
            raise ValueError("Os capítulos devem estar em ordem crescente de índice.")
        if len(set(indices)) != len(indices):
            raise ValueError("Índices de capítulo duplicados.")
        return self

    @property
    def word_count(self) -> int:
        return count_words(self.canonical_text)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    def narrative_documents(self) -> tuple[SourceDocument, ...]:
        return tuple(document for document in self.documents if document.kind.is_narrative)

    def auxiliary_documents(self) -> tuple[SourceDocument, ...]:
        return tuple(document for document in self.documents if not document.kind.is_narrative)

    def chapter_at(self, index: int) -> Chapter | None:
        for chapter in self.chapters:
            if chapter.index == index:
                return chapter
        return None


class SourceMapEntry(DomainEntity):
    """Linha do `source_map.json`: o que foi lido, de onde, com que hash."""

    source_id: SourceId
    relative_path: str
    kind: SourceKind
    source_format: SourceFormat
    content_hash: ContentHash
    size_bytes: int = Field(ge=0)
    word_count: int = Field(ge=0)
    chapter_count: int = Field(default=0, ge=0)
    is_primary: bool = False
    detection_reason: str = ""
