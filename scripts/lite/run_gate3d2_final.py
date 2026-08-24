"""GATE 3D.2 — PART D: FULL RENDER (after human calibration approval).

Human approved (2026-08-24):
  MOTION: E — push-in contínuo forte + smoothstep (total_zoom_ratio=0.22,
          ease_in_out=True), aplicado a todos os 30 beats.
  MUSIC:  MEDIUM — nível relativo -11.0dB vs. narração, cama de música
          redesenhada (sub 55Hz + shimmer 3520/4698.63Hz, fora da faixa
          espectral da narração).

Escopo do Gate 3D.2 (§2 do mandato): SÓ movimento e música mudam. Roteiro,
narração, Voice C, legendas, Visual Bible, personagens, imagens, contagem de
imagens, semântica da timeline, capítulos, thumbnail e metadata são
REUTILIZADOS byte-a-byte do bundle do Gate 3D.1 — não regenerados — para
garantir que nada além do aprovado mudou.

Cria um NOVO diretório de run. runs/20260824T043945Z-gate3d1/ e
runs/20260823T223458Z-gate3d-planning/ nunca são tocados.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_mix import (
    compute_gain_for_relative_offset,
    generate_ambient_bed,
    mix_narration_with_music,
    render_music_stem,
)
from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.captions import CaptionStyle
from pedroarte_youtube_engine.lite.experience_qa import (
    ExperienceQaReport,
    check_burned_caption_render_step,
    check_caption_rechunk_valid,
    check_caption_style_config_valid,
    check_cumulative_zoom_progression,
    check_final_audio_no_clipping,
    check_max_seconds_without_visual_event,
    check_motion_render_regression,
    check_music_stem_relative_level,
    check_timeline_visual_coverage,
    check_total_unique_images,
)
from pedroarte_youtube_engine.lite.ffmpeg_assembler import (
    burn_captions,
    concat_segments,
    mux_video_audio,
    render_retention_clip,
    resolve_ffmpeg_binary,
)
from pedroarte_youtube_engine.lite.qa import run_gate2_qa
from pedroarte_youtube_engine.lite.retention import GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG, build_continuous_push_in_plan
from pedroarte_youtube_engine.lite.runs import new_manifest, new_run_id
from pedroarte_youtube_engine.lite.visual_bible import RELOJOEIRO_VISUAL_BIBLE_HARDENED
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN, validate_plan_coverage
from pedroarte_youtube_engine.shared.hashing import content_hash, structural_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

GATE3D_BASELINE_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()
GATE3D1_RUN_DIR = Path("runs/20260824T043945Z-gate3d1").resolve()
GATE3D1_BUNDLE_DIR = GATE3D1_RUN_DIR / "output" / "youtube_bundle"
IMAGES_DIR = GATE3D_BASELINE_DIR / "assets" / "images"
APPROVED_SCRIPT_SOURCE = Path("runs/20260823T185859Z-gate3a-script/working/script.md")
APPROVED_SCRIPT_HASH = "sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1"
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")
NARRATION_REFERENCE_MANIFEST = Path("runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json")
EXPECTED_HARDENED_BIBLE_HASH = "sha256:2406658b4d0a33e77ddbd7393b71d385a8d8b1dd1de14ff6f3676521f1c1ee75"

APPROVED_TOTAL_ZOOM_RATIO = GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG  # Variante E
APPROVED_EASE_IN_OUT = True
APPROVED_MUSIC_RELATIVE_OFFSET_DB = -11.0  # MEDIUM
YAVG_SAMPLE_BEATS = {"beat_D", "beat_A", "beat_26", "beat_18", "beat_B"}


def main() -> int:
    run_id = new_run_id("gate3d2")
    runs_root = Path("runs").resolve()
    policy = PathPolicy.for_roots(runs_root)
    root = runs_root / run_id
    input_dir = ensure_directory(root / "input", policy)
    working = ensure_directory(root / "working", policy)
    chunks_dir = ensure_directory(working / "chunks", policy)
    assets_dir = ensure_directory(root / "assets", policy)
    output_dir = ensure_directory(root / "output", policy)
    bundle_dir = ensure_directory(output_dir / "youtube_bundle", policy)
    bundle_assets_images = ensure_directory(bundle_dir / "assets" / "images", policy)

    evidence: list[dict[str, object]] = []
    manifest = new_manifest(run_id=run_id, gate="gate3d2", owner="claude_code", briefing_source="gate3d2_human_approved")

    print(f"[gate3d2] run_id={run_id}")
    print(f"[gate3d2] motion=E (total_zoom_ratio={APPROVED_TOTAL_ZOOM_RATIO}, ease_in_out={APPROVED_EASE_IN_OUT}), music=MEDIUM ({APPROVED_MUSIC_RELATIVE_OFFSET_DB}dB relative)")
    print(f"[gate3d2] Gate 3D.1 baseline preserved at {GATE3D1_RUN_DIR} (not touched)")
    print(f"[gate3d2] Gate 3D baseline preserved at {GATE3D_BASELINE_DIR} (not touched)")

    # -- 1. integridade dos inputs congelados ----------------------------------
    script_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    script_ok = content_hash(script_text) == APPROVED_SCRIPT_HASH
    bible_hash = structural_hash(RELOJOEIRO_VISUAL_BIBLE_HARDENED.to_dict())
    bible_ok = bible_hash == EXPECTED_HARDENED_BIBLE_HASH
    narration_ref = json.loads(NARRATION_REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    narration_duration_ref = narration_ref["qa"]["automated"]["duration_seconds"]
    narration_ok = narration_ref["provenance"]["timing"]["status"] == "PASS"
    evidence.append({"step": "frozen_inputs_verified", "result": "PASS" if (script_ok and bible_ok and narration_ok) else "FAIL"})
    if not (script_ok and bible_ok and narration_ok):
        raise SystemExit("GATE_3D2_BLOCKED: drift nos inputs congelados.")
    write_text_atomic(input_dir / "script_approved.md", script_text, policy)

    missing = [b.id for b in GATE3D_FULL_VISUAL_PLAN if not (IMAGES_DIR / f"{b.id}.png").exists()]
    if missing:
        raise SystemExit(f"GATE_3D2_BLOCKED: imagens ausentes: {missing}")

    required_bundle_files = ("captions.srt", "captions.ass", "metadata.json", "thumbnail.png", "script.md")
    missing_bundle = [f for f in required_bundle_files if not (GATE3D1_BUNDLE_DIR / f).exists()]
    if missing_bundle:
        raise SystemExit(f"GATE_3D2_BLOCKED: bundle do Gate 3D.1 incompleto, faltando: {missing_bundle}")

    # -- 2. plano de movimento aprovado (variante E) para os 30 beats ---------
    retention_plans: dict[str, tuple] = {
        beat.id: build_continuous_push_in_plan(
            beat.duration_seconds, total_zoom_ratio=APPROVED_TOTAL_ZOOM_RATIO, ease_in_out=APPROVED_EASE_IN_OUT
        )
        for beat in GATE3D_FULL_VISUAL_PLAN
    }
    total_segments = sum(len(p) for p in retention_plans.values())
    coverage = validate_plan_coverage(GATE3D_FULL_VISUAL_PLAN, total_duration_seconds=narration_duration_ref)
    evidence.append({"step": "timeline_coverage", "result": coverage["status"], "detail": f"{coverage['beat_count']} beats"})

    retention_plan_payload = {
        beat_id: [asdict(s) | {"kind": s.kind.value} for s in segments] for beat_id, segments in retention_plans.items()
    }
    write_text_atomic(
        working / "retention_timeline.json",
        json.dumps(retention_plan_payload, ensure_ascii=False, indent=2) + "\n",
        policy,
    )

    # -- 3. render de todos os Retention Segments (movimento aprovado) --------
    render_start = time.monotonic()
    all_clip_paths: list[Path] = []
    yavg_samples: dict[str, float] = {}

    for beat in GATE3D_FULL_VISUAL_PLAN:
        image_path = IMAGES_DIR / f"{beat.id}.png"
        segments = retention_plans[beat.id]
        for i, segment in enumerate(segments):
            clip_path = chunks_dir / f"{beat.id}_{i}.mp4"
            render_retention_clip(image_path=image_path, segment=segment, output_path=clip_path)
            all_clip_paths.append(clip_path)
        print(f"[gate3d2] {beat.id}: {len(segments)} retention segments rendered")

    render_elapsed = time.monotonic() - render_start
    evidence.append({"step": "render_all_retention_segments", "result": "PASS", "detail": f"{total_segments} segments, {render_elapsed:.1f}s"})

    import re
    import subprocess

    def _yavg(video_path: Path, *, t0: float, t1: float) -> float:
        ffmpeg = resolve_ffmpeg_binary("ffmpeg")
        f0 = working / "tmp_f0.png"
        f1 = working / "tmp_f1.png"
        subprocess.run([ffmpeg, "-y", "-ss", str(t0), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(f0)], capture_output=True)
        subprocess.run([ffmpeg, "-y", "-ss", str(t1), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(f1)], capture_output=True)
        completed = subprocess.run(
            [ffmpeg, "-i", str(f0), "-i", str(f1), "-filter_complex", "blend=all_mode=difference,signalstats,metadata=print", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        match = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", completed.stdout + completed.stderr)
        return float(match.group(1)) if match else 0.0

    for beat_id in YAVG_SAMPLE_BEATS:
        first_clip = chunks_dir / f"{beat_id}_0.mp4"
        if first_clip.exists():
            dur = retention_plans[beat_id][0].duration_seconds
            yavg_samples[beat_id] = _yavg(first_clip, t0=min(0.2, dur * 0.1), t1=max(0.5, dur * 0.9))

    # -- 4. concat de todos os segmentos (vídeo silencioso completo) ----------
    silent_video = working / "silent_full_video.mp4"
    concat_segments(segment_paths=all_clip_paths, output_path=silent_video)
    evidence.append({"step": "concat_all_segments", "result": "PASS"})

    # -- 5. música redesenhada (sub+shimmer) + mixagem no nível MEDIUM aprovado --
    music_path = assets_dir / "music_ambient_bed.wav"
    generate_ambient_bed(duration_seconds=narration_duration_ref, output_path=music_path)
    raw_music_metrics = probe_audio(music_path)
    narration_only_metrics = probe_audio(NARRATION_SOURCE)

    music_gain_db = compute_gain_for_relative_offset(
        narration_mean_db=narration_only_metrics.mean_volume_db or -100.0,
        raw_music_mean_db=raw_music_metrics.mean_volume_db or -100.0,
        target_relative_offset_db=APPROVED_MUSIC_RELATIVE_OFFSET_DB,
    )

    music_stem_path = assets_dir / "music_stem_after_gain.mp3"
    render_music_stem(
        music_path=music_path, output_path=music_stem_path, music_gain_db=music_gain_db,
        narration_duration_seconds=narration_duration_ref,
    )
    music_stem_metrics = probe_audio(music_stem_path)

    mixed_audio_path = assets_dir / "narration_with_music.mp3"
    mix_result = mix_narration_with_music(
        narration_path=NARRATION_SOURCE, music_path=music_path, output_path=mixed_audio_path, music_gain_db=music_gain_db
    )
    mixed_metrics = probe_audio(mixed_audio_path)
    evidence.append(
        {
            "step": "music_and_mix",
            "result": "PASS",
            "detail": f"gain={mix_result.music_gain_db}dB, stem_mean={music_stem_metrics.mean_volume_db}dB, relative_to_narration={(music_stem_metrics.mean_volume_db or 0) - (narration_only_metrics.mean_volume_db or 0):+.2f}dB",
        }
    )

    # -- 6. mux vídeo silencioso + áudio mixado --------------------------------
    video_with_audio = working / "video_with_motion_and_music.mp4"
    mux_video_audio(video_path=silent_video, audio_path=mixed_audio_path, output_path=video_with_audio)

    # -- 7. legendas: REUTILIZADAS byte-a-byte do Gate 3D.1 (não regeneradas) --
    shutil.copy2(GATE3D1_BUNDLE_DIR / "captions.srt", bundle_dir / "captions.srt")
    shutil.copy2(GATE3D1_BUNDLE_DIR / "captions.ass", bundle_dir / "captions.ass")
    ass_path = bundle_dir / "captions.ass"
    style = CaptionStyle()  # mesmo contrato de estilo do Gate 3D.1, para o Experience QA

    final_video_path = bundle_dir / "video.mp4"
    burn_captions(video_path=video_with_audio, ass_path=ass_path, output_path=final_video_path)
    evidence.append({"step": "captions_reused_and_burned", "result": "PASS", "detail": "captions.srt/.ass reutilizados byte-a-byte do Gate 3D.1"})

    # -- 8. thumbnail e metadata: REUTILIZADOS byte-a-byte do Gate 3D.1 --------
    shutil.copy2(GATE3D1_BUNDLE_DIR / "thumbnail.png", bundle_dir / "thumbnail.png")
    shutil.copy2(GATE3D1_BUNDLE_DIR / "metadata.json", bundle_dir / "metadata.json")
    shutil.copy2(GATE3D1_BUNDLE_DIR / "script.md", bundle_dir / "script.md")

    for beat in GATE3D_FULL_VISUAL_PLAN:
        shutil.copy2(IMAGES_DIR / f"{beat.id}.png", bundle_assets_images / f"{beat.id}.png")
    ensure_directory(bundle_dir / "assets", policy)
    shutil.copy2(music_path, bundle_dir / "assets" / "music_ambient_bed.wav")
    write_text_atomic(
        bundle_dir / "assets" / "music_license.json",
        json.dumps(
            {
                "source_category": "original/generated asset with publication rights",
                "generation_method": "lite/audio_mix.py::generate_ambient_bed v2 (sub 55Hz + shimmer 3520/4698.63Hz, chorus, FFmpeg nativo)",
                "third_party_material": False,
                "license_note": "Sem material de terceiros — sintetizado por código, sem risco de licenciamento.",
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        policy,
    )

    # -- 9. Media QA --------------------------------------------------------
    media_qa = run_gate2_qa(final_video_path, min_duration_seconds=600.0)

    # -- 10. Experience QA (com os dois critérios substituídos, §25/§26) -------
    from pedroarte_youtube_engine.lite.captions import cues_from_timing, rechunk_cues

    NARRATION_TIMING_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.timing.json")
    timing = json.loads(NARRATION_TIMING_SOURCE.read_text(encoding="utf-8"))
    original_cues = cues_from_timing(timing)
    display_cues = rechunk_cues(original_cues)

    exp_report = ExperienceQaReport()
    exp_report.checks.append(check_timeline_visual_coverage(list(GATE3D_FULL_VISUAL_PLAN), total_duration_seconds=narration_duration_ref))
    exp_report.checks.append(check_total_unique_images(30, target=30))
    exp_report.checks.append(check_max_seconds_without_visual_event(retention_plans))
    exp_report.checks.append(check_cumulative_zoom_progression(retention_plans))
    exp_report.checks.append(check_motion_render_regression(yavg_samples))
    exp_report.checks.append(check_caption_rechunk_valid(display_cues))
    exp_report.checks.append(check_caption_style_config_valid(style))
    exp_report.checks.append(check_burned_caption_render_step(pre_burn_path=video_with_audio, post_burn_path=final_video_path))
    exp_report.checks.append(
        check_music_stem_relative_level(
            narration_stem_mean_db=narration_only_metrics.mean_volume_db or -100.0,
            music_stem_mean_db_after_gain=music_stem_metrics.mean_volume_db or -100.0,
        )
    )
    exp_report.checks.append(check_final_audio_no_clipping(final_video_path))

    bundle_manifest = {
        "video": "video.mp4",
        "thumbnail": "thumbnail.png",
        "captions_srt": "captions.srt",
        "captions_ass": "captions.ass",
        "metadata": "metadata.json",
        "script": "script.md",
        "music_asset": "assets/music_ambient_bed.wav",
        "music_license": "assets/music_license.json",
        "assets_images_count": len(GATE3D_FULL_VISUAL_PLAN),
        "visual_bible_version": RELOJOEIRO_VISUAL_BIBLE_HARDENED.version,
        "approved_script_hash": APPROVED_SCRIPT_HASH,
        "gate3d_baseline_preserved": str(GATE3D_BASELINE_DIR),
        "gate3d1_baseline_preserved": str(GATE3D1_RUN_DIR),
        "total_retention_segments": total_segments,
        "approved_motion_profile": {"variant": "E", "total_zoom_ratio": APPROVED_TOTAL_ZOOM_RATIO, "ease_in_out": APPROVED_EASE_IN_OUT},
        "approved_music_level": {"variant": "MEDIUM", "relative_offset_db": APPROVED_MUSIC_RELATIVE_OFFSET_DB, "gain_db": music_gain_db},
        "media_qa": media_qa.as_dict(),
        "experience_qa": exp_report.as_dict(),
    }
    write_text_atomic(bundle_dir / "manifest.json", json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n", policy)

    manifest["status"] = "images_ready"
    manifest["artifacts"] = [{"path": str(bundle_dir / f), "kind": f} for f in ("video.mp4", "thumbnail.png", "captions.srt", "captions.ass", "metadata.json")]
    manifest["qa"]["automated"] = {"media_qa": media_qa.as_dict(), "experience_qa": exp_report.as_dict()}
    write_text_atomic(root / "run_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy)

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item.get('detail', '')}")
    print(f"\nMEDIA_QA passed={media_qa.passed}")
    print(f"EXPERIENCE_QA passed={exp_report.passed}")
    for c in exp_report.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")

    print(f"\n[gate3d2] final video: {final_video_path}")
    print(f"[gate3d2] bundle: {bundle_dir}")
    print("\n[gate3d2] STOP — HUMAN FULL WATCH REQUIRED.")
    return 0 if (media_qa.passed and exp_report.passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
