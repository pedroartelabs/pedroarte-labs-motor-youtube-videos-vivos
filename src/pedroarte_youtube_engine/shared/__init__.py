"""Núcleo compartilhado: utilidades sem dependência de domínio nem de fornecedor."""

from __future__ import annotations

from pedroarte_youtube_engine.shared.clock import Clock, FrozenClock, SystemClock
from pedroarte_youtube_engine.shared.errors import (
    CapabilityError,
    ConfigurationError,
    DomainRuleViolation,
    EngineError,
    IngestionError,
    InputDiscoveryError,
    PathSecurityError,
    ProviderError,
    RepairLimitExceeded,
    StateTransitionError,
)
from pedroarte_youtube_engine.shared.hashing import content_hash, stable_short_id
from pedroarte_youtube_engine.shared.result import Err, Ok, Result
from pedroarte_youtube_engine.shared.text import (
    count_words,
    normalize_whitespace,
    safe_slug,
    slugify,
    speakable_duration_seconds,
)

__all__ = [
    "CapabilityError",
    "Clock",
    "ConfigurationError",
    "DomainRuleViolation",
    "EngineError",
    "Err",
    "FrozenClock",
    "IngestionError",
    "InputDiscoveryError",
    "Ok",
    "PathSecurityError",
    "ProviderError",
    "RepairLimitExceeded",
    "Result",
    "StateTransitionError",
    "SystemClock",
    "content_hash",
    "count_words",
    "normalize_whitespace",
    "safe_slug",
    "slugify",
    "speakable_duration_seconds",
    "stable_short_id",
]
