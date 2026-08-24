"""Validadores determinísticos do roteiro (SDD_SPDD.md §38.5).

Regra crítica (regra 44 do briefing de Gate 3): código consegue verificar
tamanho, duração estimada, constraints, estrutura mínima e repetições
grosseiras. Código NÃO mede interesse, emoção, ritmo, curiosidade, retenção,
originalidade ou qualidade editorial — por isso `human_review_required` é
sempre `True` neste v0.1, independentemente do resultado dos checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pedroarte_youtube_engine.lite.video_spec import VideoSpecification
from pedroarte_youtube_engine.shared.text import count_words, speakable_duration_seconds


class DurationStatus(StrEnum):
    TOO_SHORT = "TOO_SHORT"
    WITHIN_TARGET = "WITHIN_TARGET"
    TOO_LONG = "TOO_LONG"


class ValidationStatus(StrEnum):
    PASS_ = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


@dataclass(slots=True)
class ValidatorCheck:
    name: str
    passed: bool
    blocking: bool
    detail: str = ""


@dataclass(slots=True)
class ScriptValidationReport:
    status: ValidationStatus
    word_count: int
    estimated_duration_seconds: float
    duration_status: DurationStatus
    checks: list[ValidatorCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    human_review_required: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "word_count": self.word_count,
            "estimated_duration_seconds": round(self.estimated_duration_seconds, 1),
            "duration_status": self.duration_status.value,
            "checks": [
                {"name": c.name, "passed": c.passed, "blocking": c.blocking, "detail": c.detail}
                for c in self.checks
            ],
            "warnings": self.warnings,
            "human_review_required": self.human_review_required,
        }


def _paragraphs(script_text: str) -> list[str]:
    return [p.strip() for p in script_text.split("\n\n") if p.strip()]


def _duration_status(seconds: float, spec: VideoSpecification) -> DurationStatus:
    min_seconds = spec.target_min_minutes * 60.0
    max_seconds = spec.target_max_minutes * 60.0
    if seconds < min_seconds:
        return DurationStatus.TOO_SHORT
    if seconds > max_seconds:
        return DurationStatus.TOO_LONG
    return DurationStatus.WITHIN_TARGET


def _check_must_include(script_text: str, must_include: tuple[str, ...]) -> ValidatorCheck:
    lowered = script_text.lower()
    missing = [item for item in must_include if item.lower() not in lowered]
    passed = not missing
    detail = "todos os itens encontrados (correspondência literal)" if passed else (
        f"não encontrados literalmente: {', '.join(missing)} "
        "(pode ser falso negativo — verificação humana necessária para paráfrases)"
    )
    return ValidatorCheck("must_include_coverage", passed, blocking=True, detail=detail)


def _check_must_avoid(script_text: str, must_avoid: tuple[str, ...]) -> ValidatorCheck:
    lowered = script_text.lower()
    found = [item for item in must_avoid if item.lower() in lowered]
    passed = not found
    detail = "nenhum padrão proibido encontrado" if passed else f"encontrados: {', '.join(found)}"
    return ValidatorCheck("must_avoid_violations", passed, blocking=True, detail=detail)


def _check_repetition(paragraphs: list[str]) -> ValidatorCheck:
    """Heurística grosseira: parágrafos consecutivos com abertura idêntica, ou
    parágrafo duplicado na íntegra. Não é um motor de repetição semântica."""
    duplicates = 0
    seen: set[str] = set()
    for paragraph in paragraphs:
        normalized = " ".join(paragraph.lower().split())
        if normalized in seen:
            duplicates += 1
        seen.add(normalized)

    consecutive_same_opening = 0
    for previous, current in zip(paragraphs, paragraphs[1:]):
        prev_start = " ".join(previous.lower().split()[:5])
        cur_start = " ".join(current.lower().split()[:5])
        if prev_start and prev_start == cur_start:
            consecutive_same_opening += 1

    passed = duplicates == 0 and consecutive_same_opening == 0
    detail = (
        "sem repetição grosseira detectada"
        if passed
        else f"{duplicates} parágrafo(s) duplicado(s), {consecutive_same_opening} abertura(s) repetida(s)"
    )
    return ValidatorCheck("repetition", passed, blocking=False, detail=detail)


def _check_structure(paragraphs: list[str]) -> ValidatorCheck:
    """Confirma só a EXISTÊNCIA de abertura/desenvolvimento/fechamento
    reconhecíveis por proporção — nunca a qualidade deles (isso é humano)."""
    passed = len(paragraphs) >= 4
    detail = (
        f"{len(paragraphs)} parágrafos — estrutura mínima presente"
        if passed
        else f"apenas {len(paragraphs)} parágrafo(s) — abaixo do mínimo de 4 para "
        "abertura/desenvolvimento/fechamento reconhecíveis"
    )
    return ValidatorCheck("structure_present", passed, blocking=False, detail=detail)


def _check_non_empty_sections(paragraphs: list[str], raw_text: str) -> ValidatorCheck:
    has_blank_between = "\n\n\n" in raw_text.replace("\r\n", "\n")
    passed = bool(paragraphs) and not has_blank_between
    detail = "sem seções vazias/malformadas" if passed else "seção vazia ou malformada detectada"
    return ValidatorCheck("non_empty_sections", passed, blocking=True, detail=detail)


def validate_script(script_text: str, specification: VideoSpecification) -> ScriptValidationReport:
    words = count_words(script_text)
    estimated_seconds = speakable_duration_seconds(script_text)
    duration_status = _duration_status(estimated_seconds, specification)
    paragraphs = _paragraphs(script_text)

    checks: list[ValidatorCheck] = [
        ValidatorCheck(
            "word_count_positive", words > 0, blocking=True, detail=f"{words} palavras"
        ),
        _check_non_empty_sections(paragraphs, script_text),
        _check_must_include(script_text, specification.must_include),
        _check_must_avoid(script_text, specification.must_avoid),
        _check_repetition(paragraphs),
        _check_structure(paragraphs),
        ValidatorCheck(
            "duration_within_target",
            duration_status is DurationStatus.WITHIN_TARGET,
            blocking=duration_status is DurationStatus.TOO_SHORT,
            detail=duration_status.value,
        ),
    ]

    blocking_failures = [c for c in checks if c.blocking and not c.passed]
    non_blocking_failures = [c for c in checks if not c.blocking and not c.passed]

    if blocking_failures:
        status = ValidationStatus.FAIL
    elif non_blocking_failures:
        status = ValidationStatus.PASS_WITH_WARNINGS
    else:
        status = ValidationStatus.PASS_

    warnings = [f"{c.name}: {c.detail}" for c in non_blocking_failures]

    return ScriptValidationReport(
        status=status,
        word_count=words,
        estimated_duration_seconds=estimated_seconds,
        duration_status=duration_status,
        checks=checks,
        warnings=warnings,
        human_review_required=True,
    )
