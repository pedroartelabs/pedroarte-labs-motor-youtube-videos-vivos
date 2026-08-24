"""Gate 3D.1 SLICE B — lógica pura de planejamento de Retention Segments
(sem FFmpeg)."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.lite.retention import (
    MAX_TOTAL_ZOOM_DELTA,
    RetentionKind,
    build_continuous_push_in_plan,
    build_default_retention_plan,
    compute_zoom_delta,
    max_static_window_seconds,
    segments_share_continuous_trajectory,
)


class TestComputeZoomDelta:
    def test_scales_with_duration(self) -> None:
        assert compute_zoom_delta(5.0) < compute_zoom_delta(20.0)

    def test_never_exceeds_max_total_delta(self) -> None:
        assert compute_zoom_delta(1000.0) == MAX_TOTAL_ZOOM_DELTA

    def test_zero_duration_gives_zero_delta(self) -> None:
        assert compute_zoom_delta(0.0) == 0.0


class TestDefaultRetentionPlan:
    def test_short_beat_gets_single_segment(self) -> None:
        plan = build_default_retention_plan(6.0)
        assert len(plan) == 1
        assert plan[0].duration_seconds == 6.0
        assert plan[0].kind is RetentionKind.ZOOM_IN

    def test_plan_duration_sums_to_beat_duration(self) -> None:
        for duration in (11.6, 21.8, 29.6, 36.5, 6.8):
            plan = build_default_retention_plan(duration)
            assert sum(s.duration_seconds for s in plan) == pytest.approx(duration, abs=0.01)

    def test_long_beat_is_subdivided(self) -> None:
        plan = build_default_retention_plan(36.5)
        assert len(plan) >= 4

    def test_long_beat_alternates_kinds(self) -> None:
        plan = build_default_retention_plan(30.0)
        kinds = [s.kind for s in plan]
        assert len(set(kinds)) >= 2, "beat longo deve variar o tipo de retenção, não repetir sempre o mesmo"

    def test_pan_segments_stay_within_safe_margin_fraction(self) -> None:
        plan = build_default_retention_plan(30.0)
        for segment in plan:
            if segment.kind in (RetentionKind.PAN, RetentionKind.REFRAME):
                assert -1.0 <= segment.pan_dx_fraction <= 1.0
                assert -1.0 <= segment.pan_dy_fraction <= 1.0

    def test_zoom_in_segments_increase_scale(self) -> None:
        plan = build_default_retention_plan(30.0)
        for segment in plan:
            if segment.kind is RetentionKind.ZOOM_IN:
                assert segment.end_scale >= segment.start_scale

    def test_zoom_out_segments_decrease_scale(self) -> None:
        plan = build_default_retention_plan(30.0)
        for segment in plan:
            if segment.kind is RetentionKind.ZOOM_OUT:
                assert segment.end_scale <= segment.start_scale


class TestMaxStaticWindow:
    def test_matches_longest_segment(self) -> None:
        plan = build_default_retention_plan(36.5)
        window = max_static_window_seconds(plan)
        assert window == max(s.duration_seconds for s in plan)

    def test_contemplative_segments_excluded(self) -> None:
        plan = build_default_retention_plan(9.0)  # single contemplative-eligible segment
        assert len(plan) == 1
        if plan[0].contemplative:
            assert max_static_window_seconds(plan) == 0.0


class TestSegmentsShareContinuousTrajectory:
    """Gate 3D.2 §10 — achado de investigação: o plano ANTIGO reseta a escala
    entre segmentos; o plano NOVO (contínuo) não reseta."""

    def test_default_plan_resets_scale_between_segments(self) -> None:
        plan = build_default_retention_plan(36.5)
        assert len(plan) > 1
        assert not segments_share_continuous_trajectory(plan)

    def test_single_segment_plan_is_trivially_continuous(self) -> None:
        plan = build_default_retention_plan(6.0)
        assert segments_share_continuous_trajectory(plan)

    def test_continuous_push_in_plan_never_resets_scale(self) -> None:
        for duration in (11.6, 21.8, 23.9, 29.6, 36.5):
            plan = build_continuous_push_in_plan(duration, total_zoom_ratio=0.12)
            assert segments_share_continuous_trajectory(plan), f"reset detectado para duration={duration}"


class TestContinuousPushInPlan:
    def test_plan_duration_sums_to_beat_duration(self) -> None:
        for duration in (11.6, 21.8, 23.9, 29.6, 36.5):
            plan = build_continuous_push_in_plan(duration, total_zoom_ratio=0.12)
            assert sum(s.duration_seconds for s in plan) == pytest.approx(duration, abs=0.01)

    def test_first_segment_starts_at_scale_one(self) -> None:
        plan = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12)
        assert plan[0].start_scale == pytest.approx(1.0)

    def test_last_segment_ends_at_target_total_zoom_ratio(self) -> None:
        plan = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12)
        assert plan[-1].end_scale == pytest.approx(1.12)

    def test_scale_is_monotonically_non_decreasing_across_whole_beat(self) -> None:
        plan = build_continuous_push_in_plan(36.5, total_zoom_ratio=0.22)
        scales = [plan[0].start_scale] + [s.end_scale for s in plan]
        assert scales == sorted(scales), "push-in contínuo não deve nunca recuar em escala"

    def test_stronger_ratio_ends_more_zoomed_than_moderate_ratio(self) -> None:
        moderate = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12)
        strong = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.22)
        assert strong[-1].end_scale > moderate[-1].end_scale

    def test_short_beat_still_produces_at_least_one_segment(self) -> None:
        plan = build_continuous_push_in_plan(6.0, total_zoom_ratio=0.12)
        assert len(plan) >= 1
        assert plan[0].duration_seconds == pytest.approx(6.0)


class TestContinuousPushInPlanEasing:
    """Gate 3D.2 — feedback humano: curva suave em vez de linear, aplicada
    na trajetória GLOBAL do beat (não por chunk, para não reintroduzir uma
    parada de velocidade a cada ~7s)."""

    def test_eased_plan_still_never_resets_scale(self) -> None:
        plan = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12, ease_in_out=True)
        assert segments_share_continuous_trajectory(plan)

    def test_eased_plan_reaches_same_final_scale_as_linear(self) -> None:
        linear = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12, ease_in_out=False)
        eased = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12, ease_in_out=True)
        assert eased[-1].end_scale == pytest.approx(linear[-1].end_scale)

    def test_eased_plan_starts_slower_than_linear(self) -> None:
        linear = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12, ease_in_out=False)
        eased = build_continuous_push_in_plan(30.0, total_zoom_ratio=0.12, ease_in_out=True)
        assert eased[0].zoom_delta < linear[0].zoom_delta

    def test_eased_plan_scale_is_monotonically_non_decreasing(self) -> None:
        plan = build_continuous_push_in_plan(36.5, total_zoom_ratio=0.22, ease_in_out=True)
        scales = [plan[0].start_scale] + [s.end_scale for s in plan]
        assert scales == sorted(scales)
