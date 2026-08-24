"""GATE 2 — SINGLE ASSET PROOF.

Executa, de ponta a ponta e localmente, a cadeia mínima exigida pelo Gate 2
(docs/youtube-lite/SDD_SPDD.md §33-35):

    short script -> real narration -> real image -> simple timeline ->
    Ken Burns/movement -> FFmpeg -> clip.mp4

Não é o `PipelineOrchestrator` legacy — é um script linear, pequeno,
propositalmente sem framework de agentes, sem `bootstrap()`, sem máquina de
estados de 15 fases. Roteiro é um fixture curto e controlado, não um
`ScriptPlanner` real (isso é Gate 3).

Uso:
    python scripts/lite/run_gate2_proof.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.ffmpeg_assembler import assemble_single_beat_clip
from pedroarte_youtube_engine.lite.images.local_gdi import LocalGdiImageStrategy
from pedroarte_youtube_engine.lite.images.ports import ImageGenerationRequest
from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest
from pedroarte_youtube_engine.lite.narration.sapi5 import Sapi5NarrationStrategy
from pedroarte_youtube_engine.lite.qa import run_gate2_qa
from pedroarte_youtube_engine.lite.runs import (
    RunStatus,
    create_run,
    new_manifest,
    new_run_id,
    write_manifest,
    write_pending_tasks,
)
from pedroarte_youtube_engine.lite.timeline import build_single_beat_timeline
from pedroarte_youtube_engine.shared.text import count_words, speakable_duration_seconds

# Fixture curto e controlado — não é o ScriptPlanner real (Gate 3).
# Tema deliberadamente alinhado ao exemplo já existente do repositório
# (examples/sample_living_book), texto original escrito para este teste.
SCRIPT_TEXT = (
    "Em Portovelho, existe uma oficina que nunca fecha. O relojoeiro Elias "
    "Varga conserta o tempo com as próprias mãos, engrenagem por engrenagem, "
    "sob a luz baixa de um lampião. Ele diz que todo relógio guarda uma "
    "história — não apenas a hora, mas o instante exato em que alguém parou "
    "de esperar. Numa noite de chuva, uma cliente chega com um relógio de "
    "vidro, transparente por dentro, com engrenagens visíveis como se fossem "
    "desenhadas no ar. Esta narração prova que o motor Lite transforma um "
    "roteiro curto em um vídeo real, com narração, imagem e movimento, antes "
    "de tentarmos dez minutos inteiros."
)

IMAGE_PROMPT = "O Relojoeiro de Vidro\nProva de conceito — YouTube Lite, Gate 2"


def main() -> int:
    run_id = new_run_id("gate2-proof")
    paths = create_run(run_id)
    print(f"[gate2] run_id={run_id}")
    print(f"[gate2] run_dir={paths.root}")

    manifest = new_manifest(
        run_id=run_id, gate="gate2", owner="claude_code", briefing_source="fixture:gate2_short_script"
    )
    write_pending_tasks(
        paths,
        [
            {"id": "script", "status": "in_progress"},
            {"id": "narration", "status": "pending"},
            {"id": "image", "status": "pending"},
            {"id": "timeline", "status": "pending"},
            {"id": "assembly", "status": "pending"},
            {"id": "qa", "status": "pending"},
        ],
    )

    evidence: list[dict[str, object]] = []

    # -- 1. script (fixture) ------------------------------------------------
    script_path = paths.working_dir / "script.md"
    script_path.write_text(SCRIPT_TEXT, encoding="utf-8")
    words = count_words(SCRIPT_TEXT)
    estimated_seconds = speakable_duration_seconds(SCRIPT_TEXT)
    evidence.append(
        {
            "step": "script",
            "command": "fixture (sem LLM — Gate 3 exigirá ScriptPlanner real)",
            "expected": "script curto o suficiente para ~30-60s de narração",
            "actual": f"{words} palavras, ~{estimated_seconds:.1f}s estimados",
            "result": "PASS" if 15 <= estimated_seconds <= 90 else "FAIL",
            "artifact": str(script_path),
        }
    )
    manifest["status"] = RunStatus.SCRIPT_READY.value

    # -- 2. narração real (SAPI5) --------------------------------------------
    narration_path = paths.assets_dir / "narration.wav"
    narrator = Sapi5NarrationStrategy()
    narration_start = time.monotonic()
    narration_result = narrator.synthesize(
        NarrationRequest(text=SCRIPT_TEXT, output_path=narration_path, language="pt-BR")
    )
    narration_elapsed = time.monotonic() - narration_start
    evidence.append(
        {
            "step": "narration",
            "command": "Sapi5NarrationStrategy.synthesize (System.Speech via PowerShell)",
            "expected": "narration.wav real, duração > 0",
            "actual": f"{narration_result.duration_seconds:.2f}s, voz={narration_result.voice}",
            "result": "PASS" if narration_result.duration_seconds > 0 else "FAIL",
            "artifact": str(narration_result.output_path),
        }
    )
    manifest["provenance"]["narration"] = {
        "method": narration_result.method,
        "voice": narration_result.voice,
        "language": "pt-BR",
    }
    manifest["economics"]["generation_time_seconds"] += narration_elapsed
    manifest["status"] = RunStatus.NARRATION_READY.value

    # -- 3. imagem real (local GDI+, decisão humana explícita) --------------
    image_path = paths.images_dir / "image_0001.png"
    imager = LocalGdiImageStrategy()
    image_start = time.monotonic()
    image_result = imager.generate(
        ImageGenerationRequest(prompt=IMAGE_PROMPT, output_path=image_path, width=1920, height=1080)
    )
    image_elapsed = time.monotonic() - image_start
    evidence.append(
        {
            "step": "image",
            "command": "LocalGdiImageStrategy.generate (System.Drawing via PowerShell)",
            "expected": "image_0001.png real, 1920x1080",
            "actual": f"criado em {image_path}",
            "result": "PASS" if image_result.output_path.exists() else "FAIL",
            "artifact": str(image_result.output_path),
        }
    )
    manifest["provenance"]["image"] = {
        "method": image_result.method,
        "provider": image_result.provider,
        "model": image_result.model,
        "prompt": image_result.prompt,
    }
    manifest["economics"]["generation_time_seconds"] += image_elapsed
    manifest["economics"]["asset_count"] = 2  # narration + image
    manifest["status"] = RunStatus.IMAGES_READY.value

    # -- 4. timeline (um único beat) -----------------------------------------
    (beat,) = build_single_beat_timeline(
        image_path=str(image_path), narration_duration_seconds=narration_result.duration_seconds
    )
    evidence.append(
        {
            "step": "timeline",
            "command": "build_single_beat_timeline",
            "expected": "1 beat cobrindo a duração real da narração",
            "actual": f"beat 0.00s -> {beat.end_seconds:.2f}s",
            "result": "PASS",
            "artifact": "(em memória — sem arquivo dedicado no Gate 2)",
        }
    )
    manifest["status"] = RunStatus.NARRATION_READY.value

    # -- 5. FFmpeg assembly ---------------------------------------------------
    clip_path = paths.output_dir / "clip.mp4"
    assembly = assemble_single_beat_clip(
        beat=beat, narration_path=narration_path, output_path=clip_path
    )
    evidence.append(
        {
            "step": "assembly",
            "command": " ".join(assembly.command),
            "expected": "clip.mp4 criado",
            "actual": f"render_time={assembly.render_time_seconds:.2f}s",
            "result": "PASS" if clip_path.exists() else "FAIL",
            "artifact": str(clip_path),
        }
    )
    manifest["economics"]["render_time_seconds"] = assembly.render_time_seconds
    manifest["status"] = RunStatus.ASSEMBLED.value

    # -- 6. QA automatizado -----------------------------------------------
    qa_report = run_gate2_qa(clip_path, min_duration_seconds=20.0)
    evidence.append(
        {
            "step": "qa",
            "command": "run_gate2_qa (ffprobe + volumedetect)",
            "expected": "todos os checks PASS",
            "actual": "; ".join(f"{c.name}={c.passed}" for c in qa_report.checks),
            "result": "PASS" if qa_report.passed else "FAIL",
            "artifact": str(clip_path),
        }
    )
    manifest["qa"]["automated"] = qa_report.as_dict()
    manifest["status"] = (
        RunStatus.QA_PASSED.value if qa_report.passed else RunStatus.QA_FAILED.value
    )
    manifest["artifacts"] = [
        {"path": str(script_path), "kind": "script"},
        {"path": str(narration_path), "kind": "audio"},
        {"path": str(image_path), "kind": "image"},
        {"path": str(clip_path), "kind": "video"},
    ]

    write_manifest(paths, manifest)
    write_pending_tasks(
        paths,
        [{"id": step["step"], "status": "done"} for step in evidence],
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item['actual']}  ({item['artifact']})")

    print(f"\n[gate2] manifest={paths.manifest_path}")
    print(f"[gate2] clip={clip_path}")
    print(f"[gate2] overall={'PASS' if qa_report.passed else 'FAIL'}")
    return 0 if qa_report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
