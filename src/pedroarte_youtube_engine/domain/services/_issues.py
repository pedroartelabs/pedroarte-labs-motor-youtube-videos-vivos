"""Fábrica de `ValidationIssue` com identificadores determinísticos.

O id do problema é derivado do conteúdo, não de um contador: assim a mesma falha
recebe o mesmo id entre execuções, o que torna os relatórios diffáveis e permite
ao repair loop reconhecer um problema que reapareceu.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.validation import IssueCategory, ValidationIssue
from pedroarte_youtube_engine.domain.value_objects import (
    ProductionVariant,
    SegmentId,
    Severity,
)
from pedroarte_youtube_engine.shared.hashing import stable_short_id


def make_issue(
    *,
    category: IssueCategory,
    severity: Severity,
    message: str,
    responsible_agent: str,
    variant: ProductionVariant | None = None,
    episode_id: str | None = None,
    segment_id: SegmentId | None = None,
    field_path: str = "",
    repairable: bool = True,
    suggested_fix: str = "",
    observed: str = "",
    expected: str = "",
) -> ValidationIssue:
    """Cria um problema com id estável derivado do seu conteúdo."""
    fingerprint = stable_short_id(
        category.value,
        variant.value if variant else "",
        episode_id or "",
        str(segment_id) if segment_id else "",
        field_path,
        message,
        length=10,
    )
    return ValidationIssue(
        issue_id=f"{category.value}-{fingerprint}",
        category=category,
        severity=severity,
        message=message,
        variant=variant,
        episode_id=episode_id,
        segment_id=segment_id,
        field_path=field_path,
        responsible_agent=responsible_agent,
        repairable=repairable,
        suggested_fix=suggested_fix,
        observed=observed,
        expected=expected,
    )
