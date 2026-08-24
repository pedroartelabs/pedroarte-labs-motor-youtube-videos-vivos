"""Gate 3D — plano visual completo, decisões de reuso e o Cost Gate. Não
testa estética/geração — só integridade estrutural do plano e da política de
reuso, e a auditoria da execução de planejamento real mais recente."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.visual_bible import (
    RELOJOEIRO_VISUAL_BIBLE,
    RELOJOEIRO_VISUAL_BIBLE_HARDENED,
)
from pedroarte_youtube_engine.lite.visual_plan_gate3d import (
    GATE3C_ASSET_REUSE_DECISIONS,
    GATE3D_FULL_VISUAL_PLAN,
    estimate_mass_generation_cost,
    validate_plan_coverage,
)

NARRATION_DURATION_SECONDS = 650.3


class TestFullVisualPlanCoverage:
    def test_covers_full_narration_without_gaps(self) -> None:
        report = validate_plan_coverage(
            GATE3D_FULL_VISUAL_PLAN, total_duration_seconds=NARRATION_DURATION_SECONDS
        )
        assert report["status"] == "PASS"
        assert report["gaps"] == []

    def test_beats_are_chronologically_ordered(self) -> None:
        starts = [b.start_seconds for b in GATE3D_FULL_VISUAL_PLAN]
        assert starts == sorted(starts)

    def test_all_beats_start_before_end(self) -> None:
        for beat in GATE3D_FULL_VISUAL_PLAN:
            assert beat.start_seconds < beat.end_seconds

    def test_count_is_not_a_fixed_target_but_derived(self) -> None:
        """Não deve ser um número redondo/arbitrário como 20 ou 30 exato por
        design — deve ser o que sobrou de agrupar 99 sentenças reais."""
        assert 15 <= len(GATE3D_FULL_VISUAL_PLAN) <= 40


class TestGate3CReuse:
    def test_five_gate3c_beats_are_marked_for_reuse(self) -> None:
        reused = [b for b in GATE3D_FULL_VISUAL_PLAN if not b.requires_new_generation]
        assert {b.id for b in reused} == {"beat_A", "beat_B", "beat_C", "beat_D", "beat_E"}

    def test_reused_beats_reference_themselves(self) -> None:
        for beat in GATE3D_FULL_VISUAL_PLAN:
            if beat.reuse_of is not None:
                assert beat.reuse_of == beat.id

    def test_new_generation_count_matches_total_minus_reused(self) -> None:
        total = len(GATE3D_FULL_VISUAL_PLAN)
        reused = sum(1 for b in GATE3D_FULL_VISUAL_PLAN if not b.requires_new_generation)
        new_needed = sum(1 for b in GATE3D_FULL_VISUAL_PLAN if b.requires_new_generation)
        assert reused + new_needed == total


class TestAssetReuseDecisions:
    def test_all_five_gate3c_assets_have_a_recorded_decision(self) -> None:
        ids = {d["beat_id"] for d in GATE3C_ASSET_REUSE_DECISIONS}
        assert ids == {"beat_A", "beat_B", "beat_C", "beat_D", "beat_E"}

    def test_no_asset_is_auto_rejected(self) -> None:
        """Regra explícita: não rejeitar automaticamente por causa de um
        desvio histórico que motivou o endurecimento."""
        for decision in GATE3C_ASSET_REUSE_DECISIONS:
            assert decision["decision"] == "REUSE"

    def test_beats_with_historical_deviation_are_flagged_not_hidden(self) -> None:
        flagged = {d["beat_id"] for d in GATE3C_ASSET_REUSE_DECISIONS if d["flag"] != "nenhum"}
        assert flagged == {"beat_A", "beat_D"}


class TestCostEstimate:
    def test_estimate_scales_with_new_images_required(self) -> None:
        small = estimate_mass_generation_cost(new_images_required=5)
        large = estimate_mass_generation_cost(new_images_required=25)
        assert large["estimated_total_cost_usd_range"][1] > small["estimated_total_cost_usd_range"][1]

    def test_estimate_never_claims_exact_api_price(self) -> None:
        estimate = estimate_mass_generation_cost(new_images_required=25)
        assert "note" in estimate
        assert "não" in estimate["note"].lower() or "nao" in estimate["note"].lower()


class TestVisualBibleUsedForPlanning:
    def test_plan_uses_hardened_bible_not_v1(self) -> None:
        assert RELOJOEIRO_VISUAL_BIBLE_HARDENED.version == "v2_gate3d_hardened"
        assert RELOJOEIRO_VISUAL_BIBLE.version == "v1_gate3c"


def _latest_gate3d_planning_run() -> Path | None:
    matches = sorted(Path("runs").glob("*-gate3d-planning"))
    return matches[-1] if matches else None


class TestRealPlanningRunArtifacts:
    def test_no_images_generated_by_this_session_paid_api(self) -> None:
        """A sessão nunca chamou uma API paga para o Gate 3D — as imagens
        presentes (se houver) vieram do handoff externo (custo zero para
        esta sessão) ou foram copiadas do Gate 3C já aprovado."""
        run_dir = _latest_gate3d_planning_run()
        if run_dir is None:
            pytest.skip("Nenhuma execução real de planejamento do Gate 3D disponível.")
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        handoff = manifest["provenance"].get("image_generation_handoff")
        if handoff is not None:
            assert handoff["external_api_cost_this_session"] == 0.0

    def test_manifest_records_cost_estimate_not_actual_spend(self) -> None:
        run_dir = _latest_gate3d_planning_run()
        if run_dir is None:
            pytest.skip("Nenhuma execução real de planejamento do Gate 3D disponível.")
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["provenance"]["execution_environment"]["external_api_cost"] is None
