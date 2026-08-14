"""Analisador narrativo heurístico e determinístico.

Este é o adaptador padrão do `NarrativeAnalyzerPort`. Ele lê português
brasileiro sem modelo, sem rede e sem credencial, e produz a estrutura de que o
`CANON_EXTRACTOR_AGENT` precisa.

As heurísticas, em ordem de confiabilidade:

1. **Atribuição de fala** (`— … — disse Mariana`) é o sinal mais forte de que um
   token capitalizado é um personagem.
2. **Posição de sujeito** — um nome seguido de verbo narrativo (`Elias abriu`) é
   personagem; um nome precedido de preposição (`de Portovelho`) tende a ser
   topônimo. Esta distinção é o que impede que a cidade vire protagonista.
3. **Capitalização em meio de frase** separa nome próprio de palavra que apenas
   inicia uma sentença (`Faltavam dois minutos`).
4. **Frequência e coocorrência** ordenam protagonistas e revelam relações.

Nada aqui inventa fatos: cada saída aponta para o deslocamento no texto que a
originou, e o que não pôde ser determinado vira uma incerteza declarada.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from pedroarte_youtube_engine.adapters.analysis.lexicons import (
    ATTRIBUTION_VERBS,
    LOCATION_NOUNS,
    MYSTERY_WORDS,
    NAME_CONNECTORS,
    NARRATIVE_VERBS,
    NON_NAME_CAPITALS,
    PROHIBITION_MARKERS,
    PROP_NOUNS,
    REVELATION_WORDS,
    RULE_CONFIRMERS,
    TENSION_WORDS,
    TONE_LEXICON,
    WORLD_RULE_MARKERS,
)
from pedroarte_youtube_engine.ports.analysis import (
    DetectedBeat,
    DetectedCharacter,
    DetectedDialogue,
    DetectedLocation,
    DetectedProp,
    NarrativeAnalysis,
)
from pedroarte_youtube_engine.shared.text import (
    excerpt,
    first_sentence,
    sentence_split,
    strip_accents,
)

#: Nome próprio simples ou composto. `[ \t]+` (e não `\s+`) impede que o
#: casamento atravesse uma quebra de linha e cole um título ao parágrafo seguinte.
_NAME = re.compile(
    r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,}"
    r"(?:[ \t]+(?:de|da|do|das|dos|e)[ \t]+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,}"
    r"|[ \t]+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,})*)"
)

#: Fala com travessão: `— Texto da fala`.
_DASH_DIALOGUE = re.compile(r"^[—–]\s*(.+)$", re.MULTILINE)

#: Atribuição depois da fala: `— … — disse Mariana` ou `— …, disse Mariana`.
_ATTRIBUTION_AFTER = re.compile(
    r"[—–,]\s*(?P<verb>\w+)\s+(?P<name>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ſ]+)"
)

#: Atribuição antes da fala: `Mariana disse:`.
_ATTRIBUTION_BEFORE = re.compile(
    r"(?P<name>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ſ]+)\s+(?P<verb>\w+)\s*[:—]"
)

#: Preposições que, imediatamente antes de um nome, sugerem lugar.
_PLACE_PREPOSITIONS = re.compile(
    r"(?:\bem|\bn[ao]s?|\bd[ao]s?|\bpara|\baté|\bpel[ao]s?|\bsobre|\bdentro de|\brumo a)\s*$",
    re.IGNORECASE,
)

#: Substantivo comum de lugar precedido de artigo ou preposição.
_PLACE_PHRASE = re.compile(
    r"\b(?:[ao]s?|n[ao]s?|d[ao]s?|em|ao|à|pel[ao]s?|para|até)\s+"
    r"([a-záàâãéêíóôõúç]{3,})",
    re.IGNORECASE,
)

#: Terminadores que indicam que o próximo token inicia uma sentença.
_SENTENCE_ENDERS = frozenset({".", "!", "?", "…", "\n", ":", ";"})

#: Linhas de título (Markdown ou "Capítulo N"), removidas antes da análise para
#: que um cabeçalho não seja lido como parte da primeira frase do capítulo.
_HEADING_LINE = re.compile(
    r"^(?:#{1,6}\s+.*|(?:CAP[ÍI]TULO|PARTE|LIVRO|ATO|PRÓLOGO|EPÍLOGO)\b.*)$",
    re.MULTILINE | re.IGNORECASE,
)

#: Máxima distância, em caracteres de prosa, para que duas falas sejam
#: consideradas adjacentes. A alternância de interlocutores só vale nesse caso:
#: com um parágrafo narrativo no meio, quem fala pode ser qualquer um.
_ADJACENT_DIALOGUE_GAP = 120

#: Quantas sentenças formam um beat narrativo.
_SENTENCES_PER_BEAT = 6
_MIN_BEAT_SENTENCES = 2

#: Verbos de atribuição normalizados sem acento, para comparação rápida.
_ATTRIBUTION_VERBS_ASCII: frozenset[str] = frozenset(
    strip_accents(verb).lower() for verb in ATTRIBUTION_VERBS
)
_NARRATIVE_VERBS_ASCII: frozenset[str] = frozenset(
    strip_accents(verb).lower() for verb in NARRATIVE_VERBS
)
_NON_NAME_ASCII: frozenset[str] = frozenset(
    strip_accents(word).lower() for word in NON_NAME_CAPITALS
)


@dataclass(frozen=True, slots=True)
class _DialogueSpan:
    """Uma fala com a sua posição no texto, antes da resolução de falante."""

    chapter_index: int
    start: int
    end: int
    speaker: str
    text: str
    explicitly_attributed: bool


def _count_word(text_lower: str, word: str) -> int:
    """Conta ocorrências de `word` como palavra inteira, tolerando o plural.

    Contar por substring produziria "rio" dentro de "cemitério" e "cartório" —
    exatamente o tipo de falso positivo que polui a Bíblia de Locais.
    """
    pattern = rf"(?<![\wÀ-ÿ]){re.escape(word)}s?(?![\wÀ-ÿ])"
    return len(re.findall(pattern, text_lower))


def _strip_headings(text: str) -> str:
    """Remove linhas de título antes da análise.

    Sem isso, `## Capítulo 2 — Mariana Duarte` gruda na primeira frase do
    capítulo e contamina descrições, beats e resumos.
    """
    return _HEADING_LINE.sub("", text)


class HeuristicNarrativeAnalyzer:
    """Implementação determinística do `NarrativeAnalyzerPort`."""

    def __init__(self, *, min_character_mentions: int = 2, max_characters: int = 24) -> None:
        self._min_mentions = min_character_mentions
        self._max_characters = max_characters

    @property
    def name(self) -> str:
        return "heuristic_ptbr_v1"

    # -- API ---------------------------------------------------------------

    def analyze(
        self,
        *,
        text: str,
        chapters: tuple[tuple[int, str, str], ...],
        language: str,
    ) -> NarrativeAnalysis:
        source_chapters = chapters or ((0, "Texto integral", text),)
        clean_text = _strip_headings(text)
        effective_chapters = tuple(
            (index, title, _strip_headings(body)) for index, title, body in source_chapters
        )

        spans = self._extract_dialogue_spans(effective_chapters)
        speaker_counts = Counter(span.speaker for span in spans if span.speaker)
        characters = self._detect_characters(clean_text, effective_chapters, speaker_counts)
        dialogues = self._resolve_dialogues(spans, characters)

        known_names = {character.name for character in characters}
        for character in characters:
            known_names.update(character.aliases)

        locations = self._detect_locations(clean_text, known_names)
        props = self._detect_props(clean_text)
        beats = self._build_beats(effective_chapters, characters, locations)

        return NarrativeAnalysis(
            title=self._infer_title(source_chapters),
            logline=self._build_logline(characters, beats),
            thesis=self._build_thesis(clean_text, characters),
            characters=characters,
            locations=locations,
            props=props,
            dialogues=dialogues,
            beats=beats,
            world_rules=self._extract_world_rules(clean_text),
            prohibitions=self._extract_marked_sentences(
                clean_text, PROHIBITION_MARKERS, limit=8
            ),
            mysteries=self._extract_mysteries(clean_text),
            themes=self._extract_themes(clean_text),
            uncertainties=self._collect_uncertainties(characters, locations, effective_chapters),
            analyzer_name=self.name,
        )

    # -- personagens -------------------------------------------------------

    def _detect_characters(
        self,
        text: str,
        chapters: tuple[tuple[int, str, str], ...],
        speaker_counts: Counter[str],
    ) -> tuple[DetectedCharacter, ...]:
        """Detecta personagens combinando fala atribuída e posição de sujeito."""
        total: Counter[str] = Counter()
        mid_sentence: Counter[str] = Counter()
        subject_position: Counter[str] = Counter()
        place_position: Counter[str] = Counter()

        for match in _NAME.finditer(text):
            name = match.group(1).strip()
            if not self._is_plausible_name(name):
                continue
            total[name] += 1
            if not self._starts_sentence(text, match.start()):
                mid_sentence[name] += 1
            if self._followed_by_narrative_verb(text, match.end()):
                subject_position[name] += 1
            if _PLACE_PREPOSITIONS.search(text[max(0, match.start() - 12) : match.start()]):
                place_position[name] += 1

        selected: list[str] = []
        for name, count in total.most_common():
            head = name.split()[0]
            spoken = speaker_counts.get(head, 0) + speaker_counts.get(name, 0)
            acts = subject_position[name] > 0
            looks_like_place = place_position[name] >= max(1, total[name]) and not acts

            if looks_like_place:
                continue
            if spoken > 0 or (acts and mid_sentence[name] > 0 and count >= self._min_mentions):
                selected.append(name)
            if len(selected) >= self._max_characters:
                break

        canonical = self._merge_name_variants(selected, total)

        results: list[DetectedCharacter] = []
        for name, aliases in canonical.items():
            head = name.split()[0]
            mentions = total[name] + sum(total[alias] for alias in aliases)
            spoken = sum(
                speaker_counts.get(key, 0) for key in ({name, head, *aliases})
            )
            results.append(
                DetectedCharacter(
                    name=name,
                    mentions=mentions,
                    dialogue_lines=spoken,
                    first_chapter_index=self._first_chapter(chapters, name, aliases),
                    aliases=tuple(sorted(aliases)),
                    descriptive_sentences=self._descriptive_sentences(text, name),
                    co_occurring=self._co_occurring(text, name, set(canonical) - {name}),
                )
            )

        results.sort(key=lambda item: (-item.mentions, item.name))
        return tuple(results)

    def _merge_name_variants(
        self, names: list[str], counts: Counter[str]
    ) -> dict[str, set[str]]:
        """Agrupa variantes do mesmo nome sob a forma mais informativa."""
        ordered = sorted(names, key=lambda name: (-len(name.split()), -counts[name], name))
        canonical: dict[str, set[str]] = {}
        for name in ordered:
            merged = False
            for existing in canonical:
                if self._same_person(name, existing):
                    if name != existing:
                        canonical[existing].add(name)
                    merged = True
                    break
            if not merged:
                canonical[name] = set()
        return canonical

    @staticmethod
    def _same_person(candidate: str, existing: str) -> bool:
        candidate_parts = {
            strip_accents(part).lower() for part in candidate.split()
        } - NAME_CONNECTORS
        existing_parts = {
            strip_accents(part).lower() for part in existing.split()
        } - NAME_CONNECTORS
        if not candidate_parts or not existing_parts:
            return False
        return candidate_parts <= existing_parts or existing_parts <= candidate_parts

    @staticmethod
    def _is_plausible_name(name: str) -> bool:
        head = strip_accents(name.split()[0]).lower()
        return len(head) >= 3 and head.isalpha() and head not in _NON_NAME_ASCII

    @staticmethod
    def _starts_sentence(text: str, position: int) -> bool:
        """Verifica se a posição inicia uma sentença, ignorando pontuação de fala."""
        index = position - 1
        while index >= 0 and text[index] in " \t\"«»'—–-#*>":
            index -= 1
        return index < 0 or text[index] in _SENTENCE_ENDERS

    @staticmethod
    def _followed_by_narrative_verb(text: str, position: int) -> bool:
        """Verifica se o nome ocupa posição de sujeito de um verbo narrativo."""
        tail = text[position : position + 40].lstrip(" ,")
        if not tail:
            return False
        word = re.split(r"[^\wÀ-ſ]", tail, maxsplit=1)[0]
        return strip_accents(word).lower() in _NARRATIVE_VERBS_ASCII

    @staticmethod
    def _first_chapter(
        chapters: tuple[tuple[int, str, str], ...], name: str, aliases: set[str]
    ) -> int:
        """Primeiro capítulo em que o personagem aparece, considerando apelidos."""
        needles = {name, name.split()[0], *aliases}
        for index, _title, body in chapters:
            if any(needle in body for needle in needles):
                return index
        return 0

    @staticmethod
    def _descriptive_sentences(text: str, name: str, *, limit: int = 4) -> tuple[str, ...]:
        """Sentenças que descrevem fisicamente o personagem."""
        descriptors = (
            "olhos", "cabelo", "rosto", "mãos", "mão", "alto", "baixa", "baixo",
            "magro", "magra", "pele", "voz", "sorriso", "testa", "ombros",
            "barba", "cicatriz", "usava", "vestia", "trajava", "parecia",
            "tinha", "anos", "postura", "curvado",
        )
        head = name.split()[0]
        found: list[str] = []
        for sentence in sentence_split(text):
            cleaned = sentence.lstrip("#* ").strip()
            if head in cleaned and any(word in cleaned.lower() for word in descriptors):
                candidate = excerpt(cleaned, max_chars=300)
                if candidate not in found:
                    found.append(candidate)
            if len(found) >= limit:
                break
        return tuple(found)

    @staticmethod
    def _co_occurring(text: str, name: str, others: set[str], *, limit: int = 6) -> tuple[str, ...]:
        """Personagens que aparecem na mesma sentença — base das relações."""
        counts: Counter[str] = Counter()
        head = name.split()[0]
        for sentence in sentence_split(text):
            if head not in sentence:
                continue
            for other in others:
                if other.split()[0] in sentence:
                    counts[other] += 1
        return tuple(other for other, _ in counts.most_common(limit))

    # -- diálogos ----------------------------------------------------------

    def _extract_dialogue_spans(
        self, chapters: tuple[tuple[int, str, str], ...]
    ) -> tuple[_DialogueSpan, ...]:
        """Extrai falas por travessão, guardando a posição de cada uma.

        A posição é necessária para a inferência de falante: só a distância no
        texto distingue um bate-e-volta de duas falas separadas por narração.
        """
        spans: list[_DialogueSpan] = []
        for index, _title, body in chapters:
            for match in _DASH_DIALOGUE.finditer(body):
                raw = match.group(1).strip()
                if len(raw) < 2:
                    continue
                speaker, spoken = self._split_attribution(raw)
                spans.append(
                    _DialogueSpan(
                        chapter_index=index,
                        start=match.start(),
                        end=match.end(),
                        speaker=speaker,
                        text=spoken,
                        explicitly_attributed=bool(speaker),
                    )
                )
        return tuple(spans)

    def _split_attribution(self, line: str) -> tuple[str, str]:
        """Separa a fala da sua atribuição narrativa."""
        after = _ATTRIBUTION_AFTER.search(line)
        if after and strip_accents(after.group("verb")).lower() in _ATTRIBUTION_VERBS_ASCII:
            spoken = line[: after.start()].strip(" —–,.")
            return after.group("name"), spoken or line

        before = _ATTRIBUTION_BEFORE.search(line)
        if before and strip_accents(before.group("verb")).lower() in _ATTRIBUTION_VERBS_ASCII:
            spoken = line[before.end() :].strip(" —–:,")
            return before.group("name"), spoken or line

        return "", self._strip_trailing_attribution(line)

    @staticmethod
    def _strip_trailing_attribution(line: str) -> str:
        """Remove a marcação narrativa de falas sem nome (`— … — respondeu.`)."""
        parts = re.split(r"\s+[—–]\s+", line)
        if len(parts) < 2:
            return line
        head = parts[0].strip()
        first_word = parts[1].split()[0] if parts[1].split() else ""
        tail_word = strip_accents(first_word).lower().strip(".,;:!?")
        if tail_word in _ATTRIBUTION_VERBS_ASCII:
            remainder = " ".join(parts[2:]).strip()
            return f"{head} {remainder}".strip() if remainder else head
        return line

    def _resolve_dialogues(
        self,
        spans: tuple[_DialogueSpan, ...],
        characters: tuple[DetectedCharacter, ...],
    ) -> tuple[DetectedDialogue, ...]:
        """Preenche falantes implícitos por alternância entre dois interlocutores.

        Em diálogo a dois — o caso dominante em prosa brasileira — a fala sem
        atribuição pertence a quem não falou por último. A regra só vale para
        falas **adjacentes**: quando há um parágrafo de narração no meio, o
        turno pode ter voltado para o mesmo personagem, e o motor prefere
        registrar o falante como desconhecido a inventar uma atribuição errada.
        """
        two_hander = len(characters) >= 2
        primary = characters[0].name.split()[0] if two_hander else ""
        secondary = characters[1].name.split()[0] if two_hander else ""
        speakers = {primary, secondary}

        resolved: list[DetectedDialogue] = []
        last_speaker = ""
        last_end = -1
        last_chapter = -1

        for span in spans:
            if span.chapter_index != last_chapter:
                last_speaker = ""
                last_end = -1
                last_chapter = span.chapter_index

            speaker = span.speaker
            adjacent = last_end >= 0 and (span.start - last_end) <= _ADJACENT_DIALOGUE_GAP

            if not speaker and two_hander and adjacent and last_speaker in speakers:
                speaker = secondary if last_speaker == primary else primary

            if speaker:
                last_speaker = speaker
            last_end = span.end

            resolved.append(
                DetectedDialogue(
                    speaker=speaker,
                    text=excerpt(span.text, max_chars=400),
                    chapter_index=span.chapter_index,
                    offset=span.start,
                )
            )
        return tuple(resolved)

    # -- locais e objetos --------------------------------------------------

    def _detect_locations(
        self, text: str, known_character_names: set[str]
    ) -> tuple[DetectedLocation, ...]:
        """Detecta ambientes por substantivo de lugar e por topônimo próprio."""
        lowered = text.lower()
        counts: Counter[str] = Counter()

        # 1. Substantivos comuns de lugar, contados como palavra inteira.
        for noun in LOCATION_NOUNS:
            occurrences = _count_word(lowered, noun)
            if occurrences >= 2:
                counts[noun] = occurrences

        # 2. Frases de lugar, que reforçam o substantivo já detectado.
        for match in _PLACE_PHRASE.finditer(text):
            head = match.group(1).strip().lower()
            if head in LOCATION_NOUNS:
                counts[head] += 1

        # 3. Topônimos próprios: nomes que nunca agem e vivem depois de preposição.
        for match in _NAME.finditer(text):
            name = match.group(1).strip()
            if name in known_character_names or not self._is_plausible_name(name):
                continue
            if name.split()[0] in {n.split()[0] for n in known_character_names}:
                continue
            preceding = text[max(0, match.start() - 12) : match.start()]
            if _PLACE_PREPOSITIONS.search(preceding) and not self._followed_by_narrative_verb(
                text, match.end()
            ):
                counts[name] += 1

        exterior_markers = (
            "rua", "praça", "ponte", "cais", "porto", "campo", "estrada",
            "praia", "morro", "jardim", "quintal", "cemitério", "avenida",
        )
        results = [
            DetectedLocation(
                name=name,
                mentions=count,
                interior=not any(marker in name.lower() for marker in exterior_markers),
                descriptive_sentences=self._sentences_containing(text, name, limit=3),
            )
            for name, count in counts.most_common(16)
            if count >= 2
        ]
        return tuple(results)

    def _detect_props(self, text: str) -> tuple[DetectedProp, ...]:
        lowered = text.lower()
        counts: Counter[str] = Counter()
        for noun in PROP_NOUNS:
            occurrences = _count_word(lowered, noun)
            if occurrences >= 2:
                counts[noun] = occurrences
        return tuple(
            DetectedProp(
                name=noun,
                mentions=count,
                descriptive_sentences=self._sentences_containing(text, noun, limit=2),
            )
            for noun, count in counts.most_common(14)
        )

    @staticmethod
    def _sentences_containing(text: str, needle: str, *, limit: int) -> tuple[str, ...]:
        found: list[str] = []
        lowered_needle = needle.lower()
        for sentence in sentence_split(text):
            cleaned = sentence.lstrip("#* ").strip()
            if lowered_needle in cleaned.lower():
                candidate = excerpt(cleaned, max_chars=300)
                if candidate not in found:
                    found.append(candidate)
            if len(found) >= limit:
                break
        return tuple(found)

    # -- beats -------------------------------------------------------------

    def _build_beats(
        self,
        chapters: tuple[tuple[int, str, str], ...],
        characters: tuple[DetectedCharacter, ...],
        locations: tuple[DetectedLocation, ...],
    ) -> tuple[DetectedBeat, ...]:
        """Divide cada capítulo em beats de progressão dramática."""
        location_names = [location.name for location in locations]
        heads = {character.name: character.name.split()[0] for character in characters}
        beats: list[DetectedBeat] = []
        order = 0

        for chapter_index, _title, body in chapters:
            sentences = sentence_split(body)
            if not sentences:
                continue
            offset = 0
            for start in range(0, len(sentences), _SENTENCES_PER_BEAT):
                window = sentences[start : start + _SENTENCES_PER_BEAT]
                if len(window) < _MIN_BEAT_SENTENCES and beats:
                    break
                block = " ".join(window)
                participants = tuple(
                    sorted(name for name, head in heads.items() if head in block)
                )
                location = next(
                    (name for name in location_names if name.lower() in block.lower()), ""
                )
                tension = self._tension_of(block)
                beats.append(
                    DetectedBeat(
                        order=order,
                        chapter_index=chapter_index,
                        summary=excerpt(
                            first_sentence(block, fallback=block).lstrip("#* "), max_chars=300
                        ),
                        participants=participants,
                        location=location,
                        tension=tension,
                        tone=self._tone_of(block),
                        dialogue_excerpts=self._dialogue_excerpts(block),
                        information_revealed=self._revelations(block),
                        start_offset=offset,
                        end_offset=offset + len(block),
                        weight=self._weight_of(block, tension, participants),
                    )
                )
                offset += len(block) + 1
                order += 1

        return tuple(beats)

    @staticmethod
    def _tension_of(block: str) -> int:
        lowered = block.lower()
        hits = sum(1 for word in TENSION_WORDS if word in lowered)
        punctuation = lowered.count("!") + lowered.count("?")
        return max(0, min(10, hits * 2 + punctuation))

    @staticmethod
    def _tone_of(block: str) -> str:
        lowered = strip_accents(block).lower()
        scores: dict[str, int] = {}
        for tone, words in TONE_LEXICON.items():
            score = sum(1 for word in words if strip_accents(word).lower() in lowered)
            if score:
                scores[tone] = score
        if not scores:
            return "neutro"
        return max(scores.items(), key=lambda item: (item[1], item[0]))[0]

    @staticmethod
    def _dialogue_excerpts(block: str, *, limit: int = 3) -> tuple[str, ...]:
        found = [
            excerpt(match.group(1).strip(), max_chars=220)
            for match in _DASH_DIALOGUE.finditer(block)
        ]
        return tuple(found[:limit])

    @staticmethod
    def _revelations(block: str, *, limit: int = 3) -> tuple[str, ...]:
        found: list[str] = []
        for sentence in sentence_split(block):
            if any(word in sentence.lower() for word in REVELATION_WORDS):
                found.append(excerpt(sentence, max_chars=240))
            if len(found) >= limit:
                break
        return tuple(found)

    @staticmethod
    def _weight_of(block: str, tension: int, participants: tuple[str, ...]) -> float:
        """Peso dramático: tensão, densidade de diálogo e presença de personagens."""
        dialogue_density = block.count("—") + block.count("–")
        base = 1.0 + tension * 0.35 + min(dialogue_density, 6) * 0.2 + len(participants) * 0.25
        return round(max(0.1, min(10.0, base)), 3)

    # -- síntese -----------------------------------------------------------

    @staticmethod
    def _infer_title(chapters: tuple[tuple[int, str, str], ...]) -> str:
        return chapters[0][1] if chapters and chapters[0][1] else ""

    @staticmethod
    def _build_logline(
        characters: tuple[DetectedCharacter, ...], beats: tuple[DetectedBeat, ...]
    ) -> str:
        if not characters or not beats:
            return ""
        protagonist = characters[0].name
        peak = max(beats, key=lambda beat: beat.tension)
        return (
            f"{protagonist} — {excerpt(beats[0].summary, max_chars=160)} "
            f"Ponto de maior tensão: {excerpt(peak.summary, max_chars=160)}"
        )

    @staticmethod
    def _build_thesis(text: str, characters: tuple[DetectedCharacter, ...]) -> str:
        themes = HeuristicNarrativeAnalyzer._extract_themes(text)
        if not themes:
            return ""
        protagonist = characters[0].name if characters else "o protagonista"
        return (
            f"A obra gira em torno de {', '.join(themes[:3])}, e usa {protagonist} "
            "como o lugar onde essas forças se chocam."
        )

    @staticmethod
    def _extract_themes(text: str, *, limit: int = 6) -> tuple[str, ...]:
        lowered = strip_accents(text).lower()
        buckets = {
            "culpa": ("culpa", "arrependimento", "perdao", "penitencia"),
            "memória": ("memoria", "lembranca", "esquecimento", "recordacao"),
            "tempo": ("tempo", "relogio", "hora", "passado", "futuro"),
            "verdade": ("verdade", "mentira", "segredo", "confissao"),
            "perda": ("perda", "morte", "luto", "ausencia", "saudade"),
            "poder": ("poder", "controle", "dominio", "obediencia"),
            "identidade": ("identidade", "nome", "espelho", "reflexo"),
            "justiça": ("justica", "crime", "castigo", "vinganca"),
            "amor": ("amor", "paixao", "afeto", "ternura"),
            "medo": ("medo", "terror", "panico", "ameaca"),
            "herança": ("heranca", "herdou", "pai", "mae", "filho", "filha"),
        }
        scored = {
            theme: sum(lowered.count(word) for word in words)
            for theme, words in buckets.items()
        }
        ranked = sorted(
            ((theme, score) for theme, score in scored.items() if score >= 2),
            key=lambda item: (-item[1], item[0]),
        )
        return tuple(theme for theme, _ in ranked[:limit])

    @staticmethod
    def _extract_world_rules(text: str, *, limit: int = 10) -> tuple[str, ...]:
        """Regras do universo — confirmadas por vocabulário normativo.

        Sem o confirmador, marcadores frouxos como "sempre que" transformariam
        qualquer hábito de personagem em lei do mundo.
        """
        found: list[str] = []
        for sentence in sentence_split(text):
            lowered = sentence.lower()
            if not any(marker in lowered for marker in WORLD_RULE_MARKERS):
                continue
            if not any(confirmer in lowered for confirmer in RULE_CONFIRMERS):
                continue
            cleaned = excerpt(sentence.lstrip("#*—– "), max_chars=280)
            if cleaned not in found:
                found.append(cleaned)
            if len(found) >= limit:
                break
        return tuple(found)

    @staticmethod
    def _extract_marked_sentences(
        text: str, markers: tuple[str, ...], *, limit: int
    ) -> tuple[str, ...]:
        found: list[str] = []
        for sentence in sentence_split(text):
            lowered = sentence.lower()
            if any(marker in lowered for marker in markers):
                cleaned = excerpt(sentence.lstrip("#*—– "), max_chars=280)
                if cleaned not in found:
                    found.append(cleaned)
            if len(found) >= limit:
                break
        return tuple(found)

    @staticmethod
    def _extract_mysteries(text: str, *, limit: int = 8) -> tuple[str, ...]:
        found: list[str] = []
        for sentence in sentence_split(text):
            lowered = sentence.lower()
            if any(word in lowered for word in MYSTERY_WORDS) or lowered.rstrip().endswith("?"):
                cleaned = excerpt(sentence.lstrip("#*—– "), max_chars=280)
                if cleaned not in found:
                    found.append(cleaned)
            if len(found) >= limit:
                break
        return tuple(found)

    def _collect_uncertainties(
        self,
        characters: tuple[DetectedCharacter, ...],
        locations: tuple[DetectedLocation, ...],
        chapters: tuple[tuple[int, str, str], ...],
    ) -> tuple[str, ...]:
        """Registra o que a heurística não conseguiu determinar.

        Preferimos declarar a lacuna a preenchê-la por invenção.
        """
        uncertainties: list[str] = []
        if not characters:
            uncertainties.append(
                "Nenhum personagem foi detectado com confiança. Verifique se o texto usa "
                "travessão para diálogo e nomes próprios capitalizados."
            )
        if not locations:
            uncertainties.append(
                "Nenhum ambiente recorrente foi identificado; os prompts usarão descrições "
                "genéricas de cenário derivadas do texto."
            )
        for character in characters[:8]:
            if not character.descriptive_sentences:
                uncertainties.append(
                    f"A obra não descreve fisicamente '{character.name}'. A aparência foi "
                    "deixada em aberto e precisa de definição autoral antes da geração."
                )
        if len(chapters) == 1 and chapters[0][1] == "Texto integral":
            uncertainties.append(
                "Não foi possível identificar capítulos; o texto foi tratado como bloco único."
            )
        return tuple(uncertainties[:20])
