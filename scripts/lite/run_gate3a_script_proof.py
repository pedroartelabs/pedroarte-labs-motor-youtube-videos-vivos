"""GATE 3A — SCRIPT QUALITY.

Executa, com um briefing real (não fixture, não "lorem ipsum"):

    BRIEFING -> VIDEO SPECIFICATION -> SCRIPT GENERATION ->
    DETERMINISTIC VALIDATORS -> artefatos -> STOP FOR HUMAN REVIEW

O roteiro é autorado pelo LLM que conduz esta sessão (Claude Code), como
parte real do trabalho desta execução — não uma chamada de API programática,
e não um texto hardcoded genérico. Ver
`src/pedroarte_youtube_engine/lite/script_generation/operator_authored.py`.

NÃO implementa Gate 3B/3C/3D. Termina sempre em STOP — nunca assume
aprovação humana.

Uso:
    python scripts/lite/run_gate3a_script_proof.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pedroarte_youtube_engine.lite.briefing import BriefingSchema, FactualityMode
from pedroarte_youtube_engine.lite.runs import (
    RunStatus,
    create_run,
    new_manifest,
    new_run_id,
    write_manifest,
    write_pending_tasks,
)
from pedroarte_youtube_engine.lite.script_generation.operator_authored import (
    OperatorAuthoredScriptStrategy,
)
from pedroarte_youtube_engine.lite.script_generation.ports import ScriptGenerationRequest
from pedroarte_youtube_engine.lite.script_validators import validate_script
from pedroarte_youtube_engine.lite.video_spec import normalize_briefing
from pedroarte_youtube_engine.shared.paths import PathPolicy, write_text_atomic

# -- 1. BRIEFING REAL --------------------------------------------------------
# Não é fixture genérica: usa o próprio exemplo já existente no repositório
# (examples/sample_living_book/input/book.md, "O Relojoeiro de Vidro") como
# referência, pedindo uma continuação com desfecho — um briefing realista
# para este projeto específico (motor livro -> vídeo).
BRIEFING = BriefingSchema(
    topic="O mistério do Relojoeiro de Vidro: o que a inscrição impossível revela",
    objective=(
        "Contar uma história de mistério/fantástico completa e satisfatória, com "
        "desfecho, que prenda a atenção do espectador do início ao fim."
    ),
    audience="Adultos e jovens adultos interessados em ficção de mistério e fantástico, em português do Brasil.",
    language="pt-BR",
    tone="misterioso, contido, levemente melancólico",
    target_min_minutes=10.0,
    target_max_minutes=15.0,
    must_include=(
        "Elias Varga",
        "Mariana Duarte",
        "relógio de vidro",
        "inscrição",
    ),
    must_avoid=(
        "violência gráfica",
        "marca registrada",
    ),
    references=("examples/sample_living_book/input/book.md",),
    additional_context=(
        "Continuação direta dos quatro capítulos já existentes no repositório "
        "(personagem Elias Varga, relojoeiro de Portovelho; Mariana Duarte, "
        "cliente do cartório; o relógio de vidro com inscrição impossível "
        "gravada por dentro). Narração em terceira pessoa, um único narrador, "
        "sem exigir múltiplas vozes dramatizadas."
    ),
    visual_direction=(
        "Oficina de relojoaria à luz de lampião, tons quentes de âmbar contra "
        "azul petróleo escuro, ilustração cinematográfica melancólica, sem "
        "rostos de pessoas reais."
    ),
    factuality_mode=FactualityMode.CREATIVE,
)

SCRIPT_SOURCE_PATH = Path(__file__).with_name("gate3a_script_source.md")
MODEL_LABEL = "claude-sonnet-5 (Claude Code, operator session)"


def main() -> int:
    run_id = new_run_id("gate3a-script")
    paths = create_run(run_id)
    print(f"[gate3a] run_id={run_id}")
    print(f"[gate3a] run_dir={paths.root}")

    manifest = new_manifest(
        run_id=run_id,
        gate="gate3a",
        owner="claude_code",
        briefing_source="real:relojoeiro_de_vidro_continuation",
    )
    write_pending_tasks(
        paths,
        [
            {"id": "briefing", "status": "in_progress"},
            {"id": "video_spec", "status": "pending"},
            {"id": "script_generation", "status": "pending"},
            {"id": "script_validation", "status": "pending"},
        ],
    )

    policy = PathPolicy.for_roots(paths.root)
    evidence: list[dict[str, object]] = []

    # -- briefing -------------------------------------------------------
    briefing_path = paths.input_dir / "briefing.json"
    write_text_atomic(
        briefing_path,
        json.dumps(BRIEFING.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        policy,
    )
    evidence.append(
        {
            "step": "briefing",
            "command": "BriefingSchema(...) — briefing real, não fixture genérica",
            "expected": "briefing válido (Pydantic estrito)",
            "actual": f"topic={BRIEFING.topic!r}",
            "result": "PASS",
            "artifact": str(briefing_path),
        }
    )

    # -- video specification ----------------------------------------------
    spec = normalize_briefing(BRIEFING)
    spec_path = paths.working_dir / "video_specification.json"
    write_text_atomic(
        spec_path, json.dumps(asdict(spec), ensure_ascii=False, indent=2) + "\n", policy
    )
    evidence.append(
        {
            "step": "video_spec",
            "command": "normalize_briefing(briefing)",
            "expected": "faixa de palavras estimada a partir da duração-alvo",
            "actual": f"estimated_word_range={spec.estimated_word_range}",
            "result": "PASS",
            "artifact": str(spec_path),
        }
    )
    manifest["status"] = RunStatus.SCRIPT_READY.value

    # -- script generation (operator-authored, real, não fixture) ------------
    if not SCRIPT_SOURCE_PATH.exists():
        raise SystemExit(
            f"GATE_3A_BLOCKED: {SCRIPT_SOURCE_PATH} não encontrado. "
            "Nenhum LLM/capability disponível gerou o roteiro — não substituir "
            "silenciosamente por texto hardcoded (regra 40)."
        )
    script_text = SCRIPT_SOURCE_PATH.read_text(encoding="utf-8").strip()

    strategy = OperatorAuthoredScriptStrategy(script_text=script_text, model_label=MODEL_LABEL)
    generation_result = strategy.generate(
        ScriptGenerationRequest(specification=spec, reference_text="")
    )

    script_path = paths.working_dir / "script.md"
    write_text_atomic(script_path, generation_result.script_text + "\n", policy)
    evidence.append(
        {
            "step": "script_generation",
            "command": f"OperatorAuthoredScriptStrategy.generate (method={generation_result.method})",
            "expected": "script.md real, composto para este briefing específico",
            "actual": f"model={generation_result.model}",
            "result": "PASS",
            "artifact": str(script_path),
        }
    )
    manifest["provenance"]["script"] = {
        "method": generation_result.method,
        "provider": generation_result.provider,
        "model": generation_result.model,
        "input_tokens": generation_result.input_tokens,
        "output_tokens": generation_result.output_tokens,
    }

    # -- deterministic validators -------------------------------------------
    report = validate_script(generation_result.script_text, spec)
    report_path = paths.working_dir / "validation_report.json"
    write_text_atomic(
        report_path, json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n", policy
    )
    evidence.append(
        {
            "step": "script_validation",
            "command": "validate_script(script_text, specification)",
            "expected": "relatório determinístico (status, checks, human_review_required=True)",
            "actual": (
                f"status={report.status.value} words={report.word_count} "
                f"duration~{report.estimated_duration_seconds:.1f}s "
                f"({report.duration_status.value})"
            ),
            "result": "PASS" if report.status.value != "FAIL" else "FAIL",
            "artifact": str(report_path),
        }
    )
    manifest["qa"]["automated"] = report.as_dict()
    manifest["status"] = (
        RunStatus.SCRIPT_READY.value if report.status.value != "FAIL" else RunStatus.FAILED.value
    )
    manifest["artifacts"] = [
        {"path": str(briefing_path), "kind": "briefing"},
        {"path": str(spec_path), "kind": "video_specification"},
        {"path": str(script_path), "kind": "script"},
        {"path": str(report_path), "kind": "validation_report"},
    ]

    write_manifest(paths, manifest)
    write_pending_tasks(
        paths,
        [{"id": step["step"], "status": "done"} for step in evidence]
        + [{"id": "human_gate_a", "status": "pending"}],
    )

    print("\n=== EVIDENCE LOG ===")
    for item in evidence:
        print(f"[{item['result']}] {item['step']}: {item['actual']}  ({item['artifact']})")

    print("\n=== VALIDATION REPORT ===")
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))

    print(f"\n[gate3a] manifest={paths.manifest_path}")
    print(f"[gate3a] script={script_path}")
    print(
        "\n[gate3a] STOP — HUMAN GATE A REQUIRED. "
        "Pergunta: 'Este roteiro é bom o suficiente para justificar produzir "
        "voz e imagens?' Aguardando HUMAN_PASS / HUMAN_PASS_WITH_NOTES / HUMAN_FAIL."
    )
    return 0 if report.status.value != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
