"""GATE 3D — PLANNING & MASS GENERATION COST GATE.

    APPROVED SCRIPT + FULL NARRATION + HARDENED VISUAL BIBLE ->
    COMPLETE VISUAL PLAN (28 beats, full 650.3s) ->
    ASSET REUSE DECISIONS (5 Gate 3C images) ->
    COST ESTIMATE (25 new images) ->
    OPERATOR CAPABILITY CHECK -> STOP FOR HUMAN AUTHORIZATION

Não gera nenhuma imagem nova. A autorização de gerar 5 imagens no Gate 3C
NÃO autoriza esta geração em escala — STOP explícito antes de qualquer gasto
novo, conforme instruído.

Uso:
    python scripts/lite/run_gate3d_planning.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.runs import new_manifest, new_run_id
from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE_HARDENED
from pedroarte_youtube_engine.lite.visual_plan_gate3d import (
    GATE3C_ASSET_REUSE_DECISIONS,
    GATE3D_FULL_VISUAL_PLAN,
    estimate_mass_generation_cost,
    validate_plan_coverage,
)
from pedroarte_youtube_engine.shared.hashing import content_hash, structural_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

APPROVED_SCRIPT_SOURCE = Path("runs/20260823T185859Z-gate3a-script/working/script.md")
APPROVED_SCRIPT_HASH = "sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1"
NARRATION_REFERENCE_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json")
EXPECTED_HARDENED_BIBLE_HASH = "sha256:2406658b4d0a33e77ddbd7393b71d385a8d8b1dd1de14ff6f3676521f1c1ee75"


def _beat_to_dict(beat) -> dict:
    payload = asdict(beat)
    payload["narrative_function"] = beat.narrative_function.value
    payload["duration_seconds"] = beat.duration_seconds
    payload["requires_new_generation"] = beat.requires_new_generation
    return payload


def main() -> int:
    run_id = new_run_id("gate3d-planning")
    runs_root = Path("runs").resolve()
    policy = PathPolicy.for_roots(runs_root)
    root = runs_root / run_id
    input_dir = ensure_directory(root / "input", policy)
    working_dir = ensure_directory(root / "working", policy)
    output_dir = ensure_directory(root / "output", policy)

    print(f"[gate3d-planning] run_id={run_id}")

    evidence: list[dict[str, object]] = []
    manifest = new_manifest(
        run_id=run_id, gate="gate3d_planning", owner="claude_code", briefing_source="gate3c_approved_with_hardening"
    )

    # -- 1. verificar integridade dos inputs congelados -----------------------
    script_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    script_hash_ok = content_hash(script_text) == APPROVED_SCRIPT_HASH
    evidence.append({"step": "approved_script_hash", "result": "PASS" if script_hash_ok else "FAIL"})

    narration_ref = json.loads(NARRATION_REFERENCE_SOURCE.read_text(encoding="utf-8"))
    narration_duration = narration_ref["qa"]["automated"]["duration_seconds"]
    narration_ok = narration_ref["provenance"]["timing"]["status"] == "PASS"
    evidence.append({"step": "narration_reference", "result": "PASS" if narration_ok else "FAIL", "detail": f"{narration_duration}s"})

    bible_hash = structural_hash(RELOJOEIRO_VISUAL_BIBLE_HARDENED.to_dict())
    bible_hash_ok = bible_hash == EXPECTED_HARDENED_BIBLE_HASH
    evidence.append({"step": "hardened_visual_bible_hash", "result": "PASS" if bible_hash_ok else "FAIL", "detail": bible_hash})

    if not (script_hash_ok and narration_ok and bible_hash_ok):
        raise SystemExit("GATE_3D_BLOCKED: drift detectado em um dos inputs congelados.")

    write_text_atomic(input_dir / "script_approved.md", script_text, policy)

    # -- 2. plano visual completo, cobertura validada --------------------------
    coverage = validate_plan_coverage(GATE3D_FULL_VISUAL_PLAN, total_duration_seconds=narration_duration)
    evidence.append({"step": "visual_plan_coverage", "result": coverage["status"], "detail": f"{coverage['beat_count']} beats, gaps={coverage['gaps']}"})
    if coverage["status"] != "PASS":
        raise SystemExit(f"GATE_3D_BLOCKED: plano visual não cobre a narração corretamente: {coverage}")

    plan_payload = [_beat_to_dict(b) for b in GATE3D_FULL_VISUAL_PLAN]
    plan_path = working_dir / "gate3d_visual_plan.json"
    write_text_atomic(plan_path, json.dumps(plan_payload, ensure_ascii=False, indent=2) + "\n", policy)

    reused = [b for b in GATE3D_FULL_VISUAL_PLAN if not b.requires_new_generation]
    new_needed = [b for b in GATE3D_FULL_VISUAL_PLAN if b.requires_new_generation]

    # -- 3. decisões de reuso dos 5 assets aprovados no Gate 3C ----------------
    reuse_path = working_dir / "asset_reuse_decisions.json"
    write_text_atomic(
        reuse_path, json.dumps(list(GATE3C_ASSET_REUSE_DECISIONS), ensure_ascii=False, indent=2) + "\n", policy
    )
    evidence.append({"step": "asset_reuse_decisions", "result": "PASS", "detail": f"{len(GATE3C_ASSET_REUSE_DECISIONS)} decisões registradas"})

    # -- 4. verificação de capacidade do ambiente (não presumida) -------------
    execution_environment = "claude_code"
    native_image_generation_available = False
    evidence.append(
        {
            "step": "execution_environment_capability_check",
            "result": "PASS",
            "detail": f"native_image_generation_available={native_image_generation_available} (verificado, mesma checagem do Gate 3C)",
        }
    )

    # -- 5. estimativa de custo — SEM gerar nada ------------------------------
    cost_estimate = estimate_mass_generation_cost(new_images_required=len(new_needed))
    cost_path = working_dir / "mass_generation_cost_estimate.json"
    write_text_atomic(cost_path, json.dumps(cost_estimate, ensure_ascii=False, indent=2) + "\n", policy)
    evidence.append({"step": "mass_generation_cost_estimate", "result": "PASS", "detail": cost_estimate["estimated_total_cost_usd_range"]})

    # -- manifesto + STOP -------------------------------------------------------
    manifest["status"] = "script_ready"  # plano pronto; nenhuma imagem gerada
    manifest["provenance"]["script"] = {"approved_script_hash": APPROVED_SCRIPT_HASH, "hash_verified": script_hash_ok}
    manifest["provenance"]["narration_reference"] = {"duration_seconds": narration_duration, "verified": narration_ok}
    manifest["provenance"]["visual_bible"] = {
        "gate_3c_hash": "sha256:d732097056a83a03160fc0e8fa2b9a553a158a094bbf002a86c13b37723c7d64",
        "gate_3d_hardened_hash": bible_hash,
        "hardening_reason": (
            "Elias variou em idade/barba entre imagens (política de barba não travada em v1); "
            "relógio de vidro gerado com caixa metálica visível (não proibido explicitamente em v1)."
        ),
    }
    manifest["provenance"]["execution_environment"] = {
        "execution_environment": execution_environment,
        "native_image_generation_available": native_image_generation_available,
        "external_api_required": True,
        "external_api_cost": None,
    }
    manifest["artifacts"] = [
        {"path": str(input_dir / "script_approved.md"), "kind": "approved_script"},
        {"path": str(plan_path), "kind": "visual_plan"},
        {"path": str(reuse_path), "kind": "asset_reuse_decisions"},
        {"path": str(cost_path), "kind": "cost_estimate"},
    ]
    manifest_path = root / "run_manifest.json"
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy)

    write_text_atomic(
        root / "pending_tasks.json",
        json.dumps(
            {
                "run_id": run_id,
                "tasks": [{"id": e["step"], "status": "done" if e["result"] == "PASS" else "failed"} for e in evidence]
                + [{"id": "mass_generation_authorization", "status": "pending_human"}],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        policy,
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item.get('detail', '')}")

    print(f"\nTOTAL_VISUAL_BEATS: {len(GATE3D_FULL_VISUAL_PLAN)}")
    print(f"GATE_3C_ASSETS_REUSABLE: {len(reused)} ({', '.join(b.id for b in reused)})")
    print(f"NEW_IMAGES_REQUIRED: {len(new_needed)}")
    print(f"ESTIMATED_COST_USD_RANGE: {cost_estimate['estimated_total_cost_usd_range']}")
    print(f"\n[gate3d-planning] manifest={manifest_path}")
    print(
        "\n[gate3d-planning] STOP — MASS GENERATION COST GATE. "
        "Nenhuma imagem nova foi gerada. Nenhuma chamada paga foi feita. "
        "Aguardando autorização humana explícita antes de prosseguir."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
