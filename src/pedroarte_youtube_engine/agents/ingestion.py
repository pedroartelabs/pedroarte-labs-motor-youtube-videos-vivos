"""Agentes de descoberta e ingestão (9.2 e 9.3)."""

from __future__ import annotations

from pathlib import Path

from pedroarte_youtube_engine.adapters.parsers import ParserRegistry
from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.source import (
    BookSource,
    Chapter,
    SourceDocument,
    SourceFormat,
    SourceKind,
    SourceMapEntry,
)
from pedroarte_youtube_engine.domain.value_objects import ContentHash, SourceId
from pedroarte_youtube_engine.shared.errors import IngestionError
from pedroarte_youtube_engine.shared.hashing import content_hash, file_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, iter_input_files
from pedroarte_youtube_engine.shared.text import normalize_whitespace, safe_slug

#: Pistas de nome de arquivo que revelam a natureza do documento.
_NAME_HINTS: tuple[tuple[tuple[str, ...], SourceKind], ...] = (
    (("project", "config", "projeto"), SourceKind.PROJECT_CONFIG),
    (("personagem", "character", "elenco", "cast"), SourceKind.CHARACTER_DOCUMENT),
    (("biblia", "bible", "universo", "universe", "mundo", "world"), SourceKind.UNIVERSE_BIBLE),
    (("roteiro", "script", "screenplay"), SourceKind.SCREENPLAY),
    (("sinopse", "synopsis", "resumo"), SourceKind.EXPANDED_SYNOPSIS),
    (("nota", "note", "rascunho"), SourceKind.NARRATIVE_NOTES),
    (("conto", "short-story"), SourceKind.SHORT_STORY),
    (("serie", "series", "saga"), SourceKind.LITERARY_SERIES),
    (("livro", "book", "romance", "novel"), SourceKind.BOOK),
)

#: Abaixo disso, um documento de texto é auxiliar, não a obra principal.
_MIN_PRIMARY_WORDS = 400


class InputDiscoveryAgent(BaseAgent):
    """`INPUT_DISCOVERY_AGENT` — analisa `input/` e elege o documento principal."""

    _contract = AgentContract(
        name="INPUT_DISCOVERY_AGENT",
        responsibility=(
            "Analisar a pasta de entrada, identificar documentos e formatos, determinar "
            "o arquivo principal, calcular hashes, registrar proveniência e sinalizar "
            "ambiguidades em vez de resolvê-las em silêncio."
        ),
        phase="DISCOVERING_INPUT",
        input_type="Path",
        output_type="tuple[SourceDocument, ...]",
        authorized_tools=(AgentTool.FILESYSTEM_READ,),
        memory=MemoryScope.RUN,
        prompt_name="discovery.classify_inputs",
        completion_criteria=(
            "Ao menos um documento narrativo foi encontrado.",
            "Exatamente um documento principal foi eleito.",
            "Todo documento tem hash e motivo de classificação.",
        ),
        failure_criteria=(
            "A pasta de entrada não existe ou está vazia.",
            "Nenhum documento com conteúdo narrativo foi encontrado.",
        ),
    )

    def __init__(self, *, policy: PathPolicy, parsers: ParserRegistry | None = None) -> None:
        self._policy = policy
        self._parsers = parsers or ParserRegistry()

    def run(self, context: EngineContext) -> AgentResult:
        log = self._log(context)
        root = Path(context.input_directory)
        documents: list[SourceDocument] = []
        notes: list[str] = []

        paths = list(iter_input_files(root, self._policy))
        if not paths:
            raise IngestionError(
                "Nenhum arquivo legível encontrado na pasta de entrada. "
                f"Extensões aceitas: {sorted(self._policy.allowed_extensions)}.",
                input_directory=str(root),
            )

        for path in paths:
            size = self._policy.check_file_size(path)
            relative = path.relative_to(root).as_posix()
            source_id = SourceId(value=safe_slug(relative, max_length=100))

            try:
                parsed = self._parsers.parse(path)
            except IngestionError as exc:
                # Um documento ilegível não derruba a execução: ele é registrado
                # como não lido e o operador decide o que fazer.
                notes.append(f"{relative}: {exc.message}")
                log.warning("Documento ignorado", path=relative, reason=exc.message)
                continue

            kind = self._classify(path, parsed.text, parsed.structured is not None)
            documents.append(
                SourceDocument(
                    source_id=source_id,
                    relative_path=relative,
                    kind=kind,
                    source_format=SourceFormat.from_suffix(path.suffix),
                    content_hash=ContentHash(value=file_hash(path)),
                    size_bytes=size,
                    encoding=parsed.encoding,
                    title=parsed.title,
                    text=parsed.text,
                    sections=parsed.sections,
                    detection_reason=self._reason(path, kind, parsed.text),
                )
            )
            notes.extend(f"{relative}: {warning}" for warning in parsed.warnings)

        documents = self._elect_primary(documents, notes)
        narrative = [document for document in documents if document.kind.is_narrative]
        if not narrative:
            raise IngestionError(
                "Nenhum documento narrativo foi encontrado. O motor precisa de ao menos "
                "um livro, conto, roteiro ou sinopse expandida em `input/`.",
                found=[document.relative_path for document in documents],
            )

        log.info(
            "Entrada descoberta",
            documents=len(documents),
            narrative=len(narrative),
            primary=next(d.relative_path for d in documents if d.is_primary),
        )

        return AgentResult(
            agent=self.name,
            outputs={"documents": tuple(documents)},
            notes=tuple(notes),
            events=(
                DomainEvent(
                    event_type=DomainEventType.INPUT_DISCOVERED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "documents": len(documents),
                        "narrative_documents": len(narrative),
                        "ambiguities": len(notes),
                    },
                ),
            ),
        )

    # -- classificação -----------------------------------------------------

    def _classify(self, path: Path, text: str, structured: bool) -> SourceKind:
        stem = safe_slug(path.stem)
        for tokens, kind in _NAME_HINTS:
            if any(token in stem for token in tokens):
                return kind

        if structured:
            return SourceKind.CANON_AUXILIARY

        words = len(text.split())
        if words >= _MIN_PRIMARY_WORDS:
            return SourceKind.BOOK
        if words > 0:
            return SourceKind.NARRATIVE_NOTES
        return SourceKind.UNKNOWN

    @staticmethod
    def _reason(path: Path, kind: SourceKind, text: str) -> str:
        return (
            f"Classificado como '{kind.value}' pelo nome do arquivo "
            f"('{path.name}') e por conter {len(text.split())} palavras."
        )

    def _elect_primary(
        self, documents: list[SourceDocument], notes: list[str]
    ) -> list[SourceDocument]:
        """Elege o documento principal: o narrativo de maior volume."""
        narrative = [document for document in documents if document.kind.is_narrative]
        if not narrative:
            return documents

        ranked = sorted(narrative, key=lambda document: (-document.word_count, document.relative_path))
        primary = ranked[0]

        if len(ranked) > 1 and ranked[1].word_count >= primary.word_count * 0.8:
            notes.append(
                f"Ambiguidade: '{primary.relative_path}' e '{ranked[1].relative_path}' têm "
                "volumes semelhantes. O primeiro foi eleito como obra principal; use "
                "`project.yaml` para forçar outra escolha."
            )

        return [
            document.model_copy(update={"is_primary": document.source_id == primary.source_id})
            for document in documents
        ]


class BookIngestionAgent(BaseAgent):
    """`BOOK_INGESTION_AGENT` — produz o documento canônico com capítulos."""

    _contract = AgentContract(
        name="BOOK_INGESTION_AGENT",
        responsibility=(
            "Extrair o texto preservando capítulos, títulos e ordem, normalizar a "
            "codificação, produzir o documento canônico e criar o mapa de fontes."
        ),
        phase="INGESTING",
        input_type="tuple[SourceDocument, ...]",
        output_type="BookSource",
        authorized_tools=(AgentTool.FILESYSTEM_READ,),
        memory=MemoryScope.RUN,
        prompt_name="ingestion.normalize",
        completion_criteria=(
            "O texto canônico não está vazio.",
            "Os capítulos estão em ordem crescente e sem índices duplicados.",
            "Cada capítulo tem deslocamento inicial e final.",
        ),
        failure_criteria=("O documento principal não produziu texto legível.",),
    )

    def __init__(self, *, parsers: ParserRegistry | None = None) -> None:
        self._parsers = parsers or ParserRegistry()

    def run(self, context: EngineContext) -> AgentResult:
        log = self._log(context)
        documents: tuple[SourceDocument, ...] = context.scratch["documents"]
        primary = next(document for document in documents if document.is_primary)

        chapters = self._build_chapters(primary)
        canonical_text = self._build_canonical_text(chapters, primary)

        if not canonical_text.strip():
            raise IngestionError(
                "O documento principal não produziu texto legível.",
                path=primary.relative_path,
            )

        configuration = context.configuration
        book = BookSource(
            primary_source_id=primary.source_id,
            title=configuration.project.title or primary.title or primary.relative_path,
            author=configuration.project.author,
            language=configuration.project.language,
            documents=documents,
            chapters=chapters,
            canonical_text=canonical_text,
            canonical_hash=ContentHash(value=content_hash(canonical_text)),
        )

        source_map = tuple(
            SourceMapEntry(
                source_id=document.source_id,
                relative_path=document.relative_path,
                kind=document.kind,
                source_format=document.source_format,
                content_hash=document.content_hash,
                size_bytes=document.size_bytes,
                word_count=document.word_count,
                chapter_count=len(chapters) if document.is_primary else 0,
                is_primary=document.is_primary,
                detection_reason=document.detection_reason,
            )
            for document in documents
        )

        log.info(
            "Obra ingerida",
            title=book.title,
            chapters=book.chapter_count,
            words=book.word_count,
            hash=book.canonical_hash.short,
        )

        return AgentResult(
            agent=self.name,
            outputs={"book": book, "source_map": source_map},
            events=(
                DomainEvent(
                    event_type=DomainEventType.BOOK_INGESTED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "title": book.title,
                        "chapters": book.chapter_count,
                        "words": book.word_count,
                        "canonical_hash": book.canonical_hash.value,
                    },
                ),
            ),
        )

    # -- construção --------------------------------------------------------

    def _build_chapters(self, primary: SourceDocument) -> tuple[Chapter, ...]:
        """Reconstrói os capítulos a partir do documento principal."""
        offset = 0
        chapters: list[Chapter] = []

        sections = primary.sections or ((primary.title or "Texto integral", primary.text),)
        for index, (title, body) in enumerate(sections):
            normalized = normalize_whitespace(body)
            if not normalized:
                continue
            number, clean_title = _split_chapter_label(title)
            chapters.append(
                Chapter(
                    source_id=primary.source_id,
                    index=len(chapters),
                    number=number,
                    title=clean_title,
                    text=normalized,
                    start_offset=offset,
                    end_offset=offset + len(normalized),
                )
            )
            offset += len(normalized) + 2

        return tuple(chapters)

    @staticmethod
    def _build_canonical_text(
        chapters: tuple[Chapter, ...], primary: SourceDocument
    ) -> str:
        if not chapters:
            return normalize_whitespace(primary.text)
        return "\n\n".join(f"{chapter.label}\n\n{chapter.text}" for chapter in chapters)


def _split_chapter_label(title: str) -> tuple[str, str]:
    """Separa 'Capítulo 3 — O que o vidro guarda' em número e título."""
    for separator in ("—", "–", "-", ":"):
        if separator in title:
            head, _, tail = title.partition(separator)
            head = head.strip()
            tail = tail.strip()
            if head and tail and len(head) <= 32:
                return head, tail
    return "", title.strip()
