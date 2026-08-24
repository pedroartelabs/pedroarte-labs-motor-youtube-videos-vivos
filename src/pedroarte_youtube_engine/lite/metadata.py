"""Metadata mínimo do YouTube (Gate 3 planning §30 do briefing original —
reaproveita a FORMA de `domain/artifacts.py::PublicationMetadata`, não a
classe, que arrasta `ProductionVariant` do legacy). Sem SEO engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chapter:
    at_seconds: float
    title: str

    def formatted_timestamp(self) -> str:
        total = int(self.at_seconds)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def build_metadata(
    *,
    title: str,
    description: str,
    chapters: tuple[Chapter, ...],
    language: str,
    duration_seconds: float,
    hashtags: tuple[str, ...],
) -> dict[str, object]:
    return {
        "title": title[:100],
        "description": description[:5000],
        "chapters": [{"at": c.formatted_timestamp(), "title": c.title} for c in chapters],
        "language": language,
        "duration_seconds": round(duration_seconds, 1),
        "hashtags": list(hashtags),
    }
