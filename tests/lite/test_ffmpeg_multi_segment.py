"""Integração real (não mock) das funções multi-segmento do assembler —
com fixtures minúsculas (1-2s, imagens sintéticas geradas via FFmpeg lavfi),
para não depender da execução real de 650s do Gate 3D nem gastar tempo de
render desnecessário."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.ffmpeg_assembler import (
    concat_segments,
    mux_video_audio,
    render_silent_segment,
    render_thumbnail,
    resolve_ffmpeg_binary,
)
from pedroarte_youtube_engine.lite.image_qa import probe_image


def _make_test_image(path: Path, *, color: str, size: str = "800x600") -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}", "-frames:v", "1", str(path)],
        check=True, capture_output=True,
    )


def _make_test_wav(path: Path, *, seconds: float = 2.0) -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-ar", "22050", "-ac", "1", str(path),
        ],
        check=True, capture_output=True,
    )


@pytest.fixture()
def two_test_images(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _make_test_image(a, color="red", size="1536x1024")  # simula o caso 3:2 do Gate 3C
    _make_test_image(b, color="blue", size="1672x941")  # simula o caso ~16:9 do handoff
    return a, b


class TestRenderSilentSegmentNormalization:
    def test_non_16_9_source_is_normalized_to_1920x1080(self, tmp_path: Path, two_test_images) -> None:
        image_a, _ = two_test_images
        output = tmp_path / "seg_a.mp4"
        result = render_silent_segment(image_path=image_a, duration_seconds=1.0, output_path=output)
        assert result.output_path.exists()
        info = probe_image(output)  # ffprobe funciona em vídeo também (primeiro stream)
        assert (info.width, info.height) == (1920, 1080)

    def test_near_16_9_source_is_also_normalized_without_distortion(self, tmp_path: Path, two_test_images) -> None:
        _, image_b = two_test_images
        output = tmp_path / "seg_b.mp4"
        render_silent_segment(image_path=image_b, duration_seconds=1.0, output_path=output)
        info = probe_image(output)
        assert (info.width, info.height) == (1920, 1080)


class TestConcatAndMux:
    def test_concat_then_mux_produces_playable_video_with_correct_duration(
        self, tmp_path: Path, two_test_images
    ) -> None:
        image_a, image_b = two_test_images
        seg_a = tmp_path / "seg_a.mp4"
        seg_b = tmp_path / "seg_b.mp4"
        render_silent_segment(image_path=image_a, duration_seconds=1.0, output_path=seg_a)
        render_silent_segment(image_path=image_b, duration_seconds=1.0, output_path=seg_b)

        silent = tmp_path / "silent.mp4"
        concat_segments(segment_paths=[seg_a, seg_b], output_path=silent)
        assert silent.exists()

        audio = tmp_path / "audio.wav"
        _make_test_wav(audio, seconds=2.0)

        final = tmp_path / "final.mp4"
        mux_video_audio(video_path=silent, audio_path=audio, output_path=final)

        metrics = probe_audio(final)
        assert metrics.duration_seconds == pytest.approx(2.0, abs=0.2)
        assert metrics.codec == "aac"


class TestThumbnail:
    def test_render_thumbnail_produces_1280x720(self, tmp_path: Path, two_test_images) -> None:
        image_a, _ = two_test_images
        output = tmp_path / "thumb.png"
        render_thumbnail(image_path=image_a, output_path=output)
        info = probe_image(output)
        assert (info.width, info.height) == (1280, 720)
