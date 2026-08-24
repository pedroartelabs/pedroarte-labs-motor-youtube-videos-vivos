"""GATE 3D.1 — MOTION PROOF (before any new image is generated).

Renders 5 representative beats (short / medium / long / emotional /
atmospheric) using ONLY the 30 already-approved Gate 3C/3D images, the
corrected Ken Burns (Slice A) and the default Retention Beat plan (Slice B).
Muxes each with the real corresponding narration slice for a realistic
excerpt. No new images. No captions burned yet. No music yet.

Uso:
    python scripts/lite/run_gate3d1_motion_proof.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.ffmpeg_assembler import (
    concat_segments,
    mux_video_audio,
    render_retention_clip,
    resolve_ffmpeg_binary,
)
from pedroarte_youtube_engine.lite.image_qa import probe_image
from pedroarte_youtube_engine.lite.retention import build_default_retention_plan, max_static_window_seconds
from pedroarte_youtube_engine.lite.visual_plan_gate3d import GATE3D_FULL_VISUAL_PLAN
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic

import subprocess

GATE3D_RUN_DIR = Path("runs/20260823T223458Z-gate3d-planning").resolve()
IMAGES_DIR = GATE3D_RUN_DIR / "assets" / "images"
NARRATION_SOURCE = Path("runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3")

REPRESENTATIVE_BEATS = {
    "short": "beat_D",
    "medium": "beat_A",
    "long": "beat_26",
    "emotional": "beat_18",
    "atmospheric": "beat_B",
}


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


def main() -> int:
    out_root = Path("runs") / "gate3d1-motion-proof"
    policy = PathPolicy.for_roots(out_root.resolve().parent)
    working = ensure_directory(out_root / "working", policy)
    output_dir = ensure_directory(out_root / "output", policy)

    report: dict[str, object] = {}
    evidence: list[dict[str, object]] = []

    for label, beat_id in REPRESENTATIVE_BEATS.items():
        beat = next(b for b in GATE3D_FULL_VISUAL_PLAN if b.id == beat_id)
        image_path = IMAGES_DIR / f"{beat_id}.png"
        plan = build_default_retention_plan(beat.duration_seconds)

        chunk_dir = ensure_directory(working / f"{label}_{beat_id}" / "chunks", policy)
        chunk_paths = []
        for i, segment in enumerate(plan):
            chunk_path = chunk_dir / f"chunk_{i}.mp4"
            render_retention_clip(image_path=image_path, segment=segment, output_path=chunk_path)
            chunk_paths.append(chunk_path)

        silent_path = working / f"{label}_{beat_id}" / "silent.mp4"
        concat_segments(segment_paths=chunk_paths, output_path=silent_path)

        audio_path = working / f"{label}_{beat_id}" / "audio.mp3"
        _extract_audio_slice(start=beat.start_seconds, end=beat.end_seconds, output_path=audio_path)

        final_path = output_dir / f"proof_{label}_{beat_id}.mp4"
        mux_video_audio(video_path=silent_path, audio_path=audio_path, output_path=final_path)

        info = probe_image(final_path)
        static_window = max_static_window_seconds(plan)
        evidence.append(
            {
                "label": label,
                "beat_id": beat_id,
                "duration_seconds": beat.duration_seconds,
                "retention_segments": len(plan),
                "segment_kinds": [s.kind.value for s in plan],
                "max_static_window_seconds": round(static_window, 2),
                "resolution": f"{info.width}x{info.height}",
                "output": str(final_path),
            }
        )
        print(
            f"[motion-proof] {label} ({beat_id}, {beat.duration_seconds:.1f}s): "
            f"{len(plan)} retention segments, kinds={[s.kind.value for s in plan]}, "
            f"max_static_window={static_window:.1f}s -> {final_path}"
        )

    report["excerpts"] = evidence
    report_path = working / "motion_proof_report.json"
    write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n", policy)

    print(f"\n[motion-proof] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
