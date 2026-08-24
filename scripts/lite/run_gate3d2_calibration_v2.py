"""GATE 3D.2 — calibration round 2, after human feedback on round 1:

  1. "Confundindo a voz do narrador com a música" -> investigação empírica
     mostrou que o desenho de música anterior (3 tons em 110/164.5/220Hz)
     caía exatamente na faixa onde a narração concentra energia
     (80-3000Hz, medido). Novo desenho (`audio_mix.generate_ambient_bed`)
     usa sub-grave (<80Hz) + shimmer agudo (>3000Hz), fora do "bolso vocal".
     Produz aqui: um clipe de MÚSICA ISOLADA (sem narração) para confirmar
     que a música soa como música por si só, mais as 3 variantes
     LOW/MEDIUM/HIGH remixadas com o novo desenho.

  2. "Zoom mais profissional" -> nova curva smoothstep aplicada à trajetória
     GLOBAL do beat (não por chunk). Produz aqui: variantes D (moderado
     suavizado) e E (forte suavizado), sobre o MESMO excerto/imagem/
     narração do round 1 (beat_18) para comparação direta com A/B/C.

Reutiliza o mesmo excerto de calibração do round 1 (não regenera a fatia de
narração, já existe em runs/gate3d2-calibration/working/narration_excerpt.mp3).
"""

from __future__ import annotations

import json
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
from pedroarte_youtube_engine.lite.ffmpeg_assembler import concat_segments, mux_video_audio, render_retention_clip
from pedroarte_youtube_engine.lite.retention import (
    GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_MODERATE,
    GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG,
    build_continuous_push_in_plan,
    segments_share_continuous_trajectory,
)
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

GATE3D_RUN_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()
IMAGES_DIR = GATE3D_RUN_DIR / "assets" / "images"
CALIBRATION_BEAT_ID = "beat_18"

MUSIC_RELATIVE_OFFSETS_DB = {"low": -16.0, "medium": -11.0, "high": -7.0}


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
    return {
        "label": label,
        "output": str(final_path),
        "segments": len(plan),
        "continuous_trajectory": continuous,
        "net_scale_change": round(plan[-1].end_scale - plan[0].start_scale, 4),
    }


def main() -> int:
    out_root = Path("runs") / "gate3d2-calibration"
    policy = PathPolicy.for_roots(out_root.resolve().parent)
    working = ensure_directory(out_root / "working", policy)
    output_dir = ensure_directory(out_root / "output", policy)

    beat = next(b for b in GATE3D_FULL_VISUAL_PLAN if b.id == CALIBRATION_BEAT_ID)
    image_path = IMAGES_DIR / f"{CALIBRATION_BEAT_ID}.png"

    narration_slice_path = working / "narration_excerpt.mp3"
    if not narration_slice_path.exists():
        raise SystemExit(f"Excerto de narração do round 1 não encontrado: {narration_slice_path}")
    narration_metrics = probe_audio(narration_slice_path)
    print(f"[gate3d2-v2] narração: mean={narration_metrics.mean_volume_db}dB duration={narration_metrics.duration_seconds:.2f}s")

    # ---- PART A round 2: EASED MOTION VARIANTS D/E ----
    plan_d = build_continuous_push_in_plan(
        beat.duration_seconds, total_zoom_ratio=GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_MODERATE, ease_in_out=True
    )
    plan_e = build_continuous_push_in_plan(
        beat.duration_seconds, total_zoom_ratio=GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG, ease_in_out=True
    )

    motion_results = []
    for label, plan in (("D_moderate_eased", plan_d), ("E_strong_eased", plan_e)):
        print(f"[gate3d2-v2] renderizando variante de movimento {label} ({len(plan)} segmentos, smoothstep global)...")
        result = _render_motion_variant(
            label=label, image_path=image_path, plan=plan, narration_path=narration_slice_path,
            working=working, output_dir=output_dir,
        )
        motion_results.append(result)
        print(
            f"[gate3d2-v2]   {label}: continuous={result['continuous_trajectory']} "
            f"net_scale_change={result['net_scale_change']:+.4f} -> {result['output']}"
        )

    # ---- PART B round 2: RESPECTRALIZED MUSIC ----
    music_bed_path = working / "music_bed_v2.wav"
    generate_ambient_bed(duration_seconds=beat.duration_seconds, output_path=music_bed_path)
    raw_music_metrics = probe_audio(music_bed_path)
    print(f"[gate3d2-v2] cama de música (novo desenho, espectralmente afastada da voz): mean={raw_music_metrics.mean_volume_db}dB")

    # Amostra de música ISOLADA (sem narração), para o humano confirmar que
    # soa como música por si só, decoupled do julgamento sobre a narração.
    music_only_path = output_dir / "music_only_isolated_high.mp3"
    gain_for_solo = compute_gain_for_relative_offset(
        narration_mean_db=narration_metrics.mean_volume_db or -100.0,
        raw_music_mean_db=raw_music_metrics.mean_volume_db or -100.0,
        target_relative_offset_db=MUSIC_RELATIVE_OFFSETS_DB["high"],
    )
    render_music_stem(
        music_path=music_bed_path, output_path=music_only_path, music_gain_db=gain_for_solo,
        narration_duration_seconds=beat.duration_seconds,
    )
    print(f"[gate3d2-v2]   música isolada (sem narração, nível HIGH): {music_only_path}")

    music_results = []
    for label, relative_offset_db in MUSIC_RELATIVE_OFFSETS_DB.items():
        gain_db = compute_gain_for_relative_offset(
            narration_mean_db=narration_metrics.mean_volume_db or -100.0,
            raw_music_mean_db=raw_music_metrics.mean_volume_db or -100.0,
            target_relative_offset_db=relative_offset_db,
        )
        stem_path = working / f"music_stem_v2_{label}.mp3"
        render_music_stem(
            music_path=music_bed_path, output_path=stem_path, music_gain_db=gain_db,
            narration_duration_seconds=beat.duration_seconds,
        )
        stem_metrics = probe_audio(stem_path)

        mixed_path = output_dir / f"music_variant_v2_{label}.mp3"
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
            f"[gate3d2-v2]   {label}: gain={gain_db:+.2f}dB stem_mean={stem_metrics.mean_volume_db}dB "
            f"relative_to_narration={relative_actual:+.2f}dB peak={mixed_metrics.max_volume_db}dB -> {mixed_path}"
        )

    report = {
        "excerpt": {"beat_id": CALIBRATION_BEAT_ID, "duration_seconds": beat.duration_seconds},
        "motion_variants_round2": motion_results,
        "raw_music_bed_mean_db_v2": raw_music_metrics.mean_volume_db,
        "music_only_isolated_sample": str(music_only_path),
        "music_variants_round2": music_results,
    }
    report_path = working / "calibration_report_round2.json"
    write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n", policy)
    print(f"\n[gate3d2-v2] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
