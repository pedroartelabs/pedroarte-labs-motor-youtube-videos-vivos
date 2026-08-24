"""GATE 3D.1 SLICE A — teste de regressão permanente do bug do zoompan
(docs/youtube-lite/GATE_3D_POSTMORTEM_AND_3D1_PLAN.md §6/§28).

Reproduz o experimento do postmortem: renderiza um segmento real, extrai
frames distantes no tempo, mede a diferença de pixel real via
`blend=difference` + `signalstats` (mesma técnica usada para encontrar o bug
originalmente). O teste DEVE falhar se o movimento estiver configurado mas os
frames de saída permanecerem efetivamente idênticos — exatamente o cenário
que passou despercebido do Gate 2 até o Gate 3D por falta deste teste.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.ffmpeg_assembler import render_retention_clip, resolve_ffmpeg_binary
from pedroarte_youtube_engine.lite.retention import RetentionKind, RetentionSegment, build_default_retention_plan

# Piso de diferença de luminância média (escala 0-255) entre dois frames
# distantes no tempo. Calibrado pela própria evidência do postmortem: a
# receita quebrada deu ~0.01-0.04; a corrigida deu ~25. Um piso de 1.0 detecta
# com folga qualquer regressão para o comportamento quebrado, sem ser frágil
# a diferenças de compressão/ruído de 1 imagem para outra.
MIN_PERCEPTIBLE_YAVG = 1.0


def _make_high_detail_test_image(path: Path) -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=1", "-frames:v", "1", str(path)],
        check=True, capture_output=True,
    )


def _extract_frame(video_path: Path, *, at_seconds: float, output_path: Path) -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    subprocess.run(
        [ffmpeg, "-y", "-ss", str(at_seconds), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(output_path)],
        check=True, capture_output=True,
    )


def _pixel_diff_yavg(frame_a: Path, frame_b: Path) -> float:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    completed = subprocess.run(
        [
            ffmpeg, "-i", str(frame_a), "-i", str(frame_b),
            "-filter_complex", "blend=all_mode=difference,signalstats,metadata=print",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    match = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", completed.stdout + completed.stderr)
    assert match, "signalstats YAVG não encontrado na saída do ffmpeg"
    return float(match.group(1))


@pytest.fixture()
def test_image(tmp_path: Path) -> Path:
    path = tmp_path / "synth.png"
    _make_high_detail_test_image(path)
    return path


class TestMotionRegression:
    """O teste que teria pego o bug do Gate 3D."""

    def test_zoom_in_segment_produces_perceptible_pixel_change(self, tmp_path: Path, test_image: Path) -> None:
        segment = RetentionSegment(
            kind=RetentionKind.ZOOM_IN, duration_seconds=8.0, start_scale=1.0, end_scale=1.16
        )
        output = tmp_path / "seg.mp4"
        render_retention_clip(image_path=test_image, segment=segment, output_path=output)

        frame_start = tmp_path / "f0.png"
        frame_end = tmp_path / "f7.png"
        _extract_frame(output, at_seconds=0.0, output_path=frame_start)
        _extract_frame(output, at_seconds=7.0, output_path=frame_end)

        yavg = _pixel_diff_yavg(frame_start, frame_end)
        assert yavg >= MIN_PERCEPTIBLE_YAVG, (
            f"Movimento configurado mas frames efetivamente idênticos (YAVG={yavg}) — "
            "regressão para o bug do zoompan (postmortem §6)."
        )

    def test_static_segment_shows_no_regression_false_positive(self, tmp_path: Path, test_image: Path) -> None:
        """Controle negativo: start_scale == end_scale deve, de fato, produzir
        pouquíssima diferença — prova que o teste mede o que diz medir."""
        segment = RetentionSegment(
            kind=RetentionKind.ZOOM_IN, duration_seconds=3.0, start_scale=1.05, end_scale=1.05
        )
        output = tmp_path / "static.mp4"
        render_retention_clip(image_path=test_image, segment=segment, output_path=output)

        frame_a = tmp_path / "fa.png"
        frame_b = tmp_path / "fb.png"
        _extract_frame(output, at_seconds=0.2, output_path=frame_a)
        _extract_frame(output, at_seconds=2.5, output_path=frame_b)
        yavg = _pixel_diff_yavg(frame_a, frame_b)
        assert yavg < MIN_PERCEPTIBLE_YAVG

    def test_pan_segment_produces_perceptible_pixel_change(self, tmp_path: Path, test_image: Path) -> None:
        segment = RetentionSegment(
            kind=RetentionKind.PAN, duration_seconds=7.0, start_scale=1.05, end_scale=1.05, pan_dx_fraction=0.85
        )
        output = tmp_path / "pan.mp4"
        render_retention_clip(image_path=test_image, segment=segment, output_path=output)

        frame_a = tmp_path / "pa.png"
        frame_b = tmp_path / "pb.png"
        _extract_frame(output, at_seconds=0.0, output_path=frame_a)
        _extract_frame(output, at_seconds=6.5, output_path=frame_b)
        yavg = _pixel_diff_yavg(frame_a, frame_b)
        assert yavg >= MIN_PERCEPTIBLE_YAVG

    def test_default_retention_plan_covers_full_beat_with_perceptible_motion(
        self, tmp_path: Path, test_image: Path
    ) -> None:
        """Beat longo (30s, como beat_03 real) — cada sub-segmento do plano
        padrão deve produzir movimento real, não só o primeiro."""
        plan = build_default_retention_plan(30.0)
        assert len(plan) >= 2  # beat longo deve ter sido subdividido

        for i, segment in enumerate(plan):
            output = tmp_path / f"chunk_{i}.mp4"
            render_retention_clip(image_path=test_image, segment=segment, output_path=output)
            frame_a = tmp_path / f"c{i}_a.png"
            frame_b = tmp_path / f"c{i}_b.png"
            mid = max(0.1, segment.duration_seconds * 0.15)
            end = segment.duration_seconds * 0.9
            _extract_frame(output, at_seconds=mid, output_path=frame_a)
            _extract_frame(output, at_seconds=end, output_path=frame_b)
            yavg = _pixel_diff_yavg(frame_a, frame_b)
            assert yavg >= MIN_PERCEPTIBLE_YAVG, f"chunk {i} ({segment.kind.value}) sem movimento perceptível"
