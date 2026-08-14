"""Consistência com o cânone (`CANON_GUARDIAN_AGENT`).

Compara o que os prompts afirmam com o que a obra sustenta. Detecta invenção
indevida — personagens, lugares e objetos que o livro não contém — e conflitos
com regras e proibições declaradas do universo.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.aggregates import CanonBible
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Severity
from pedroarte_youtube_engine.shared.text import strip_accents

AGENT = "CANON_GUARDIAN_AGENT"


class CanonConsistencyService:
    """Bloqueia violações graves; sinaliza as demais."""

    def validate(
        self, segments: tuple[PromptSegment, ...], canon: CanonBible
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        known_locations = {
            _normalize(location.canonical_name) for location in canon.locations
        }
        known_props = {_normalize(prop.canonical_name) for prop in canon.props}
        prohibitions = tuple(_normalize(rule) for rule in canon.prohibitions)

        for segment in segments:
            issues.extend(self._check_characters(segment, canon))
            issues.extend(self._check_location(segment, canon, known_locations))
            issues.extend(self._check_props(segment, known_props))
            issues.extend(self._check_prohibitions(segment, prohibitions))

        failing = {issue.segment_id for issue in issues if issue.segment_id}
        return ValidationReport(
            gate="canon_consistency",
            issues=tuple(issues),
            checked_count=len(segments),
            passed_count=max(0, len(segments) - len(failing)),
        )

    def _check_characters(
        self, segment: PromptSegment, canon: CanonBible
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for presence in segment.video.characters:
            if canon.character(presence.character_id) is None:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.CANON_CONTRADICTION,
                        Severity.CRITICAL,
                        (
                            f"Personagem inventado: '{presence.display_name}' não consta "
                            "no cânone extraído da obra."
                        ),
                        field_path="video.characters[]",
                        repairable=True,
                        suggested_fix=(
                            "Substitua por um personagem canônico ou registre a criação "
                            "como decisão de adaptação explícita."
                        ),
                    )
                )
        return issues

    def _check_location(
        self,
        segment: PromptSegment,
        canon: CanonBible,
        known_locations: set[str],
    ) -> list[ValidationIssue]:
        location_id = segment.video.location_id
        if location_id is None:
            return []
        if canon.location(location_id) is None:
            return [
                self._issue(
                    segment,
                    IssueCategory.CANON_CONTRADICTION,
                    Severity.ERROR,
                    f"Local '{location_id}' não existe no cânone.",
                    field_path="video.location_id",
                    suggested_fix="Use um local extraído da obra.",
                )
            ]
        return []

    def _check_props(
        self, segment: PromptSegment, known_props: set[str]
    ) -> list[ValidationIssue]:
        if not known_props:
            return []
        issues: list[ValidationIssue] = []
        for prop in segment.video.relevant_props:
            normalized = _normalize(prop)
            if normalized and not any(
                normalized in known or known in normalized for known in known_props
            ):
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.CANON_CONTRADICTION,
                        Severity.INFO,
                        f"Objeto '{prop}' não aparece no inventário canônico.",
                        field_path="video.relevant_props",
                        suggested_fix=(
                            "Objetos de cenário genéricos são aceitáveis; objetos com peso "
                            "narrativo devem vir do livro."
                        ),
                    )
                )
        return issues

    def _check_prohibitions(
        self, segment: PromptSegment, prohibitions: tuple[str, ...]
    ) -> list[ValidationIssue]:
        if not prohibitions:
            return []
        haystack = _normalize(
            " ".join(
                (
                    segment.video.action,
                    segment.video.setting,
                    segment.video.performance,
                    segment.narrative.purpose,
                )
            )
        )
        issues: list[ValidationIssue] = []
        for rule in prohibitions:
            keyword = rule.strip()
            if len(keyword) >= 6 and keyword in haystack:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.CANON_CONTRADICTION,
                        Severity.ERROR,
                        f"O segmento toca uma proibição declarada do universo: '{rule}'.",
                        field_path="video.action",
                        suggested_fix="Reescreva a ação respeitando as regras do mundo.",
                    )
                )
        return issues

    def _issue(
        self,
        segment: PromptSegment,
        category: IssueCategory,
        severity: Severity,
        message: str,
        *,
        field_path: str,
        repairable: bool = True,
        suggested_fix: str = "",
    ) -> ValidationIssue:
        return make_issue(
            category=category,
            severity=severity,
            message=message,
            responsible_agent=AGENT,
            variant=segment.production_variant,
            episode_id=segment.episode_id,
            segment_id=segment.segment_id,
            field_path=field_path,
            repairable=repairable,
            suggested_fix=suggested_fix,
        )


def _normalize(value: str) -> str:
    return strip_accents(value).casefold().strip()
