"""GATE 3D — IMAGE GENERATION HANDOFF (custo zero para esta sessão).

Em vez de chamar a API paga diretamente, produz o manifesto + o pacote de
instruções para que o operador humano gere as 25 imagens novas externamente
(qualquer ferramenta, zero custo para esta sessão) e as coloque no diretório
esperado. Quando prontas, a execução retoma a partir daí — sem depender de
memória desta conversa (Handoff Contract, OPERATOR_CONTRACT.md).

Não gera nenhuma imagem. Não chama nenhuma API.

Uso:
    python scripts/lite/run_gate3d_handoff.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE_HARDENED
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.lite.visual_prompt import build_image_request
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

GATE3D_RUN_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()


def main() -> int:
    policy = PathPolicy.for_roots(GATE3D_RUN_DIR)
    images_dir = ensure_directory(GATE3D_RUN_DIR / "assets" / "images", policy)
    working_dir = GATE3D_RUN_DIR / "working"
    output_dir = GATE3D_RUN_DIR / "output"

    new_beats = [b for b in GATE3D_FULL_VISUAL_PLAN if b.requires_new_generation]

    manifest_entries = []
    for beat in new_beats:
        output_path = images_dir / f"{beat.id}.png"
        request = build_image_request(
            bible=RELOJOEIRO_VISUAL_BIBLE_HARDENED, beat=beat, output_path=output_path
        )
        manifest_entries.append(
            {
                "beat_id": beat.id,
                "start_seconds": beat.start_seconds,
                "end_seconds": beat.end_seconds,
                "narrative_function": beat.narrative_function.value,
                "prompt": request.prompt,
                "style_prefix": request.style_prefix,
                "full_prompt": f"{request.style_prefix}\n\n{request.prompt}\n\nEVITAR: {request.negative_constraints}",
                "negative_constraints": request.negative_constraints,
                "aspect_ratio": "16:9",
                "width": request.width,
                "height": request.height,
                "continuity_refs": list(beat.continuity_refs),
                "visual_bible_version": RELOJOEIRO_VISUAL_BIBLE_HARDENED.version,
                "output_path": str(output_path),
                "required": True,
            }
        )

    manifest_path = working_dir / "image_manifest_gate3d.json"
    write_text_atomic(
        manifest_path, json.dumps(manifest_entries, ensure_ascii=False, indent=2) + "\n", policy
    )

    # -- pacote humano legível ---------------------------------------------
    lines: list[str] = [
        "# GATE 3D — GENERATE THESE IMAGES (handoff, custo zero para esta sessão)",
        "",
        f"25 imagens novas, uma por beat. Visual Bible: `{RELOJOEIRO_VISUAL_BIBLE_HARDENED.version}` "
        "(endurecida — sem barba em Elias, sem caixa metálica no relógio de vidro).",
        "",
        "Instruções gerais:",
        "- Uma geração por beat. Não reescrever os prompts abaixo, a menos que uma falha de "
        "geração exija ajuste pontual — nesse caso, registre o que mudou.",
        "- Tamanho alvo: 1920x1080 (16:9). Se o provider usado não oferecer esse tamanho nativo "
        "(a OpenAI, por exemplo, não oferece — ver Gate 3C), gere no maior formato paisagem "
        "disponível e registre a resolução real.",
        "- Salvar cada imagem exatamente no caminho indicado abaixo.",
        "- Ao terminar, avise para retomarmos — não é preciso guardar contexto desta conversa, "
        "o manifesto machine-readable está em "
        f"`{manifest_path.relative_to(Path.cwd()) if manifest_path.is_absolute() else manifest_path}`.",
        "",
        "---",
        "",
    ]
    for entry in manifest_entries:
        lines += [
            f"## {entry['beat_id']} ({entry['start_seconds']}s–{entry['end_seconds']}s, "
            f"{entry['narrative_function']})",
            "",
            "**Prompt completo:**",
            "```",
            entry["full_prompt"],
            "```",
            "",
            f"**Aspect ratio:** {entry['aspect_ratio']} (alvo {entry['width']}x{entry['height']})",
            f"**Salvar em:** `{entry['output_path']}`",
            "",
        ]

    review_path = output_dir / "GENERATE_THESE_IMAGES.md"
    write_text_atomic(review_path, "\n".join(lines), policy)

    # -- atualizar manifesto do run com o estado de handoff ---------------------
    run_manifest_path = GATE3D_RUN_DIR / "run_manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    run_manifest["status"] = "images_ready"  # aguardando materialização externa
    run_manifest["provenance"]["image_generation_handoff"] = {
        "state": "IMAGE_GENERATION_PENDING",
        "manifest": str(manifest_path),
        "expected_outputs": [e["output_path"] for e in manifest_entries],
        "instructions": (
            "Generate exactly the requests in image_manifest_gate3d.json. "
            "Do not rewrite prompts unless a generation failure requires it. "
            "Record provenance and attempts. Save each image at its output_path. "
            "external_api_cost for THIS session: 0.00 USD — generation happens outside this session."
        ),
        "external_api_cost_this_session": 0.0,
    }
    run_manifest["artifacts"].append({"path": str(manifest_path), "kind": "image_manifest_gate3d"})
    run_manifest["artifacts"].append({"path": str(review_path), "kind": "handoff_instructions"})
    write_text_atomic(
        run_manifest_path, json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", policy
    )

    print(f"[gate3d-handoff] {len(manifest_entries)} requests -> {manifest_path}")
    print(f"[gate3d-handoff] human package -> {review_path}")
    print(f"[gate3d-handoff] expected images directory -> {images_dir}")
    print("[gate3d-handoff] external_api_cost_this_session: 0.00 USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
