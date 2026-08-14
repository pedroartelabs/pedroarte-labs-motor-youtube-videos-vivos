"""Parsers de formatos textuais — sem dependências externas.

Markdown, texto puro, JSON e YAML cobrem o caminho principal do motor e
funcionam em qualquer instalação, inclusive a mínima.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from pedroarte_youtube_engine.ports.parsing import ParsedDocument
from pedroarte_youtube_engine.shared.errors import IngestionError
from pedroarte_youtube_engine.shared.text import normalize_whitespace

#: Cabeçalhos de capítulo em Markdown (`#` a `###`).
_MD_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)

#: Cabeçalhos de capítulo em texto puro, no estilo brasileiro.
_TXT_HEADING = re.compile(
    r"^\s*(CAP[ÍI]TULO|CAPITULO|PARTE|LIVRO|ATO)\s+([\dIVXLCDM]+|[A-Za-zÀ-ÿ]+)\s*[-–—:.]?\s*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_text(path: Path) -> tuple[str, str]:
    """Lê um arquivo tentando UTF-8 e recaindo para Latin-1 quando necessário."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise IngestionError("Não foi possível decodificar o arquivo.", path=str(path))


class MarkdownParser:
    """Lê Markdown preservando a hierarquia de títulos como capítulos."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def parse(self, path: Path) -> ParsedDocument:
        raw, encoding = _read_text(path)
        title = ""
        author = ""
        warnings: list[str] = []

        frontmatter_match = _FRONTMATTER.match(raw)
        if frontmatter_match:
            try:
                metadata = yaml.safe_load(frontmatter_match.group(1)) or {}
                if isinstance(metadata, dict):
                    title = str(metadata.get("title", "") or "")
                    author = str(metadata.get("author", "") or "")
            except yaml.YAMLError:
                warnings.append("Frontmatter YAML inválido; ignorado.")
            raw = raw[frontmatter_match.end() :]

        headings = list(_MD_HEADING.finditer(raw))
        sections = self._split_sections(raw, headings)

        if not title and headings and len(headings[0].group(1)) == 1:
            title = headings[0].group(2).strip()

        return ParsedDocument(
            text=normalize_whitespace(raw),
            title=title,
            author=author,
            encoding=encoding,
            sections=sections,
            warnings=tuple(warnings),
        )

    def _split_sections(
        self, raw: str, headings: list[re.Match[str]]
    ) -> tuple[tuple[str, str], ...]:
        """Divide por títulos, preferindo o nível mais usado como 'capítulo'."""
        if not headings:
            return ()
        levels = [len(match.group(1)) for match in headings]
        # O nível de capítulo é o mais frequente com pelo menos duas ocorrências.
        counts = {level: levels.count(level) for level in set(levels)}
        chapter_level = max(
            (level for level, count in counts.items() if count >= 2),
            default=max(levels),
        )
        chapter_headings = [
            match for match in headings if len(match.group(1)) == chapter_level
        ]
        if not chapter_headings:
            return ()

        sections: list[tuple[str, str]] = []
        for index, match in enumerate(chapter_headings):
            start = match.end()
            end = (
                chapter_headings[index + 1].start()
                if index + 1 < len(chapter_headings)
                else len(raw)
            )
            body = normalize_whitespace(raw[start:end])
            if body:
                sections.append((match.group(2).strip(), body))
        return tuple(sections)


class PlainTextParser:
    """Lê `.txt` detectando cabeçalhos de capítulo em português."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset({".txt", ".text"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def parse(self, path: Path) -> ParsedDocument:
        raw, encoding = _read_text(path)
        normalized = normalize_whitespace(raw)
        matches = list(_TXT_HEADING.finditer(normalized))

        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
            heading = " ".join(part for part in match.groups() if part).strip()
            body = normalized[start:end].strip()
            if body:
                sections.append((heading, body))

        first_line = normalized.split("\n", 1)[0].strip()
        title = first_line if len(first_line) <= 120 and not matches else ""

        return ParsedDocument(
            text=normalized,
            title=title,
            encoding=encoding,
            sections=tuple(sections),
        )


class JsonParser:
    """Lê JSON estruturado (fichas de personagem, bíblias de universo)."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset({".json"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def parse(self, path: Path) -> ParsedDocument:
        raw, encoding = _read_text(path)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IngestionError(
                f"JSON inválido: {exc.msg} (linha {exc.lineno}).", path=str(path)
            ) from exc
        structured = payload if isinstance(payload, dict) else {"items": payload}
        return ParsedDocument(
            text=_flatten_structure(payload),
            title=str(structured.get("title", "") or "") if isinstance(payload, dict) else "",
            encoding=encoding,
            structured=structured,
        )


class YamlParser:
    """Lê YAML estruturado — inclusive o `project.yaml`."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        return frozenset({".yaml", ".yml"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def parse(self, path: Path) -> ParsedDocument:
        raw, encoding = _read_text(path)
        try:
            payload = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise IngestionError(f"YAML inválido: {exc}", path=str(path)) from exc
        if payload is None:
            payload = {}
        structured = payload if isinstance(payload, dict) else {"items": payload}
        title = ""
        if isinstance(payload, dict):
            project = payload.get("project")
            if isinstance(project, dict):
                title = str(project.get("title", "") or "")
            else:
                title = str(payload.get("title", "") or "")
        return ParsedDocument(
            text=_flatten_structure(payload),
            title=title,
            encoding=encoding,
            structured=structured,
        )


def _flatten_structure(payload: Any, *, prefix: str = "") -> str:
    """Achata uma estrutura em linhas legíveis, para indexação no RAG."""
    lines: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif node is not None:
            lines.append(f"{path}: {node}")

    walk(payload, prefix)
    return "\n".join(lines)
