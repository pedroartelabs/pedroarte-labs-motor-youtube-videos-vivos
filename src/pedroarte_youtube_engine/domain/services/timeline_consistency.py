"""Consistência de timecodes e durações.

Este serviço sustenta três exigências da Definition of Done: os timecodes são
consistentes, as durações são validadas e o vídeo principal tem *exatamente* a
duração configurada.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.production import FormatProfile
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Duration, Severity

AGENT = "SCENE_DECOMPOSER_AGENT"


class TimelineConsistencyService:
    """Verifica monotonicidade, contiguidade e fechamento exato da duração."""

    def validate(
        self,
        segments: tuple[PromptSegment, ...],
        *,
        profile: FormatProfile,
        episode_id: str | None = None,
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []

        if not segments:
            issues.append(
                make_issue(
                    category=IssueCategory.WRONG_TOTAL_DURATION,
                    severity=Severity.CRITICAL,
                    message=f"O perfil {profile.profile_id} não produziu nenhum segmento.",
                    responsible_agent=AGENT,
                    variant=profile.variant,
                    episode_id=episode_id,
                    field_path="segments",
                )
            )
            return ValidationReport(
                gate="timeline_consistency", issues=tuple(issues), checked_count=1, passed_count=0
            )

        issues.extend(self._check_monotonic(segments, profile, episode_id))
        issues.extend(self._check_numbering(segments, profile, episode_id))
        issues.extend(self._check_segment_durations(segments, profile, episode_id))
        issues.extend(self._check_total_duration(segments, profile, episode_id))

        checks = len(segments) + 2
        return ValidationReport(
            gate="timeline_consistency",
            issues=tuple(issues),
            checked_count=checks,
            passed_count=max(0, checks - len(issues)),
        )

    def _check_monotonic(
        self,
        segments: tuple[PromptSegment, ...],
        profile: FormatProfile,
        episode_id: str | None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for previous, current in zip(segments, segments[1:], strict=False):
            if current.range.start.milliseconds < previous.range.end.milliseconds:
                issues.append(
                    make_issue(
                        category=IssueCategory.TIMECODE_INCONSISTENCY,
                        severity=Severity.CRITICAL,
                        message=(
                            "Sobreposição indevida de timecodes: "
                            f"{current.range.start} começa antes de {previous.range.end}."
                        ),
                        responsible_agent=AGENT,
                        variant=profile.variant,
                        episode_id=episode_id,
                        segment_id=current.segment_id,
                        field_path="range.start",
                    )
                )
            elif current.range.start.milliseconds > previous.range.end.milliseconds:
                gap = current.range.start.milliseconds - previous.range.end.milliseconds
                issues.append(
                    make_issue(
                        category=IssueCategory.TIMECODE_INCONSISTENCY,
                        severity=Severity.ERROR,
                        message=f"Lacuna não autorizada de {gap} ms entre segmentos.",
                        responsible_agent=AGENT,
                        variant=profile.variant,
                        episode_id=episode_id,
                        segment_id=current.segment_id,
                        field_path="range.start",
                        suggested_fix="Segmentos devem ser contíguos dentro de um episódio.",
                    )
                )
        return issues

    def _check_numbering(
        self,
        segments: tuple[PromptSegment, ...],
        profile: FormatProfile,
        episode_id: str | None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for expected, segment in enumerate(segments, start=1):
            if segment.segment_number != expected:
                issues.append(
                    make_issue(
                        category=IssueCategory.TIMECODE_INCONSISTENCY,
                        severity=Severity.ERROR,
                        message=(
                            f"Numeração fora de sequência: esperado {expected}, "
                            f"encontrado {segment.segment_number}."
                        ),
                        responsible_agent=AGENT,
                        variant=profile.variant,
                        episode_id=episode_id,
                        segment_id=segment.segment_id,
                        field_path="segment_number",
                    )
                )
        return issues

    def _check_segment_durations(
        self,
        segments: tuple[PromptSegment, ...],
        profile: FormatProfile,
        episode_id: str | None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        expected = profile.segment_duration.milliseconds
        for segment in segments:
            measured = segment.range.duration.milliseconds
            if measured != expected:
                issues.append(
                    make_issue(
                        category=IssueCategory.TIMECODE_INCONSISTENCY,
                        severity=Severity.ERROR,
                        message=(
                            f"Segmento com {measured} ms, esperado {expected} ms."
                        ),
                        responsible_agent=AGENT,
                        variant=profile.variant,
                        episode_id=episode_id,
                        segment_id=segment.segment_id,
                        field_path="duration.target",
                        observed=f"{measured} ms",
                        expected=f"{expected} ms",
                    )
                )
        return issues

    def _check_total_duration(
        self,
        segments: tuple[PromptSegment, ...],
        profile: FormatProfile,
        episode_id: str | None,
    ) -> list[ValidationIssue]:
        total = sum(segment.range.duration.milliseconds for segment in segments)
        expected = profile.total_duration.milliseconds
        issues: list[ValidationIssue] = []
        if total != expected:
            issues.append(
                make_issue(
                    category=IssueCategory.WRONG_TOTAL_DURATION,
                    severity=Severity.CRITICAL,
                    message=(
                        f"A duração total de {profile.profile_id} é {total / 1000:.3f}s, "
                        f"mas a configuração exige exatamente {expected / 1000:.3f}s."
                    ),
                    responsible_agent=AGENT,
                    variant=profile.variant,
                    episode_id=episode_id,
                    field_path="total_duration",
                    observed=f"{total / 1000:.3f}s",
                    expected=f"{expected / 1000:.3f}s",
                )
            )
        minimum = profile.minimum_duration
        if minimum is not None and total < minimum.milliseconds:
            issues.append(
                make_issue(
                    category=IssueCategory.WRONG_TOTAL_DURATION,
                    severity=Severity.CRITICAL,
                    message=(
                        f"{profile.profile_id} tem {total / 1000:.1f}s, abaixo do mínimo "
                        f"de {minimum.seconds:.1f}s exigido para o formato."
                    ),
                    responsible_agent=AGENT,
                    variant=profile.variant,
                    episode_id=episode_id,
                    field_path="total_duration",
                )
            )
        return issues

    @staticmethod
    def total_duration(segments: tuple[PromptSegment, ...]) -> Duration:
        return Duration(
            milliseconds=sum(segment.range.duration.milliseconds for segment in segments)
        )
