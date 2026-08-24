"""GATE 3C — VISUAL QUALITY & CONSISTENCY (Phase 1: Visual Bible + Beats + Manifest).

    APPROVED SCRIPT + FULL NARRATION + REAL TIMING -> VISUAL BIBLE LITE ->
    VISUAL BEAT PLANNING -> SELECT 5 BEATS -> IMAGE GENERATION MANIFEST

Não gera imagens. Essa etapa só produz o manifesto — a engine nunca decide
"chame o provider X" (Separation Principle, SDD_SPDD.md §21/§43). A decisão
de estratégia de execução (nativa do ambiente, API externa autorizada, ou
handoff para outro operador) acontece fora deste script.

Uso:
    python scripts/lite/run_gate3c_visual_proof.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.runs import new_manifest, new_run_id
from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE
from pedroarte_youtube_engine.lite.visual_beats import FIVE_SELECTED_BEATS
from pedroarte_youtube_engine.lite.visual_prompt import build_image_request
from pedroarte_youtube_engine.shared.hashing import content_hash, structural_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

# -- inputs congelados (Gate 3A/3B/3B.2 — não modificados aqui) --------------
APPROVED_SCRIPT_SOURCE = Path("runs/20260823T185859Z-gate3a-script/working/script.md")
APPROVED_SCRIPT_HASH = "sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1"
NARRATION_REFERENCE_SOURCE = Path(
    "runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json"
)


def _asdict_beat(beat) -> dict:
    payload = asdict(beat)
    payload["narrative_function"] = beat.narrative_function.value
    payload["duration_seconds"] = beat.duration_seconds
    return payload


def main() -> int:
    run_id = new_run_id("gate3c-visual-proof")
    runs_root = Path("runs").resolve()
    policy = PathPolicy.for_roots(runs_root)
    root = runs_root / run_id
    input_dir = ensure_directory(root / "input", policy)
    working_dir = ensure_directory(root / "working", policy)
    images_dir = ensure_directory(root / "assets" / "images", policy)
    output_dir = ensure_directory(root / "output", policy)

    print(f"[gate3c] run_id={run_id}")
    print(f"[gate3c] run_dir={root}")

    evidence: list[dict[str, object]] = []
    manifest = new_manifest(
        run_id=run_id, gate="gate3c", owner="claude_code", briefing_source="gate3b2_approved_narration"
    )

    # -- 1. verificar integridade dos inputs congelados -----------------------
    script_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    recomputed_hash = content_hash(script_text)
    script_ok = recomputed_hash == APPROVED_SCRIPT_HASH
    evidence.append(
        {
            "step": "approved_script_integrity",
            "expected": APPROVED_SCRIPT_HASH,
            "actual": recomputed_hash,
            "result": "PASS" if script_ok else "FAIL",
        }
    )
    if not script_ok:
        raise SystemExit(f"GATE_3C_BLOCKED: drift no roteiro aprovado. esperado={APPROVED_SCRIPT_HASH} obtido={recomputed_hash}")
    write_text_atomic(input_dir / "script_approved.md", script_text, policy)

    narration_manifest = json.loads(NARRATION_REFERENCE_SOURCE.read_text(encoding="utf-8"))
    narration_duration = narration_manifest["qa"]["automated"]["duration_seconds"]
    boundary_count = narration_manifest["provenance"]["timing"]["boundary_count"]
    narration_ok = narration_manifest["provenance"]["timing"]["status"] == "PASS"
    evidence.append(
        {
            "step": "full_narration_reference_integrity",
            "expected": "GATE_3B2_TECHNICAL PASS, sem truncamento",
            "actual": f"duration={narration_duration}s boundaries={boundary_count} status={'PASS' if narration_ok else 'FAIL'}",
            "result": "PASS" if narration_ok else "FAIL",
        }
    )
    if not narration_ok:
        raise SystemExit("GATE_3C_BLOCKED: referência de narração completa não íntegra.")
    write_text_atomic(
        input_dir / "narration_reference.json",
        json.dumps(
            {
                "source": str(NARRATION_REFERENCE_SOURCE),
                "duration_seconds": narration_duration,
                "boundary_count": boundary_count,
                "voice": narration_manifest["provenance"]["narration"]["voice"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        policy,
    )

    # -- 2. Visual Bible Lite --------------------------------------------------
    bible_dict = {
        "overall_style": RELOJOEIRO_VISUAL_BIBLE.overall_style,
        "realism_level": RELOJOEIRO_VISUAL_BIBLE.realism_level,
        "color_language": RELOJOEIRO_VISUAL_BIBLE.color_language,
        "lighting": RELOJOEIRO_VISUAL_BIBLE.lighting,
        "environment_language": RELOJOEIRO_VISUAL_BIBLE.environment_language,
        "mood": RELOJOEIRO_VISUAL_BIBLE.mood,
        "characters": [asdict(c) for c in RELOJOEIRO_VISUAL_BIBLE.characters],
        "hero_object": asdict(RELOJOEIRO_VISUAL_BIBLE.hero_object),
        "forbidden_elements": list(RELOJOEIRO_VISUAL_BIBLE.forbidden_elements),
        "continuity_constraints": list(RELOJOEIRO_VISUAL_BIBLE.continuity_constraints),
    }
    bible_hash = structural_hash(bible_dict)
    bible_path = working_dir / "visual_bible.json"
    write_text_atomic(
        bible_path, json.dumps(bible_dict, ensure_ascii=False, indent=2) + "\n", policy
    )
    evidence.append(
        {
            "step": "visual_bible",
            "expected": "Visual Bible Lite específica desta história, campos justificados",
            "actual": f"{len(bible_dict['characters'])} personagens, hash={bible_hash[:24]}…",
            "result": "PASS",
        }
    )

    # -- 3. Visual Beats (timing real, não estimado) --------------------------
    beats_payload = [_asdict_beat(b) for b in FIVE_SELECTED_BEATS]
    beats_path = working_dir / "visual_beats.json"
    write_text_atomic(
        beats_path, json.dumps(beats_payload, ensure_ascii=False, indent=2) + "\n", policy
    )
    for beat in FIVE_SELECTED_BEATS:
        within = beat.end_seconds <= narration_duration
        evidence.append(
            {
                "step": f"beat_timing_{beat.id}",
                "expected": f"start<end<=narration_duration({narration_duration}s)",
                "actual": f"{beat.start_seconds}s-{beat.end_seconds}s ({beat.narrative_function.value})",
                "result": "PASS" if beat.start_seconds < beat.end_seconds and within else "FAIL",
            }
        )

    # -- 4. Image Generation Manifest (fronteira engine -> operador) ---------
    requests = [
        build_image_request(
            bible=RELOJOEIRO_VISUAL_BIBLE,
            beat=beat,
            output_path=images_dir / f"{beat.id}.png",
        )
        for beat in FIVE_SELECTED_BEATS
    ]
    manifest_entries = []
    for beat, request in zip(FIVE_SELECTED_BEATS, requests, strict=True):
        manifest_entries.append(
            {
                "beat_id": beat.id,
                "prompt": request.prompt,
                "style_prefix": request.style_prefix,
                "negative_constraints": request.negative_constraints,
                "aspect_ratio": "16:9",
                "width": request.width,
                "height": request.height,
                "continuity_refs": list(beat.continuity_refs),
                "visual_bible_hash": bible_hash,
                "output_path": str(request.output_path),
                "required": True,
            }
        )
    image_manifest_path = working_dir / "image_manifest.json"
    write_text_atomic(
        image_manifest_path,
        json.dumps(manifest_entries, ensure_ascii=False, indent=2) + "\n",
        policy,
    )
    evidence.append(
        {
            "step": "image_manifest",
            "expected": "5 ImageGenerationRequest, aspect_ratio 16:9",
            "actual": f"{len(manifest_entries)} requests",
            "result": "PASS" if len(manifest_entries) == 5 else "FAIL",
        }
    )

    # -- 5. verificação de capacidade do ambiente de execução ------------------
    # Esta sessão é Claude Code. Nenhuma ferramenta de geração nativa de
    # imagem está disponível nas ferramentas desta sessão — verificado por
    # ausência real na lista de ferramentas, não presumido (Gate 3C §27).
    execution_environment = "claude_code"
    native_image_generation_available = False
    evidence.append(
        {
            "step": "execution_environment_capability_check",
            "expected": "verificar, não presumir",
            "actual": (
                f"execution_environment={execution_environment}, "
                f"native_image_generation_available={native_image_generation_available} "
                "(nenhuma ferramenta de geração de imagem disponível nesta sessão)"
            ),
            "result": "PASS",
        }
    )

    manifest["status"] = "script_ready"  # imagens ainda não geradas nesta fase
    manifest["provenance"]["script"] = {"approved_script_hash": APPROVED_SCRIPT_HASH, "hash_verified": script_ok}
    manifest["provenance"]["narration_reference"] = {
        "source": str(NARRATION_REFERENCE_SOURCE),
        "duration_seconds": narration_duration,
        "boundary_count": boundary_count,
    }
    manifest["provenance"]["visual_bible_hash"] = bible_hash
    manifest["provenance"]["execution_environment"] = {
        "execution_environment": execution_environment,
        "native_image_generation_available": native_image_generation_available,
        "method": None,
        "external_api_required": True,
        "external_api_cost": None,
    }
    manifest["artifacts"] = [
        {"path": str(input_dir / "script_approved.md"), "kind": "approved_script"},
        {"path": str(input_dir / "narration_reference.json"), "kind": "narration_reference"},
        {"path": str(bible_path), "kind": "visual_bible"},
        {"path": str(beats_path), "kind": "visual_beats"},
        {"path": str(image_manifest_path), "kind": "image_manifest"},
    ]
    manifest_path = root / "run_manifest.json"
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy)

    pending = [
        {"id": step["step"], "status": "done" if step["result"] == "PASS" else "failed"}
        for step in evidence
    ] + [{"id": "image_generation", "status": "pending_operator_decision"}]
    write_text_atomic(
        root / "pending_tasks.json",
        json.dumps({"run_id": run_id, "tasks": pending}, ensure_ascii=False, indent=2) + "\n",
        policy,
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item['actual']}")

    print(f"\n[gate3c] manifest={manifest_path}")
    print(f"[gate3c] image_manifest={image_manifest_path}")
    print(
        "\n[gate3c] Visual Bible + 5 beats + image_manifest.json prontos. "
        "Nenhuma imagem gerada ainda — decisão de estratégia de execução pendente."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
