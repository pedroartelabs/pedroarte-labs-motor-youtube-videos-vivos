"""GATE 3D.2 — calibration bake-off (Parts A + B, both human micro-gates).

Produz, sobre o MESMO excerto representativo (beat_18, "emocional", 23.9s,
imagem já aprovada + narração real correspondente):

  - 3 variantes de MOVIMENTO (A=comportamento atual do Gate 3D.1,
    B=push-in contínuo moderado, C=push-in contínuo forte), cada uma muxada
    apenas com a narração real (sem música, para isolar o julgamento visual).
  - 3 variantes de NÍVEL DE MÚSICA (LOW/MEDIUM/HIGH), derivadas por medição
    real do stem de música após o ganho vs. o stem de narração — não por
    presets absolutos adivinhados (Gate 3D.2 §17).

NÃO renderiza o vídeo completo de 650.3s. Para depois do STOP humano.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_mix import (
    compute_gain_for_relative_offset,
    generate_ambient_bed,
    mix_narration_with_music,
    render_music_stem,
)
from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.ffmpeg_assembler import (
    concat_segments,
    mux_video_audio,
    render_retention_clip,
    resolve_ffmpeg_binary,
)
from pedroarte_youtube_engine.lite.retention import (
    GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_MODERATE,
    GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG,
    build_continuous_push_in_plan,
    build_default_retention_plan,
    segments_share_continuous_trajectory,
)
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

GATE3D_RUN_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()
IMAGES_DIR = GATE3D_RUN_DIR / "assets" / "images"
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")

CALIBRATION_BEAT_ID = "beat_18"

# Deslocamentos RELATIVOS (dB abaixo da narração), não valores absolutos —
# aplicados a `compute_gain_for_relative_offset` sobre o nível REAL medido
# do stem de música bruto para este excerto (Gate 3D.2 §17).
MUSIC_RELATIVE_OFFSETS_DB = {"low": -16.0, "medium": -11.0, "high": -7.0}


def _extract_audio_slice(*, start: float, end: float, output_path: Path) -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(NARRATION_SOURCE), "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-c:a", "libmp3lame", "-q:a", "2", str(output_path),
        ],
        check=True, capture_output=True,
    )


def _render_motion_variant(*, label: str, image_path: Path, plan, narration_path: Path, working: Path, output_dir: Path) -> dict:
    chunk_dir = working / f"variant_{label}" / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = []
    for i, segment in enumerate(plan):
        chunk_path = chunk_dir / f"chunk_{i}.mp4"
        render_retention_clip(image_path=image_path, segment=segment, output_path=chunk_path)
        chunk_paths.append(chunk_path)

    silent_path = working / f"variant_{label}" / "silent.mp4"
    concat_segments(segment_paths=chunk_paths, output_path=silent_path)

    final_path = output_dir / f"motion_variant_{label}.mp4"
    mux_video_audio(video_path=silent_path, audio_path=narration_path, output_path=final_path)

    continuous = segments_share_continuous_trajectory(plan)
    zoom_summary = [
        {"kind": s.kind.value, "duration_s": round(s.duration_seconds, 2), "start_scale": round(s.start_scale, 4), "end_scale": round(s.end_scale, 4)}
        for s in plan
    ]
    return {
        "label": label,
        "output": str(final_path),
        "segments": len(plan),
        "continuous_trajectory": continuous,
        "net_scale_change": round(plan[-1].end_scale - plan[0].start_scale, 4),
        "segment_detail": zoom_summary,
    }


def main() -> int:
    out_root = Path("runs") / "gate3d2-calibration"
    policy = PathPolicy.for_roots(out_root.resolve().parent)
    working = ensure_directory(out_root / "working", policy)
    output_dir = ensure_directory(out_root / "output", policy)

    beat = next(b for b in GATE3D_FULL_VISUAL_PLAN if b.id == CALIBRATION_BEAT_ID)
    image_path = IMAGES_DIR / f"{CALIBRATION_BEAT_ID}.png"

    narration_slice_path = working / "narration_excerpt.mp3"
    _extract_audio_slice(start=beat.start_seconds, end=beat.end_seconds, output_path=narration_slice_path)
    narration_metrics = probe_audio(narration_slice_path)

    print(f"[gate3d2] excerto de calibração: {CALIBRATION_BEAT_ID} ({beat.duration_seconds:.2f}s)")
    print(f"[gate3d2] narração: mean={narration_metrics.mean_volume_db}dB duration={narration_metrics.duration_seconds:.2f}s")

    # ---- PART A: MOTION BAKEOFF ----
    plan_a = build_default_retention_plan(beat.duration_seconds)
    plan_b = build_continuous_push_in_plan(beat.duration_seconds, total_zoom_ratio=GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_MODERATE)
    plan_c = build_continuous_push_in_plan(beat.duration_seconds, total_zoom_ratio=GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG)

    motion_results = []
    for label, plan in (("A_current_gate3d1", plan_a), ("B_moderate_continuous", plan_b), ("C_strong_continuous", plan_c)):
        print(f"[gate3d2] renderizando variante de movimento {label} ({len(plan)} segmentos)...")
        result = _render_motion_variant(
            label=label, image_path=image_path, plan=plan, narration_path=narration_slice_path,
            working=working, output_dir=output_dir,
        )
        motion_results.append(result)
        print(
            f"[gate3d2]   {label}: continuous={result['continuous_trajectory']} "
            f"net_scale_change={result['net_scale_change']:+.4f} -> {result['output']}"
        )

    # ---- PART B: MUSIC BAKEOFF ----
    music_bed_path = working / "music_bed_raw.wav"
    generate_ambient_bed(duration_seconds=beat.duration_seconds, output_path=music_bed_path)
    raw_music_metrics = probe_audio(music_bed_path)
    print(f"[gate3d2] cama de música bruta: mean={raw_music_metrics.mean_volume_db}dB")

    music_results = []
    for label, relative_offset_db in MUSIC_RELATIVE_OFFSETS_DB.items():
        gain_db = compute_gain_for_relative_offset(
            narration_mean_db=narration_metrics.mean_volume_db or -100.0,
            raw_music_mean_db=raw_music_metrics.mean_volume_db or -100.0,
            target_relative_offset_db=relative_offset_db,
        )
        stem_path = working / f"music_stem_{label}.mp3"
        render_music_stem(
            music_path=music_bed_path, output_path=stem_path, music_gain_db=gain_db,
            narration_duration_seconds=beat.duration_seconds,
        )
        stem_metrics = probe_audio(stem_path)

        mixed_path = output_dir / f"music_variant_{label}.mp3"
        mix_narration_with_music(
            narration_path=narration_slice_path, music_path=music_bed_path, output_path=mixed_path,
            music_gain_db=gain_db,
        )
        mixed_metrics = probe_audio(mixed_path)

        relative_actual = (stem_metrics.mean_volume_db or -100.0) - (narration_metrics.mean_volume_db or -100.0)
        music_results.append(
            {
                "label": label,
                "target_relative_offset_db": relative_offset_db,
                "gain_db": round(gain_db, 2),
                "stem_mean_db_after_gain": stem_metrics.mean_volume_db,
                "relative_to_narration_db_actual": round(relative_actual, 2),
                "final_mix_peak_db": mixed_metrics.max_volume_db,
                "output": str(mixed_path),
            }
        )
        print(
            f"[gate3d2]   {label}: gain={gain_db:+.2f}dB stem_mean={stem_metrics.mean_volume_db}dB "
            f"relative_to_narration={relative_actual:+.2f}dB peak={mixed_metrics.max_volume_db}dB -> {mixed_path}"
        )

    report = {
        "excerpt": {
            "beat_id": CALIBRATION_BEAT_ID,
            "duration_seconds": beat.duration_seconds,
            "narration_mean_db": narration_metrics.mean_volume_db,
        },
        "motion_variants": motion_results,
        "raw_music_bed_mean_db": raw_music_metrics.mean_volume_db,
        "music_variants": music_results,
    }
    report_path = working / "calibration_report.json"
    write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n", policy)
    print(f"\n[gate3d2] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
