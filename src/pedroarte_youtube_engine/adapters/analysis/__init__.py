"""Adaptadores de análise narrativa."""

from __future__ import annotations

from pedroarte_youtube_engine.adapters.analysis.heuristic import HeuristicNarrativeAnalyzer
from pedroarte_youtube_engine.adapters.analysis.lexicons import (
    ATTRIBUTION_VERBS,
    LOCATION_NOUNS,
    PROP_NOUNS,
    TONE_LEXICON,
)

__all__ = [
    "ATTRIBUTION_VERBS",
    "HeuristicNarrativeAnalyzer",
    "LOCATION_NOUNS",
    "PROP_NOUNS",
    "TONE_LEXICON",
]
