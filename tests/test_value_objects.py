"""Testes unitários dos value objects do domínio."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    CharacterId,
    ContentHash,
    Duration,
    Identifier,
    LocationId,
    ProjectId,
    PromptVersion,
    PropId,
    Timecode,
)

pytestmark = pytest.mark.unit


class TestIdentifier:
    def test_valid(self) -> None:
        assert Identifier(value="abc-123").value == "abc-123"

    def test_normalizes_to_lowercase(self) -> None:
        assert Identifier(value="ABC").value == "abc"

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError):
            Identifier(value="has space")

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError):
            Identifier(value="a")

    def test_frozen(self) -> None:
        i = Identifier(value="frozen")
        with pytest.raises(Exception):
            i.value = "other"  # type: ignore[misc]


class TestProjectId:
    def test_from_title(self) -> None:
        pid = ProjectId.from_title("A Morte Ainda Não Nasceu")
        assert "morte" in pid.value


class TestCharacterId:
    def test_from_name(self) -> None:
        cid = CharacterId.from_name("João")
        assert cid.value.startswith("character_")


class TestLocationId:
    def test_from_name(self) -> None:
        lid = LocationId.from_name("Floresta Negra")
        assert lid.value.startswith("location_")


class TestPropId:
    def test_from_name(self) -> None:
        pid = PropId.from_name("Espada Mágica")
        assert pid.value.startswith("prop_")


class TestTimecode:
    def test_zero(self) -> None:
        t = Timecode.zero()
        assert t.milliseconds == 0
        assert t.formatted() == "00:00:00.000"

    def test_from_seconds(self) -> None:
        t = Timecode.from_seconds(61.5)
        assert t.milliseconds == 61500
        assert t.formatted() == "00:01:01.500"

    def test_parse(self) -> None:
        t = Timecode.parse("01:02:03.456")
        assert t.milliseconds == 3723456

    def test_parse_rejects_bad_format(self) -> None:
        with pytest.raises(ValueError):
            Timecode.parse("not a timecode")

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            Timecode.from_seconds(-1)

    def test_ordering(self) -> None:
        a = Timecode.from_seconds(1)
        b = Timecode.from_seconds(2)
        assert a < b
        assert b > a
        assert a <= a
        assert a >= a

    def test_plus_minus(self) -> None:
        t = Timecode.from_seconds(10)
        d = Duration.from_seconds(5)
        result = t.plus(d)
        assert result.milliseconds == 15000
        delta = result.minus(t)
        assert delta.milliseconds == 5000

    def test_minus_negative_raises(self) -> None:
        a = Timecode.from_seconds(1)
        b = Timecode.from_seconds(10)
        with pytest.raises(ValueError):
            a.minus(b)

    def test_srt_format(self) -> None:
        t = Timecode.parse("00:01:30.500")
        assert t.srt() == "00:01:30,500"

    def test_vtt_format(self) -> None:
        t = Timecode.parse("00:01:30.500")
        assert t.vtt() == "00:01:30.500"


class TestDuration:
    def test_from_seconds(self) -> None:
        d = Duration.from_seconds(90.5)
        assert d.milliseconds == 90500

    def test_from_minutes(self) -> None:
        d = Duration.from_minutes(1.5)
        assert d.seconds == 90.0

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            Duration.from_seconds(-1)

    def test_plus(self) -> None:
        a = Duration.from_seconds(5)
        b = Duration.from_seconds(3)
        assert a.plus(b).milliseconds == 8000

    def test_times(self) -> None:
        d = Duration.from_seconds(10)
        assert d.times(3).milliseconds == 30000

    def test_times_negative_rejected(self) -> None:
        d = Duration.from_seconds(1)
        with pytest.raises(ValueError):
            d.times(-1)

    def test_ordering(self) -> None:
        a = Duration.from_seconds(1)
        b = Duration.from_seconds(2)
        assert a < b

    def test_human(self) -> None:
        assert Duration.from_seconds(30).human() == "30.0s"
        assert Duration.from_seconds(90).human() == "1min 30s"


class TestAspectRatio:
    def test_valid(self) -> None:
        ar = AspectRatio(width=16, height=9)
        assert ar.width == 16

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            AspectRatio(width=0, height=9)


class TestContentHash:
    def test_valid(self) -> None:
        h = ContentHash(value="sha256:" + "a" * 64)
        assert h.short == "a" * 12

    def test_invalid_pattern(self) -> None:
        with pytest.raises(ValueError):
            ContentHash(value="md5:abc")


class TestPromptVersion:
    def test_creation(self) -> None:
        v = PromptVersion(major=1, minor=2, patch=3)
        assert v.major == 1

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            PromptVersion(major=-1, minor=0, patch=0)
