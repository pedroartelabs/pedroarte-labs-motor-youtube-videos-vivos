"""Gate 3A — unidades puras: BriefingSchema, VideoSpecification, validadores.

Não testa comportamento criativo do LLM como se fosse determinístico (regra
38 do briefing de Gate 3) — isso é provado pela execução real em
`scripts/lite/run_gate3a_script_proof.py`, não por um teste unitário.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pedroarte_youtube_engine.lite.briefing import BriefingSchema, FactualityMode
from pedroarte_youtube_engine.lite.script_validators import DurationStatus, ValidationStatus, validate_script
from pedroarte_youtube_engine.lite.video_spec import normalize_briefing


def _briefing(**overrides: object) -> BriefingSchema:
    defaults: dict[str, object] = {
        "topic": "Um tema de teste",
        "objective": "Testar o schema do briefing",
    }
    defaults.update(overrides)
    return BriefingSchema(**defaults)  # type: ignore[arg-type]


class TestBriefingSchema:
    def test_minimal_valid_briefing(self) -> None:
        briefing = _briefing()
        assert briefing.language == "pt-BR"
        assert briefing.target_min_minutes == 10.0
        assert briefing.target_max_minutes == 15.0
        assert briefing.factuality_mode is FactualityMode.GENERAL_KNOWLEDGE

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            BriefingSchema(topic="x", objective="y", unexpected_field="nope")  # type: ignore[call-arg]

    def test_rejects_max_duration_below_min(self) -> None:
        with pytest.raises(ValidationError):
            _briefing(target_min_minutes=15.0, target_max_minutes=10.0)

    def test_must_include_and_must_avoid_are_tuples(self) -> None:
        briefing = _briefing(must_include=["a", "b"], must_avoid=["c"])
        assert briefing.must_include == ("a", "b")
        assert briefing.must_avoid == ("c",)

    def test_is_frozen(self) -> None:
        briefing = _briefing()
        with pytest.raises(ValidationError):
            briefing.topic = "outra coisa"  # type: ignore[misc]


class TestVideoSpecification:
    def test_normalize_briefing_computes_word_range_from_duration(self) -> None:
        briefing = _briefing(target_min_minutes=10.0, target_max_minutes=15.0)
        spec = normalize_briefing(briefing)
        low, high = spec.estimated_word_range
        assert low < high
        # 150 wpm padrão: 10 min ~= 1500 palavras, 15 min ~= 2250 palavras.
        assert 1400 <= low <= 1600
        assert 2100 <= high <= 2400

    def test_normalize_briefing_carries_factuality_mode(self) -> None:
        briefing = _briefing(factuality_mode=FactualityMode.FACT_SENSITIVE)
        spec = normalize_briefing(briefing)
        assert spec.factuality_mode is FactualityMode.FACT_SENSITIVE


class TestScriptValidators:
    def _spec(self, **overrides: object):
        briefing = _briefing(**overrides)  # type: ignore[arg-type]
        return normalize_briefing(briefing)

    def test_too_short_script_is_blocking_fail(self) -> None:
        spec = self._spec(target_min_minutes=10.0, target_max_minutes=15.0)
        report = validate_script("Um roteiro muito curto.\n\nSó isso.", spec)
        assert report.duration_status is DurationStatus.TOO_SHORT
        assert report.status is ValidationStatus.FAIL

    def test_within_target_script_with_structure_passes(self) -> None:
        spec = self._spec(target_min_minutes=0.07, target_max_minutes=0.15)  # ~4.2-9s a 150wpm
        paragraph = " ".join(["palavra"] * 4)
        script = "\n\n".join([f"{paragraph} {i}." for i in range(4)])
        report = validate_script(script, spec)
        assert report.duration_status is DurationStatus.WITHIN_TARGET
        assert report.status in (ValidationStatus.PASS_, ValidationStatus.PASS_WITH_WARNINGS)

    def test_too_long_script_is_non_blocking_warning(self) -> None:
        spec = self._spec(target_min_minutes=0.001, target_max_minutes=0.002)
        paragraph = " ".join(["palavra"] * 20)
        script = "\n\n".join([f"{paragraph} {i}." for i in range(6)])
        report = validate_script(script, spec)
        assert report.duration_status is DurationStatus.TOO_LONG
        # TOO_LONG não é bloqueante por si só.
        assert report.status is not ValidationStatus.FAIL or any(
            c.name != "duration_within_target" and c.blocking and not c.passed
            for c in report.checks
        )

    def test_empty_script_fails(self) -> None:
        spec = self._spec()
        report = validate_script("", spec)
        assert report.status is ValidationStatus.FAIL

    def test_obvious_repetition_is_warning_not_blocking(self) -> None:
        spec = self._spec(target_min_minutes=0.01, target_max_minutes=0.05)
        paragraph = "Esta frase se repete sem nenhuma variação de conteúdo relevante aqui."
        script = "\n\n".join([paragraph] * 5)
        report = validate_script(script, spec)
        repetition_check = next(c for c in report.checks if c.name == "repetition")
        assert repetition_check.passed is False
        assert repetition_check.blocking is False

    def test_must_include_missing_blocks(self) -> None:
        spec = self._spec(must_include=["palavra-chave-inexistente"])
        script = "\n\n".join(["Um texto qualquer sem a palavra-chave."] * 4)
        report = validate_script(script, spec)
        coverage_check = next(c for c in report.checks if c.name == "must_include_coverage")
        assert coverage_check.passed is False
        assert report.status is ValidationStatus.FAIL

    def test_must_avoid_violation_blocks(self) -> None:
        spec = self._spec(must_avoid=["palavra proibida"])
        script = "\n\n".join(["Este texto contém a palavra proibida aqui dentro."] * 4)
        report = validate_script(script, spec)
        avoid_check = next(c for c in report.checks if c.name == "must_avoid_violations")
        assert avoid_check.passed is False
        assert report.status is ValidationStatus.FAIL

    def test_human_review_always_required(self) -> None:
        spec = self._spec()
        report = validate_script("Um texto qualquer.\n\nMais um pouco.\n\nE mais.\n\nFim.", spec)
        assert report.human_review_required is True
