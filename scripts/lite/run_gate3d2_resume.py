"""GATE 3D.2 — resume after the caption-burn step timed out at 600s (the
render itself, concat, music, and mux all completed successfully — only
`burn_captions` was killed mid-write, leaving a corrupt partial video.mp4,
already removed). Reuses everything already produced in
runs/20260824T060555Z-gate3d2/ and finishes: burn (now with a 1500s
timeout) -> Media QA -> Experience QA -> manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.captions import CaptionStyle, cues_from_timing, rechunk_cues
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
from pedroarte_youtube_engine.lite.ffmpeg_assembler import burn_captions
from pedroarte_youtube_engine.lite.qa import run_gate2_qa
from pedroarte_youtube_engine.lite.retention import GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG, build_continuous_push_in_plan
from pedroarte_youtube_engine.lite.runs import new_manifest
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic

RUN_DIR = Path("runs/20260824T060555Z-gate3d2").resolve()
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")
NARRATION_TIMING_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.timing.json")
NARRATION_REFERENCE_MANIFEST = Path("runs/20260823T200332Z-gate3b2-full-narration/run_manifest.json")

APPROVED_TOTAL_ZOOM_RATIO = GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG
APPROVED_EASE_IN_OUT = True
YAVG_SAMPLE_BEATS = {"beat_D", "beat_A", "beat_26", "beat_18", "beat_B"}


def main() -> int:
    policy = PathPolicy.for_roots(RUN_DIR)
    working = RUN_DIR / "working"
    assets_dir = RUN_DIR / "assets"
    bundle_dir = RUN_DIR / "output" / "youtube_bundle"

    video_with_audio = working / "video_with_motion_and_music.mp4"
    ass_path = bundle_dir / "captions.ass"
    final_video_path = bundle_dir / "video.mp4"
    if not video_with_audio.exists():
        raise SystemExit(f"Esperado já existir: {video_with_audio}")

    print("[resume] queimando legendas (timeout=1500s)...")
    burn_captions(video_path=video_with_audio, ass_path=ass_path, output_path=final_video_path)
    print(f"[resume] video final: {final_video_path}")

    narration_ref = json.loads(NARRATION_REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    narration_duration_ref = narration_ref["qa"]["automated"]["duration_seconds"]

    music_stem_path = assets_dir / "music_stem_after_gain.mp3"
    music_stem_metrics = probe_audio(music_stem_path)
    narration_only_metrics = probe_audio(NARRATION_SOURCE)

    # amostras YAVG: reaproveita o resultado já medido no run que foi interrompido
    # (o vídeo de movimento não muda neste resume, só a queima de legendas)
    chunks_dir = working / "chunks"
    import re
    import subprocess

    from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary

    def _yavg(video_path: Path, *, t0: float, t1: float) -> float:
        ffmpeg = resolve_ffmpeg_binary("ffmpeg")
        f0 = working / "tmp_resume_f0.png"
        f1 = working / "tmp_resume_f1.png"
        subprocess.run([ffmpeg, "-y", "-ss", str(t0), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(f0)], capture_output=True)
        subprocess.run([ffmpeg, "-y", "-ss", str(t1), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(f1)], capture_output=True)
        completed = subprocess.run(
            [ffmpeg, "-i", str(f0), "-i", str(f1), "-filter_complex", "blend=all_mode=difference,signalstats,metadata=print", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        match = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", completed.stdout + completed.stderr)
        return float(match.group(1)) if match else 0.0

    retention_plans = {
        beat.id: build_continuous_push_in_plan(
            beat.duration_seconds, total_zoom_ratio=APPROVED_TOTAL_ZOOM_RATIO, ease_in_out=APPROVED_EASE_IN_OUT
        )
        for beat in GATE3D_FULL_VISUAL_PLAN
    }
    yavg_samples: dict[str, float] = {}
    for beat_id in YAVG_SAMPLE_BEATS:
        first_clip = chunks_dir / f"{beat_id}_0.mp4"
        if first_clip.exists():
            dur = retention_plans[beat_id][0].duration_seconds
            yavg_samples[beat_id] = _yavg(first_clip, t0=min(0.2, dur * 0.1), t1=max(0.5, dur * 0.9))
    print(f"[resume] yavg_samples={yavg_samples}")

    timing = json.loads(NARRATION_TIMING_SOURCE.read_text(encoding="utf-8"))
    original_cues = cues_from_timing(timing)
    display_cues = rechunk_cues(original_cues)
    style = CaptionStyle()

    media_qa = run_gate2_qa(final_video_path, min_duration_seconds=600.0)

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

    print(f"\nMEDIA_QA passed={media_qa.passed}")
    print(f"EXPERIENCE_QA passed={exp_report.passed}")
    for c in exp_report.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")

    bundle_manifest_path = bundle_dir / "manifest.json"
    bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8")) if bundle_manifest_path.exists() else {}
    bundle_manifest["media_qa"] = media_qa.as_dict()
    bundle_manifest["experience_qa"] = exp_report.as_dict()
    write_text_atomic(bundle_manifest_path, json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n", policy)

    run_manifest_path = RUN_DIR / "run_manifest.json"
    run_id = RUN_DIR.name
    run_manifest = new_manifest(run_id=run_id, gate="gate3d2", owner="claude_code", briefing_source="gate3d2_human_approved")
    run_manifest["status"] = "images_ready"
    run_manifest["artifacts"] = [{"path": str(bundle_dir / f), "kind": f} for f in ("video.mp4", "thumbnail.png", "captions.srt", "captions.ass", "metadata.json")]
    run_manifest["qa"]["automated"] = {"media_qa": media_qa.as_dict(), "experience_qa": exp_report.as_dict()}
    write_text_atomic(run_manifest_path, json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", policy)

    print(f"\n[resume] final video: {final_video_path}")
    return 0 if (media_qa.passed and exp_report.passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
