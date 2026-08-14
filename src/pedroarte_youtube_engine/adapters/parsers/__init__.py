"""Parsers de documentos de entrada."""

from __future__ import annotations

from pedroarte_youtube_engine.adapters.parsers.binary import (
    DocxParser,
    EpubParser,
    PdfParser,
)
from pedroarte_youtube_engine.adapters.parsers.registry import ParserRegistry
from pedroarte_youtube_engine.adapters.parsers.text import (
    JsonParser,
    MarkdownParser,
    PlainTextParser,
    YamlParser,
)

__all__ = [
    "DocxParser",
    "EpubParser",
    "JsonParser",
    "MarkdownParser",
    "ParserRegistry",
    "PdfParser",
    "PlainTextParser",
    "YamlParser",
]
