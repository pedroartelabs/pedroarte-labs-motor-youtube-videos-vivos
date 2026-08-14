"""O contrato do segmento audiovisual — o coração do motor.

Regra inegociável da seção 3.1: **todo segmento tem uma seção visual e uma
seção sonora**. Um segmento só com imagem não é representável neste modelo: o
`AudioPlan` exige um `voice_plan` não vazio, e o silêncio vocal só é aceito
quando declarado explicitamente e justificado.

A invariante é estrutural, não uma verificação posterior. Um agente não
consegue construir um `PromptSegment` mudo.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    CameraAngle,
    CameraMovement,
    CharacterId,
    ContinuityReference,
    Duration,
    EmotionalTone,
    FrameRate,
    Language,
    LocationId,
    MixLevel,
    NarrativeFunction,
    ProductionVariant,
    Resolution,
    SceneId,
    SegmentId,
    SequenceId,
    ShotType,
    SourceReference,
    TimeRange,
    Timecode,
    TransitionType,
)
from pedroarte_youtube_engine.shared.text import count_words, speakable_duration_seconds

# ---------------------------------------------------------------------------
# Vídeo
# ---------------------------------------------------------------------------


class CameraPlan(DomainEntity):
    """Direção de câmera de um segmento."""

    shot_type: ShotType
    angle: CameraAngle
    lens: str = Field(min_length=2, max_length=64)
    height: str = Field(default="altura do peito", max_length=120)
    distance: str = Field(default="média", max_length=120)
    movement: CameraMovement
    movement_speed: str = Field(default="lenta e contínua", max_length=120)
    focus: str = Field(min_length=2, max_length=200)
    depth_of_field: str = Field(min_length=2, max_length=200)

    def descriptor(self) -> str:
        return (
            f"{self.shot_type.value}, ângulo {self.angle.value}, lente {self.lens}, "
            f"altura {self.height}, distância {self.distance}, "
            f"movimento {self.movement.value} ({self.movement_speed}), "
            f"foco {self.focus}, profundidade {self.depth_of_field}"
        )


class CharacterPresence(DomainEntity):
    """Presença de um personagem no segmento, com tudo que a imagem precisa fixar."""

    character_id: CharacterId
    display_name: str = Field(min_length=1, max_length=160)
    appearance_anchor: str = Field(min_length=10, max_length=1200)
    wardrobe: str = Field(min_length=2, max_length=600)
    wardrobe_condition: str = Field(default="íntegro", max_length=200)
    expression: str = Field(min_length=2, max_length=300)
    posture: str = Field(min_length=2, max_length=300)
    blocking: str = Field(min_length=2, max_length=400)
    hands_occupied_with: str = Field(default="mãos livres", max_length=200)
    gaze_direction: str = Field(default="para o interlocutor", max_length=160)
    visible_injuries: tuple[str, ...] = Field(default_factory=tuple)

    def descriptor(self) -> str:
        injuries = ", ".join(self.visible_injuries) or "nenhum ferimento visível"
        return (
            f"{self.display_name} — {self.appearance_anchor}. "
            f"Figurino: {self.wardrobe} ({self.wardrobe_condition}). "
            f"Expressão: {self.expression}. Postura: {self.posture}. "
            f"Ação/posição: {self.blocking}. Mãos: {self.hands_occupied_with}. "
            f"Olhar: {self.gaze_direction}. Ferimentos: {injuries}."
        )


class VideoPlan(DomainEntity):
    """A seção visual completa. Nenhum campo obrigatório aceita placeholder."""

    initial_frame: str = Field(min_length=10, max_length=1200)
    final_frame: str = Field(min_length=10, max_length=1200)
    setting: str = Field(min_length=10, max_length=1200)
    location_id: LocationId | None = None
    characters: tuple[CharacterPresence, ...] = Field(default_factory=tuple)
    action: str = Field(min_length=10, max_length=2000)
    performance: str = Field(min_length=10, max_length=2000)
    relevant_props: tuple[str, ...] = Field(default_factory=tuple)
    time_of_day: str = Field(min_length=2, max_length=64)
    weather: str = Field(min_length=2, max_length=120)
    lighting: str = Field(min_length=5, max_length=800)
    composition: str = Field(min_length=5, max_length=800)
    camera: CameraPlan
    visual_rhythm: str = Field(min_length=3, max_length=400)
    transition_in: TransitionType = TransitionType.CUT
    transition_out: TransitionType = TransitionType.CUT
    negative_constraints: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_placeholders(self) -> Self:
        _assert_no_placeholder(self.action, "video.action")
        _assert_no_placeholder(self.setting, "video.setting")
        _assert_no_placeholder(self.initial_frame, "video.initial_frame")
        _assert_no_placeholder(self.final_frame, "video.final_frame")
        if self.initial_frame.strip() == self.final_frame.strip():
            raise ValueError(
                "O quadro inicial e o quadro final não podem ser idênticos: "
                "todo segmento precisa registrar uma mudança."
            )
        return self


# ---------------------------------------------------------------------------
# Áudio
# ---------------------------------------------------------------------------


class VocalDecision(StrEnum):
    """As decisões vocais aceitas quando não há palavras faladas (seção 3.1).

    A ausência de fala é sempre uma escolha declarada, nunca um esquecimento.
    """

    DIALOGUE = "dialogo"
    NARRATION = "narracao"
    BREATHING = "respiracao"
    MURMUR = "murmurio"
    VOCAL_REACTION = "reacao_vocal"
    CRYING = "choro"
    LAUGHTER = "riso"
    DISTANT_SCREAM = "grito_distante"
    VOCALIZATION = "vocalizacao"
    INTENTIONAL_SILENCE = "silencio_vocal_intencional"

    @property
    def has_words(self) -> bool:
        return self in {VocalDecision.DIALOGUE, VocalDecision.NARRATION}


class VoicePlanEntry(DomainEntity):
    """Uma decisão vocal posicionada no tempo."""

    decision: VocalDecision
    voice_id: str = Field(min_length=3, max_length=80)
    character_id: CharacterId | None = None
    description: str = Field(min_length=3, max_length=600)
    justification: str = Field(default="", max_length=600)
    range: TimeRange
    intensity: str = Field(default="média", max_length=64)

    @model_validator(mode="after")
    def _require_justified_silence(self) -> Self:
        if self.decision is VocalDecision.INTENTIONAL_SILENCE and not self.justification.strip():
            raise ValueError(
                "Silêncio vocal intencional exige justificativa narrativa explícita."
            )
        return self


class SpokenLine(DomainEntity):
    """Base de diálogo e narração: texto falado com direção de interpretação."""

    voice_id: str = Field(min_length=3, max_length=80)
    text: str = Field(min_length=1, max_length=1200)
    language: Language
    intention: str = Field(min_length=2, max_length=300)
    emotion: EmotionalTone = EmotionalTone.NEUTRAL
    pace: str = Field(default="medido", max_length=64)
    pauses: str = Field(default="pausa curta antes da última oração", max_length=300)
    breathing: str = Field(default="respiração contida antes de falar", max_length=300)
    range: TimeRange

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    @property
    def estimated_speech_seconds(self) -> float:
        return speakable_duration_seconds(self.text)

    @property
    def fits_in_range(self) -> bool:
        """A fala cabe na janela reservada, com 15% de folga para respiração."""
        return self.estimated_speech_seconds <= self.range.duration.seconds * 1.15


class DialogueLine(SpokenLine):
    """Fala de um personagem em cena."""

    character_id: CharacterId
    speaker_name: str = Field(min_length=1, max_length=160)
    overlaps_previous: bool = False
    lip_sync_note: str = Field(default="sincronia labial natural", max_length=300)


class NarrationLine(SpokenLine):
    """Narração fora de quadro."""

    narrator_name: str = Field(default="Narrador", max_length=160)
    rhythm: str = Field(default="constante, sem pressa", max_length=200)


class AmbientSound(DomainEntity):
    """Som persistente do local."""

    description: str = Field(min_length=3, max_length=400)
    source: str = Field(default="difuso", max_length=200)
    spatiality: str = Field(default="estéreo amplo, ao fundo", max_length=200)
    continuous: bool = True
    relative_db: float = Field(default=-22.0, ge=-60.0, le=0.0)


class SoundEffect(DomainEntity):
    """Efeito pontual sincronizado a uma ação."""

    description: str = Field(min_length=3, max_length=400)
    at: Timecode
    duration: Duration
    synced_to_action: str = Field(min_length=3, max_length=400)
    spatiality: str = Field(default="centro", max_length=200)
    relative_db: float = Field(default=-12.0, ge=-60.0, le=6.0)
    off_screen: bool = False


class MusicCue(DomainEntity):
    """Presença musical no segmento."""

    enabled: bool = True
    theme_id: str | None = None
    description: str = Field(default="", max_length=800)
    function: str = Field(default="", max_length=400)
    instrumentation: tuple[str, ...] = Field(default_factory=tuple)
    tempo: str = Field(default="", max_length=64)
    intensity_start: str = Field(default="", max_length=64)
    intensity_end: str = Field(default="", max_length=64)
    entry_timecode: Timecode | None = None
    exit_timecode: Timecode | None = None
    relationship_to_dialogue: str = Field(
        default="recua 6 dB sob a fala", max_length=300
    )

    @model_validator(mode="after")
    def _validate_enabled_cue(self) -> Self:
        if self.enabled and not self.description.strip():
            raise ValueError("Uma entrada musical habilitada precisa de descrição.")
        if (
            self.entry_timecode is not None
            and self.exit_timecode is not None
            and self.exit_timecode <= self.entry_timecode
        ):
            raise ValueError("A saída da música deve ocorrer depois da entrada.")
        return self


class SilenceBeat(DomainEntity):
    """Silêncio deliberado, com função dramática declarada."""

    range: TimeRange
    kind: str = Field(default="suspensão", max_length=64)
    justification: str = Field(min_length=3, max_length=400)


class SyncCue(DomainEntity):
    """Amarra uma ação visual a um evento sonoro por timecode."""

    at: Timecode
    visual_action: str = Field(min_length=3, max_length=400)
    audio_event: str = Field(min_length=3, max_length=400)


class AudioPlan(DomainEntity):
    """A seção sonora completa. Sem ela não existe segmento."""

    voice_plan: tuple[VoicePlanEntry, ...] = Field(min_length=1)
    dialogue: tuple[DialogueLine, ...] = Field(default_factory=tuple)
    narration: tuple[NarrationLine, ...] = Field(default_factory=tuple)
    ambient_sound: tuple[AmbientSound, ...] = Field(min_length=1)
    sound_effects: tuple[SoundEffect, ...] = Field(default_factory=tuple)
    music: MusicCue
    silence: tuple[SilenceBeat, ...] = Field(default_factory=tuple)
    mixing_notes: tuple[MixLevel, ...] = Field(min_length=1)
    synchronization_cues: tuple[SyncCue, ...] = Field(default_factory=tuple)
    audio_transition_out: str = Field(min_length=3, max_length=400)

    @model_validator(mode="after")
    def _validate_voice_coverage(self) -> Self:
        """Se o plano vocal promete palavras, as palavras têm de existir."""
        promises_words = any(entry.decision.has_words for entry in self.voice_plan)
        has_words = bool(self.dialogue or self.narration)
        if promises_words and not has_words:
            raise ValueError(
                "O voice_plan declara diálogo ou narração, mas nenhuma linha falada foi fornecida."
            )
        if has_words and not promises_words:
            raise ValueError(
                "Há linhas faladas sem a decisão vocal correspondente no voice_plan."
            )
        return self

    @property
    def spoken_word_count(self) -> int:
        return sum(line.word_count for line in (*self.dialogue, *self.narration))

    @property
    def has_spoken_words(self) -> bool:
        return bool(self.dialogue or self.narration)

    def all_spoken_lines(self) -> tuple[SpokenLine, ...]:
        return (*self.dialogue, *self.narration)


# ---------------------------------------------------------------------------
# Legendas, continuidade e narrativa
# ---------------------------------------------------------------------------


class SubtitleCue(DomainEntity):
    """Legenda com identificação de falante, exigida pela acessibilidade."""

    index: int = Field(ge=1)
    range: TimeRange
    speaker: str = Field(default="", max_length=160)
    text: str = Field(min_length=1, max_length=400)
    sound_description: str = Field(default="", max_length=200)

    def to_srt(self) -> str:
        prefix = f"[{self.speaker}] " if self.speaker else ""
        suffix = f" ({self.sound_description})" if self.sound_description else ""
        return (
            f"{self.index}\n"
            f"{self.range.start.srt()} --> {self.range.end.srt()}\n"
            f"{prefix}{self.text}{suffix}\n"
        )

    def to_vtt(self) -> str:
        prefix = f"<v {self.speaker}>" if self.speaker else ""
        suffix = f" ({self.sound_description})" if self.sound_description else ""
        return (
            f"{self.range.start.vtt()} --> {self.range.end.vtt()}\n"
            f"{prefix}{self.text}{suffix}\n"
        )


class ContinuitySnapshot(DomainEntity):
    """Estado narrativo e físico em um instante (o `Continuity Ledger`, seção 16).

    O segmento seguinte recebe este objeto como entrada. O motor nunca confia na
    memória do modelo para saber onde o personagem estava ou o que ele segurava.
    """

    time_of_day: str = Field(default="indefinido", max_length=64)
    weather: str = Field(default="indefinido", max_length=120)
    location_id: LocationId | None = None
    character_positions: dict[str, str] = Field(default_factory=dict)
    movement_directions: dict[str, str] = Field(default_factory=dict)
    hands_occupied: dict[str, str] = Field(default_factory=dict)
    wardrobe: dict[str, str] = Field(default_factory=dict)
    wardrobe_condition: dict[str, str] = Field(default_factory=dict)
    injuries: dict[str, str] = Field(default_factory=dict)
    hair_state: dict[str, str] = Field(default_factory=dict)
    emotions: dict[str, str] = Field(default_factory=dict)
    knowledge_acquired: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    relationship_changes: tuple[str, ...] = Field(default_factory=tuple)
    props_on_scene: tuple[str, ...] = Field(default_factory=tuple)
    doors_open: tuple[str, ...] = Field(default_factory=tuple)
    vehicles: tuple[str, ...] = Field(default_factory=tuple)
    damage: tuple[str, ...] = Field(default_factory=tuple)
    lighting_state: str = Field(default="", max_length=300)
    music_intensity: str = Field(default="silêncio", max_length=64)
    persistent_sounds: tuple[str, ...] = Field(default_factory=tuple)
    last_spoken_words: str = Field(default="", max_length=400)
    final_frame_description: str = Field(default="", max_length=800)
    narrative_state: str = Field(default="", max_length=800)

    def merged_with(self, updates: "ContinuitySnapshot") -> "ContinuitySnapshot":
        """Aplica um delta preservando o que o delta não menciona."""
        base = self.model_dump()
        incoming = updates.model_dump(exclude_defaults=True)
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merged = dict(base[key])
                merged.update(value)
                base[key] = merged
            else:
                base[key] = value
        return ContinuitySnapshot.model_validate(base)


class SegmentNarrative(DomainEntity):
    """A função dramática do segmento. Sem ela, o segmento não se justifica."""

    purpose: str = Field(min_length=10, max_length=800)
    beat: str = Field(min_length=3, max_length=400)
    function: NarrativeFunction
    emotional_start: EmotionalTone
    emotional_end: EmotionalTone
    information_revealed: tuple[str, ...] = Field(default_factory=tuple)
    information_withheld: tuple[str, ...] = Field(default_factory=tuple)
    tension: int = Field(default=0, ge=0, le=10)


class SegmentFormat(DomainEntity):
    """Formato pretendido de exibição."""

    aspect_ratio: AspectRatio
    resolution: Resolution
    frame_rate: FrameRate

    def descriptor(self) -> str:
        return f"{self.aspect_ratio} · {self.resolution} · {self.frame_rate}"


class SegmentDuration(DomainEntity):
    """Duração narrativa e duração aceita pelo provedor (seção 4).

    O domínio nunca se acopla ao limite de uma API: `target` é a verdade
    narrativa; `provider` é uma consequência da compilação.
    """

    target: Duration
    provider: Duration | None = None
    provider_call_count: int = Field(default=1, ge=1)
    recompilation_strategy: str = Field(default="", max_length=200)

    @property
    def target_seconds(self) -> float:
        return self.target.seconds

    @property
    def provider_seconds(self) -> float | None:
        return self.provider.seconds if self.provider else None


class SegmentValidationFlags(DomainEntity):
    """Resultado consolidado dos gates para este segmento."""

    audio_complete: bool = False
    video_complete: bool = False
    canon_valid: bool = False
    continuity_valid: bool = False
    duration_valid: bool = False
    approved: bool = False

    def all_green(self) -> bool:
        return all(
            (
                self.audio_complete,
                self.video_complete,
                self.canon_valid,
                self.continuity_valid,
                self.duration_valid,
            )
        )

    def approve(self) -> "SegmentValidationFlags":
        return self.model_copy(update={"approved": self.all_green()})


class ProviderCompilation(DomainEntity):
    """Registro de como o segmento foi traduzido para um provedor concreto."""

    provider: str = Field(default="generic", max_length=64)
    model: str = Field(default="", max_length=128)
    calls: int = Field(default=1, ge=1)
    strategy: str = Field(default="direto", max_length=200)
    compiled_prompt: str = Field(default="", max_length=20000)
    negative_prompt: str = Field(default="", max_length=4000)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    notes: tuple[str, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# O segmento
# ---------------------------------------------------------------------------


class PromptSegment(DomainEntity):
    """A unidade de produção do motor: 10 segundos de vídeo vivo.

    Corresponde ao schema conceitual da seção 14 da especificação.
    """

    segment_id: SegmentId
    project_id: str = Field(min_length=1, max_length=128)
    production_variant: ProductionVariant
    episode_id: str | None = None
    sequence_id: SequenceId
    scene_id: SceneId
    segment_number: int = Field(ge=1)
    range: TimeRange
    duration: SegmentDuration
    segment_format: SegmentFormat
    narrative: SegmentNarrative
    continuity_reference: ContinuityReference
    continuity_in: ContinuitySnapshot
    continuity_out: ContinuitySnapshot
    video: VideoPlan
    audio: AudioPlan
    subtitles: tuple[SubtitleCue, ...] = Field(default_factory=tuple)
    source_references: tuple[SourceReference, ...] = Field(default_factory=tuple)
    provider_compilation: ProviderCompilation | None = None
    validation: SegmentValidationFlags = Field(default_factory=SegmentValidationFlags)

    @model_validator(mode="after")
    def _validate_time_consistency(self) -> Self:
        """A duração declarada tem de bater com o intervalo de timecodes."""
        declared = self.duration.target.milliseconds
        measured = self.range.duration.milliseconds
        if declared != measured:
            raise ValueError(
                f"Duração alvo ({declared} ms) diverge do intervalo de timecode ({measured} ms)."
            )
        for entry in self.audio.voice_plan:
            if not _within(entry.range, self.range):
                raise ValueError(
                    f"Entrada de voice_plan fora do intervalo do segmento: {entry.range}."
                )
        for line in self.audio.all_spoken_lines():
            if not _within(line.range, self.range):
                raise ValueError(f"Linha falada fora do intervalo do segmento: {line.range}.")
        for effect in self.audio.sound_effects:
            if not self.range.contains(effect.at):
                raise ValueError(f"Efeito sonoro fora do intervalo do segmento: {effect.at}.")
        return self

    @property
    def timecode_start(self) -> Timecode:
        return self.range.start

    @property
    def timecode_end(self) -> Timecode:
        return self.range.end

    @property
    def present_character_ids(self) -> tuple[CharacterId, ...]:
        return tuple(presence.character_id for presence in self.video.characters)

    def with_validation(self, flags: SegmentValidationFlags) -> "PromptSegment":
        return self.model_copy(update={"validation": flags})

    def with_provider_compilation(self, compilation: ProviderCompilation) -> "PromptSegment":
        return self.model_copy(
            update={
                "provider_compilation": compilation,
                "duration": self.duration.model_copy(
                    update={
                        "provider_call_count": compilation.calls,
                        "recompilation_strategy": compilation.strategy,
                    }
                ),
            }
        )


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

_PLACEHOLDER_TOKENS = (
    "tbd",
    "todo",
    "lorem ipsum",
    "placeholder",
    "preencher",
    "a definir",
    "xxx",
    "<insira",
    "{{",
    "n/a",
)


def _assert_no_placeholder(text: str, field_name: str) -> None:
    lowered = text.lower()
    for token in _PLACEHOLDER_TOKENS:
        if token in lowered:
            raise ValueError(
                f"Campo {field_name} contém placeholder proibido ({token!r}). "
                "Prompts precisam ser autossuficientes para o gerador externo."
            )


def _within(inner: TimeRange, outer: TimeRange) -> bool:
    return (
        inner.start.milliseconds >= outer.start.milliseconds
        and inner.end.milliseconds <= outer.end.milliseconds
    )
