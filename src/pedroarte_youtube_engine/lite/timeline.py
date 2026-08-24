"""TimelineBuilder — versão mínima do Gate 2.

Alinhamento por parágrafo/beat usando a duração REAL do áudio pós-TTS, nunca
forced alignment fonema-a-fonema (discovery Lite §16, SDD_SPDD.md §14). No
Gate 2 há um único beat: a imagem cobre a narração inteira. A função já está
desenhada para múltiplos beats (Gate 3) sem exigir reescrita.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimelineBeat:
    image_path: str
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def build_single_beat_timeline(*, image_path: str, narration_duration_seconds: float) -> tuple[TimelineBeat, ...]:
    if narration_duration_seconds <= 0:
        raise ValueError("A duração da narração deve ser positiva.")
    return (TimelineBeat(image_path=image_path, start_seconds=0.0, end_seconds=narration_duration_seconds),)


def build_proportional_timeline(
    *, image_paths: tuple[str, ...], beat_word_counts: tuple[int, ...], total_duration_seconds: float
) -> tuple[TimelineBeat, ...]:
    """Distribui `total_duration_seconds` entre os beats proporcionalmente à
    contagem de palavras de cada um — a menor abordagem de sincronização
    aceitável quando o TTS não fornece marcações reais de palavra
    (discovery Lite §16). Não usada no Gate 2 (um único beat); existe pronta
    para o Gate 3, sem depender de nenhum outro componente novo.
    """
    if len(image_paths) != len(beat_word_counts):
        raise ValueError("image_paths e beat_word_counts devem ter o mesmo tamanho.")
    total_words = sum(beat_word_counts)
    if total_words <= 0:
        raise ValueError("A soma de palavras deve ser positiva.")

    beats: list[TimelineBeat] = []
    cursor = 0.0
    for image_path, words in zip(image_paths, beat_word_counts, strict=True):
        share = (words / total_words) * total_duration_seconds
        beats.append(
            TimelineBeat(image_path=image_path, start_seconds=cursor, end_seconds=cursor + share)
        )
        cursor += share
    return tuple(beats)
