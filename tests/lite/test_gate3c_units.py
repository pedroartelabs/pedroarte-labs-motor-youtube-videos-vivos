"""Gate 3C — Visual Bible, Visual Beats, image manifest e auditoria da
execução real mais recente. Não testa estética (naturalidade/consistência
percebida é Human Gate) — só forma de dados, timing dentro da narração real,
e integridade do manifesto/artefatos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.image_qa import aspect_ratio_acceptable
from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE
from pedroarte_youtube_engine.lite.visual_beats import FIVE_SELECTED_BEATS, NarrativeFunction
from pedroarte_youtube_engine.lite.visual_prompt import build_image_request

NARRATION_DURATION_SECONDS = 650.3  # Gate 3B.2, fonte de verdade real


class TestVisualBible:
    def test_has_at_least_the_two_recurring_characters(self) -> None:
        names = {c.name for c in RELOJOEIRO_VISUAL_BIBLE.characters}
        assert {"Elias Varga", "Mariana Duarte"} <= names

    def test_hero_object_is_the_glass_watch(self) -> None:
        assert "vidro" in RELOJOEIRO_VISUAL_BIBLE.hero_object.name.lower()

    def test_forbidden_elements_cover_must_avoid_from_briefing(self) -> None:
        forbidden = " ".join(RELOJOEIRO_VISUAL_BIBLE.forbidden_elements).lower()
        assert "marca" in forbidden
        assert "violência" in forbidden or "violencia" in forbidden

    def test_global_style_prefix_is_non_empty_and_concrete(self) -> None:
        prefix = RELOJOEIRO_VISUAL_BIBLE.global_style_prefix()
        assert len(prefix) > 20
        assert "âmbar" in prefix.lower() or "ambar" in prefix.lower()


class TestVisualBeats:
    def test_exactly_five_beats(self) -> None:
        assert len(FIVE_SELECTED_BEATS) == 5

    def test_all_beats_start_before_end(self) -> None:
        for beat in FIVE_SELECTED_BEATS:
            assert beat.start_seconds < beat.end_seconds

    def test_all_beats_within_real_narration_duration(self) -> None:
        for beat in FIVE_SELECTED_BEATS:
            assert beat.end_seconds <= NARRATION_DURATION_SECONDS

    def test_beats_cover_diverse_narrative_functions(self) -> None:
        functions = {beat.narrative_function for beat in FIVE_SELECTED_BEATS}
        assert len(functions) >= 4, "Os 5 beats devem testar funções narrativas diferentes."

    def test_hero_object_and_both_characters_are_referenced_across_beats(self) -> None:
        all_refs = {ref for beat in FIVE_SELECTED_BEATS for ref in beat.continuity_refs}
        assert "Elias Varga" in all_refs
        assert "Mariana Duarte" in all_refs
        assert RELOJOEIRO_VISUAL_BIBLE.hero_object.name in all_refs

    def test_resolution_beat_echoes_establishing_beat(self) -> None:
        """Beat E é um callback deliberado do Beat B (mesma vitrine) — confere
        que os continuity_refs realmente se sobrepõem."""
        beat_b = next(b for b in FIVE_SELECTED_BEATS if b.id == "beat_B")
        beat_e = next(b for b in FIVE_SELECTED_BEATS if b.id == "beat_E")
        assert set(beat_b.continuity_refs) & set(beat_e.continuity_refs)


class TestPromptBuilder:
    def test_prompt_includes_scene_and_continuity_and_composition(self, tmp_path: Path) -> None:
        beat = FIVE_SELECTED_BEATS[0]
        request = build_image_request(
            bible=RELOJOEIRO_VISUAL_BIBLE, beat=beat, output_path=tmp_path / "x.png"
        )
        assert "CENA:" in request.prompt
        assert "CONTINUIDADE:" in request.prompt
        assert "COMPOSIÇÃO:" in request.prompt
        assert request.style_prefix == RELOJOEIRO_VISUAL_BIBLE.global_style_prefix()

    def test_negative_constraints_include_forbidden_elements(self, tmp_path: Path) -> None:
        beat = FIVE_SELECTED_BEATS[0]
        request = build_image_request(
            bible=RELOJOEIRO_VISUAL_BIBLE, beat=beat, output_path=tmp_path / "x.png"
        )
        assert "marcas registradas" in request.negative_constraints

    def test_aspect_ratio_16_9_default(self, tmp_path: Path) -> None:
        beat = FIVE_SELECTED_BEATS[0]
        request = build_image_request(
            bible=RELOJOEIRO_VISUAL_BIBLE, beat=beat, output_path=tmp_path / "x.png"
        )
        assert request.width / request.height == pytest.approx(16 / 9, abs=0.01)


class TestAspectRatioAcceptable:
    def test_true_16_9_is_acceptable(self) -> None:
        assert aspect_ratio_acceptable(1920 / 1080)

    def test_openai_landscape_1536x1024_is_3_2_not_16_9(self) -> None:
        """A API da OpenAI não oferece um tamanho nativo 16:9 — o maior
        'landscape' disponível (1536x1024) é 3:2 (1.5), fora da tolerância de
        16:9 (1.778). Registrado como limitação real (Gate 3C §41), não
        escondido: o pipeline de montagem (FFmpeg, Gate 3D) precisa recortar
        ou preencher para chegar a 16:9 final."""
        assert not aspect_ratio_acceptable(1536 / 1024)

    def test_square_is_not_acceptable(self) -> None:
        assert not aspect_ratio_acceptable(1.0)


def _latest_gate3c_run() -> Path | None:
    matches = sorted(Path("runs").glob("*-gate3c-visual-proof"))
    return matches[-1] if matches else None


class TestRealRunArtifacts:
    """Audita a execução real mais recente do Gate 3C, sem regenerar nada."""

    def test_image_manifest_has_five_entries_matching_beats(self) -> None:
        run_dir = _latest_gate3c_run()
        if run_dir is None:
            pytest.skip("Nenhuma execução real do Gate 3C disponível neste ambiente.")
        manifest = json.loads((run_dir / "working" / "image_manifest.json").read_text(encoding="utf-8"))
        assert len(manifest) == 5
        assert {e["beat_id"] for e in manifest} == {b.id for b in FIVE_SELECTED_BEATS}

    def test_all_manifest_outputs_exist_and_are_non_empty(self) -> None:
        run_dir = _latest_gate3c_run()
        if run_dir is None:
            pytest.skip("Nenhuma execução real do Gate 3C disponível neste ambiente.")
        manifest = json.loads((run_dir / "working" / "image_manifest.json").read_text(encoding="utf-8"))
        run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        if "image_generation" not in run_manifest["provenance"]:
            pytest.skip("Imagens ainda não materializadas nesta execução (fase manifesto apenas).")
        for entry in manifest:
            path = Path(entry["output_path"])
            assert path.exists() and path.stat().st_size > 0

    def test_gate_3d_not_started(self) -> None:
        run_dir = _latest_gate3c_run()
        if run_dir is None:
            pytest.skip("Nenhuma execução real do Gate 3C disponível neste ambiente.")
        run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        kinds = {a["kind"] for a in run_manifest["artifacts"]}
        assert not any("video" in k or "bundle" in k or "thumbnail" in k for k in kinds)
