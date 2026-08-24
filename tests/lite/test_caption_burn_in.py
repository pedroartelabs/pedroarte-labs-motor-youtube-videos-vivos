"""Gate 3D.1 SLICE C — rechunking, .ass, e queima real via FFmpeg/libass."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.captions import (
    APPROX_MAX_DISPLAY_CHARS,
    Cue,
    CaptionStyle,
    PROPORTIONAL_CAPTION_TIMING_APPROXIMATION,
    render_ass,
    render_srt,
    rechunk_cue,
    rechunk_cues,
)
from pedroarte_youtube_engine.lite.ffmpeg_assembler import burn_captions, resolve_ffmpeg_binary


class TestRechunkCue:
    def test_short_cue_is_unchanged(self) -> None:
        cue = Cue(index=1, start_seconds=0.0, end_seconds=3.0, text="Uma frase curta.")
        result = rechunk_cue(cue)
        assert result == (cue,)

    def test_long_cue_is_split(self) -> None:
        text = " ".join(["palavra"] * 40)  # bem acima de 84 chars
        cue = Cue(index=1, start_seconds=0.0, end_seconds=20.0, text=text)
        result = rechunk_cue(cue)
        assert len(result) > 1
        for block in result:
            assert len(block.text) <= APPROX_MAX_DISPLAY_CHARS

    def test_never_splits_inside_a_word(self) -> None:
        text = " ".join(["antidisestablishmentarianism"] * 6)
        cue = Cue(index=1, start_seconds=0.0, end_seconds=10.0, text=text)
        result = rechunk_cue(cue)
        rejoined = " ".join(b.text for b in result)
        assert rejoined == text

    def test_duration_redistributed_proportionally_and_sums_to_original(self) -> None:
        text = " ".join(["palavra"] * 40)
        cue = Cue(index=1, start_seconds=10.0, end_seconds=30.0, text=text)
        result = rechunk_cue(cue)
        assert result[0].start_seconds == pytest.approx(10.0)
        assert result[-1].end_seconds == pytest.approx(30.0)
        for a, b in zip(result, result[1:]):
            assert a.end_seconds == pytest.approx(b.start_seconds)

    def test_approximation_flag_is_documented_true(self) -> None:
        assert PROPORTIONAL_CAPTION_TIMING_APPROXIMATION is True


class TestRechunkCues:
    def test_reindexes_sequentially_without_gaps(self) -> None:
        long_text = " ".join(["palavra"] * 40)
        cues = (
            Cue(index=1, start_seconds=0.0, end_seconds=3.0, text="Curta."),
            Cue(index=2, start_seconds=3.0, end_seconds=20.0, text=long_text),
        )
        result = rechunk_cues(cues)
        indices = [c.index for c in result]
        assert indices == list(range(1, len(result) + 1))
        assert len(result) > 2  # o segundo cue foi dividido


class TestRenderAss:
    def test_produces_script_info_and_events(self) -> None:
        cues = rechunk_cues((Cue(index=1, start_seconds=0.0, end_seconds=2.0, text="Olá, mundo."),))
        ass = render_ass(cues)
        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "Olá, mundo." in ass

    def test_custom_style_reflected_in_output(self) -> None:
        cues = rechunk_cues((Cue(index=1, start_seconds=0.0, end_seconds=1.0, text="x"),))
        style = CaptionStyle(font_name="Georgia", opaque_background_box=True)
        ass = render_ass(cues, style=style)
        assert "Georgia" in ass


class TestBurnCaptionsReal:
    def test_burns_captions_into_real_video(self, tmp_path: Path) -> None:
        ffmpeg = resolve_ffmpeg_binary("ffmpeg")
        video = tmp_path / "src.mp4"
        subprocess.run(
            [
                ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
            ],
            check=True, capture_output=True,
        )
        cues = rechunk_cues((Cue(index=1, start_seconds=0.0, end_seconds=2.0, text="Legenda de teste."),))
        ass_text = render_ass(cues, resolution=(640, 360))
        ass_path = tmp_path / "captions.ass"
        ass_path.write_text(ass_text, encoding="utf-8")

        output = tmp_path / "burned.mp4"
        result = burn_captions(video_path=video, ass_path=ass_path, output_path=output)

        assert result.output_path.exists()
        assert result.output_path.stat().st_size > 0
