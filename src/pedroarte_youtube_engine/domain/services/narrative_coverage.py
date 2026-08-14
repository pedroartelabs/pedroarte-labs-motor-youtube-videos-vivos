"""Cobertura narrativa e detecção de repetição.

Duas falhas opostas são medidas aqui: a adaptação que *perde* a obra (cobertura
insuficiente) e a adaptação que se *repete* (o mesmo momento reaproveitado
mecanicamente em vários formatos, proibido pela seção 5.6).
"""

from __future__ import annotations

from dataclasses import dataclass

from pedroarte_youtube_engine.domain.aggregates import CanonBible
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import ProductionVariant, Severity
from pedroarte_youtube_engine.shared.text import strip_accents

AGENT = "ADAPTATION_ARCHITECT_AGENT"

#: Abaixo desta fração de beats cobertos, o formato longo perde a obra.
MIN_LONG_FORM_COVERAGE = 0.70
MIN_MAIN_COVERAGE = 0.35
MIN_SERIES_COVERAGE = 0.60

#: Acima desta fração de segmentos idênticos, a montagem é repetitiva.
MAX_REPEATED_RATIO = 0.15


@dataclass(frozen=True, slots=True)
class CoverageResult:
    """Resultado bruto da medição de cobertura."""

    total_beats: int
    covered_beats: int

    @property
    def ratio(self) -> float:
        if self.total_beats == 0:
            return 1.0
        return self.covered_beats / self.total_beats


class NarrativeCoverageService:
    """Mede o quanto de obra sobreviveu à adaptação."""

    def measure(
        self, segments: tuple[PromptSegment, ...], canon: CanonBible
    ) -> CoverageResult:
        covered = {
            segment.narrative.beat.strip()
            for segment in segments
            if segment.narrative.beat.strip()
        }
        known = {beat.beat_id for beat in canon.beats}
        matched = len(covered & known) if known else len(covered)
        return CoverageResult(total_beats=len(known), covered_beats=matched)

    def minimum_for(self, variant: ProductionVariant) -> float:
        return {
            ProductionVariant.LONG_FORM: MIN_LONG_FORM_COVERAGE,
            ProductionVariant.SERIES: MIN_SERIES_COVERAGE,
            ProductionVariant.MINI_NOVELA: MIN_SERIES_COVERAGE,
            ProductionVariant.MAIN_10_MINUTES: MIN_MAIN_COVERAGE,
        }.get(variant, 0.0)

    def validate(
        self,
        segments: tuple[PromptSegment, ...],
        canon: CanonBible,
        *,
        variant: ProductionVariant,
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        coverage = self.measure(segments, canon)
        minimum = self.minimum_for(variant)

        if coverage.ratio < minimum:
            issues.append(
                make_issue(
                    category=IssueCategory.COVERAGE_GAP,
                    severity=Severity.WARNING,
                    message=(
                        f"Cobertura narrativa de {coverage.ratio:.0%} para {variant.value}, "
                        f"abaixo do piso de {minimum:.0%}."
                    ),
                    responsible_agent=AGENT,
                    variant=variant,
                    field_path="narrative.beat",
                    observed=f"{coverage.covered_beats}/{coverage.total_beats} beats",
                    suggested_fix=(
                        "Amplie a seleção de beats ou reveja a estratégia de condensação."
                    ),
                )
            )

        issues.extend(self._detect_repetition(segments, variant))

        return ValidationReport(
            gate="narrative_coverage",
            issues=tuple(issues),
            checked_count=max(1, len(segments)),
            passed_count=max(0, max(1, len(segments)) - len(issues)),
        )

    def _detect_repetition(
        self, segments: tuple[PromptSegment, ...], variant: ProductionVariant
    ) -> list[ValidationIssue]:
        if len(segments) < 4:
            return []
        seen: dict[str, PromptSegment] = {}
        repeated: list[tuple[PromptSegment, PromptSegment]] = []
        for segment in segments:
            fingerprint = _fingerprint(segment)
            first = seen.get(fingerprint)
            if first is None:
                seen[fingerprint] = segment
            else:
                repeated.append((first, segment))

        ratio = len(repeated) / len(segments)
        if ratio <= MAX_REPEATED_RATIO:
            return []

        return [
            make_issue(
                category=IssueCategory.REPEATED_SCENE,
                severity=Severity.WARNING,
                message=(
                    f"{len(repeated)} de {len(segments)} segmentos repetem uma cena já "
                    f"utilizada ({ratio:.0%})."
                ),
                responsible_agent=AGENT,
                variant=variant,
                segment_id=duplicate.segment_id,
                field_path="video.action",
                observed=f"idêntico a {original.segment_id}",
                suggested_fix=(
                    "Reescreva a cena com outro enquadramento, outro momento ou outra "
                    "função dramática."
                ),
            )
            for original, duplicate in repeated[:10]
        ]


def _fingerprint(segment: PromptSegment) -> str:
    """Assinatura textual de um segmento, insensível a acento e caixa."""
    raw = " ".join(
        (
            segment.video.action,
            segment.video.setting,
            segment.video.camera.shot_type.value,
        )
    )
    return strip_accents(raw).casefold().strip()
