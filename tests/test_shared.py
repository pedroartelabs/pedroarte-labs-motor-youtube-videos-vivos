"""Testes unitários do módulo shared."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pedroarte_youtube_engine.shared.clock import FrozenClock, SystemClock
from pedroarte_youtube_engine.shared.errors import EngineError, StateTransitionError
from pedroarte_youtube_engine.shared.hashing import (
    canonical_json,
    content_hash,
    stable_short_id,
    structural_hash,
)
from pedroarte_youtube_engine.shared.text import (
    count_words,
    excerpt,
    first_sentence,
    max_words_for_duration,
    normalize_whitespace,
    safe_slug,
    sentence_split,
    slugify,
    speakable_duration_seconds,
    strip_accents,
    truncate_words,
)

pytestmark = pytest.mark.unit


class TestClock:
    def test_system_clock_has_timezone(self) -> None:
        clock = SystemClock()
        now = clock.now()
        assert now.tzinfo is not None

    def test_frozen_clock_deterministic(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = FrozenClock(start=start)
        assert clock.now() == start
        assert clock.now() == start

    def test_frozen_clock_step(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = FrozenClock(start=start, step_seconds=1.0)
        first = clock.now()
        second = clock.now()
        assert (second - first).total_seconds() == 1.0

    def test_frozen_clock_requires_tz(self) -> None:
        with pytest.raises(ValueError):
            FrozenClock(start=datetime(2026, 1, 1))


class TestHashing:
    def test_content_hash_deterministic(self) -> None:
        a = content_hash("hello")
        b = content_hash("hello")
        assert a == b
        assert a.startswith("sha256:")

    def test_content_hash_bytes(self) -> None:
        h = content_hash(b"bytes")
        assert h.startswith("sha256:")

    def test_canonical_json_stable(self) -> None:
        a = canonical_json({"b": 2, "a": 1})
        b = canonical_json({"a": 1, "b": 2})
        assert a == b

    def test_structural_hash(self) -> None:
        h = structural_hash({"key": "value"})
        assert h.startswith("sha256:")

    def test_stable_short_id(self) -> None:
        a = stable_short_id("seed1", "seed2")
        b = stable_short_id("seed1", "seed2")
        assert a == b
        assert len(a) == 6

    def test_stable_short_id_custom_length(self) -> None:
        result = stable_short_id("x", length=12)
        assert len(result) == 12

    def test_stable_short_id_bad_length(self) -> None:
        with pytest.raises(ValueError):
            stable_short_id("x", length=2)


class TestText:
    def test_strip_accents(self) -> None:
        assert strip_accents("café") == "cafe"
        assert strip_accents("ação") == "acao"

    def test_slugify(self) -> None:
        assert slugify("A Morte Ainda Não Nasceu") == "a-morte-ainda-nao-nasceu"

    def test_slugify_empty(self) -> None:
        assert slugify("!!!") == "sem-titulo"

    def test_slugify_max_length(self) -> None:
        long = "a" * 200
        assert len(slugify(long, max_length=10)) <= 10

    def test_safe_slug_windows_reserved(self) -> None:
        assert safe_slug("CON") == "con-item"
        assert safe_slug("NUL") == "nul-item"

    def test_safe_slug_dots(self) -> None:
        result = safe_slug("..")
        assert result not in {".", "..", ""}

    def test_normalize_whitespace(self) -> None:
        result = normalize_whitespace("  hello   world  \n\n\n\n  extra  ")
        assert "\n\n\n" not in result

    def test_count_words(self) -> None:
        assert count_words("Olá mundo cruel") == 3

    def test_speakable_duration(self) -> None:
        text = " ".join(["palavra"] * 150)
        seconds = speakable_duration_seconds(text)
        assert abs(seconds - 60.0) < 0.1

    def test_speakable_duration_bad_rate(self) -> None:
        with pytest.raises(ValueError):
            speakable_duration_seconds("x", words_per_minute=0)

    def test_max_words_for_duration(self) -> None:
        assert max_words_for_duration(60.0) == 150
        assert max_words_for_duration(0) == 0

    def test_truncate_words(self) -> None:
        assert truncate_words("a b c d e", 3).endswith("…")
        assert truncate_words("a b c", 5) == "a b c"
        assert truncate_words("anything", 0) == ""

    def test_sentence_split(self) -> None:
        sentences = sentence_split("Sr. João chegou. Ele disse olá.")
        assert any("Sr." in s for s in sentences)

    def test_first_sentence(self) -> None:
        assert first_sentence("Primeira. Segunda.") == "Primeira."
        assert first_sentence("") == ""

    def test_excerpt_short(self) -> None:
        assert excerpt("curto") == "curto"

    def test_excerpt_long(self) -> None:
        long = "palavra " * 100
        result = excerpt(long, max_chars=50)
        assert len(result) <= 50
        assert result.endswith("…")


class TestErrors:
    def test_engine_error_to_dict(self) -> None:
        err = EngineError("broken", key="val")
        d = err.to_dict()
        assert d["code"] == "engine_error"
        assert d["message"] == "broken"
        assert d["details"]["key"] == "val"

    def test_state_transition_error_code(self) -> None:
        err = StateTransitionError("bad transition")
        assert err.code == "state_transition_error"
