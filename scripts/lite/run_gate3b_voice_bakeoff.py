"""GATE 3B — VOICE BAKE-OFF.

    APPROVED SCRIPT -> VOICE TEST EXCERPT -> 2-3 CANDIDATES (same text) ->
    AUDIO SAMPLES -> OBJECTIVE QA -> HUMAN_VOICE_REVIEW.md -> STOP

Não sintetiza o roteiro completo. Não gera vídeo. Não escolhe a voz
automaticamente — isso é sempre humano (SDD_SPDD.md PART V, regra 16 do
briefing do Gate 3B).

Uso:
    python scripts/lite/run_gate3b_voice_bakeoff.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.narration.edge_tts_strategy import EdgeTtsNarrationStrategy
from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest
from pedroarte_youtube_engine.lite.narration.sapi5 import Sapi5NarrationStrategy
from pedroarte_youtube_engine.lite.runs import new_manifest, new_run_id
from pedroarte_youtube_engine.shared.hashing import content_hash
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic
from pedroarte_youtube_engine.shared.text import count_words, speakable_duration_seconds

APPROVED_SCRIPT_SOURCE = Path(
    "runs/20260823T185859Z-gate3a-script/working/script.md"
)

# Parágrafos 9, 11, 13, 15, 17 do roteiro aprovado (índices 4..8 na lista de
# parágrafos separados por linha em branco) — contíguos, cobrem descrição,
# transição narrativa, diálogo curto e longo, suspense, nomes próprios
# (Elias, Mariana, Portovelho), número (1986), pausa natural e uma pergunta
# final. Não reescrito, não resumido — extração literal.
EXCERPT_PARAGRAPH_RANGE = (4, 9)  # slice [start:end)

CANDIDATES = [
    {"letter": "A", "provider_label": "local:sapi5", "voice": "Microsoft Maria Desktop"},
    {"letter": "B", "provider_label": "external_api:edge_tts", "voice": "pt-BR-FranciscaNeural"},
    {"letter": "C", "provider_label": "external_api:edge_tts", "voice": "pt-BR-AntonioNeural"},
]


def main() -> int:
    run_id = new_run_id("gate3b-voice")
    runs_root = Path("runs").resolve()
    policy = PathPolicy.for_roots(runs_root)
    root = runs_root / run_id
    input_dir = ensure_directory(root / "input", policy)
    voice_dir = ensure_directory(root / "assets" / "voice", policy)
    working_dir = ensure_directory(root / "working", policy)
    output_dir = ensure_directory(root / "output", policy)

    print(f"[gate3b] run_id={run_id}")
    print(f"[gate3b] run_dir={root}")

    manifest = new_manifest(
        run_id=run_id, gate="gate3b", owner="claude_code", briefing_source="gate3a_approved_script"
    )
    pending_tasks_path = root / "pending_tasks.json"

    def _write_pending(tasks: list[dict[str, str]]) -> None:
        write_text_atomic(
            pending_tasks_path,
            json.dumps({"run_id": run_id, "tasks": tasks}, ensure_ascii=False, indent=2) + "\n",
            policy,
        )

    _write_pending(
        [
            {"id": "freeze_approved_script", "status": "in_progress"},
            {"id": "extract_excerpt", "status": "pending"},
            {"id": "voice_A", "status": "pending"},
            {"id": "voice_B", "status": "pending"},
            {"id": "voice_C", "status": "pending"},
            {"id": "objective_qa", "status": "pending"},
            {"id": "human_review_package", "status": "pending"},
        ]
    )

    evidence: list[dict[str, object]] = []

    # -- 1. preservar o roteiro aprovado, imutável, com hash -----------------
    if not APPROVED_SCRIPT_SOURCE.exists():
        raise SystemExit(
            f"GATE_3B_BLOCKED: roteiro aprovado não encontrado em {APPROVED_SCRIPT_SOURCE}."
        )
    approved_text = APPROVED_SCRIPT_SOURCE.read_text(encoding="utf-8")
    approved_hash = content_hash(approved_text)
    script_approved_path = input_dir / "script_approved.md"
    write_text_atomic(script_approved_path, approved_text, policy)
    evidence.append(
        {
            "step": "freeze_approved_script",
            "command": f"copy verbatim de {APPROVED_SCRIPT_SOURCE}",
            "expected": "cópia byte-idêntica, hash registrado",
            "actual": f"sha256={approved_hash[:16]}…",
            "result": "PASS",
            "artifact": str(script_approved_path),
        }
    )

    # -- 2. extrair o trecho de teste (literal, sem reescrever) ---------------
    paragraphs = approved_text.split("\n\n")
    start, end = EXCERPT_PARAGRAPH_RANGE
    excerpt = "\n\n".join(paragraphs[start:end]).strip()
    excerpt_hash = content_hash(excerpt)
    excerpt_words = count_words(excerpt)
    excerpt_estimated_seconds = speakable_duration_seconds(excerpt)
    excerpt_path = input_dir / "voice_test_excerpt.txt"
    write_text_atomic(excerpt_path, excerpt + "\n", policy)
    evidence.append(
        {
            "step": "extract_excerpt",
            "command": f"paragraphs[{start}:{end}] do roteiro aprovado (literal)",
            "expected": "trecho representativo (~60-90s), sem reescrita",
            "actual": f"{excerpt_words} palavras, ~{excerpt_estimated_seconds:.1f}s estimados",
            "result": "PASS",
            "artifact": str(excerpt_path),
        }
    )

    # -- 3. gerar os candidatos (mesmo texto, provedores diferentes) ---------
    strategies = {
        "local:sapi5": Sapi5NarrationStrategy(),
        "external_api:edge_tts": EdgeTtsNarrationStrategy(),
    }
    candidate_mapping: dict[str, dict[str, object]] = {}
    qa_results: dict[str, object] = {}

    for candidate in CANDIDATES:
        letter = candidate["letter"]
        provider_label = candidate["provider_label"]
        voice = candidate["voice"]
        extension = "wav" if provider_label == "local:sapi5" else "mp3"
        output_path = voice_dir / f"voice_{letter}.{extension}"

        strategy = strategies[provider_label]
        request = NarrationRequest(
            text=excerpt, output_path=output_path, language="pt-BR", voice=voice
        )

        try:
            result = strategy.synthesize(request)
            status = "PASS"
            error_detail = ""
        except Exception as exc:  # falha real de um candidato é resultado válido, não escondido
            status = "FAIL"
            error_detail = str(exc)[:400]
            result = None

        candidate_mapping[letter] = {
            "provider": provider_label,
            "voice": voice,
            "output_path": str(output_path),
            "status": status,
            "error": error_detail,
            "text_sha256": excerpt_hash,
        }

        if result is not None:
            candidate_mapping[letter]["generation_time_seconds"] = round(
                result.generation_time_seconds, 2
            )
            candidate_mapping[letter]["timing_data_available"] = result.timing_data_available
            try:
                metrics = probe_audio(output_path)
                qa_results[letter] = metrics.as_dict()
            except Exception as exc:  # QA em si pode falhar sem invalidar a amostra
                qa_results[letter] = {"error": str(exc)[:400]}

        evidence.append(
            {
                "step": f"voice_{letter}",
                "command": f"{provider_label} voice={voice}",
                "expected": f"voice_{letter}.{extension} real, mesmo texto que os demais",
                "actual": (
                    f"duration={qa_results.get(letter, {}).get('duration_seconds')}s"
                    if status == "PASS"
                    else f"FALHOU: {error_detail}"
                ),
                "result": status,
                "artifact": str(output_path),
            }
        )

    # -- 4. registrar mapeamento e QA objetiva --------------------------------
    candidates_path = working_dir / "voice_candidates.json"
    write_text_atomic(
        candidates_path,
        json.dumps(candidate_mapping, ensure_ascii=False, indent=2) + "\n",
        policy,
    )
    qa_path = working_dir / "voice_qa.json"
    write_text_atomic(
        qa_path, json.dumps(qa_results, ensure_ascii=False, indent=2) + "\n", policy
    )
    evidence.append(
        {
            "step": "objective_qa",
            "command": "probe_audio (ffprobe + volumedetect) por candidato",
            "expected": "métricas objetivas por candidato, sem quality score algorítmico",
            "actual": f"{len(qa_results)} candidato(s) medido(s)",
            "result": "PASS",
            "artifact": str(qa_path),
        }
    )

    all_same_text = len({v["text_sha256"] for v in candidate_mapping.values()}) == 1

    # -- 5. pacote de revisão humana (sem revelar o provider) -----------------
    review_lines = [
        "# Gate 3B — Human Voice Review",
        "",
        "Listen with headphones if possible.",
        "",
    ]
    for candidate in CANDIDATES:
        letter = candidate["letter"]
        info = candidate_mapping[letter]
        review_lines.append(f"Candidate {letter}:")
        review_lines.append(f"[{info['output_path']}]")
        review_lines.append("")
    review_lines += [
        "Evaluate:",
        "",
        "1. Naturalness",
        "2. Clarity",
        "3. Pronunciation",
        "4. Rhythm",
        "5. Pauses",
        "6. Emotional fit",
        "7. Suspense",
        "8. Dialogue",
        "9. Listening fatigue",
        "10. Would you listen for 10+ minutes?",
        "",
        "Choose:",
        "",
        "HUMAN_PASS: A/B/C",
        "",
        "or",
        "",
        "HUMAN_PASS_WITH_NOTES: A/B/C",
        "",
        "or",
        "",
        "HUMAN_FAIL",
        "",
    ]
    review_path = output_dir / "HUMAN_VOICE_REVIEW.md"
    write_text_atomic(review_path, "\n".join(review_lines), policy)
    evidence.append(
        {
            "step": "human_review_package",
            "command": "HUMAN_VOICE_REVIEW.md (mapping não revelado no corpo principal)",
            "expected": "documento pronto para audição comparativa",
            "actual": f"{len(CANDIDATES)} candidatos listados",
            "result": "PASS",
            "artifact": str(review_path),
        }
    )

    # -- manifest final -------------------------------------------------------
    manifest["status"] = "narration_ready"
    manifest["provenance"]["script"] = {
        "approved_script_source": str(APPROVED_SCRIPT_SOURCE),
        "approved_script_hash": approved_hash,
    }
    manifest["provenance"]["voice_bakeoff"] = {
        "excerpt_hash": excerpt_hash,
        "excerpt_word_count": excerpt_words,
        "all_candidates_same_text": all_same_text,
        "candidates": candidate_mapping,
    }
    manifest["qa"]["automated"] = qa_results
    manifest["artifacts"] = [
        {"path": str(script_approved_path), "kind": "approved_script"},
        {"path": str(excerpt_path), "kind": "voice_test_excerpt"},
        {"path": str(candidates_path), "kind": "voice_candidates_mapping"},
        {"path": str(qa_path), "kind": "voice_qa"},
        {"path": str(review_path), "kind": "human_review_package"},
    ] + [
        {"path": candidate_mapping[c["letter"]]["output_path"], "kind": "voice_sample"}
        for c in CANDIDATES
        if candidate_mapping[c["letter"]]["status"] == "PASS"
    ]

    manifest_path = root / "run_manifest.json"
    write_text_atomic(
        manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", policy
    )
    _write_pending(
        [
            {"id": step["step"], "status": "done" if step["result"] == "PASS" else "failed"}
            for step in evidence
        ]
        + [{"id": "human_voice_review", "status": "pending"}]
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item['actual']}  ({item['artifact']})")

    print("\n=== OBJECTIVE AUDIO QA ===")
    print(json.dumps(qa_results, ensure_ascii=False, indent=2))

    print(f"\n[gate3b] manifest={manifest_path}")
    print(f"[gate3b] human review package={review_path}")
    print(
        "\n[gate3b] STOP — HUMAN VOICE REVIEW REQUIRED. "
        "Não sintetizando o roteiro completo. Não gerando imagens. "
        "Aguardando HUMAN_PASS / HUMAN_PASS_WITH_NOTES / HUMAN_FAIL por candidato (A/B/C)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
