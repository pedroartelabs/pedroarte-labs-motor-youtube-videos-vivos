"""Value Objects imutáveis do domínio audiovisual.

Todos são congelados (`frozen=True`) e comparados por valor. Cada um carrega as
invariantes que o motor precisa garantir *antes* de qualquer agente escrever um
prompt — timecodes não retrocedem, durações não são negativas, proporções são
reconhecíveis por um provedor, uma voz sempre tem idioma.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pedroarte_youtube_engine.shared.hashing import stable_short_id
from pedroarte_youtube_engine.shared.text import safe_slug

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class ValueObject(BaseModel):
    """Base de todos os value objects: imutável, estrito e comparável por valor."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_\-.]{0,126}[a-z0-9]$")


class Identifier(ValueObject):
    """Identificador textual estável, seguro para nome de arquivo e para URL."""

    value: str = Field(min_length=2, max_length=128)

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _IDENTIFIER_RE.match(normalized):
            raise ValueError(
                f"Identificador inválido: {value!r}. "
                "Use apenas minúsculas, dígitos, '-', '_' e '.', com 2 a 128 caracteres."
            )
        return normalized

    def __str__(self) -> str:
        return self.value


class ProjectId(Identifier):
    """Identifica um projeto de adaptação. Derivado do slug da obra."""

    @classmethod
    def from_title(cls, title: str) -> Self:
        return cls(value=safe_slug(title))


class CharacterId(Identifier):
    @classmethod
    def from_name(cls, name: str) -> Self:
        return cls(value=f"character_{safe_slug(name, max_length=100)}")


class LocationId(Identifier):
    @classmethod
    def from_name(cls, name: str) -> Self:
        return cls(value=f"location_{safe_slug(name, max_length=100)}")


class PropId(Identifier):
    @classmethod
    def from_name(cls, name: str) -> Self:
        return cls(value=f"prop_{safe_slug(name, max_length=100)}")


class SourceId(Identifier):
    """Identifica um documento de entrada."""


class ChunkId(Identifier):
    """Identifica um trecho indexado pelo RAG."""


class EpisodeId(Identifier):
    """Identifica um episódio publicável."""


class SequenceId(Identifier):
    """Identifica uma sequência dramática dentro de um episódio."""


class SceneId(Identifier):
    """Identifica uma cena — unidade contínua de espaço, tempo e ação."""


class ShotId(Identifier):
    """Identifica um plano dentro de uma cena."""


class SegmentId(Identifier):
    """Identifica um segmento narrativo temporizado (a unidade de prompt)."""


class RunId(ValueObject):
    """Identifica uma execução do motor.

    Formato: `<timestamp ISO 8601 sem dois-pontos>_<sufixo curto>`, por exemplo
    `2026-08-06T003700-03-00_a81f2c`. Duas execuções nunca colidem, e o nome
    ordena cronologicamente quando listado.
    """

    value: str = Field(min_length=8, max_length=64)

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if not re.match(r"^[0-9TZ:+\-.]{8,48}_[a-f0-9]{4,32}$", value):
            raise ValueError(f"run_id inválido: {value!r}")
        return value

    @classmethod
    def create(cls, *, timestamp_iso: str, seed: str) -> Self:
        stamp = timestamp_iso.replace(":", "").replace(" ", "T")
        return cls(value=f"{stamp}_{stable_short_id(timestamp_iso, seed)}")

    def __str__(self) -> str:
        return self.value


class ContentHash(ValueObject):
    """Hash de conteúdo, sempre prefixado pelo algoritmo."""

    value: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    def __str__(self) -> str:
        return self.value

    @property
    def short(self) -> str:
        return self.value.split(":", 1)[1][:12]


# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------

_TIMECODE_RE = re.compile(r"^(?P<h>\d{2,3}):(?P<m>[0-5]\d):(?P<s>[0-5]\d)\.(?P<ms>\d{3})$")


class Timecode(ValueObject):
    """Posição temporal `HH:MM:SS.mmm` dentro de uma produção.

    A precisão interna é de milissegundos inteiros: usar float aqui produziria
    somas que não fecham exatamente na duração alvo, e a especificação exige que
    o vídeo principal tenha *exatamente* a duração configurada.
    """

    milliseconds: int = Field(ge=0)

    @classmethod
    def zero(cls) -> Self:
        return cls(milliseconds=0)

    @classmethod
    def from_seconds(cls, seconds: float) -> Self:
        if seconds < 0:
            raise ValueError("Timecode não pode ser negativo.")
        return cls(milliseconds=int(round(seconds * 1000)))

    @classmethod
    def parse(cls, text: str) -> Self:
        match = _TIMECODE_RE.match(text.strip())
        if not match:
            raise ValueError(f"Timecode inválido: {text!r}. Formato esperado HH:MM:SS.mmm")
        hours = int(match.group("h"))
        minutes = int(match.group("m"))
        seconds = int(match.group("s"))
        millis = int(match.group("ms"))
        return cls(milliseconds=((hours * 3600 + minutes * 60 + seconds) * 1000) + millis)

    @property
    def seconds(self) -> float:
        return self.milliseconds / 1000.0

    def formatted(self) -> str:
        total, millis = divmod(self.milliseconds, 1000)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    def srt(self) -> str:
        """Formato exigido pelo SubRip: vírgula no separador de milissegundos."""
        return self.formatted().replace(".", ",")

    def vtt(self) -> str:
        """WebVTT usa ponto, igual à representação canônica."""
        return self.formatted()

    def plus(self, duration: "Duration") -> "Timecode":
        return Timecode(milliseconds=self.milliseconds + duration.milliseconds)

    def minus(self, other: "Timecode") -> "Duration":
        delta = self.milliseconds - other.milliseconds
        if delta < 0:
            raise ValueError("Subtração de timecodes produziria duração negativa.")
        return Duration(milliseconds=delta)

    def __lt__(self, other: "Timecode") -> bool:
        return self.milliseconds < other.milliseconds

    def __le__(self, other: "Timecode") -> bool:
        return self.milliseconds <= other.milliseconds

    def __gt__(self, other: "Timecode") -> bool:
        return self.milliseconds > other.milliseconds

    def __ge__(self, other: "Timecode") -> bool:
        return self.milliseconds >= other.milliseconds

    def __str__(self) -> str:
        return self.formatted()


class Duration(ValueObject):
    """Intervalo de tempo não negativo, em milissegundos inteiros."""

    milliseconds: int = Field(ge=0)

    @classmethod
    def from_seconds(cls, seconds: float) -> Self:
        if seconds < 0:
            raise ValueError("Duração não pode ser negativa.")
        return cls(milliseconds=int(round(seconds * 1000)))

    @classmethod
    def from_minutes(cls, minutes: float) -> Self:
        return cls.from_seconds(minutes * 60.0)

    @property
    def seconds(self) -> float:
        return self.milliseconds / 1000.0

    @property
    def minutes(self) -> float:
        return self.milliseconds / 60_000.0

    def plus(self, other: "Duration") -> "Duration":
        return Duration(milliseconds=self.milliseconds + other.milliseconds)

    def times(self, factor: int) -> "Duration":
        if factor < 0:
            raise ValueError("Fator não pode ser negativo.")
        return Duration(milliseconds=self.milliseconds * factor)

    def human(self) -> str:
        total_seconds = self.milliseconds / 1000.0
        if total_seconds < 60:
            return f"{total_seconds:.1f}s"
        minutes, seconds = divmod(int(total_seconds), 60)
        return f"{minutes}min {seconds:02d}s"

    def __lt__(self, other: "Duration") -> bool:
        return self.milliseconds < other.milliseconds

    def __le__(self, other: "Duration") -> bool:
        return self.milliseconds <= other.milliseconds

    def __gt__(self, other: "Duration") -> bool:
        return self.milliseconds > other.milliseconds

    def __ge__(self, other: "Duration") -> bool:
        return self.milliseconds >= other.milliseconds

    def __str__(self) -> str:
        return self.human()


class TimeRange(ValueObject):
    """Intervalo `[start, end)` com invariante de ordem."""

    start: Timecode
    end: Timecode

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if self.end.milliseconds <= self.start.milliseconds:
            raise ValueError(
                f"Intervalo inválido: fim ({self.end}) deve ser maior que início ({self.start})."
            )
        return self

    @classmethod
    def of(cls, start: Timecode, duration: Duration) -> Self:
        return cls(start=start, end=start.plus(duration))

    @property
    def duration(self) -> Duration:
        return self.end.minus(self.start)

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start.milliseconds < other.end.milliseconds and (
            other.start.milliseconds < self.end.milliseconds
        )

    def contains(self, moment: Timecode) -> bool:
        return self.start.milliseconds <= moment.milliseconds < self.end.milliseconds

    def __str__(self) -> str:
        return f"{self.start} → {self.end}"


# ---------------------------------------------------------------------------
# Formato de imagem
# ---------------------------------------------------------------------------


class AspectRatio(ValueObject):
    """Proporção de tela, como `16:9` ou `9:16`."""

    width: int = Field(gt=0, le=1000)
    height: int = Field(gt=0, le=1000)

    @classmethod
    def parse(cls, text: str) -> Self:
        parts = text.strip().replace("x", ":").split(":")
        if len(parts) != 2:
            raise ValueError(f"Proporção inválida: {text!r}. Formato esperado L:A, ex.: 16:9")
        try:
            return cls(width=int(parts[0]), height=int(parts[1]))
        except ValueError as exc:
            raise ValueError(f"Proporção inválida: {text!r}") from exc

    @classmethod
    def landscape(cls) -> Self:
        return cls(width=16, height=9)

    @classmethod
    def vertical(cls) -> Self:
        return cls(width=9, height=16)

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    @property
    def is_square(self) -> bool:
        return self.height == self.width

    @property
    def ratio(self) -> float:
        return self.width / self.height

    def __str__(self) -> str:
        return f"{self.width}:{self.height}"


_RESOLUTION_LABELS: dict[str, tuple[int, int]] = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2160p": (3840, 2160),
    "4k": (3840, 2160),
}


class Resolution(ValueObject):
    """Resolução pretendida, expressa por rótulo e por pixels."""

    label: str = Field(min_length=2, max_length=8)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @classmethod
    def parse(cls, text: str) -> Self:
        key = text.strip().lower()
        if key in _RESOLUTION_LABELS:
            width, height = _RESOLUTION_LABELS[key]
            return cls(label=key if key != "4k" else "2160p", width=width, height=height)
        raise ValueError(
            f"Resolução desconhecida: {text!r}. Use uma de {sorted(_RESOLUTION_LABELS)}."
        )

    def oriented(self, aspect: AspectRatio) -> "Resolution":
        """Reorienta a resolução para a proporção pedida.

        Um Short 9:16 em 1080p mede 1080x1920, não 1920x1080.
        """
        long_side = max(self.width, self.height)
        short_side = min(self.width, self.height)
        if aspect.is_vertical:
            return Resolution(label=self.label, width=short_side, height=long_side)
        if aspect.is_square:
            return Resolution(label=self.label, width=short_side, height=short_side)
        return Resolution(label=self.label, width=long_side, height=short_side)

    def __str__(self) -> str:
        return f"{self.label} ({self.width}x{self.height})"


class FrameRate(ValueObject):
    """Taxa de quadros por segundo."""

    fps: int = Field(ge=12, le=120)

    def __str__(self) -> str:
        return f"{self.fps}fps"


# ---------------------------------------------------------------------------
# Idioma e voz
# ---------------------------------------------------------------------------

_LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class Language(ValueObject):
    """Tag de idioma BCP-47 simplificada, como `pt-BR`."""

    tag: str = Field(min_length=2, max_length=5)

    @field_validator("tag")
    @classmethod
    def _validate(cls, value: str) -> str:
        normalized = value.strip()
        if "-" in normalized:
            base, region = normalized.split("-", 1)
            normalized = f"{base.lower()}-{region.upper()}"
        else:
            normalized = normalized.lower()
        if not _LANGUAGE_RE.match(normalized):
            raise ValueError(f"Idioma inválido: {value!r}. Use algo como 'pt-BR' ou 'en'.")
        return normalized

    @classmethod
    def brazilian_portuguese(cls) -> Self:
        return cls(tag="pt-BR")

    @property
    def base(self) -> str:
        return self.tag.split("-")[0]

    def __str__(self) -> str:
        return self.tag


class VoiceIdentity(ValueObject):
    """Identidade vocal reutilizável entre segmentos e episódios.

    É o que impede um mesmo personagem de "trocar de voz" entre o segmento 12 e
    o segmento 13: o motor referencia sempre o mesmo `voice_id`.
    """

    voice_id: str = Field(min_length=3, max_length=80)
    language: Language
    apparent_age_range: str = Field(min_length=1, max_length=32)
    pitch: str = Field(min_length=2, max_length=48)
    texture: str = Field(min_length=2, max_length=120)
    accent_region: str = Field(default="neutro", max_length=64)
    pace: str = Field(default="medido", max_length=48)
    articulation: str = Field(default="precisa", max_length=48)
    breathing: str = Field(default="contida", max_length=48)

    @field_validator("voice_id")
    @classmethod
    def _validate_voice_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.match(r"^voice_[a-z0-9_]+$", normalized):
            raise ValueError(
                f"voice_id inválido: {value!r}. Use o padrão 'voice_<nome>_<idioma>_v<n>'."
            )
        return normalized

    def __str__(self) -> str:
        return self.voice_id


# ---------------------------------------------------------------------------
# Vocabulário cinematográfico
# ---------------------------------------------------------------------------


class ShotType(StrEnum):
    """Tipos de plano. Os nomes seguem a nomenclatura usada em set no Brasil."""

    EXTREME_WIDE = "plano_geral_extremo"
    WIDE = "plano_geral"
    FULL = "plano_inteiro"
    MEDIUM_FULL = "plano_americano"
    MEDIUM = "plano_medio"
    MEDIUM_CLOSE = "plano_proximo"
    CLOSE_UP = "primeiro_plano"
    EXTREME_CLOSE_UP = "primeirissimo_plano"
    INSERT = "inserto"
    OVER_THE_SHOULDER = "over_the_shoulder"
    POV = "ponto_de_vista"
    TWO_SHOT = "plano_duplo"


class CameraAngle(StrEnum):
    EYE_LEVEL = "altura_do_olhar"
    LOW = "contra_plongee"
    HIGH = "plongee"
    DUTCH = "camera_inclinada"
    OVERHEAD = "zenital"
    GROUND = "rasante"


class CameraMovement(StrEnum):
    STATIC = "estatica"
    PAN = "panoramica"
    TILT = "tilt"
    DOLLY_IN = "travelling_de_aproximacao"
    DOLLY_OUT = "travelling_de_afastamento"
    TRACKING = "travelling_lateral"
    CRANE = "grua"
    HANDHELD = "camera_na_mao"
    STEADICAM = "steadicam"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    ORBIT = "orbital"
    PUSH_THROUGH = "atravessamento"


class TransitionType(StrEnum):
    CUT = "corte_seco"
    MATCH_CUT = "corte_de_correspondencia"
    DISSOLVE = "dissolucao"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    FADE_TO_BLACK = "fade_para_preto"
    WHIP_PAN = "chicote"
    SOUND_BRIDGE = "ponte_sonora"
    J_CUT = "corte_em_j"
    L_CUT = "corte_em_l"


class EmotionalTone(StrEnum):
    """Paleta emocional usada por narrativa, atuação e mixagem."""

    NEUTRAL = "neutro"
    CALM = "sereno"
    TENSE = "tenso"
    FEARFUL = "amedrontado"
    MELANCHOLIC = "melancolico"
    HOPEFUL = "esperancoso"
    ANGRY = "irado"
    TENDER = "terno"
    SUSPICIOUS = "desconfiado"
    DETERMINED = "determinado"
    GRIEVING = "enlutado"
    AWED = "maravilhado"
    OMINOUS = "sombrio"
    RELIEVED = "aliviado"
    BITTER = "amargo"


class NarrativeFunction(StrEnum):
    """Função dramática de um segmento. Nenhum segmento pode existir sem uma."""

    HOOK = "gancho"
    SETUP = "apresentacao"
    INCITING_INCIDENT = "incidente_incitante"
    RISING_ACTION = "escalada"
    COMPLICATION = "complicacao"
    CONFRONTATION = "confronto"
    REVELATION = "revelacao"
    REVERSAL = "virada"
    CLIMAX = "climax"
    FALLING_ACTION = "consequencia"
    RESOLUTION = "resolucao"
    BREATHING = "respiro"
    TRANSITION = "transicao"
    CLIFFHANGER = "cliffhanger"
    EPILOGUE = "epilogo"
    CALL_TO_ACTION = "chamada"


class ProductionVariant(StrEnum):
    """Os seis produtos audiovisuais suportados pelo motor."""

    MAIN_10_MINUTES = "youtube_video_principal_10_minutos"
    SHORTS = "youtube_video_shorts"
    LONG_FORM = "youtube_video_mais_de_30_minutos_longa"
    SERIES = "youtube_serie"
    MINI_NOVELA = "youtube_mini_novela"
    TRAILERS = "youtube_trailers"

    @property
    def directory(self) -> str:
        return self.value


class Severity(StrEnum):
    """Gravidade de um problema de validação."""

    INFO = "info"
    WARNING = "advertencia"
    ERROR = "erro"
    CRITICAL = "critico"

    @property
    def blocks_approval(self) -> bool:
        return self in {Severity.ERROR, Severity.CRITICAL}


# ---------------------------------------------------------------------------
# Proveniência e confiança
# ---------------------------------------------------------------------------


class ConfidenceScore(ValueObject):
    """Confiança de uma afirmação canônica, entre 0 e 1."""

    value: Annotated[float, Field(ge=0.0, le=1.0)]

    @classmethod
    def certain(cls) -> Self:
        return cls(value=1.0)

    @classmethod
    def high(cls) -> Self:
        return cls(value=0.85)

    @classmethod
    def medium(cls) -> Self:
        return cls(value=0.6)

    @classmethod
    def low(cls) -> Self:
        return cls(value=0.35)

    @property
    def is_uncertain(self) -> bool:
        return self.value < 0.5

    def __str__(self) -> str:
        return f"{self.value:.2f}"


class SourceReference(ValueObject):
    """Aponta uma afirmação de volta para o texto que a sustenta.

    A especificação exige que nenhum output saia sem proveniência; este value
    object é o mecanismo que torna a exigência verificável.
    """

    source_id: SourceId
    source_path: str = Field(min_length=1, max_length=512)
    chapter: str | None = None
    chunk_id: ChunkId | None = None
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)
    excerpt: str = Field(default="", max_length=400)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore.medium)

    @model_validator(mode="after")
    def _validate_offsets(self) -> Self:
        if self.end_offset and self.end_offset < self.start_offset:
            raise ValueError("end_offset não pode preceder start_offset.")
        return self

    def citation(self) -> str:
        parts = [self.source_path]
        if self.chapter:
            parts.append(self.chapter)
        if self.chunk_id:
            parts.append(str(self.chunk_id))
        return " › ".join(parts)


class ContinuityReference(ValueObject):
    """Liga um segmento ao estado herdado do segmento anterior."""

    previous_segment_id: SegmentId | None = None
    next_segment_id: SegmentId | None = None
    state_hash: ContentHash | None = None

    @property
    def is_opening(self) -> bool:
        return self.previous_segment_id is None


# ---------------------------------------------------------------------------
# Provedores
# ---------------------------------------------------------------------------


class ProviderName(ValueObject):
    """Nome de um provedor de mídia. `generic` é o alvo neutro padrão."""

    value: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_\-]*$")

    @classmethod
    def generic(cls) -> Self:
        return cls(value="generic")

    def __str__(self) -> str:
        return self.value


class ModelName(ValueObject):
    """Modelo concreto de um provedor."""

    value: str = Field(min_length=1, max_length=128)

    def __str__(self) -> str:
        return self.value


class PromptVersion(ValueObject):
    """Versão semântica de um prompt do registry."""

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)

    @classmethod
    def parse(cls, text: str) -> Self:
        parts = text.strip().lstrip("v").split(".")
        if len(parts) != 3:
            raise ValueError(f"Versão de prompt inválida: {text!r}. Use 'MAJOR.MINOR.PATCH'.")
        try:
            return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))
        except ValueError as exc:
            raise ValueError(f"Versão de prompt inválida: {text!r}") from exc

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class MixLevel(ValueObject):
    """Nível relativo de mixagem, em dB, referente ao elemento dominante."""

    element: str = Field(min_length=2, max_length=48)
    relative_db: float = Field(ge=-60.0, le=6.0)
    priority: int = Field(ge=1, le=5)

    def __str__(self) -> str:
        return f"{self.element}: {self.relative_db:+.1f} dB (prioridade {self.priority})"


def as_dict(value: ValueObject) -> dict[str, Any]:
    """Converte um value object para dicionário serializável."""
    return value.model_dump(mode="json")
