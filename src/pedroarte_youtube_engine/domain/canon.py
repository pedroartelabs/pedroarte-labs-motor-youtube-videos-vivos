"""Entidades do cânone: a verdade narrativa extraída da obra.

O cânone é a autoridade contra a qual o `CANON_GUARDIAN_AGENT` compara cada
prompt. Tudo aqui carrega proveniência e confiança — o motor precisa distinguir
"o livro afirma" de "o motor inferiu".
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    CharacterId,
    ConfidenceScore,
    EmotionalTone,
    LocationId,
    PropId,
    SourceReference,
)


class CanonFactKind(StrEnum):
    """Categorias de fato canônico."""

    EVENT = "evento"
    CHARACTER_TRAIT = "traco_de_personagem"
    RELATIONSHIP = "relacao"
    LOCATION_DETAIL = "detalhe_de_local"
    OBJECT_DETAIL = "detalhe_de_objeto"
    WORLD_RULE = "regra_do_mundo"
    LIMITATION = "limitacao"
    MYSTERY = "misterio"
    PROHIBITION = "proibicao"
    THEME = "tema"
    CHRONOLOGY = "cronologia"


class CanonFact(DomainEntity):
    """Uma afirmação verificável sobre a obra."""

    fact_id: str = Field(min_length=3, max_length=128)
    kind: CanonFactKind
    statement: str = Field(min_length=3, max_length=1200)
    subjects: tuple[str, ...] = Field(default_factory=tuple)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore.medium)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)
    contradicts: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def is_uncertain(self) -> bool:
        return self.confidence.is_uncertain or not self.references


class CharacterAppearance(DomainEntity):
    """Âncora visual de um personagem (seção 17).

    Cada campo existe para impedir uma deriva específica que os geradores de
    vídeo cometem entre um segmento e o seguinte.
    """

    apparent_age: str = Field(default="indeterminada", max_length=64)
    height_range: str = Field(default="média", max_length=64)
    body_type: str = Field(default="não especificado", max_length=120)
    face_shape: str = Field(default="não especificado", max_length=120)
    skin_description: str = Field(default="não especificado", max_length=160)
    eyes: str = Field(default="não especificado", max_length=160)
    eyebrows: str = Field(default="não especificado", max_length=120)
    nose: str = Field(default="não especificado", max_length=120)
    mouth: str = Field(default="não especificado", max_length=120)
    hair: str = Field(default="não especificado", max_length=200)
    distinctive_features: tuple[str, ...] = Field(default_factory=tuple)
    default_posture: str = Field(default="ereta e contida", max_length=160)
    default_gestures: tuple[str, ...] = Field(default_factory=tuple)
    neutral_expression: str = Field(default="atenta, sem sorriso", max_length=160)
    movement_signature: str = Field(default="movimentos econômicos", max_length=200)

    def anchor_text(self) -> str:
        """Bloco descritivo reinjetado em todo prompt em que o personagem aparece."""
        features = ", ".join(self.distinctive_features) or "nenhum traço distintivo registrado"
        return (
            f"idade aparente {self.apparent_age}; estatura {self.height_range}; "
            f"compleição {self.body_type}; rosto {self.face_shape}; pele {self.skin_description}; "
            f"olhos {self.eyes}; sobrancelhas {self.eyebrows}; nariz {self.nose}; "
            f"boca {self.mouth}; cabelo {self.hair}; traços distintivos: {features}; "
            f"postura padrão {self.default_posture}; expressão neutra {self.neutral_expression}"
        )


class WardrobeSet(DomainEntity):
    """Conjunto de figurino associado a um trecho da história."""

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    applies_from_chapter: int = Field(default=0, ge=0)
    condition: str = Field(default="íntegro e limpo", max_length=200)


class Character(DomainEntity):
    """Ficha completa de personagem, usada por vídeo, voz e continuidade."""

    character_id: CharacterId
    canonical_name: str = Field(min_length=1, max_length=160)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    role: str = Field(default="secundário", max_length=64)
    summary: str = Field(default="", max_length=1200)
    appearance: CharacterAppearance = Field(default_factory=CharacterAppearance)
    wardrobe_sets: tuple[WardrobeSet, ...] = Field(default_factory=tuple)
    temperament: tuple[str, ...] = Field(default_factory=tuple)
    objectives: tuple[str, ...] = Field(default_factory=tuple)
    fears: tuple[str, ...] = Field(default_factory=tuple)
    arc: str = Field(default="", max_length=800)
    signature_props: tuple[PropId, ...] = Field(default_factory=tuple)
    dominant_tone: EmotionalTone = EmotionalTone.NEUTRAL
    forbidden_variations: tuple[str, ...] = Field(default_factory=tuple)
    mention_count: int = Field(default=0, ge=0)
    dialogue_line_count: int = Field(default=0, ge=0)
    first_chapter_index: int = Field(default=0, ge=0)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)

    @property
    def is_lead(self) -> bool:
        return self.role in {"protagonista", "deuteragonista"}

    def default_wardrobe(self) -> WardrobeSet | None:
        return self.wardrobe_sets[0] if self.wardrobe_sets else None

    def wardrobe_for_chapter(self, chapter_index: int) -> WardrobeSet | None:
        """Figurino vigente no capítulo — o último conjunto que já entrou em vigor."""
        applicable = [
            wardrobe
            for wardrobe in self.wardrobe_sets
            if wardrobe.applies_from_chapter <= chapter_index
        ]
        return applicable[-1] if applicable else self.default_wardrobe()


class RelationshipKind(StrEnum):
    FAMILY = "familia"
    ROMANTIC = "romantica"
    FRIENDSHIP = "amizade"
    PROFESSIONAL = "profissional"
    ANTAGONISM = "antagonismo"
    MENTORSHIP = "mentoria"
    ALLIANCE = "alianca"
    DEBT = "divida"
    SUSPICION = "suspeita"
    UNKNOWN = "indefinida"


class CharacterRelationship(DomainEntity):
    """Relação dirigida entre dois personagens."""

    source_character_id: CharacterId
    target_character_id: CharacterId
    kind: RelationshipKind = RelationshipKind.UNKNOWN
    description: str = Field(default="", max_length=600)
    tension: int = Field(default=0, ge=0, le=10)
    evolves_to: str = Field(default="", max_length=400)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_distinct(self) -> "CharacterRelationship":
        if self.source_character_id == self.target_character_id:
            raise ValueError("Uma relação exige dois personagens distintos.")
        return self


class Location(DomainEntity):
    """Ambiente recorrente da obra."""

    location_id: LocationId
    canonical_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1200)
    interior: bool = True
    architecture: str = Field(default="", max_length=400)
    textures: tuple[str, ...] = Field(default_factory=tuple)
    default_time_of_day: str = Field(default="indefinido", max_length=64)
    default_weather: str = Field(default="indefinido", max_length=64)
    ambient_sound_signature: tuple[str, ...] = Field(default_factory=tuple)
    mention_count: int = Field(default=0, ge=0)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)


class Prop(DomainEntity):
    """Objeto com peso narrativo — precisa não desaparecer entre segmentos."""

    prop_id: PropId
    canonical_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)
    narrative_weight: int = Field(default=1, ge=1, le=5)
    owner_character_id: CharacterId | None = None
    sound_signature: str = Field(default="", max_length=200)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)


class TimelineEvent(DomainEntity):
    """Acontecimento posicionado na cronologia da obra."""

    event_id: str = Field(min_length=3, max_length=128)
    order: int = Field(ge=0)
    chapter_index: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=1200)
    participants: tuple[CharacterId, ...] = Field(default_factory=tuple)
    location_id: LocationId | None = None
    consequences: tuple[str, ...] = Field(default_factory=tuple)
    tension: int = Field(default=0, ge=0, le=10)
    tone: EmotionalTone = EmotionalTone.NEUTRAL
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)


class NarrativeBeat(DomainEntity):
    """Unidade mínima de progressão dramática.

    É o que o `SCENE_DECOMPOSER_AGENT` transforma em cenas e, depois, em
    segmentos de dez segundos.
    """

    beat_id: str = Field(min_length=3, max_length=128)
    order: int = Field(ge=0)
    chapter_index: int = Field(default=0, ge=0)
    summary: str = Field(min_length=3, max_length=800)
    participants: tuple[CharacterId, ...] = Field(default_factory=tuple)
    location_id: LocationId | None = None
    tone_start: EmotionalTone = EmotionalTone.NEUTRAL
    tone_end: EmotionalTone = EmotionalTone.NEUTRAL
    tension: int = Field(default=0, ge=0, le=10)
    information_revealed: tuple[str, ...] = Field(default_factory=tuple)
    dialogue_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    weight: float = Field(default=1.0, gt=0.0, le=10.0)
    references: tuple[SourceReference, ...] = Field(default_factory=tuple)

    @property
    def changes_tone(self) -> bool:
        return self.tone_start != self.tone_end


class UnresolvedQuestion(DomainEntity):
    """Ponto que o motor não conseguiu resolver a partir do texto.

    Sai em `canon/unresolved_questions.json` para revisão humana, em vez de ser
    preenchido por invenção.
    """

    question_id: str = Field(min_length=3, max_length=128)
    question: str = Field(min_length=5, max_length=600)
    why_it_matters: str = Field(default="", max_length=600)
    affected_subjects: tuple[str, ...] = Field(default_factory=tuple)
    assumed_answer: str = Field(default="", max_length=600)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore.low)
