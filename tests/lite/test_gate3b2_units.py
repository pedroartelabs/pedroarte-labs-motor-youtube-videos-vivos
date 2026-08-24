"""Gate 3B.2 — audita os artefatos reais da execução mais recente de
`run_gate3b2_full_narration.py`. Não testa naturalidade programaticamente
(Human Gate) — só integridade técnica: hash preservado, sem truncamento,
timing monotônico, recortes derivados do áudio completo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _latest_run_dir() -> Path | None:
    matches = sorted(Path("runs").glob("*-gate3b2-full-narration"))
    return matches[-1] if matches else None


@pytest.fixture()
def manifest() -> dict:
    run_dir = _latest_run_dir()
    if run_dir is None:
        pytest.skip("Nenhuma execução real do Gate 3B.2 disponível neste ambiente.")
    return json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))


class TestApprovedScriptIntegrity:
    def test_hash_matches_gate3b_approved_hash(self, manifest: dict) -> None:
        script_info = manifest["provenance"]["script"]
        assert script_info["hash_verified"] is True
        assert script_info["approved_script_hash"].startswith("sha256:")


class TestSelectedVoiceConfigurationPreserved:
    def test_voice_c_configuration_unchanged(self, manifest: dict) -> None:
        narration = manifest["provenance"]["narration"]
        assert narration["voice"] == "pt-BR-AntonioNeural"
        assert narration["rate"] == "+0%"
        assert narration["pitch"] == "+0Hz"
        assert narration["volume"] == "+0%"


class TestFullNarrationExists:
    def test_narration_full_artifact_recorded(self, manifest: dict) -> None:
        kinds = {a["kind"] for a in manifest["artifacts"]}
        assert "narration_full" in kinds
        narration_path = next(
            a["path"] for a in manifest["artifacts"] if a["kind"] == "narration_full"
        )
        assert Path(narration_path).exists()
        assert Path(narration_path).stat().st_size > 0

    def test_duration_measurable_and_within_target(self, manifest: dict) -> None:
        qa = manifest["qa"]["automated"]
        assert qa["duration_seconds"] > 0
        assert qa["duration_status"] == "WITHIN_TARGET"


class TestTimingData:
    def test_timing_json_parseable_and_present(self, manifest: dict) -> None:
        timing_path = next(
            a["path"] for a in manifest["artifacts"] if a["kind"] == "timing_data"
        )
        timing = json.loads(Path(timing_path).read_text(encoding="utf-8"))
        assert len(timing) > 0

    def test_timing_monotonically_increases(self, manifest: dict) -> None:
        timing_path = next(
            a["path"] for a in manifest["artifacts"] if a["kind"] == "timing_data"
        )
        timing = json.loads(Path(timing_path).read_text(encoding="utf-8"))
        starts = [b["start_seconds"] for b in timing]
        assert starts == sorted(starts)

    def test_last_boundary_within_tolerance_of_audio_duration(self, manifest: dict) -> None:
        completeness = manifest["provenance"]["timing"]
        assert completeness["alignment_within_tolerance"] is True
        assert (
            abs(completeness["last_boundary_end_seconds"] - completeness["actual_duration_seconds"])
            <= max(2.0, completeness["actual_duration_seconds"] * 0.05)
        )


class TestCompletenessCheck:
    def test_first_and_last_sentence_present(self, manifest: dict) -> None:
        completeness = manifest["provenance"]["timing"]
        assert completeness["first_sentence_present_in_first_boundary"] is True
        assert completeness["last_sentence_present_in_last_boundary"] is True
        assert completeness["status"] == "PASS"

    def test_boundary_count_matches_script_sentence_count(self, manifest: dict) -> None:
        completeness = manifest["provenance"]["timing"]
        assert completeness["boundary_count"] == completeness["script_sentence_count_approx"]


class TestReviewClipsOriginateFromFullNarration:
    def test_three_review_clips_exist(self, manifest: dict) -> None:
        review_kinds = {"review_clip_beginning", "review_clip_middle", "review_clip_end"}
        present = {a["kind"] for a in manifest["artifacts"]} & review_kinds
        assert present == review_kinds
        for artifact in manifest["artifacts"]:
            if artifact["kind"] in review_kinds:
                assert Path(artifact["path"]).exists()
                assert Path(artifact["path"]).stat().st_size > 0


class TestGate3CNotStarted:
    def test_no_image_or_video_artifacts_produced(self, manifest: dict) -> None:
        kinds = {a["kind"] for a in manifest["artifacts"]}
        assert not any("image" in k or "video" in k or "bundle" in k for k in kinds)
