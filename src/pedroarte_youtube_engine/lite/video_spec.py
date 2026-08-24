"""VideoSpecification — o contrato editorial do vídeo (SDD_SPDD.md §38.2).

Derivado do briefing por uma função pura, não por um agente. Não inclui
Visual Bible (isso é exclusivo do Gate 3C).
"""

from __future__ import annotations

from dataclasses import dataclass

from pedroarte_youtube_engine.lite.briefing import BriefingSchema, FactualityMode
from pedroarte_youtube_engine.shared.text import max_words_for_duration


@dataclass(frozen=True, slots=True)
class VideoSpecification:
    topic: str
    objective: str
    audience: str
    language: str
    tone: str
    target_min_minutes: float
    target_max_minutes: float
    estimated_word_range: tuple[int, int]
    must_include: tuple[str, ...]
    must_avoid: tuple[str, ...]
    factuality_mode: FactualityMode
    visual_direction: str
    additional_context: str
    references: tuple[str, ...]


def normalize_briefing(briefing: BriefingSchema) -> VideoSpecification:
    word_range = (
        max_words_for_duration(briefing.target_min_minutes * 60.0),
        max_words_for_duration(briefing.target_max_minutes * 60.0),
    )
    return VideoSpecification(
        topic=briefing.topic,
        objective=briefing.objective,
        audience=briefing.audience,
        language=briefing.language,
        tone=briefing.tone,
        target_min_minutes=briefing.target_min_minutes,
        target_max_minutes=briefing.target_max_minutes,
        estimated_word_range=word_range,
        must_include=briefing.must_include,
        must_avoid=briefing.must_avoid,
        factuality_mode=briefing.factuality_mode,
        visual_direction=briefing.visual_direction,
        additional_context=briefing.additional_context,
        references=briefing.references,
    )
