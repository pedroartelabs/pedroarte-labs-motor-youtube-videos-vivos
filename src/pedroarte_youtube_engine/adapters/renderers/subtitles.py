"""Legendas e transcrições (seção 9.28).

As legendas identificam o falante e descrevem sons importantes — requisitos de
acessibilidade, não enfeite.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.segment import PromptSegment, SubtitleCue


def build_cues(segments: tuple[PromptSegment, ...]) -> tuple[SubtitleCue, ...]:
    """Monta as legendas de uma produção inteira, renumerando em sequência."""
    cues: list[SubtitleCue] = []
    index = 1
    for segment in segments:
        for cue in segment.subtitles:
            cues.append(cue.model_copy(update={"index": index}))
            index += 1
    return tuple(cues)


def render_srt(cues: tuple[SubtitleCue, ...]) -> str:
    """Formato SubRip."""
    return "\n".join(cue.to_srt() for cue in cues)


def render_vtt(cues: tuple[SubtitleCue, ...]) -> str:
    """Formato WebVTT, com cabeçalho obrigatório."""
    body = "\n".join(cue.to_vtt() for cue in cues)
    return f"WEBVTT\n\n{body}"


def render_transcript(segments: tuple[PromptSegment, ...], *, title: str = "") -> str:
    """Transcrição legível, com falantes, narração e sons relevantes."""
    lines: list[str] = []
    if title:
        lines.append(f"# Transcrição — {title}")
        lines.append("")

    for segment in segments:
        lines.append(f"## [{segment.range.start} – {segment.range.end}]")
        lines.append("")

        described = False
        for line in segment.audio.dialogue:
            lines.append(f"**{line.speaker_name}:** {line.text}")
            described = True
        for line in segment.audio.narration:
            lines.append(f"**{line.narrator_name} (narração):** {line.text}")
            described = True

        if not described:
            decisions = ", ".join(
                entry.decision.value for entry in segment.audio.voice_plan
            )
            lines.append(f"*(sem fala — decisão vocal: {decisions})*")

        important_sounds = [
            effect.description
            for effect in segment.audio.sound_effects
            if effect.relative_db >= -18.0
        ]
        if important_sounds:
            lines.append(f"*[sons: {'; '.join(important_sounds)}]*")

        lines.append("")

    return "\n".join(lines)
