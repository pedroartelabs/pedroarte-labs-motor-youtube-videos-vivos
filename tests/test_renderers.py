"""Testes unitários dos renderers de markdown."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.adapters.renderers.subtitles import render_srt, render_vtt
from pedroarte_youtube_engine.domain.value_objects import Timecode

pytestmark = pytest.mark.unit


class TestSubtitleFormats:
    def test_srt_format_uses_comma(self) -> None:
        t = Timecode.parse("00:01:30.500")
        assert "," in t.srt()

    def test_vtt_format_uses_dot(self) -> None:
        t = Timecode.parse("00:01:30.500")
        assert "." in t.vtt()
