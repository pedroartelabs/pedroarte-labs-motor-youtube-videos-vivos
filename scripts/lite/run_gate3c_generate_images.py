"""GATE 3C — Phase 2: materialização das 5 imagens do `image_manifest.json`.

Só executa depois de autorização humana explícita para a chamada paga
específica (registrada na conversa, não presumida). Uma geração por beat
(§32); retry só para falha técnica clara, máximo 2 tentativas (§33).

Uso:
    python scripts/lite/run_gate3c_generate_images.py <gate3c_run_id>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.image_qa import aspect_ratio_acceptable, probe_image
from pedroarte_youtube_engine.lite.images.openai_strategy import OpenAiImageStrategy
from pedroarte_youtube_engine.lite.images.ports import ImageGenerationRequest
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic

MAX_ATTEMPTS = 2


def main(run_id: str) -> int:
    runs_root = Path("runs").resolve()
    root = runs_root / run_id
    policy = PathPolicy.for_roots(root)
    manifest_path = root / "run_manifest.json"
    image_manifest_path = root / "working" / "image_manifest.json"
    output_dir = root / "output"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_requests = json.loads(image_manifest_path.read_text(encoding="utf-8"))

    strategy = OpenAiImageStrategy()
    results: list[dict[str, object]] = []
    qa_results: dict[str, object] = {}

    for entry in image_requests:
        beat_id = entry["beat_id"]
        output_path = Path(entry["output_path"])
        request = ImageGenerationRequest(
            prompt=entry["prompt"],
            output_path=output_path,
            width=entry["width"],
            height=entry["height"],
            negative_constraints=entry["negative_constraints"],
            style_prefix=entry["style_prefix"],
        )

        attempt = 0
        last_error = ""
        success = False
        generation_result = None
        while attempt < MAX_ATTEMPTS and not success:
            attempt += 1
            try:
                generation_result = strategy.generate(request)
                success = True
            except Exception as exc:
                last_error = str(exc)[:400]
                print(f"[gate3c] {beat_id} tentativa {attempt} falhou: {last_error}")
                time.sleep(2.0)

        qa = probe_image(output_path)
        qa_results[beat_id] = qa.as_dict()

        results.append(
            {
                "beat_id": beat_id,
                "output_path": str(output_path),
                "attempts": attempt,
                "success": success,
                "error": last_error if not success else "",
                "provider": generation_result.provider if generation_result else None,
                "model": generation_result.model if generation_result else None,
                "aspect_ratio_acceptable": aspect_ratio_acceptable(qa.aspect_ratio) if qa.opens else False,
            }
        )
        status = "PASS" if success and qa.opens else "FAIL"
        print(
            f"[gate3c] {beat_id}: {status} attempts={attempt} "
            f"{qa.width}x{qa.height} ({qa.format})"
        )

    manifest["provenance"]["execution_environment"]["method"] = "external_api:openai"
    manifest["provenance"]["execution_environment"]["external_api_cost"] = "observado na conta OpenAI, não retornado pela API de imagem"
    manifest["provenance"]["image_generation"] = results
    manifest["qa"]["automated"] = qa_results
    manifest["status"] = "images_ready"
    manifest["artifacts"].extend(
        [{"path": r["output_path"], "kind": f"image_{r['beat_id']}"} for r in results if r["success"]]
    )
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy)

    all_pass = all(r["success"] and qa_results[r["beat_id"]]["opens"] for r in results)

    review_lines = [
        "# Gate 3C — Human Visual Review",
        "",
        "5 imagens geradas a partir do image_manifest.json (Visual Bible Lite + 5 Visual Beats).",
        "",
    ]
    for r in results:
        review_lines.append(f"{r['beat_id']}: [{r['output_path']}]")
    review_lines += [
        "",
        "Evaluate together (not one by one):",
        "",
        "1. Individual Quality",
        "2. Same Production (as 5 parecem do mesmo vídeo?)",
        "3. Character Continuity (Elias / Mariana)",
        "4. Object Continuity (relógio de vidro)",
        "5. Environment Continuity (oficina / Portovelho)",
        "6. Narrative Fit",
        "7. Composition (espaço para Ken Burns em 16:9)",
        "8. AI Look (parece ilustração genérica de IA?)",
        "9. Visual Fatigue (a linguagem sustenta dezenas de frames?)",
        "10. Publication Question",
        "",
        "Verdict:",
        "",
        "HUMAN_PASS",
        "HUMAN_PASS_WITH_NOTES",
        "HUMAN_FAIL",
        "",
    ]
    review_path = output_dir / "HUMAN_VISUAL_REVIEW.md"
    write_text_atomic(review_path, "\n".join(review_lines), policy)

    print(f"\n[gate3c] all_images_pass={all_pass}")
    print(f"[gate3c] human review package={review_path}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else "20260823T203236Z-gate3c-visual-proof"
    raise SystemExit(main(run_id))
