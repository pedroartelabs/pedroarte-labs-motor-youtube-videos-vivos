"""Captions (SRT) e metadata — funções puras, sem FFmpeg."""

from __future__ import annotations

from pedroarte_youtube_engine.lite.captions import cues_from_timing, render_srt
from pedroarte_youtube_engine.lite.metadata import Chapter, build_metadata


class TestCaptions:
    def test_cues_from_timing_skips_empty_text(self) -> None:
        timing = [
            {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Olá."},
            {"start_seconds": 1.0, "end_seconds": 1.5, "text": "  "},
            {"start_seconds": 1.5, "end_seconds": 3.0, "text": "Mundo."},
        ]
        cues = cues_from_timing(timing)
        assert len(cues) == 2
        assert cues[0].index == 1
        assert cues[1].index == 2

    def test_render_srt_format(self) -> None:
        cues = cues_from_timing(
            [{"start_seconds": 0.0, "end_seconds": 1.5, "text": "Teste."}]
        )
        srt = render_srt(cues)
        assert srt.startswith("1\n00:00:00,000 --> 00:00:01,500\nTeste.")

    def test_render_srt_handles_hours(self) -> None:
        cues = cues_from_timing(
            [{"start_seconds": 3725.25, "end_seconds": 3726.0, "text": "Uma hora depois."}]
        )
        srt = render_srt(cues)
        assert "01:02:05,250" in srt

    def test_render_srt_multiple_cues_separated_by_blank_line(self) -> None:
        cues = cues_from_timing(
            [
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "A."},
                {"start_seconds": 1.0, "end_seconds": 2.0, "text": "B."},
            ]
        )
        srt = render_srt(cues)
        assert "\n\n2\n" in srt


class TestMetadata:
    def test_build_metadata_shape(self) -> None:
        chapters = (Chapter(at_seconds=0.0, title="Abertura"), Chapter(at_seconds=90.0, title="Meio"))
        metadata = build_metadata(
            title="Título de teste",
            description="Descrição.",
            chapters=chapters,
            language="pt-BR",
            duration_seconds=650.3,
            hashtags=("a", "b"),
        )
        assert metadata["title"] == "Título de teste"
        assert metadata["language"] == "pt-BR"
        assert metadata["duration_seconds"] == 650.3
        assert metadata["chapters"][0]["at"] == "00:00"
        assert metadata["chapters"][1]["at"] == "01:30"
        assert metadata["hashtags"] == ["a", "b"]

    def test_title_truncated_to_100_chars(self) -> None:
        metadata = build_metadata(
            title="x" * 150,
            description="d",
            chapters=(),
            language="pt-BR",
            duration_seconds=1.0,
            hashtags=(),
        )
        assert len(metadata["title"]) == 100

    def test_chapter_formats_hours_when_needed(self) -> None:
        chapter = Chapter(at_seconds=3725.0, title="x")
        assert chapter.formatted_timestamp() == "1:02:05"
