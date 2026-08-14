"""Entidades da Bíblia Audiovisual: a tradução do cânone em decisões de tela.

Enquanto `canon.py` responde "o que é verdade na obra", este módulo responde
"como essa verdade soa e aparece" — e faz isso de forma reutilizável, para que o
segmento 1 e o segmento 216 pertençam visivelmente ao mesmo filme.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    CameraAngle,
    CameraMovement,
    CharacterId,
    EmotionalTone,
    LocationId,
    ShotType,
    TransitionType,
    VoiceIdentity,
)


class VoiceProfile(DomainEntity):
    """Entrada da `voice_bible` (seção 18).

    O `voice_id` é a chave de consistência: o mesmo personagem sempre aponta
    para o mesmo perfil, em todos os formatos e episódios.
    """

    identity: VoiceIdentity
    character_id: CharacterId | None = None
    display_name: str = Field(min_length=1, max_length=160)
    is_narrator: bool = False
    emotional_range: tuple[EmotionalTone, ...] = Field(default_factory=tuple)
    intensity_default: str = Field(default="média", max_length=48)
    pauses: str = Field(default="pausas curtas entre orações", max_length=200)
    pronunciation_dictionary: dict[str, str] = Field(default_factory=dict)
    forbidden_variations: tuple[str, ...] = Field(
        default_factory=lambda: (
            "voz teatral exagerada",
            "tom cômico",
            "voz de trailer excessivamente grave",
            "imitação de pessoa real identificável",
        )
    )
    reference_notes: str = Field(default="", max_length=600)

    @property
    def voice_id(self) -> str:
        return self.identity.voice_id

    def descriptor(self) -> str:
        """Uma linha densa, reinjetada em todo prompt que use esta voz."""
        return (
            f"{self.identity.voice_id} — {self.display_name}: "
            f"{self.identity.pitch}, textura {self.identity.texture}, "
            f"idade vocal {self.identity.apparent_age_range}, "
            f"sotaque {self.identity.accent_region}, ritmo {self.identity.pace}, "
            f"articulação {self.identity.articulation}, respiração {self.identity.breathing}"
        )


class MusicRole(StrEnum):
    MAIN_THEME = "tema_principal"
    CHARACTER_THEME = "tema_de_personagem"
    TENSION = "tensao"
    GRIEF = "luto"
    WONDER = "deslumbramento"
    PURSUIT = "perseguicao"
    INTIMACY = "intimidade"
    REVELATION = "revelacao"
    CLOSING = "encerramento"


class MusicTheme(DomainEntity):
    """Tema musical original da obra.

    O motor descreve instrumentação e intenção; nunca pede cópia ou imitação de
    obra protegida ou de artista específico (regra da seção 9.20).
    """

    theme_id: str = Field(min_length=3, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    role: MusicRole
    instrumentation: tuple[str, ...] = Field(min_length=1)
    tempo_bpm_range: str = Field(default="60-80", max_length=32)
    key_character: str = Field(default="modo menor, sem resolução clara", max_length=200)
    motif_description: str = Field(min_length=3, max_length=600)
    intensity_curve: str = Field(default="entra baixa, cresce, recua no diálogo", max_length=400)
    associated_character_id: CharacterId | None = None
    associated_tone: EmotionalTone = EmotionalTone.NEUTRAL

    @model_validator(mode="after")
    def _forbid_imitation(self) -> "MusicTheme":
        banned = ("no estilo de ", "igual a ", "cópia de ", "soundtrack de ")
        haystack = f"{self.motif_description} {self.key_character}".lower()
        for token in banned:
            if token in haystack:
                raise ValueError(
                    "A descrição musical não pode pedir imitação de obra ou artista específico."
                )
        return self


class SoundMotif(DomainEntity):
    """Assinatura sonora recorrente ligada a um personagem, objeto ou ideia."""

    motif_id: str = Field(min_length=3, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=3, max_length=600)
    trigger: str = Field(min_length=3, max_length=400)
    spatiality: str = Field(default="centro, próximo", max_length=160)
    associated_character_id: CharacterId | None = None
    associated_location_id: LocationId | None = None


class VisualIdentity(DomainEntity):
    """Identidade fotográfica do projeto inteiro."""

    style_statement: str = Field(min_length=10, max_length=800)
    conceptual_palette: tuple[str, ...] = Field(min_length=1)
    lighting_doctrine: str = Field(min_length=5, max_length=600)
    lens_language: str = Field(min_length=5, max_length=600)
    camera_doctrine: str = Field(min_length=5, max_length=600)
    texture_and_grain: str = Field(default="grão fino, contraste médio-alto", max_length=400)
    default_shot_type: ShotType = ShotType.MEDIUM
    default_angle: CameraAngle = CameraAngle.EYE_LEVEL
    default_movement: CameraMovement = CameraMovement.STATIC
    default_transition: TransitionType = TransitionType.CUT
    recurring_motifs: tuple[str, ...] = Field(default_factory=tuple)
    visual_restrictions: tuple[str, ...] = Field(
        default_factory=lambda: (
            "sem texto sobreposto não solicitado",
            "sem logotipos ou marcas registradas",
            "sem rostos de pessoas públicas reais",
            "sem membros ou dedos extras",
            "sem mudança de idade, etnia aparente ou estrutura facial dos personagens",
        )
    )


class CharacterVisualProfile(DomainEntity):
    """Como um personagem específico é fotografado."""

    character_id: CharacterId
    preferred_shot_types: tuple[ShotType, ...] = Field(default_factory=tuple)
    lighting_note: str = Field(default="", max_length=400)
    color_association: str = Field(default="", max_length=160)
    framing_note: str = Field(default="", max_length=400)
    forbidden_variations: tuple[str, ...] = Field(default_factory=tuple)


class LocationVisualProfile(DomainEntity):
    """Como um ambiente é fotografado e como ele soa."""

    location_id: LocationId
    palette: tuple[str, ...] = Field(default_factory=tuple)
    lighting: str = Field(default="", max_length=400)
    ambient_sound: tuple[str, ...] = Field(default_factory=tuple)
    camera_note: str = Field(default="", max_length=400)
    default_lens: str = Field(default="35mm", max_length=64)


class ContinuityAnchor(DomainEntity):
    """Fato visual ou sonoro que não pode variar sem justificativa narrativa."""

    anchor_id: str = Field(min_length=3, max_length=128)
    subject: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=64)
    statement: str = Field(min_length=3, max_length=600)
    applies_to_variants: tuple[str, ...] = Field(default_factory=tuple)
    hard_constraint: bool = True
