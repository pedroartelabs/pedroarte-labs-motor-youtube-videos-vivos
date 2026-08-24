"""Gate 3D.1 SLICE F — Experience QA, testado com fixtures pequenas."""

from __future__ import annotations

from pathlib import Path

from pedroarte_youtube_engine.lite.captions import Cue, CaptionStyle
from pedroarte_youtube_engine.lite.experience_qa import (
    check_background_music_mix_step,
    check_burned_caption_render_step,
    check_caption_rechunk_valid,
    check_caption_style_config_valid,
    check_cumulative_zoom_progression,
    check_max_seconds_without_visual_event,
    check_motion_configuration,
    check_motion_render_regression,
    check_music_stem_relative_level,
    check_total_unique_images,
)
from pedroarte_youtube_engine.lite.retention import (
    RetentionKind,
    RetentionSegment,
    build_continuous_push_in_plan,
    build_default_retention_plan,
)


class TestTotalUniqueImages:
    def test_passes_when_at_or_above_target(self) -> None:
        assert check_total_unique_images(45, target=42).passed
        assert check_total_unique_images(42, target=42).passed

    def test_fails_below_target(self) -> None:
        assert not check_total_unique_images(30, target=42).passed


class TestMaxSecondsWithoutVisualEvent:
    def test_passes_when_all_beats_within_threshold(self) -> None:
        plans = {"beat_D": build_default_retention_plan(11.6), "beat_A": build_default_retention_plan(21.8)}
        check = check_max_seconds_without_visual_event(plans, threshold_seconds=10.0)
        assert check.passed

    def test_fails_on_a_single_long_uninterrupted_segment(self) -> None:
        plans = {"fake_beat": (RetentionSegment(RetentionKind.ZOOM_IN, 25.0, 1.0, 1.1),)}
        check = check_max_seconds_without_visual_event(plans, threshold_seconds=10.0)
        assert not check.passed

    def test_contemplative_segments_exempted(self) -> None:
        plans = {"fake_beat": (RetentionSegment(RetentionKind.ZOOM_IN, 25.0, 1.0, 1.1, contemplative=True),)}
        check = check_max_seconds_without_visual_event(plans, threshold_seconds=10.0)
        assert check.passed


class TestMotionConfiguration:
    def test_passes_for_default_plan(self) -> None:
        plans = {"beat_26": build_default_retention_plan(36.5)}
        check = check_motion_configuration(plans)
        assert check.passed

    def test_fails_for_static_segment(self) -> None:
        plans = {"fake": (RetentionSegment(RetentionKind.ZOOM_IN, 10.0, 1.05, 1.05),)}
        check = check_motion_configuration(plans, min_rate=0.004)
        assert not check.passed


class TestMotionRenderRegression:
    def test_passes_when_all_samples_above_floor(self) -> None:
        check = check_motion_render_regression({"beat_A": 11.4, "beat_D": 8.2}, min_yavg=1.0)
        assert check.passed

    def test_fails_when_any_sample_below_floor(self) -> None:
        check = check_motion_render_regression({"beat_A": 11.4, "beat_broken": 0.02}, min_yavg=1.0)
        assert not check.passed


class TestCaptionRechunkValid:
    def test_passes_for_short_well_formed_cues(self) -> None:
        cues = (Cue(1, 0.0, 2.0, "Curto."), Cue(2, 2.0, 4.0, "Também curto."))
        assert check_caption_rechunk_valid(cues).passed

    def test_fails_for_overlong_cue(self) -> None:
        cues = (Cue(1, 0.0, 5.0, "x" * 200),)
        assert not check_caption_rechunk_valid(cues).passed

    def test_fails_for_non_monotonic_cue(self) -> None:
        cues = (Cue(1, 5.0, 5.0, "erro"),)
        assert not check_caption_rechunk_valid(cues).passed


class TestCaptionStyleConfigValid:
    def test_default_style_is_valid(self) -> None:
        assert check_caption_style_config_valid(CaptionStyle()).passed

    def test_absurd_font_size_is_invalid(self) -> None:
        assert not check_caption_style_config_valid(CaptionStyle(font_size_fraction_of_height=0.5)).passed


class TestBurnedCaptionRenderStep:
    def test_passes_when_output_exists_and_size_differs(self, tmp_path: Path) -> None:
        pre = tmp_path / "pre.mp4"
        post = tmp_path / "post.mp4"
        pre.write_bytes(b"x" * 100)
        post.write_bytes(b"x" * 250)
        assert check_burned_caption_render_step(pre_burn_path=pre, post_burn_path=post).passed

    def test_fails_when_output_missing(self, tmp_path: Path) -> None:
        pre = tmp_path / "pre.mp4"
        pre.write_bytes(b"x")
        missing = tmp_path / "missing.mp4"
        assert not check_burned_caption_render_step(pre_burn_path=pre, post_burn_path=missing).passed


class TestBackgroundMusicMixStep:
    def test_passes_when_levels_differ(self) -> None:
        assert check_background_music_mix_step(narration_only_mean_db=-23.0, mixed_mean_db=-21.5).passed

    def test_fails_when_levels_identical(self) -> None:
        assert not check_background_music_mix_step(narration_only_mean_db=-23.0, mixed_mean_db=-23.0).passed


class TestCumulativeZoomProgression:
    """Gate 3D.2 §26 — substitui a pergunta "existe movimento configurado?"
    por "o zoom acumula pelo beat inteiro, sem reset entre segmentos?"."""

    def test_fails_for_old_default_plan_that_resets(self) -> None:
        plans = {"beat_26": build_default_retention_plan(36.5)}
        check = check_cumulative_zoom_progression(plans)
        assert not check.passed
        assert "beat_26" in check.detail

    def test_passes_for_new_continuous_plan(self) -> None:
        plans = {
            "beat_A": build_continuous_push_in_plan(21.8, total_zoom_ratio=0.12),
            "beat_26": build_continuous_push_in_plan(36.5, total_zoom_ratio=0.22, ease_in_out=True),
        }
        assert check_cumulative_zoom_progression(plans).passed

    def test_passes_for_single_segment_beats(self) -> None:
        plans = {"beat_D": build_default_retention_plan(6.0)}
        assert check_cumulative_zoom_progression(plans).passed

    def test_mixed_plans_fail_if_any_beat_resets(self) -> None:
        plans = {
            "good": build_continuous_push_in_plan(20.0, total_zoom_ratio=0.12),
            "bad": build_default_retention_plan(30.0),
        }
        check = check_cumulative_zoom_progression(plans)
        assert not check.passed
        assert "bad" in check.detail
        assert "good" not in check.detail


class TestMusicStemRelativeLevel:
    """Gate 3D.2 §25 — substitui o critério de nível médio da mixagem
    (provado insuficiente pelo feedback humano) por comparação stem-a-stem."""

    def test_passes_when_music_stem_clearly_subordinate_but_present(self) -> None:
        check = check_music_stem_relative_level(narration_stem_mean_db=-21.0, music_stem_mean_db_after_gain=-32.9)
        assert check.passed

    def test_fails_when_music_stem_effectively_silent(self) -> None:
        check = check_music_stem_relative_level(narration_stem_mean_db=-21.0, music_stem_mean_db_after_gain=-70.0)
        assert not check.passed

    def test_fails_when_music_stem_louder_than_narration(self) -> None:
        check = check_music_stem_relative_level(narration_stem_mean_db=-21.0, music_stem_mean_db_after_gain=-5.0)
        assert not check.passed
