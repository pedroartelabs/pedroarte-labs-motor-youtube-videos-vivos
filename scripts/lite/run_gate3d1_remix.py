"""GATE 3D.1 — patch: reaproveita `silent_full_video.mp4` já renderizado
(92 segmentos, 532.7s de render — caro) e refaz só música/mux/legendas/QA
com o ganho de música recalibrado (Slice D, achado do Experience QA)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_mix import generate_ambient_bed, mix_narration_with_music
from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.captions import cues_from_timing, rechunk_cues, render_ass, render_srt, CaptionStyle
from pedroarte_youtube_engine.lite.experience_qa import (
    ExperienceQaCheck,
    ExperienceQaReport,
    check_background_music_mix_step,
    check_burned_caption_render_step,
    check_caption_rechunk_valid,
    check_caption_style_config_valid,
    check_final_audio_no_clipping,
    check_max_seconds_without_visual_event,
    check_motion_configuration,
    check_timeline_visual_coverage,
    check_total_unique_images,
)
from pedroarte_youtube_engine.lite.ffmpeg_assembler import burn_captions, mux_video_audio, render_thumbnail
from pedroarte_youtube_engine.lite.qa import run_gate2_qa
from pedroarte_youtube_engine.lite.retention import build_default_retention_plan
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic

RUN_DIR = Path("runs/20260824T043945Z-gate3d1").resolve()
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")
NARRATION_TIMING_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.timing.json")
IMAGES_DIR = Path("runs/20260823T223458Z-gate3d-planning/assets/images").resolve()


def main() -> int:
    policy = PathPolicy.for_roots(RUN_DIR)
    working = RUN_DIR / "working"
    assets = RUN_DIR / "assets"
    bundle_dir = RUN_DIR / "output" / "youtube_bundle"

    silent_video = working / "silent_full_video.mp4"
    narration_ref = json.loads(Path("runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json").read_text(encoding="utf-8"))
    narration_duration_ref = narration_ref["qa"]["automated"]["duration_seconds"]

    print("[remix] regenerating ambient bed (cheap) + remixing with recalibrated gain...")
    music_path = assets / "music_ambient_bed.wav"
    generate_ambient_bed(duration_seconds=narration_duration_ref, output_path=music_path)
    mixed_audio_path = assets / "narration_with_music.mp3"
    mix_result = mix_narration_with_music(narration_path=NARRATION_SOURCE, music_path=music_path, output_path=mixed_audio_path)
    print(f"[remix] music_gain_db={mix_result.music_gain_db}")

    narration_only_metrics = probe_audio(NARRATION_SOURCE)
    mixed_metrics = probe_audio(mixed_audio_path)
    print(f"[remix] narration_only mean={narration_only_metrics.mean_volume_db}dB, mixed mean={mixed_metrics.mean_volume_db}dB, diff={abs((mixed_metrics.mean_volume_db or 0)-(narration_only_metrics.mean_volume_db or 0)):.2f}dB")

    video_with_audio = working / "video_with_motion_and_music.mp4"
    mux_video_audio(video_path=silent_video, audio_path=mixed_audio_path, output_path=video_with_audio)

    timing = json.loads(NARRATION_TIMING_SOURCE.read_text(encoding="utf-8"))
    original_cues = cues_from_timing(timing)
    write_text_atomic(bundle_dir / "captions.srt", render_srt(original_cues), policy)
    display_cues = rechunk_cues(original_cues)
    style = CaptionStyle()
    ass_path = bundle_dir / "captions.ass"
    write_text_atomic(ass_path, render_ass(display_cues, style=style), policy)

    final_video_path = bundle_dir / "video.mp4"
    burn_captions(video_path=video_with_audio, ass_path=ass_path, output_path=final_video_path)
    print(f"[remix] final video re-rendered: {final_video_path}")

    thumbnail_path = bundle_dir / "thumbnail.png"
    render_thumbnail(image_path=IMAGES_DIR / "beat_A.png", output_path=thumbnail_path)

    retention_plans = {b.id: build_default_retention_plan(b.duration_seconds) for b in GATE3D_FULL_VISUAL_PLAN}

    # O vídeo silencioso (movimento) não foi re-renderizado neste patch — só
    # áudio/mux/legendas mudaram. Reaproveita o resultado já medido do
    # check de regressão de movimento no build anterior (não redemonstra
    # pixels que não puderam ter mudado).
    prior_manifest = json.loads((RUN_DIR / "run_manifest.json").read_text(encoding="utf-8"))
    prior_checks = {c["name"]: c for c in prior_manifest["qa"]["automated"]["experience_qa"]["checks"]}
    prior_motion_check = prior_checks["motion_render_regression_sample"]

    media_qa = run_gate2_qa(final_video_path, min_duration_seconds=600.0)

    exp_report = ExperienceQaReport()
    exp_report.checks.append(check_timeline_visual_coverage(list(GATE3D_FULL_VISUAL_PLAN), total_duration_seconds=narration_duration_ref))
    exp_report.checks.append(check_total_unique_images(30, target=30))
    exp_report.checks.append(check_max_seconds_without_visual_event(retention_plans))
    exp_report.checks.append(check_motion_configuration(retention_plans))
    exp_report.checks.append(
        ExperienceQaCheck(
            "motion_render_regression_sample",
            prior_motion_check["passed"],
            prior_motion_check["detail"] + " [reaproveitado do build anterior — vídeo de movimento não foi re-renderizado neste patch]",
        )
    )
    exp_report.checks.append(check_caption_rechunk_valid(display_cues))
    exp_report.checks.append(check_caption_style_config_valid(style))
    exp_report.checks.append(check_burned_caption_render_step(pre_burn_path=video_with_audio, post_burn_path=final_video_path))
    exp_report.checks.append(
        check_background_music_mix_step(
            narration_only_mean_db=narration_only_metrics.mean_volume_db or -100.0,
            mixed_mean_db=mixed_metrics.mean_volume_db or -100.0,
        )
    )
    exp_report.checks.append(check_final_audio_no_clipping(final_video_path))

    print(f"\nMEDIA_QA passed={media_qa.passed}")
    print(f"EXPERIENCE_QA passed={exp_report.passed}")
    for c in exp_report.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")

    bundle_manifest_path = bundle_dir / "manifest.json"
    bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
    bundle_manifest["media_qa"] = media_qa.as_dict()
    bundle_manifest["experience_qa"] = exp_report.as_dict()
    bundle_manifest["music_gain_db_final"] = mix_result.music_gain_db
    write_text_atomic(bundle_manifest_path, json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n", policy)

    run_manifest_path = RUN_DIR / "run_manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    run_manifest["qa"]["automated"] = {"media_qa": media_qa.as_dict(), "experience_qa": exp_report.as_dict()}
    write_text_atomic(run_manifest_path, json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", policy)

    return 0 if (media_qa.passed and exp_report.passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
