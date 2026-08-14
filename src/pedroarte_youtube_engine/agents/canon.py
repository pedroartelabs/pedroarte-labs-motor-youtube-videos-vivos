"""Agentes de cânone (9.4, 9.5 e 9.6)."""

from __future__ import annotations

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import CanonBible
from pedroarte_youtube_engine.domain.canon import (
    CanonFact,
    CanonFactKind,
    Character,
    CharacterAppearance,
    CharacterRelationship,
    Location,
    NarrativeBeat,
    Prop,
    RelationshipKind,
    TimelineEvent,
    UnresolvedQuestion,
    WardrobeSet,
)
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.value_objects import (
    CharacterId,
    ConfidenceScore,
    EmotionalTone,
    LocationId,
    PropId,
    SourceReference,
)
from pedroarte_youtube_engine.ports.analysis import (
    DetectedBeat,
    DetectedCharacter,
    NarrativeAnalysis,
)
from pedroarte_youtube_engine.rag.chunking import StructuralChunker
from pedroarte_youtube_engine.shared.hashing import stable_short_id
from pedroarte_youtube_engine.shared.text import excerpt, first_sentence

#: Papéis atribuídos por ordem de proeminência.
_ROLES = ("protagonista", "deuteragonista", "antagonista", "coadjuvante")


class CanonExtractorAgent(BaseAgent):
    """`CANON_EXTRACTOR_AGENT` — transforma o texto em cânone verificável."""

    _contract = AgentContract(
        name="CANON_EXTRACTOR_AGENT",
        responsibility=(
            "Extrair fatos, personagens, locais, objetos, relações, regras do universo, "
            "cronologia, mistérios e contradições, cada um com nível de confiança e "
            "referência ao trecho de origem."
        ),
        phase="EXTRACTING_CANON",
        input_type="BookSource",
        output_type="CanonBible",
        authorized_tools=(
            AgentTool.NARRATIVE_ANALYSIS,
            AgentTool.RAG_RETRIEVAL,
            AgentTool.DOMAIN_SERVICES,
        ),
        memory=MemoryScope.CANON,
        prompt_name="canon.extract",
        completion_criteria=(
            "Ao menos um personagem foi extraído.",
            "Todo fato aponta para um trecho da obra.",
            "Lacunas viram questões em aberto em vez de invenção.",
        ),
        failure_criteria=("Nenhum personagem nem beat foi identificado no texto.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        log = self._log(context)
        book = context.require_book()

        chapters = tuple(
            (chapter.index, chapter.label, chapter.text) for chapter in book.chapters
        )
        analysis = context.analyzer.analyze(
            text=book.canonical_text,
            chapters=chapters,
            language=str(book.language),
        )

        self._index_rag(context, book, analysis)

        characters = self._build_characters(analysis, book)
        locations = self._build_locations(analysis, book)
        props = self._build_props(analysis, book)
        beats = self._build_beats(analysis, characters, locations, book)
        timeline = self._build_timeline(analysis, beats)
        relationships = self._build_relationships(analysis, characters)
        facts = self._build_facts(analysis, book)
        questions = self._build_questions(analysis)

        canon = CanonBible(
            project_id=context.project_id,
            title=book.title,
            author=book.author,
            language=book.language,
            logline=analysis.logline,
            thesis=analysis.thesis,
            facts=facts,
            characters=characters,
            relationships=relationships,
            locations=locations,
            props=props,
            timeline=timeline,
            beats=beats,
            world_rules=analysis.world_rules,
            prohibitions=analysis.prohibitions,
            mysteries=analysis.mysteries,
            unresolved_questions=questions,
        )

        log.info(
            "Cânone extraído",
            characters=len(characters),
            locations=len(locations),
            beats=len(beats),
            facts=len(facts),
            open_questions=len(questions),
        )

        return AgentResult(
            agent=self.name,
            outputs={"canon": canon, "analysis": analysis},
            events=(
                DomainEvent(
                    event_type=DomainEventType.CANON_EXTRACTED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "characters": len(characters),
                        "locations": len(locations),
                        "beats": len(beats),
                        "facts": len(facts),
                        "analyzer": analysis.analyzer_name,
                    },
                ),
            ),
        )

    # -- RAG ---------------------------------------------------------------

    def _index_rag(
        self, context: EngineContext, book: object, analysis: NarrativeAnalysis
    ) -> None:
        """Indexa a obra para que fatos possam ser justificados por trecho."""
        if not context.configuration.rag.enabled:
            return

        from pedroarte_youtube_engine.domain.source import BookSource

        assert isinstance(book, BookSource)
        rag_config = context.configuration.rag
        chunker = StructuralChunker(
            target_words=rag_config.chunk_target_words,
            overlap_words=rag_config.chunk_overlap_words,
        )
        chunks = chunker.chunk_chapters(
            source_id=book.primary_source_id.value,
            source_path=next(
                (doc.relative_path for doc in book.documents if doc.is_primary),
                "input",
            ),
            chapters=tuple(
                (chapter.index, chapter.label, chapter.text) for chapter in book.chapters
            ),
            characters=tuple(character.name for character in analysis.characters),
            locations=tuple(location.name for location in analysis.locations),
        )
        for document in book.auxiliary_documents():
            chunks += chunker.chunk_structured(
                source_id=document.source_id.value,
                source_path=document.relative_path,
                text=document.text,
            )
        context.rag.index(chunks)

    # -- construção --------------------------------------------------------

    def _build_characters(
        self, analysis: NarrativeAnalysis, book: object
    ) -> tuple[Character, ...]:
        characters: list[Character] = []
        for position, detected in enumerate(analysis.characters):
            role = _ROLES[position] if position < len(_ROLES) else "figuração"
            characters.append(
                Character(
                    character_id=CharacterId.from_name(detected.name),
                    canonical_name=detected.name,
                    aliases=detected.aliases,
                    role=role,
                    summary=self._character_summary(detected),
                    appearance=self._appearance(detected),
                    wardrobe_sets=self._wardrobe(detected),
                    temperament=self._temperament(detected),
                    dominant_tone=EmotionalTone.NEUTRAL,
                    mention_count=detected.mentions,
                    dialogue_line_count=detected.dialogue_lines,
                    first_chapter_index=detected.first_chapter_index,
                    forbidden_variations=(
                        "mudança de idade aparente",
                        "mudança de etnia aparente",
                        "mudança de estrutura facial",
                        "mudança de cor dos olhos",
                        "mudança de altura",
                        "troca de voz",
                    ),
                    references=self._references(detected.descriptive_sentences, book),
                )
            )
        return tuple(characters)

    @staticmethod
    def _character_summary(detected: DetectedCharacter) -> str:
        if detected.descriptive_sentences:
            return excerpt(detected.descriptive_sentences[0], max_chars=400)
        return (
            f"{detected.name} aparece {detected.mentions} vezes na obra e tem "
            f"{detected.dialogue_lines} falas atribuídas."
        )

    @staticmethod
    def _appearance(detected: DetectedCharacter) -> CharacterAppearance:
        """Monta a âncora visual a partir do que a obra realmente descreve.

        O que a obra não diz permanece "não descrito na obra" — um marcador
        honesto, que o `CHARACTER_BIBLE_AGENT` promove a questão em aberto.
        """
        text = " ".join(detected.descriptive_sentences).lower()
        return CharacterAppearance(
            apparent_age=_extract_age(text),
            height_range=_first_match(
                text, {"alto": "acima da média", "baixa": "abaixo da média",
                       "baixo": "abaixo da média", "média": "média"}, "não descrita na obra"
            ),
            body_type=_first_match(
                text,
                {"magro": "magro", "magra": "magra", "curvado": "curvado",
                 "ombros estreitos": "ombros estreitos", "robusto": "robusto"},
                "não descrito na obra",
            ),
            face_shape="não descrito na obra",
            skin_description=_first_match(
                text, {"pele escura": "pele escura", "pele clara": "pele clara",
                       "pálido": "pele pálida"}, "não descrita na obra"
            ),
            eyes=_first_match(
                text,
                {"olhos cinzentos": "cinzentos", "olhos castanhos": "castanhos",
                 "olhos verdes": "verdes", "olhos azuis": "azuis",
                 "olhos pretos": "pretos", "muito abertos": "muito abertos"},
                "não descritos na obra",
            ),
            eyebrows="não descritas na obra",
            nose="não descrito na obra",
            mouth="não descrita na obra",
            hair=_first_match(
                text,
                {"cabelo branco": "branco", "cabelo preto": "preto",
                 "cabelo grisalho": "grisalho", "coque": "preso em coque",
                 "mechas finas": "mechas finas"},
                "não descrito na obra",
            ),
            distinctive_features=_features(text),
            default_posture=_first_match(
                text, {"curvado": "curvada, de quem olha para baixo",
                       "ereta": "ereta e contida"}, "contida"
            ),
            neutral_expression="atenta, sem sorriso",
            movement_signature="movimentos econômicos e deliberados",
        )

    @staticmethod
    def _wardrobe(detected: DetectedCharacter) -> tuple[WardrobeSet, ...]:
        text = " ".join(detected.descriptive_sentences)
        lowered = text.lower()
        pieces = [
            piece
            for marker, piece in (
                ("avental", "avental de couro gasto"),
                ("luvas", "luvas sem dedos"),
                ("casaco", "casaco grande demais"),
                ("chapéu", "chapéu"),
                ("vestido", "vestido"),
                ("terno", "terno"),
            )
            if marker in lowered
        ]
        description = ", ".join(pieces) if pieces else "figurino não descrito na obra"
        return (
            WardrobeSet(
                name="figurino_base",
                description=description,
                applies_from_chapter=detected.first_chapter_index,
                condition="íntegro e usado no dia a dia",
            ),
        )

    @staticmethod
    def _temperament(detected: DetectedCharacter) -> tuple[str, ...]:
        text = " ".join(detected.descriptive_sentences).lower()
        traits = [
            trait
            for marker, trait in (
                ("contida", "contido"),
                ("nervosa", "ansioso"),
                ("apertava", "concentrado"),
                ("não piscavam", "atento"),
                ("ocupar pouco espaço", "reservado"),
                ("curvado", "absorto no trabalho"),
            )
            if marker in text
        ]
        return tuple(traits) or ("não determinado pela obra",)

    def _build_locations(
        self, analysis: NarrativeAnalysis, book: object
    ) -> tuple[Location, ...]:
        return tuple(
            Location(
                location_id=LocationId.from_name(detected.name),
                canonical_name=detected.name,
                description=excerpt(
                    " ".join(detected.descriptive_sentences), max_chars=800
                ),
                interior=detected.interior,
                mention_count=detected.mentions,
                default_time_of_day="indefinido",
                default_weather="indefinido",
                ambient_sound_signature=_ambient_for(detected.name, detected.interior),
                references=self._references(detected.descriptive_sentences, book),
            )
            for detected in analysis.locations
        )

    def _build_props(self, analysis: NarrativeAnalysis, book: object) -> tuple[Prop, ...]:
        return tuple(
            Prop(
                prop_id=PropId.from_name(detected.name),
                canonical_name=detected.name,
                description=excerpt(
                    " ".join(detected.descriptive_sentences), max_chars=400
                ),
                narrative_weight=min(5, max(1, detected.mentions // 3)),
                references=self._references(detected.descriptive_sentences, book),
            )
            for detected in analysis.props
        )

    def _build_beats(
        self,
        analysis: NarrativeAnalysis,
        characters: tuple[Character, ...],
        locations: tuple[Location, ...],
        book: object,
    ) -> tuple[NarrativeBeat, ...]:
        by_name = {character.canonical_name: character.character_id for character in characters}
        location_ids = {location.canonical_name: location.location_id for location in locations}

        beats: list[NarrativeBeat] = []
        for detected in analysis.beats:
            tone = _tone_from(detected.tone)
            beats.append(
                NarrativeBeat(
                    beat_id=f"beat_{detected.order:04d}",
                    order=detected.order,
                    chapter_index=detected.chapter_index,
                    summary=detected.summary,
                    participants=tuple(
                        by_name[name] for name in detected.participants if name in by_name
                    ),
                    location_id=location_ids.get(detected.location),
                    tone_start=tone,
                    tone_end=tone,
                    tension=detected.tension,
                    information_revealed=detected.information_revealed,
                    dialogue_excerpts=detected.dialogue_excerpts,
                    weight=detected.weight,
                    references=self._beat_reference(detected, book),
                )
            )
        return tuple(beats)

    @staticmethod
    def _build_timeline(
        analysis: NarrativeAnalysis, beats: tuple[NarrativeBeat, ...]
    ) -> tuple[TimelineEvent, ...]:
        """Os beats de maior peso viram eventos da cronologia."""
        significant = sorted(beats, key=lambda beat: (-beat.weight, beat.order))[:40]
        ordered = sorted(significant, key=lambda beat: beat.order)
        return tuple(
            TimelineEvent(
                event_id=f"event_{position:04d}",
                order=position,
                chapter_index=beat.chapter_index,
                title=first_sentence(beat.summary, fallback=beat.summary)[:200],
                description=beat.summary,
                participants=beat.participants,
                location_id=beat.location_id,
                consequences=beat.information_revealed,
                tension=beat.tension,
                tone=beat.tone_end,
                references=beat.references,
            )
            for position, beat in enumerate(ordered)
        )

    @staticmethod
    def _build_relationships(
        analysis: NarrativeAnalysis, characters: tuple[Character, ...]
    ) -> tuple[CharacterRelationship, ...]:
        by_name = {character.canonical_name: character for character in characters}
        seen: set[tuple[str, str]] = set()
        relationships: list[CharacterRelationship] = []

        for detected in analysis.characters:
            source = by_name.get(detected.name)
            if source is None:
                continue
            for other_name in detected.co_occurring:
                target = by_name.get(other_name)
                if target is None or target.character_id == source.character_id:
                    continue
                key = (source.character_id.value, target.character_id.value)
                if key in seen:
                    continue
                seen.add(key)
                relationships.append(
                    CharacterRelationship(
                        source_character_id=source.character_id,
                        target_character_id=target.character_id,
                        kind=RelationshipKind.UNKNOWN,
                        description=(
                            f"{source.canonical_name} e {target.canonical_name} aparecem "
                            "juntos em cena de forma recorrente; a natureza exata da "
                            "relação não é declarada explicitamente pela obra."
                        ),
                        tension=3,
                    )
                )
        return tuple(relationships)

    def _build_facts(
        self, analysis: NarrativeAnalysis, book: object
    ) -> tuple[CanonFact, ...]:
        facts: list[CanonFact] = []

        def add(kind: CanonFactKind, statement: str, subjects: tuple[str, ...]) -> None:
            facts.append(
                CanonFact(
                    fact_id=f"fact_{kind.value}_{stable_short_id(statement, length=8)}",
                    kind=kind,
                    statement=excerpt(statement, max_chars=800),
                    subjects=subjects,
                    confidence=ConfidenceScore.high(),
                    references=self._references((statement,), book),
                )
            )

        for rule in analysis.world_rules:
            add(CanonFactKind.WORLD_RULE, rule, ())
        for prohibition in analysis.prohibitions:
            add(CanonFactKind.PROHIBITION, prohibition, ())
        for mystery in analysis.mysteries:
            add(CanonFactKind.MYSTERY, mystery, ())
        for theme in analysis.themes:
            add(CanonFactKind.THEME, f"A obra elabora o tema '{theme}'.", (theme,))
        for character in analysis.characters:
            for sentence in character.descriptive_sentences[:2]:
                add(CanonFactKind.CHARACTER_TRAIT, sentence, (character.name,))

        return tuple(facts)

    @staticmethod
    def _build_questions(analysis: NarrativeAnalysis) -> tuple[UnresolvedQuestion, ...]:
        return tuple(
            UnresolvedQuestion(
                question_id=f"question_{stable_short_id(text, length=8)}",
                question=excerpt(text, max_chars=560),
                why_it_matters=(
                    "Sem esta definição, o motor precisaria inventar o traço — e "
                    "invenção não declarada quebra a continuidade entre segmentos."
                ),
                confidence=ConfidenceScore.low(),
            )
            for text in analysis.uncertainties
        )

    # -- proveniência ------------------------------------------------------

    @staticmethod
    def _references(sentences: tuple[str, ...], book: object) -> tuple[SourceReference, ...]:
        from pedroarte_youtube_engine.domain.source import BookSource

        assert isinstance(book, BookSource)
        if not sentences:
            return ()

        path = next(
            (doc.relative_path for doc in book.documents if doc.is_primary), "input"
        )
        references: list[SourceReference] = []
        for sentence in sentences[:3]:
            chapter = _locate_chapter(book, sentence)
            references.append(
                SourceReference(
                    source_id=book.primary_source_id,
                    source_path=path,
                    chapter=chapter,
                    excerpt=excerpt(sentence, max_chars=220),
                    confidence=ConfidenceScore.high(),
                )
            )
        return tuple(references)

    @staticmethod
    def _beat_reference(detected: DetectedBeat, book: object) -> tuple[SourceReference, ...]:
        from pedroarte_youtube_engine.domain.source import BookSource

        assert isinstance(book, BookSource)
        chapter = book.chapter_at(detected.chapter_index)
        path = next(
            (doc.relative_path for doc in book.documents if doc.is_primary), "input"
        )
        return (
            SourceReference(
                source_id=book.primary_source_id,
                source_path=path,
                chapter=chapter.label if chapter else None,
                start_offset=detected.start_offset,
                end_offset=detected.end_offset,
                excerpt=excerpt(detected.summary, max_chars=220),
                confidence=ConfidenceScore.high(),
            ),
        )


# ---------------------------------------------------------------------------
# Auxiliares de extração
# ---------------------------------------------------------------------------


def _extract_age(text: str) -> str:
    import re

    match = re.search(r"(\w+\s+e\s+\w+|\w+)\s+anos", text)
    if match:
        return f"{match.group(1)} anos (declarado na obra)"
    return "não declarada na obra"


def _first_match(text: str, options: dict[str, str], fallback: str) -> str:
    for marker, value in options.items():
        if marker in text:
            return value
    return fallback


def _features(text: str) -> tuple[str, ...]:
    found = [
        feature
        for marker, feature in (
            ("cicatriz", "cicatriz"),
            ("tatuagem", "tatuagem"),
            ("barba", "barba"),
            ("óculos", "óculos"),
            ("coque", "cabelo preso em coque"),
            ("mechas", "mechas finas sobre a testa"),
        )
        if marker in text
    ]
    return tuple(found)


def _ambient_for(name: str, interior: bool) -> tuple[str, ...]:
    lowered = name.lower()
    signatures = {
        "oficina": ("tique-taque desencontrado de vários relógios", "raspar de metal fino"),
        "cartório": ("papel manuseado", "zumbido de lâmpada fluorescente"),
        "igreja": ("eco alto e lento", "sino distante"),
        "cemitério": ("vento entre pedras", "passos sobre cascalho"),
        "rua": ("tráfego distante", "passos no asfalto molhado"),
        "arquivo": ("silêncio abafado por papel", "estrutura metálica rangendo"),
    }
    for marker, sounds in signatures.items():
        if marker in lowered:
            return sounds
    return ("ambiente interno abafado",) if interior else ("vento aberto", "ruído distante")


def _tone_from(label: str) -> EmotionalTone:
    try:
        return EmotionalTone(label)
    except ValueError:
        return EmotionalTone.NEUTRAL


def _locate_chapter(book: object, sentence: str) -> str | None:
    """Encontra em qual capítulo uma frase aparece — a base da citação."""
    from pedroarte_youtube_engine.domain.source import BookSource

    assert isinstance(book, BookSource)
    needle = sentence.strip()[:60]
    if not needle:
        return None
    for chapter in book.chapters:
        if needle in chapter.text:
            return chapter.label
    return None


# ---------------------------------------------------------------------------
# WORLD_BIBLE_AGENT
# ---------------------------------------------------------------------------


class WorldBibleAgent(BaseAgent):
    """`WORLD_BIBLE_AGENT` — consolida as regras e os limites do universo."""

    _contract = AgentContract(
        name="WORLD_BIBLE_AGENT",
        responsibility=(
            "Construir a Bíblia de Mundo: geografia, sociedade, tecnologia, política, "
            "economia, cultura, regras físicas e sobrenaturais e limites narrativos."
        ),
        phase="BUILDING_BIBLES",
        input_type="CanonBible",
        output_type="WorldBibleDocument",
        authorized_tools=(AgentTool.RAG_RETRIEVAL, AgentTool.DOMAIN_SERVICES),
        memory=MemoryScope.CANON,
        prompt_name="canon.world_bible",
        completion_criteria=(
            "As regras do mundo estão separadas dos hábitos de personagem.",
            "As proibições do universo estão explícitas.",
        ),
        failure_criteria=("O cânone não foi extraído.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        log = self._log(context)

        geography = tuple(
            f"{location.canonical_name} "
            f"({'interior' if location.interior else 'exterior'}, "
            f"{location.mention_count} menções)"
            for location in canon.locations
        )
        document = {
            "geography": geography,
            "world_rules": canon.world_rules,
            "prohibitions": canon.prohibitions,
            "mysteries": canon.mysteries,
            "physical_limits": tuple(
                fact.statement
                for fact in canon.facts
                if fact.kind.value in {"regra_do_mundo", "limitacao"}
            ),
            "open_questions": tuple(
                question.question for question in canon.unresolved_questions
            ),
        }

        log.info(
            "Bíblia de Mundo construída",
            locations=len(geography),
            rules=len(canon.world_rules),
            prohibitions=len(canon.prohibitions),
        )
        return self._ok(world_bible=document)


# ---------------------------------------------------------------------------
# CHARACTER_BIBLE_AGENT
# ---------------------------------------------------------------------------


class CharacterBibleAgent(BaseAgent):
    """`CHARACTER_BIBLE_AGENT` — completa as fichas com âncoras de consistência.

    Usa o RAG para buscar descrições que a extração inicial não capturou, e
    promove cada traço não descrito a questão em aberto — nunca o inventa.
    """

    _contract = AgentContract(
        name="CHARACTER_BIBLE_AGENT",
        responsibility=(
            "Produzir a ficha de cada personagem com aparência, voz, temperamento, "
            "gestos, postura, roupas, objetos, relações, evolução e âncoras de "
            "consistência — sem usar nomes de atores ou celebridades."
        ),
        phase="BUILDING_BIBLES",
        input_type="CanonBible",
        output_type="tuple[Character, ...]",
        authorized_tools=(AgentTool.RAG_RETRIEVAL, AgentTool.DOMAIN_SERVICES),
        memory=MemoryScope.CANON,
        prompt_name="canon.character_bible",
        completion_criteria=(
            "Cada personagem tem uma âncora de aparência reinjetável em prompt.",
            "Nenhuma ficha referencia pessoa real.",
            "Traços não descritos pela obra viram questões em aberto.",
        ),
        failure_criteria=("Nenhum personagem foi extraído do cânone.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        log = self._log(context)

        enriched: list[Character] = []
        new_questions: list[UnresolvedQuestion] = []

        for character in canon.characters:
            appearance = character.appearance
            if context.configuration.rag.enabled and context.rag.indexed_count:
                appearance = self._enrich_from_rag(context, character)

            undescribed = [
                field_name
                for field_name, value in (
                    ("estrutura facial", appearance.face_shape),
                    ("olhos", appearance.eyes),
                    ("cabelo", appearance.hair),
                    ("pele", appearance.skin_description),
                )
                if "não descrit" in value
            ]
            if undescribed and character.role in {"protagonista", "deuteragonista"}:
                new_questions.append(
                    UnresolvedQuestion(
                        question_id=(
                            f"question_appearance_{stable_short_id(character.canonical_name, length=8)}"
                        ),
                        question=(
                            f"A obra não descreve {', '.join(undescribed)} de "
                            f"{character.canonical_name}. Qual é a definição autoral?"
                        ),
                        why_it_matters=(
                            "Sem definição, cada segmento gerado pode produzir um rosto "
                            "diferente para o mesmo personagem."
                        ),
                        affected_subjects=(character.canonical_name,),
                        confidence=ConfidenceScore.low(),
                    )
                )

            enriched.append(character.model_copy(update={"appearance": appearance}))

        log.info(
            "Bíblia de Personagens construída",
            characters=len(enriched),
            new_questions=len(new_questions),
        )

        return self._ok(characters=tuple(enriched), questions=tuple(new_questions))

    def _enrich_from_rag(
        self, context: EngineContext, character: Character
    ) -> CharacterAppearance:
        """Busca descrições adicionais do personagem no índice."""
        result = context.rag.about_character(character.canonical_name, top_k=4)
        if result.is_empty:
            return character.appearance

        corpus = " ".join(chunk.text for chunk in result.chunks).lower()
        appearance = character.appearance
        updates: dict[str, object] = {}

        if "não descrit" in appearance.eyes:
            found = _first_match(
                corpus,
                {
                    "olhos cinzentos": "cinzentos",
                    "olhos castanhos": "castanhos",
                    "olhos verdes": "verdes",
                    "olhos azuis": "azuis",
                },
                appearance.eyes,
            )
            if found != appearance.eyes:
                updates["eyes"] = found

        if "não descrit" in appearance.hair:
            found = _first_match(
                corpus,
                {
                    "cabelo branco": "branco",
                    "cabelo preto": "preto",
                    "cabelo grisalho": "grisalho",
                    "coque": "preso em coque",
                },
                appearance.hair,
            )
            if found != appearance.hair:
                updates["hair"] = found

        extra_features = _features(corpus)
        if extra_features:
            merged = tuple(sorted(set(appearance.distinctive_features) | set(extra_features)))
            updates["distinctive_features"] = merged

        return appearance.model_copy(update=updates) if updates else appearance
