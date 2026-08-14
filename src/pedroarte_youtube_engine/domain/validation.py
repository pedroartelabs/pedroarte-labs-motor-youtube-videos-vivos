"""Problemas de validação e relatórios de qualidade.

Os problemas são *estruturados* (não strings) porque alimentam o repair loop:
`RepairPlanner` precisa saber qual agente é responsável, qual segmento está
afetado e se a falha é reparável antes de decidir o que reexecutar.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from pedroarte_youtube_engine.domain.source import DomainEntity
from pedroarte_youtube_engine.domain.value_objects import (
    ProductionVariant,
    SegmentId,
    Severity,
)


class IssueCategory(StrEnum):
    """Categorias espelham a seção 25.1 da especificação."""

    MISSING_AUDIO = "audio_ausente"
    MISSING_VOICE = "voz_ausente"
    MISSING_VIDEO_FIELD = "campo_visual_ausente"
    CHARACTER_WITHOUT_IDENTITY = "personagem_sem_identidade"
    UNEXPLAINED_PHYSICAL_CHANGE = "mudanca_fisica_nao_explicada"
    SPEECH_TOO_LONG = "fala_longa_demais"
    IMPOSSIBLE_CAMERA = "camera_impossivel"
    ACTION_EXCEEDS_DURATION = "acao_maior_que_a_duracao"
    UNTRANSITIONED_LOCATION_CHANGE = "mudanca_de_ambiente_sem_transicao"
    INCOMPATIBLE_LIGHT = "luz_incompativel"
    VANISHING_PROP = "objeto_desaparecendo"
    REPEATED_SCENE = "repeticao_de_cena"
    TOO_ABSTRACT = "prompt_abstrato_demais"
    PLACEHOLDER = "uso_de_placeholder"
    MISSING_CONTEXT = "dependencia_de_contexto_nao_incluido"
    CANON_CONTRADICTION = "contradicao_com_o_livro"
    WRONG_TOTAL_DURATION = "duracao_total_incorreta"
    TIMECODE_INCONSISTENCY = "timecode_inconsistente"
    CONTINUITY_BREAK = "quebra_de_continuidade"
    PROVIDER_INCOMPATIBILITY = "incompatibilidade_com_provedor"
    MISSING_PROVENANCE = "proveniencia_ausente"
    RIGHTS_RISK = "risco_de_direitos"
    ACCESSIBILITY_GAP = "lacuna_de_acessibilidade"
    COVERAGE_GAP = "cobertura_narrativa_insuficiente"


class ValidationIssue(DomainEntity):
    """Um problema concreto, endereçado a um responsável."""

    issue_id: str = Field(min_length=3, max_length=128)
    category: IssueCategory
    severity: Severity
    message: str = Field(min_length=5, max_length=1200)
    variant: ProductionVariant | None = None
    episode_id: str | None = None
    segment_id: SegmentId | None = None
    field_path: str = Field(default="", max_length=200)
    responsible_agent: str = Field(default="", max_length=96)
    repairable: bool = True
    suggested_fix: str = Field(default="", max_length=800)
    observed: str = Field(default="", max_length=600)
    expected: str = Field(default="", max_length=600)

    @property
    def blocks_approval(self) -> bool:
        return self.severity.blocks_approval

    def location(self) -> str:
        parts = [part for part in (self.variant.value if self.variant else None,
                                   self.episode_id,
                                   str(self.segment_id) if self.segment_id else None,
                                   self.field_path or None) if part]
        return " / ".join(parts) or "projeto"


class ValidationReport(DomainEntity):
    """Consolidação dos problemas de um gate."""

    gate: str = Field(min_length=2, max_length=96)
    issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    checked_count: int = Field(default=0, ge=0)
    passed_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_counts(self) -> "ValidationReport":
        if self.passed_count > self.checked_count:
            raise ValueError("passed_count não pode exceder checked_count.")
        return self

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.ERROR)

    @property
    def criticals(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.CRITICAL)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is Severity.WARNING)

    @property
    def blocking_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocks_approval)

    @property
    def repairable_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.blocks_approval and issue.repairable
        )

    @property
    def passed(self) -> bool:
        return not self.blocking_issues

    @property
    def score(self) -> float:
        """Score do gate: proporção de verificações aprovadas, penalizada por críticos.

        Um único problema crítico zera o score — é exatamente o comportamento
        pedido por `fail_on_critical_issue`.
        """
        if self.criticals:
            return 0.0
        if self.checked_count == 0:
            return 1.0
        base = self.passed_count / self.checked_count
        penalty = 0.02 * len(self.warnings)
        return max(0.0, min(1.0, base - penalty))

    def merged_with(self, other: "ValidationReport") -> "ValidationReport":
        return ValidationReport(
            gate=f"{self.gate}+{other.gate}",
            issues=self.issues + other.issues,
            checked_count=self.checked_count + other.checked_count,
            passed_count=self.passed_count + other.passed_count,
        )


class QualityVerdict(StrEnum):
    APPROVED = "aprovado"
    APPROVED_WITH_WARNINGS = "aprovado_com_advertencias"
    REJECTED = "reprovado"


class QualityAssessment(DomainEntity):
    """Veredito final do `FINAL_QA_AGENT`."""

    verdict: QualityVerdict
    score: float = Field(ge=0.0, le=1.0)
    minimum_required: float = Field(ge=0.0, le=1.0)
    reports: tuple[ValidationReport, ...] = Field(default_factory=tuple)
    repair_iterations: int = Field(default=0, ge=0)
    summary: str = Field(default="", max_length=2000)

    @property
    def approved(self) -> bool:
        return self.verdict is not QualityVerdict.REJECTED

    @property
    def all_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for report in self.reports for issue in report.issues)

    @property
    def blocking_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.all_issues if issue.blocks_approval)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.all_issues if issue.severity is Severity.WARNING)

    @classmethod
    def from_reports(
        cls,
        reports: tuple[ValidationReport, ...],
        *,
        minimum_required: float,
        repair_iterations: int = 0,
        fail_on_critical: bool = True,
    ) -> "QualityAssessment":
        scores = [report.score for report in reports]
        score = sum(scores) / len(scores) if scores else 1.0
        has_critical = any(report.criticals for report in reports)
        has_blocking = any(report.blocking_issues for report in reports)
        has_warning = any(report.warnings for report in reports)

        if (has_critical and fail_on_critical) or has_blocking or score < minimum_required:
            verdict = QualityVerdict.REJECTED
        elif has_warning:
            verdict = QualityVerdict.APPROVED_WITH_WARNINGS
        else:
            verdict = QualityVerdict.APPROVED

        return cls(
            verdict=verdict,
            score=round(score, 4),
            minimum_required=minimum_required,
            reports=reports,
            repair_iterations=repair_iterations,
            summary=_build_summary(verdict, score, minimum_required, reports),
        )


def _build_summary(
    verdict: QualityVerdict,
    score: float,
    minimum: float,
    reports: tuple[ValidationReport, ...],
) -> str:
    total_issues = sum(len(report.issues) for report in reports)
    blocking = sum(len(report.blocking_issues) for report in reports)
    return (
        f"Veredito: {verdict.value}. Score {score:.4f} (mínimo {minimum:.2f}). "
        f"{len(reports)} gates avaliados, {total_issues} problemas registrados, "
        f"{blocking} bloqueantes."
    )
