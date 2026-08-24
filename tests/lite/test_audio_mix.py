"""Gate 3D.1 SLICE D — geração de cama ambiente original e mixagem.
Usa um fixture de narração sintética (não a narração aprovada) para não
depender de arquivos de um run específico."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.audio_mix import (
    DEFAULT_MUSIC_GAIN_DB,
    compute_gain_for_relative_offset,
    generate_ambient_bed,
    mix_narration_with_music,
    render_music_stem,
)
from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary


def _make_narration_fixture(path: Path, *, seconds: float = 6.0) -> None:
    """Fala sintética simples (não é a narração real aprovada — só um
    fixture técnico, ver Gate 3D.1 §15: 'Test Music Asset ... NOT
    necessarily the publication soundtrack')."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
            "-af", "volume=0.8", str(path),
        ],
        check=True, capture_output=True,
    )


class TestGenerateAmbientBed:
    def test_produces_audio_of_requested_duration(self, tmp_path: Path) -> None:
        output = tmp_path / "bed.wav"
        generate_ambient_bed(duration_seconds=5.0, output_path=output)
        metrics = probe_audio(output)
        assert metrics.duration_seconds == pytest.approx(5.0, abs=0.15)

    def test_bed_has_no_clipping(self, tmp_path: Path) -> None:
        output = tmp_path / "bed.wav"
        generate_ambient_bed(duration_seconds=5.0, output_path=output)
        metrics = probe_audio(output)
        assert (metrics.max_volume_db or 0.0) <= 0.0

    def test_bed_is_audible_not_silent(self, tmp_path: Path) -> None:
        output = tmp_path / "bed.wav"
        generate_ambient_bed(duration_seconds=5.0, output_path=output)
        metrics = probe_audio(output)
        assert (metrics.mean_volume_db or -100.0) > -60.0


class TestMixNarrationWithMusic:
    def test_narration_stays_dominant_and_no_clipping(self, tmp_path: Path) -> None:
        narration = tmp_path / "narration.wav"
        _make_narration_fixture(narration, seconds=6.0)
        music = tmp_path / "music.wav"
        generate_ambient_bed(duration_seconds=6.0, output_path=music)

        mixed = tmp_path / "mixed.mp3"
        result = mix_narration_with_music(
            narration_path=narration, music_path=music, output_path=mixed
        )
        assert result.music_gain_db == DEFAULT_MUSIC_GAIN_DB

        narration_metrics = probe_audio(narration)
        mixed_metrics = probe_audio(mixed)
        assert (mixed_metrics.max_volume_db or 0.0) <= 0.0  # sem clipping
        # narração pura não deveria ficar mais silenciosa que a mixagem final
        assert (mixed_metrics.mean_volume_db or -100.0) >= (narration_metrics.mean_volume_db or -100.0) - 3.0

    def test_mixed_duration_matches_narration_not_music(self, tmp_path: Path) -> None:
        narration = tmp_path / "narration.wav"
        _make_narration_fixture(narration, seconds=4.0)
        music = tmp_path / "music.wav"
        generate_ambient_bed(duration_seconds=10.0, output_path=music)  # música mais longa

        mixed = tmp_path / "mixed.mp3"
        mix_narration_with_music(narration_path=narration, music_path=music, output_path=mixed)
        metrics = probe_audio(mixed)
        assert metrics.duration_seconds == pytest.approx(4.0, abs=0.3)


class TestComputeGainForRelativeOffset:
    """Gate 3D.2 §17 — ganho é DERIVADO da medição real da cama bruta, nunca
    um valor absoluto adivinhado."""

    def test_derives_gain_from_measured_raw_level(self) -> None:
        # narração a -21dB, cama bruta medida a -48dB, alvo: música 12dB
        # mais silenciosa que a narração (-33dB) -> ganho = -33 - (-48) = +15
        gain = compute_gain_for_relative_offset(
            narration_mean_db=-21.0, raw_music_mean_db=-48.0, target_relative_offset_db=-12.0
        )
        assert gain == pytest.approx(15.0)

    def test_quieter_raw_bed_requires_more_gain_for_same_target(self) -> None:
        gain_quiet_bed = compute_gain_for_relative_offset(
            narration_mean_db=-21.0, raw_music_mean_db=-55.0, target_relative_offset_db=-12.0
        )
        gain_loud_bed = compute_gain_for_relative_offset(
            narration_mean_db=-21.0, raw_music_mean_db=-40.0, target_relative_offset_db=-12.0
        )
        assert gain_quiet_bed > gain_loud_bed

    def test_larger_negative_offset_means_quieter_target_and_less_gain(self) -> None:
        gain_low = compute_gain_for_relative_offset(
            narration_mean_db=-21.0, raw_music_mean_db=-48.0, target_relative_offset_db=-16.0
        )
        gain_high = compute_gain_for_relative_offset(
            narration_mean_db=-21.0, raw_music_mean_db=-48.0, target_relative_offset_db=-7.0
        )
        assert gain_low < gain_high


class TestRenderMusicStem:
    """Gate 3D.2 §15 — o stem isolado (pós-ganho, sem narração) é o objeto
    de medição correto, não a mixagem final."""

    def test_stem_mean_reflects_applied_gain(self, tmp_path: Path) -> None:
        music = tmp_path / "music.wav"
        generate_ambient_bed(duration_seconds=6.0, output_path=music)
        raw_metrics = probe_audio(music)

        stem_low = tmp_path / "stem_low.mp3"
        render_music_stem(
            music_path=music, output_path=stem_low, music_gain_db=6.0, narration_duration_seconds=6.0
        )
        stem_high = tmp_path / "stem_high.mp3"
        render_music_stem(
            music_path=music, output_path=stem_high, music_gain_db=18.0, narration_duration_seconds=6.0
        )

        low_metrics = probe_audio(stem_low)
        high_metrics = probe_audio(stem_high)
        assert (raw_metrics.mean_volume_db or -100.0) < (low_metrics.mean_volume_db or -100.0) < (
            high_metrics.mean_volume_db or -100.0
        )

    def test_stem_duration_matches_narration_duration_not_music_duration(self, tmp_path: Path) -> None:
        music = tmp_path / "music.wav"
        generate_ambient_bed(duration_seconds=15.0, output_path=music)
        stem = tmp_path / "stem.mp3"
        render_music_stem(
            music_path=music, output_path=stem, music_gain_db=10.0, narration_duration_seconds=5.0
        )
        metrics = probe_audio(stem)
        assert metrics.duration_seconds == pytest.approx(5.0, abs=0.3)
