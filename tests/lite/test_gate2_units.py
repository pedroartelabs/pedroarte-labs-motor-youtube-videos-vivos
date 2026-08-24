"""Gate 2 — unidades puras (SDD_SPDD.md §11: "proteger o cano", não maximizar
número de testes). Não chama SAPI5/GDI+/FFmpeg — isso é coberto pela prova de
integração real em `scripts/lite/run_gate2_proof.py` (smoke test, não pytest,
porque depende de binários externos ao Python)."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.lite.qa import QaCheck, QaReport
from pedroarte_youtube_engine.lite.runs import RunStatus, new_run_id
from pedroarte_youtube_engine.lite.timeline import (
    build_proportional_timeline,
    build_single_beat_timeline,
)


class TestTimeline:
    def test_single_beat_covers_full_narration_duration(self) -> None:
        (beat,) = build_single_beat_timeline(image_path="img.png", narration_duration_seconds=42.5)
        assert beat.start_seconds == 0.0
        assert beat.end_seconds == 42.5
        assert beat.duration_seconds == 42.5

    def test_single_beat_rejects_non_positive_duration(self) -> None:
        with pytest.raises(ValueError):
            build_single_beat_timeline(image_path="img.png", narration_duration_seconds=0.0)

    def test_proportional_timeline_splits_by_word_share(self) -> None:
        beats = build_proportional_timeline(
            image_paths=("a.png", "b.png"),
            beat_word_counts=(10, 30),
            total_duration_seconds=40.0,
        )
        assert beats[0].duration_seconds == pytest.approx(10.0)
        assert beats[1].duration_seconds == pytest.approx(30.0)
        assert beats[1].start_seconds == pytest.approx(beats[0].end_seconds)

    def test_proportional_timeline_rejects_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError):
            build_proportional_timeline(
                image_paths=("a.png",),
                beat_word_counts=(10, 30),
                total_duration_seconds=40.0,
            )


class TestQaReport:
    def test_report_passes_only_when_all_checks_pass(self) -> None:
        report = QaReport(checks=[QaCheck("a", True), QaCheck("b", True)])
        assert report.passed is True

    def test_report_fails_when_any_check_fails(self) -> None:
        report = QaReport(checks=[QaCheck("a", True), QaCheck("b", False, "detail")])
        assert report.passed is False
        assert report.as_dict()["passed"] is False


class TestRunId:
    def test_new_run_id_contains_timestamp_and_slug(self) -> None:
        run_id = new_run_id("gate2-proof")
        assert run_id.endswith("-gate2-proof")
        assert "T" in run_id and run_id.endswith("Z-gate2-proof")

    def test_run_status_has_gate2_terminal_states(self) -> None:
        assert RunStatus.QA_PASSED.value == "qa_passed"
        assert RunStatus.QA_FAILED.value == "qa_failed"
