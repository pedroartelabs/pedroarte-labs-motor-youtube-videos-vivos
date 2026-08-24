"""GATE 3D — ASSEMBLY: full video render, captions, thumbnail, metadata,
youtube_bundle, automated QA, STOP for human full watch.

    30 IMAGES (5 reused + 25 handoff) -> per-beat Ken Burns segments (16:9
    normalization embedded in the same FFmpeg pass) -> concat -> mux with
    real narration -> captions.srt (real timing) -> thumbnail (reused
    asset, no new generation) -> metadata.json -> youtube_bundle/ ->
    automated QA -> STOP.

Não gera nenhuma imagem nova. Não usa música (adiada, Gate 3D §27 do
briefing original). Não chama nenhuma API paga.

Uso:
    python scripts/lite/run_gate3d_assembly.py
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.captions import cues_from_timing, render_srt
from pedroarte_youtube_engine.lite.ffmpeg_assembler import (
    concat_segments,
    mux_video_audio,
    render_silent_segment,
    render_thumbnail,
    resolve_ffmpeg_binary,
)
from pedroarte_youtube_engine.lite.image_qa import probe_image
from pedroarte_youtube_engine.lite.metadata import Chapter, build_metadata
from pedroarte_youtube_engine.lite.qa import run_gate2_qa
from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE_HARDENED
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.hashing import content_hash, structural_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

GATE3D_RUN_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()
APPROVED_SCRIPT_SOURCE = Path("runs/20260823T185859Z-gate3a-script/working/script.md")
APPROVED_SCRIPT_HASH = "sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1"
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")
NARRATION_TIMING_SOURCE = Path(
    "runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.timing.json"
)
NARRATION_REFERENCE_MANIFEST = Path("runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json")
EXPECTED_HARDENED_BIBLE_HASH = "sha256:2406658b4d0a33e77ddbd7393b71d385a8d8b1dd1de14ff6f3676521f1c1ee75"

CHAPTER_BEAT_IDS = ("beat_A", "beat_03", "beat_05", "beat_08", "beat_10", "beat_14", "beat_19", "beat_22", "beat_25")
CHAPTER_TITLES = {
    "beat_A": "Abertura — A Inscrição Impossível",
    "beat_03": "Portovelho",
    "beat_05": "Mariana Duarte",
    "beat_08": "A Descoberta no Arquivo Morto",
    "beat_10": "O Confronto",
    "beat_14": "A Origem do Relógio",
    "beat_19": "A Pergunta",
    "beat_22": "O Conserto",
    "beat_25": "O Desfecho",
}


def main() -> int:
    images_dir = GATE3D_RUN_DIR / "assets" / "images"
    working_dir = ensure_directory(GATE3D_RUN_DIR / "working", PathPolicy.for_roots(GATE3D_RUN_DIR))
    segments_dir = ensure_directory(working_dir / "segments", PathPolicy.for_roots(GATE3D_RUN_DIR))
    output_dir = GATE3D_RUN_DIR / "output"
    bundle_dir = ensure_directory(output_dir / "youtube_bundle", PathPolicy.for_roots(GATE3D_RUN_DIR))
    bundle_assets_images = ensure_directory(bundle_dir / "assets" / "images", PathPolicy.for_roots(GATE3D_RUN_DIR))
    policy = PathPolicy.for_roots(GATE3D_RUN_DIR)

    evidence: list[dict[str, object]] = []

    # -- 1. integridade dos inputs congelados ----------------------------------
    script_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    script_ok = content_hash(script_text) == APPROVED_SCRIPT_HASH
    evidence.append({"step": "approved_script_hash", "result": "PASS" if script_ok else "FAIL"})

    bible_hash = structural_hash(RELOJOEIRO_VISUAL_BIBLE_HARDENED.to_dict())
    bible_ok = bible_hash == EXPECTED_HARDENED_BIBLE_HASH
    evidence.append({"step": "hardened_visual_bible_hash", "result": "PASS" if bible_ok else "FAIL"})

    narration_ref = json.loads(NARRATION_REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    narration_duration_ref = narration_ref["qa"]["automated"]["duration_seconds"]
    narration_ok = narration_ref["provenance"]["timing"]["status"] == "PASS"
    evidence.append({"step": "narration_reference", "result": "PASS" if narration_ok else "FAIL"})

    if not (script_ok and bible_ok and narration_ok):
        raise SystemExit("GATE_3D_BLOCKED: drift detectado nos inputs congelados.")

    # -- 2. confirmar os 30 assets --------------------------------------------
    missing = [b.id for b in GATE3D_FULL_VISUAL_PLAN if not (images_dir / f"{b.id}.png").exists()]
    evidence.append({"step": "all_30_images_present", "result": "PASS" if not missing else "FAIL", "detail": missing})
    if missing:
        raise SystemExit(f"GATE_3D_BLOCKED: imagens ausentes: {missing}")

    image_qa: dict[str, object] = {}
    for beat in GATE3D_FULL_VISUAL_PLAN:
        result = probe_image(images_dir / f"{beat.id}.png")
        image_qa[beat.id] = result.as_dict()
        if not result.opens:
            raise SystemExit(f"GATE_3D_BLOCKED: {beat.id}.png não abre.")
    evidence.append({"step": "all_images_open", "result": "PASS", "detail": f"{len(image_qa)} imagens verificadas"})

    # -- 3. renderizar segmentos silenciosos (normalização 16:9 embutida) -----
    start_render = time.monotonic()
    segment_paths: list[Path] = []
    for beat in GATE3D_FULL_VISUAL_PLAN:
        seg_path = segments_dir / f"{beat.id}.mp4"
        render_silent_segment(
            image_path=images_dir / f"{beat.id}.png",
            duration_seconds=beat.duration_seconds,
            output_path=seg_path,
        )
        segment_paths.append(seg_path)
        print(f"[gate3d-assembly] segment {beat.id} ({beat.duration_seconds:.1f}s) OK")
    render_elapsed = time.monotonic() - start_render
    evidence.append({"step": "render_30_segments", "result": "PASS", "detail": f"{render_elapsed:.1f}s"})

    # -- 4. concatenar + mux com a narração real -------------------------------
    silent_video_path = working_dir / "silent_full_video.mp4"
    concat_segments(segment_paths=segment_paths, output_path=silent_video_path)
    evidence.append({"step": "concat_segments", "result": "PASS"})

    video_path = bundle_dir / "video.mp4"
    mux_video_audio(video_path=silent_video_path, audio_path=NARRATION_SOURCE, output_path=video_path)
    evidence.append({"step": "mux_audio", "result": "PASS", "detail": str(video_path)})

    # -- 5. captions (timing real) ---------------------------------------------
    timing = json.loads(NARRATION_TIMING_SOURCE.read_text(encoding="utf-8"))
    cues = cues_from_timing(timing)
    srt_text = render_srt(cues)
    captions_path = bundle_dir / "captions.srt"
    write_text_atomic(captions_path, srt_text, policy)
    evidence.append({"step": "captions", "result": "PASS", "detail": f"{len(cues)} cues"})

    # -- 6. thumbnail (reuso, sem gerar nada novo) -----------------------------
    thumbnail_path = bundle_dir / "thumbnail.png"
    render_thumbnail(image_path=images_dir / "beat_A.png", output_path=thumbnail_path)
    evidence.append({"step": "thumbnail", "result": "PASS", "detail": "reused beat_A.png"})

    # -- 7. metadata -------------------------------------------------------------
    chapters = tuple(
        Chapter(at_seconds=b.start_seconds, title=CHAPTER_TITLES[b.id])
        for b in GATE3D_FULL_VISUAL_PLAN
        if b.id in CHAPTER_BEAT_IDS
    )
    metadata = build_metadata(
        title="O Relojoeiro de Vidro",
        description=(
            "Em Portovelho, um relojoeiro guarda um segredo entre engrenagens de vidro. "
            "Quando Mariana Duarte traz um relógio de bolso feito inteiramente de vidro para "
            "consertar, ela encontra uma inscrição impossível — e uma dívida antiga que a "
            "cidade inteira paga em silêncio.\n\n"
            "Conto original de mistério e realismo mágico, narrado por completo, produzido "
            "localmente com o motor YouTube Lite (roteiro aprovado por revisão humana, voz "
            "aprovada por bake-off + prova de escala, linguagem visual aprovada com "
            "endurecimento de continuidade).\n\n"
            "#ficcao #misterio #realismomagico"
        ),
        chapters=chapters,
        language="pt-BR",
        duration_seconds=narration_duration_ref,
        hashtags=("ficcao", "misterio", "realismomagico", "audiolivro", "contocurto"),
    )
    metadata_path = bundle_dir / "metadata.json"
    write_text_atomic(metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", policy)
    evidence.append({"step": "metadata", "result": "PASS", "detail": f"{len(chapters)} capítulos"})

    # -- 8. script + assets no bundle -------------------------------------------
    write_text_atomic(bundle_dir / "script.md", script_text, policy)
    bundle_assets_dir = ensure_directory(bundle_dir / "assets", policy)
    shutil.copy2(NARRATION_SOURCE, bundle_assets_dir / "narration.mp3")
    for beat in GATE3D_FULL_VISUAL_PLAN:
        shutil.copy2(images_dir / f"{beat.id}.png", bundle_assets_images / f"{beat.id}.png")

    # -- 9. QA automatizada do vídeo final ---------------------------------------
    # `run_gate2_qa` é uma função de QA de mídia genérica (ffprobe + volumedetect),
    # nomeada no Gate 2 mas sem nenhum acoplamento específico a ele — reaproveitada
    # aqui como está, sem duplicar lógica.
    video_qa = run_gate2_qa(video_path, min_duration_seconds=600.0)
    final_video_duration = probe_audio(video_path).duration_seconds
    audio_metrics = probe_audio(NARRATION_SOURCE)
    captions_parse_ok = len(cues) > 0 and cues[-1].end_seconds <= narration_duration_ref + 2.0
    evidence.append(
        {
            "step": "final_automated_qa",
            "result": "PASS" if video_qa.passed and captions_parse_ok else "FAIL",
            "detail": video_qa.as_dict(),
        }
    )

    bundle_manifest = {
        "video": str(video_path.relative_to(bundle_dir)),
        "thumbnail": str(thumbnail_path.relative_to(bundle_dir)),
        "captions": str(captions_path.relative_to(bundle_dir)),
        "metadata": str(metadata_path.relative_to(bundle_dir)),
        "script": "script.md",
        "assets_images_count": len(GATE3D_FULL_VISUAL_PLAN),
        "narration_source": str(NARRATION_SOURCE),
        "visual_bible_version": RELOJOEIRO_VISUAL_BIBLE_HARDENED.version,
        "approved_script_hash": APPROVED_SCRIPT_HASH,
        "video_qa": video_qa.as_dict(),
        "final_video_duration_seconds": round(final_video_duration, 1),
        "required_assets_accounted_for": not missing,
    }
    write_text_atomic(
        bundle_dir / "manifest.json", json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n", policy
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item.get('detail', '')}")

    print(f"\n[gate3d-assembly] video={video_path}")
    print(f"[gate3d-assembly] duration={final_video_duration:.1f}s (~{final_video_duration/60:.2f}min)")
    print(f"[gate3d-assembly] bundle={bundle_dir}")
    print(
        "\n[gate3d-assembly] STOP — HUMAN FULL WATCH REQUIRED. "
        "Nenhuma música foi adicionada (adiada). Aguardando HUMAN_PASS / "
        "HUMAN_PASS_WITH_NOTES / HUMAN_FAIL sobre o vídeo completo."
    )
    return 0 if video_qa.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
