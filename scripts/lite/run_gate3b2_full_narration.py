"""GATE 3B.2 — FULL NARRATION PROOF.

    APPROVED SCRIPT -> SELECTED VOICE C -> FULL NARRATION -> REAL TIMING DATA
    -> OBJECTIVE AUDIO QA -> DURATION ANALYSIS -> HUMAN SCALE REVIEW -> STOP

Não faz novo bake-off. Não altera rate/pitch/volume da voz C aprovada no
Gate 3B. Não gera imagens. Não monta vídeo.

Uso:
    python scripts/lite/run_gate3b2_full_narration.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.ffmpeg_assembler import resolve_ffmpeg_binary
from pedroarte_youtube_engine.lite.narration.edge_tts_strategy import EdgeTtsNarrationStrategy
from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest
from pedroarte_youtube_engine.lite.runs import new_manifest, new_run_id
from pedroarte_youtube_engine.shared.errors import EngineError
from pedroarte_youtube_engine.shared.hashing import content_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic
from pedroarte_youtube_engine.shared.text import count_words, sentence_split

# -- decisão humana já tomada no Gate 3B (não reaberta aqui) -----------------
APPROVED_SCRIPT_SOURCE = Path("runs/20260823T185859Z-gate3a-script/working/script.md")
APPROVED_SCRIPT_HASH = (
    "sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1"
)
SELECTED_VOICE = "pt-BR-AntonioNeural"  # Voice C — configuração idêntica ao Gate 3B, sem rate/pitch/volume customizados

GATE3A_ESTIMATED_DURATION_SECONDS = 673.6
TARGET_MIN_MINUTES = 10.0
TARGET_MAX_MINUTES = 15.0

REVIEW_CLIP_SECONDS = 75.0  # ~45-90s pedido; ponto médio da faixa


def _duration_status(seconds: float) -> str:
    if seconds < TARGET_MIN_MINUTES * 60:
        return "TOO_SHORT"
    if seconds > TARGET_MAX_MINUTES * 60:
        return "TOO_LONG"
    return "WITHIN_TARGET"


def _parse_timing(raw_boundaries: list[dict]) -> list[dict]:
    parsed = []
    for index, item in enumerate(raw_boundaries, start=1):
        offset = float(item.get("offset_100ns") or 0) / 10_000_000.0
        duration = float(item.get("duration_100ns") or 0) / 10_000_000.0
        parsed.append(
            {
                "index": index,
                "text": item.get("text", ""),
                "offset_100ns": item.get("offset_100ns"),
                "duration_100ns": item.get("duration_100ns"),
                "start_seconds": round(offset, 3),
                "end_seconds": round(offset + duration, 3),
            }
        )
    return parsed


def _extract_review_clip(
    *, source: Path, output: Path, start_seconds: float, end_seconds: float
) -> None:
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    completed = subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(source),
            "-ss", f"{start_seconds:.3f}",
            "-to", f"{end_seconds:.3f}",
            "-c:a", "libmp3lame", "-q:a", "2",
            str(output),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if completed.returncode != 0 or not output.exists():
        raise EngineError(
            "Falha ao extrair trecho de revisão.",
            stderr=(completed.stderr or "")[-800:],
        )


def _clip_bounds_from_timing(
    timing: list[dict], target_start: float, target_end: float, total_duration: float
) -> tuple[float, float]:
    """Alinha os cortes às fronteiras de sentença mais próximas dos alvos —
    nunca corta no meio de uma frase."""
    starts = [b["start_seconds"] for b in timing] or [0.0]
    ends = [b["end_seconds"] for b in timing] or [total_duration]
    start = min(starts, key=lambda s: abs(s - target_start))
    end = min(ends, key=lambda e: abs(e - target_end))
    if end <= start:
        end = min(start + REVIEW_CLIP_SECONDS, total_duration)
    return start, min(end, total_duration)


def main() -> int:
    run_id = new_run_id("gate3b2-full-narration")
    runs_root = Path("runs").resolve()
    policy = PathPolicy.for_roots(runs_root)
    root = runs_root / run_id
    input_dir = ensure_directory(root / "input", policy)
    narration_dir = ensure_directory(root / "assets" / "narration", policy)
    working_dir = ensure_directory(root / "working", policy)
    output_dir = ensure_directory(root / "output", policy)

    print(f"[gate3b2] run_id={run_id}")
    print(f"[gate3b2] run_dir={root}")

    evidence: list[dict[str, object]] = []
    manifest = new_manifest(
        run_id=run_id, gate="gate3b2", owner="claude_code", briefing_source="gate3b_selected_voice_C"
    )

    # -- 1. verificar integridade do roteiro aprovado (sem reabrir a escolha) -
    if not APPROVED_SCRIPT_SOURCE.exists():
        raise SystemExit(f"GATE_3B2_BLOCKED: roteiro aprovado não encontrado em {APPROVED_SCRIPT_SOURCE}.")
    script_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    recomputed_hash = content_hash(script_text)
    hash_verified = recomputed_hash == APPROVED_SCRIPT_HASH
    evidence.append(
        {
            "step": "script_hash_verification",
            "command": "content_hash(script_text) == APPROVED_SCRIPT_HASH",
            "expected": APPROVED_SCRIPT_HASH,
            "actual": recomputed_hash,
            "result": "PASS" if hash_verified else "FAIL",
            "artifact": str(APPROVED_SCRIPT_SOURCE),
        }
    )
    if not hash_verified:
        raise SystemExit(
            "GATE_3B2_BLOCKED: drift não autorizado detectado no roteiro aprovado. "
            f"esperado={APPROVED_SCRIPT_HASH} obtido={recomputed_hash}"
        )
    script_approved_path = input_dir / "script_approved.md"
    write_text_atomic(script_approved_path, script_text, policy)

    # -- 2. normalização TTS — investigada, desnecessária (sem markdown) ------
    # Confirmado: sem headers, sem markup de ênfase, sem listas — o roteiro já
    # é texto falável. Nenhuma transformação foi criada (regra: não criar
    # transformação desnecessária).
    speakable_text = script_text
    evidence.append(
        {
            "step": "tts_normalization",
            "command": "inspeção de markdown/markup no roteiro aprovado",
            "expected": "decisão registrada (transformar ou não)",
            "actual": "nenhum elemento não-falável encontrado — enviado diretamente, sem speakable_script.txt",
            "result": "PASS",
            "artifact": "(nenhum arquivo — decisão de não transformar)",
        }
    )

    word_count = count_words(script_text)

    # -- 3. narração completa, voz C, configuração idêntica ao Gate 3B --------
    narration_config = {
        "provider": "external_api:edge_tts",
        "voice": SELECTED_VOICE,
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "boundary": "SentenceBoundary",
        "output_format": "mp3 (edge-tts default)",
        "note": "Configuração idêntica à usada para voice_C.mp3 no Gate 3B — nenhum parâmetro alterado.",
    }
    config_path = working_dir / "narration_config.json"
    write_text_atomic(
        config_path, json.dumps(narration_config, ensure_ascii=False, indent=2) + "\n", policy
    )

    narration_path = narration_dir / "narration_full.mp3"
    strategy = EdgeTtsNarrationStrategy(voice=SELECTED_VOICE)
    request = NarrationRequest(
        text=speakable_text, output_path=narration_path, language="pt-BR", voice=SELECTED_VOICE
    )

    segmented = False
    try:
        result = strategy.synthesize(request)
        evidence.append(
            {
                "step": "full_narration_synthesis",
                "command": f"EdgeTtsNarrationStrategy(voice={SELECTED_VOICE}).synthesize (single call)",
                "expected": "narration_full.mp3 real, roteiro completo, sem segmentação",
                "actual": f"generation_time={result.generation_time_seconds:.1f}s",
                "result": "PASS",
                "artifact": str(narration_path),
            }
        )
    except Exception as exc:
        raise SystemExit(
            f"GATE_3B2_BLOCKED: síntese completa falhou sem segmentação: {exc}. "
            "Segmentação não implementada nesta execução por não ter sido necessária "
            "até este ponto — reavaliar manualmente se isso ocorrer."
        )

    timing_raw_path = narration_path.with_suffix(".timing.json")
    raw_boundaries = json.loads(timing_raw_path.read_text(encoding="utf-8")) if timing_raw_path.exists() else []
    timing = _parse_timing(raw_boundaries)
    timing_path = narration_dir / "narration_full.timing.json"
    write_text_atomic(timing_path, json.dumps(timing, ensure_ascii=False, indent=2) + "\n", policy)

    # -- 4. duração real (fonte de verdade) -----------------------------------
    metrics = probe_audio(narration_path)
    actual_duration = metrics.duration_seconds
    actual_wpm = word_count / (actual_duration / 60.0) if actual_duration else 0.0
    difference_seconds = actual_duration - GATE3A_ESTIMATED_DURATION_SECONDS
    difference_percent = (
        (difference_seconds / GATE3A_ESTIMATED_DURATION_SECONDS) * 100.0
        if GATE3A_ESTIMATED_DURATION_SECONDS
        else 0.0
    )
    duration_status = _duration_status(actual_duration)
    evidence.append(
        {
            "step": "real_duration",
            "command": "probe_audio(narration_full.mp3) via ffprobe",
            "expected": "duração real, fonte de verdade (substitui estimativa do Gate 3A)",
            "actual": (
                f"{actual_duration:.1f}s (~{actual_duration/60:.2f}min), "
                f"{actual_wpm:.0f} wpm real, status={duration_status}"
            ),
            "result": "PASS",
            "artifact": str(narration_path),
        }
    )

    # -- 5. completeness check --------------------------------------------
    script_sentences = sentence_split(script_text)
    first_sentence_prefix = " ".join(script_sentences[0].split()[:5]) if script_sentences else ""
    last_sentence_suffix = " ".join(script_sentences[-1].split()[-5:]) if script_sentences else ""
    first_boundary_text = timing[0]["text"] if timing else ""
    last_boundary_text = timing[-1]["text"] if timing else ""
    first_present = bool(first_sentence_prefix) and first_sentence_prefix.lower() in first_boundary_text.lower()
    last_present = bool(last_sentence_suffix) and last_sentence_suffix.lower() in last_boundary_text.lower()
    last_boundary_end = timing[-1]["end_seconds"] if timing else 0.0
    alignment_ok = abs(last_boundary_end - actual_duration) <= max(2.0, actual_duration * 0.05)
    completeness_pass = bool(timing) and first_present and last_present and alignment_ok
    completeness = {
        "boundary_count": len(timing),
        "script_sentence_count_approx": len(script_sentences),
        "first_sentence_present_in_first_boundary": first_present,
        "last_sentence_present_in_last_boundary": last_present,
        "last_boundary_end_seconds": last_boundary_end,
        "actual_duration_seconds": actual_duration,
        "alignment_within_tolerance": alignment_ok,
        "status": "PASS" if completeness_pass else "FAIL",
    }
    evidence.append(
        {
            "step": "completeness_check",
            "command": "primeira/última sentença presentes + alinhamento timing<->duração",
            "expected": "sem truncamento silencioso",
            "actual": json.dumps(completeness, ensure_ascii=False),
            "result": completeness["status"],
            "artifact": str(timing_path),
        }
    )

    # -- 6. QA objetiva completa ------------------------------------------
    audio_qa = metrics.as_dict()
    audio_qa["word_count"] = word_count
    audio_qa["actual_words_per_minute"] = round(actual_wpm, 1)
    audio_qa["gate3a_estimated_duration_seconds"] = GATE3A_ESTIMATED_DURATION_SECONDS
    audio_qa["difference_seconds"] = round(difference_seconds, 1)
    audio_qa["difference_percent"] = round(difference_percent, 1)
    audio_qa["duration_status"] = duration_status
    audio_qa["no_obvious_clipping"] = (metrics.max_volume_db or 0.0) <= 0.0
    audio_qa["audible"] = (metrics.mean_volume_db or -100.0) > -40.0
    qa_path = working_dir / "audio_qa.json"
    write_text_atomic(qa_path, json.dumps(audio_qa, ensure_ascii=False, indent=2) + "\n", policy)
    evidence.append(
        {
            "step": "objective_audio_qa",
            "command": "probe_audio + volumedetect sobre narration_full.mp3",
            "expected": "arquivo abre, áudio presente, audível, sem clipping",
            "actual": f"audible={audio_qa['audible']} no_clipping={audio_qa['no_obvious_clipping']}",
            "result": "PASS" if audio_qa["audible"] and audio_qa["no_obvious_clipping"] else "FAIL",
            "artifact": str(qa_path),
        }
    )

    # -- 7. trechos de revisão distribuída (recortes, não ressíntese) --------
    thirds = actual_duration / 3.0
    targets = {
        "beginning": (0.0, min(REVIEW_CLIP_SECONDS, actual_duration)),
        "middle": (
            max(0.0, thirds - REVIEW_CLIP_SECONDS / 2),
            min(thirds + REVIEW_CLIP_SECONDS / 2, actual_duration),
        ),
        "end": (max(0.0, actual_duration - REVIEW_CLIP_SECONDS), actual_duration),
    }
    review_paths: dict[str, str] = {}
    for label, (target_start, target_end) in targets.items():
        start, end = _clip_bounds_from_timing(timing, target_start, target_end, actual_duration)
        clip_path = narration_dir / f"review_{label}.mp3"
        _extract_review_clip(source=narration_path, output=clip_path, start_seconds=start, end_seconds=end)
        review_paths[label] = str(clip_path)
        evidence.append(
            {
                "step": f"review_clip_{label}",
                "command": f"ffmpeg cut [{start:.1f}s, {end:.1f}s], alinhado a fronteira de sentença",
                "expected": "recorte real do narration_full, sem ressíntese",
                "actual": f"{end - start:.1f}s",
                "result": "PASS" if clip_path.exists() else "FAIL",
                "artifact": str(clip_path),
            }
        )

    # -- 8. pacote de revisão humana ------------------------------------------
    review_lines = [
        "# Gate 3B.2 — Full Narration Review",
        "",
        "Selected voice:",
        "C (edge-tts, pt-BR-AntonioNeural)",
        "",
        "Full narration:",
        f"[{narration_path}]",
        "",
        "Actual duration:",
        f"{actual_duration:.1f}s (~{actual_duration/60:.2f} min) — status: {duration_status}",
        "",
        "Review excerpts:",
        "",
        "Beginning:",
        f"[{review_paths['beginning']}]",
        "",
        "Middle:",
        f"[{review_paths['middle']}]",
        "",
        "End:",
        f"[{review_paths['end']}]",
        "",
        "Evaluate:",
        "",
        "1. Naturalness",
        "2. Pronunciation",
        "3. Rhythm",
        "4. Pauses",
        "5. Storytelling",
        "6. Dialogue",
        "7. Monotony",
        "8. Listening fatigue",
        "9. Would I listen to the full narration?",
        "10. Would I publish a video with this voice?",
        "",
        "Verdict:",
        "",
        "HUMAN_PASS",
        "HUMAN_PASS_WITH_NOTES",
        "HUMAN_FAIL",
        "",
    ]
    review_path = output_dir / "HUMAN_FULL_NARRATION_REVIEW.md"
    write_text_atomic(review_path, "\n".join(review_lines), policy)

    # -- manifesto final -------------------------------------------------------
    manifest["status"] = "narration_ready"
    manifest["provenance"]["script"] = {
        "approved_script_source": str(APPROVED_SCRIPT_SOURCE),
        "approved_script_hash": APPROVED_SCRIPT_HASH,
        "hash_verified": hash_verified,
    }
    manifest["provenance"]["narration"] = narration_config
    manifest["provenance"]["timing"] = completeness
    manifest["qa"]["automated"] = audio_qa
    manifest["artifacts"] = [
        {"path": str(script_approved_path), "kind": "approved_script"},
        {"path": str(narration_path), "kind": "narration_full"},
        {"path": str(timing_path), "kind": "timing_data"},
        {"path": str(config_path), "kind": "narration_config"},
        {"path": str(qa_path), "kind": "audio_qa"},
        {"path": str(review_path), "kind": "human_review_package"},
    ] + [{"path": p, "kind": f"review_clip_{label}"} for label, p in review_paths.items()]

    manifest_path = root / "run_manifest.json"
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy)

    pending = [
        {"id": step["step"], "status": "done" if step["result"] == "PASS" else "failed"}
        for step in evidence
    ] + [{"id": "human_full_narration_review", "status": "pending"}, {"id": "gate_3c", "status": "blocked"}]
    write_text_atomic(
        root / "pending_tasks.json",
        json.dumps({"run_id": run_id, "tasks": pending}, ensure_ascii=False, indent=2) + "\n",
        policy,
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item['actual']}")

    print(f"\n[gate3b2] manifest={manifest_path}")
    print(f"[gate3b2] narration_full={narration_path} ({actual_duration:.1f}s)")
    print(f"[gate3b2] human review package={review_path}")
    print(
        "\n[gate3b2] STOP — HUMAN SCALE REVIEW REQUIRED. "
        "Gate 3C permanece BLOCKED. Nenhuma imagem gerada. Nenhum MP4 montado. "
        "Aguardando HUMAN_PASS / HUMAN_PASS_WITH_NOTES / HUMAN_FAIL."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
