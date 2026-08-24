"""Legendas SRT — a implementação REPLACE decidida no Gate 1 (SDD_SPDD.md
§15): o formato SRT em si é trivial; reimplementado aqui, isolado, em vez de
reutilizar `adapters/renderers/subtitles.py`/`domain/segment.py::SubtitleCue`
do legacy, que exigiriam construir `PromptSegment` completo.

Fonte dos cues: os `SentenceBoundary` reais da narração completa (Gate
3B.2), não segmentos sintéticos — sidecar `.srt`, não burn-in (decisão já
registrada no Gate 3 planning).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


def _format_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def cues_from_timing(timing: list[dict]) -> tuple[Cue, ...]:
    """Índices sequenciais e sem furos — filtra primeiro, numera depois
    (um boundary sem texto não deve "gastar" um número de cue)."""
    non_empty = [item for item in timing if str(item.get("text", "")).strip()]
    return tuple(
        Cue(
            index=i,
            start_seconds=float(item["start_seconds"]),
            end_seconds=float(item["end_seconds"]),
            text=str(item["text"]).strip(),
        )
        for i, item in enumerate(non_empty, start=1)
    )


MAX_LINES = 2
APPROX_CHARS_PER_LINE = 42
APPROX_MAX_DISPLAY_CHARS = MAX_LINES * APPROX_CHARS_PER_LINE  # 84

#: Gate 3D.1 SLICE C §12 — quando o timing por palavra não existe, a
#: duração do cue-pai é redistribuída PROPORCIONALMENTE à contagem de
#: palavras de cada bloco. Isso não é timing real por palavra — é uma
#: aproximação documentada, nunca apresentada como precisa.
PROPORTIONAL_CAPTION_TIMING_APPROXIMATION = True


def rechunk_cue(cue: Cue, *, max_display_chars: int = APPROX_MAX_DISPLAY_CHARS) -> tuple[Cue, ...]:
    """Divide um cue longo em blocos de exibição menores, sem cortar
    palavras, redistribuindo a duração original proporcionalmente à
    contagem de palavras de cada bloco (mesma técnica de
    `lite/timeline.py::build_proportional_timeline`, aplicada aqui ao
    problema análogo de granularidade de legenda)."""
    text = cue.text.strip()
    if len(text) <= max_display_chars:
        return (cue,)

    words = text.split()
    blocks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if len(candidate) > max_display_chars and current:
            blocks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        blocks.append(" ".join(current))

    total_words = len(words)
    total_duration = cue.end_seconds - cue.start_seconds
    cursor = cue.start_seconds
    result: list[Cue] = []
    for block in blocks:
        block_words = len(block.split())
        share = (block_words / total_words) * total_duration if total_words else 0.0
        result.append(
            Cue(index=cue.index, start_seconds=cursor, end_seconds=cursor + share, text=block)
        )
        cursor += share
    return tuple(result)


def rechunk_cues(cues: tuple[Cue, ...], *, max_display_chars: int = APPROX_MAX_DISPLAY_CHARS) -> tuple[Cue, ...]:
    """Reindexação sequencial após o rechunking — mesma regra do Gate 1
    (`cues_from_timing`): nenhum furo, nenhuma sobreposição de índice."""
    expanded: list[Cue] = []
    for cue in cues:
        expanded.extend(rechunk_cue(cue, max_display_chars=max_display_chars))
    return tuple(
        Cue(index=i, start_seconds=c.start_seconds, end_seconds=c.end_seconds, text=c.text)
        for i, c in enumerate(expanded, start=1)
    )


def render_srt(cues: tuple[Cue, ...]) -> str:
    blocks = [
        f"{cue.index}\n{_format_timestamp(cue.start_seconds)} --> {_format_timestamp(cue.end_seconds)}\n{cue.text}"
        for cue in cues
    ]
    return "\n\n".join(blocks) + "\n"


@dataclass(frozen=True, slots=True)
class CaptionStyle:
    """Contrato mínimo de estilo (Gate 3D.1 §17) — não um sistema de design
    de legendas, só os parâmetros necessários para o `.ass`/`libass`."""

    font_name: str = "Arial"
    font_size_fraction_of_height: float = 0.045
    bottom_margin_fraction: float = 0.08
    primary_color_ass: str = "&H00FFFFFF"  # branco (formato AABBGGRR do ASS)
    outline_color_ass: str = "&H00000000"  # preto
    outline_width: float = 2.5
    shadow: float = 1.0
    opaque_background_box: bool = False


def _ass_timestamp(seconds: float) -> str:
    total_cs = round(seconds * 100)
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, cs = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def render_ass(
    cues: tuple[Cue, ...], *, style: CaptionStyle = CaptionStyle(), resolution: tuple[int, int] = (1920, 1080)
) -> str:
    """Gera um `.ass` mínimo — só os campos que `style` realmente usa,
    sem sistema de design de legendas (Gate 3D.1 §13/§17)."""
    width, height = resolution
    font_size = round(height * style.font_size_fraction_of_height)
    margin_v = round(height * style.bottom_margin_fraction)
    border_style = 3 if style.opaque_background_box else 1  # 3=caixa opaca, 1=contorno+sombra

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{font_size},{style.primary_color_ass},{style.primary_color_ass},{style.outline_color_ass},&H80000000,0,0,0,0,100,100,0,0,{border_style},{style.outline_width},{style.shadow},2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for cue in cues:
        text = cue.text.replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(cue.start_seconds)},{_ass_timestamp(cue.end_seconds)},Default,,0,0,0,,{text}"
        )
    return header + "\n".join(lines) + "\n"
