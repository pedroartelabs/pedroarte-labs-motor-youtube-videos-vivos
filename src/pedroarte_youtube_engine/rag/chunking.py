"""Chunking estrutural.

Regra da seção 19.2: **não dividir o texto por quantidade fixa de caracteres**.
Um corte cego separa a pergunta da resposta, o gesto da reação, o nome do
personagem da descrição dele — e o RAG passa a recuperar metades inúteis.

A divisão segue, nesta ordem: capítulo → mudança de cena (local, tempo,
personagem) → beat → limite de palavras como último recurso.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from pedroarte_youtube_engine.shared.hashing import content_hash
from pedroarte_youtube_engine.shared.text import count_words, sentence_split

#: Marcadores de mudança de tempo ou lugar que justificam um novo chunk.
_SCENE_BREAK_MARKERS: tuple[str, ...] = (
    "mais tarde",
    "naquela noite",
    "na manhã seguinte",
    "no dia seguinte",
    "horas depois",
    "dias depois",
    "semanas depois",
    "anos depois",
    "enquanto isso",
    "de volta",
    "quando chegou",
    "ao amanhecer",
    "ao entardecer",
    "à meia-noite",
    "lá fora",
)

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_DIALOGUE_LINE = re.compile(r"^\s*[—–]")


class ContentType(StrEnum):
    """Natureza do trecho — usada como filtro de metadados na recuperação."""

    NARRATION = "narracao"
    DIALOGUE = "dialogo"
    DESCRIPTION = "descricao"
    RULE = "regra"
    STRUCTURED = "estruturado"
    MIXED = "misto"


class NarrativeChunk(BaseModel):
    """Trecho indexável, com todos os metadados exigidos pela seção 19.2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    source_id: str
    source_path: str
    chapter: str = ""
    chapter_index: int = Field(default=0, ge=0)
    scene: str = ""
    characters: tuple[str, ...] = Field(default_factory=tuple)
    locations: tuple[str, ...] = Field(default_factory=tuple)
    timeline_position: str = ""
    content_type: ContentType = ContentType.NARRATION
    text: str
    hash: str
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    def metadata(self) -> dict[str, str]:
        """Metadados achatados, no formato aceito pelos índices."""
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "chapter": self.chapter,
            "chapter_index": str(self.chapter_index),
            "scene": self.scene,
            "content_type": self.content_type.value,
            "characters": "|".join(self.characters),
            "locations": "|".join(self.locations),
            "start_offset": str(self.start_offset),
            "end_offset": str(self.end_offset),
        }


class StructuralChunker:
    """Divide um documento respeitando a estrutura narrativa."""

    def __init__(
        self,
        *,
        target_words: int = 280,
        overlap_words: int = 40,
        max_words: int = 520,
    ) -> None:
        if overlap_words >= target_words:
            raise ValueError("A sobreposição deve ser menor que o tamanho alvo do chunk.")
        self._target = target_words
        self._overlap = overlap_words
        self._max = max_words

    def chunk_chapters(
        self,
        *,
        source_id: str,
        source_path: str,
        chapters: tuple[tuple[int, str, str], ...],
        characters: tuple[str, ...] = (),
        locations: tuple[str, ...] = (),
    ) -> tuple[NarrativeChunk, ...]:
        """Gera os chunks de um documento narrativo inteiro."""
        chunks: list[NarrativeChunk] = []
        global_offset = 0

        for chapter_index, chapter_title, body in chapters:
            scenes = self._split_scenes(body)
            for scene_number, scene_text in enumerate(scenes, start=1):
                for piece in self._split_by_size(scene_text):
                    chunk_id = f"{source_id}.c{chapter_index:03d}.s{scene_number:02d}.{len(chunks):04d}"
                    chunks.append(
                        NarrativeChunk(
                            chunk_id=chunk_id,
                            source_id=source_id,
                            source_path=source_path,
                            chapter=chapter_title,
                            chapter_index=chapter_index,
                            scene=f"cena_{scene_number:02d}",
                            characters=self._present(piece, characters),
                            locations=self._present(piece, locations),
                            timeline_position=f"cap{chapter_index:03d}:cena{scene_number:02d}",
                            content_type=self._classify(piece),
                            text=piece,
                            hash=content_hash(piece),
                            start_offset=global_offset,
                            end_offset=global_offset + len(piece),
                        )
                    )
                    global_offset += len(piece) + 1

        return tuple(chunks)

    def chunk_structured(
        self,
        *,
        source_id: str,
        source_path: str,
        text: str,
    ) -> tuple[NarrativeChunk, ...]:
        """Chunking de documentos auxiliares (JSON/YAML já achatados)."""
        lines = [line for line in text.split("\n") if line.strip()]
        chunks: list[NarrativeChunk] = []
        buffer: list[str] = []
        offset = 0

        def flush() -> None:
            nonlocal buffer, offset
            if not buffer:
                return
            piece = "\n".join(buffer)
            chunks.append(
                NarrativeChunk(
                    chunk_id=f"{source_id}.struct.{len(chunks):04d}",
                    source_id=source_id,
                    source_path=source_path,
                    content_type=ContentType.STRUCTURED,
                    text=piece,
                    hash=content_hash(piece),
                    start_offset=offset,
                    end_offset=offset + len(piece),
                )
            )
            offset += len(piece) + 1
            buffer = []

        for line in lines:
            buffer.append(line)
            if count_words("\n".join(buffer)) >= self._target:
                flush()
        flush()
        return tuple(chunks)

    # -- divisão -----------------------------------------------------------

    def _split_scenes(self, body: str) -> list[str]:
        """Separa por mudança de cena: marcador temporal ou bloco de diálogo."""
        paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(body) if p.strip()]
        if not paragraphs:
            return []

        scenes: list[list[str]] = [[]]
        previous_was_dialogue = False

        for paragraph in paragraphs:
            is_dialogue = bool(_DIALOGUE_LINE.match(paragraph))
            starts_new_scene = self._has_scene_marker(paragraph) or (
                previous_was_dialogue and not is_dialogue and len(scenes[-1]) >= 4
            )
            if starts_new_scene and scenes[-1]:
                scenes.append([])
            scenes[-1].append(paragraph)
            previous_was_dialogue = is_dialogue

        return ["\n\n".join(scene) for scene in scenes if scene]

    @staticmethod
    def _has_scene_marker(paragraph: str) -> bool:
        head = paragraph[:80].lower()
        return any(marker in head for marker in _SCENE_BREAK_MARKERS)

    def _split_by_size(self, scene_text: str) -> list[str]:
        """Último recurso: divide cenas longas por sentença, com sobreposição."""
        if count_words(scene_text) <= self._max:
            return [scene_text]

        sentences = sentence_split(scene_text)
        pieces: list[str] = []
        buffer: list[str] = []

        for sentence in sentences:
            buffer.append(sentence)
            if count_words(" ".join(buffer)) >= self._target:
                pieces.append(" ".join(buffer))
                buffer = self._tail_overlap(buffer)

        if buffer:
            remainder = " ".join(buffer)
            # Um resto muito curto é absorvido pelo pedaço anterior.
            if pieces and count_words(remainder) < self._overlap:
                pieces[-1] = f"{pieces[-1]} {remainder}"
            else:
                pieces.append(remainder)

        return pieces

    def _tail_overlap(self, buffer: list[str]) -> list[str]:
        """Mantém as últimas sentenças como contexto do próximo chunk."""
        tail: list[str] = []
        for sentence in reversed(buffer):
            tail.insert(0, sentence)
            if count_words(" ".join(tail)) >= self._overlap:
                break
        return tail

    # -- metadados ---------------------------------------------------------

    @staticmethod
    def _present(text: str, candidates: tuple[str, ...]) -> tuple[str, ...]:
        """Quais entidades conhecidas aparecem neste trecho."""
        found = [
            candidate
            for candidate in candidates
            if candidate and candidate.split()[0] in text
        ]
        return tuple(sorted(set(found)))

    @staticmethod
    def _classify(text: str) -> ContentType:
        lines = text.split("\n")
        dialogue_lines = sum(1 for line in lines if _DIALOGUE_LINE.match(line))
        ratio = dialogue_lines / max(1, len(lines))
        lowered = text.lower()

        if any(word in lowered for word in ("regra", "proibido", "jamais", "nunca se")):
            return ContentType.RULE
        if ratio >= 0.5:
            return ContentType.DIALOGUE
        if ratio > 0:
            return ContentType.MIXED
        if any(
            word in lowered
            for word in ("olhos", "cabelo", "rosto", "usava", "vestia", "parede", "luz")
        ):
            return ContentType.DESCRIPTION
        return ContentType.NARRATION
