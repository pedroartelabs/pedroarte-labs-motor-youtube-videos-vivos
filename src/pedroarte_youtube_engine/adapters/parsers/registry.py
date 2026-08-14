"""Registro de parsers — o ponto de extensão para novos formatos de entrada."""

from __future__ import annotations

from pathlib import Path

from pedroarte_youtube_engine.adapters.parsers.binary import (
    DocxParser,
    EpubParser,
    PdfParser,
)
from pedroarte_youtube_engine.adapters.parsers.text import (
    JsonParser,
    MarkdownParser,
    PlainTextParser,
    YamlParser,
)
from pedroarte_youtube_engine.ports.parsing import DocumentParserPort, ParsedDocument
from pedroarte_youtube_engine.shared.errors import IngestionError


class ParserRegistry:
    """Escolhe o parser adequado para cada arquivo.

    Registrar um novo formato é uma linha: `registry.register(MeuParser())`.
    """

    def __init__(self, parsers: tuple[DocumentParserPort, ...] | None = None) -> None:
        self._parsers: list[DocumentParserPort] = list(
            parsers
            if parsers is not None
            else (
                MarkdownParser(),
                PlainTextParser(),
                JsonParser(),
                YamlParser(),
                DocxParser(),
                PdfParser(),
                EpubParser(),
            )
        )

    def register(self, parser: DocumentParserPort) -> None:
        self._parsers.insert(0, parser)

    def supported_suffixes(self) -> frozenset[str]:
        merged: set[str] = set()
        for parser in self._parsers:
            merged |= parser.supported_suffixes
        return frozenset(merged)

    def find(self, path: Path) -> DocumentParserPort | None:
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser
        return None

    def parse(self, path: Path) -> ParsedDocument:
        parser = self.find(path)
        if parser is None:
            raise IngestionError(
                f"Nenhum parser registrado para {path.suffix!r}.",
                path=str(path),
                supported=sorted(self.supported_suffixes()),
            )
        return parser.parse(path)
