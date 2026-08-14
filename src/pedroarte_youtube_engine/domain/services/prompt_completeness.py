"""Completude do prompt (seção 25).

A lista de rejeição da seção 25.1 é implementada aqui de forma executável. O
exemplo canônico de prompt ruim — *"Uma cena cinematográfica de um homem
andando."* — falha em cinco verificações distintas deste serviço.
"""

from __future__ import annotations

import re

from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Severity
from pedroarte_youtube_engine.shared.text import count_words

AGENT = "AUDIOVISUAL_QUALITY_GUARDIAN_AGENT"

#: Abaixo deste número de palavras, uma descrição visual é vaga demais para um
#: gerador de vídeo produzir algo reprodutível.
MIN_ACTION_WORDS = 12
MIN_SETTING_WORDS = 8
MIN_FRAME_WORDS = 6

_PLACEHOLDER_RE = re.compile(
    r"\b(tbd|todo|placeholder|lorem ipsum|a definir|preencher|xxx|n/?a)\b|\{\{|<insira",
    re.IGNORECASE,
)

#: Movimentos de câmera fisicamente incompatíveis entre si no mesmo segmento.
_IMPOSSIBLE_COMBINATIONS: tuple[tuple[str, str], ...] = (
    ("estatica", "travelling"),
    ("estatica", "grua"),
    ("estatica", "orbital"),
    ("estatica", "steadicam"),
)


class PromptCompletenessService:
    """Reprova prompts incompletos, abstratos ou dependentes de contexto externo."""

    def validate_segment(self, segment: PromptSegment) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        video = segment.video

        issues.extend(self._check_placeholders(segment))
        issues.extend(self._check_density(segment))
        issues.extend(self._check_narrative_function(segment))
        issues.extend(self._check_characters(segment))
        issues.extend(self._check_camera(segment))
        issues.extend(self._check_provenance(segment))

        if not video.negative_constraints:
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_VIDEO_FIELD,
                    Severity.ERROR,
                    "O segmento não declara restrições negativas.",
                    field_path="video.negative_constraints",
                    suggested_fix="Liste o que não pode acontecer na imagem.",
                )
            )

        if video.initial_frame.strip() == video.final_frame.strip():
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.TOO_ABSTRACT,
                    Severity.ERROR,
                    "Quadro inicial e quadro final idênticos: o segmento não muda nada.",
                    field_path="video.final_frame",
                    suggested_fix="Descreva a mudança concreta ocorrida em dez segundos.",
                )
            )

        return issues

    # -- verificações ------------------------------------------------------

    def _check_placeholders(self, segment: PromptSegment) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        fields = {
            "video.action": segment.video.action,
            "video.setting": segment.video.setting,
            "video.performance": segment.video.performance,
            "video.lighting": segment.video.lighting,
            "video.initial_frame": segment.video.initial_frame,
            "video.final_frame": segment.video.final_frame,
            "narrative.purpose": segment.narrative.purpose,
        }
        for path, value in fields.items():
            if _PLACEHOLDER_RE.search(value):
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.PLACEHOLDER,
                        Severity.CRITICAL,
                        f"Placeholder encontrado em {path}.",
                        field_path=path,
                        observed=value[:120],
                        suggested_fix="Substitua por conteúdo real e específico.",
                    )
                )
        return issues

    def _check_density(self, segment: PromptSegment) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        checks = (
            ("video.action", segment.video.action, MIN_ACTION_WORDS),
            ("video.setting", segment.video.setting, MIN_SETTING_WORDS),
            ("video.initial_frame", segment.video.initial_frame, MIN_FRAME_WORDS),
            ("video.final_frame", segment.video.final_frame, MIN_FRAME_WORDS),
        )
        for path, value, minimum in checks:
            words = count_words(value)
            if words < minimum:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.TOO_ABSTRACT,
                        Severity.ERROR,
                        (
                            f"{path} é abstrato demais: {words} palavras "
                            f"(mínimo {minimum} para ser reprodutível)."
                        ),
                        field_path=path,
                        observed=value[:120],
                        expected=f"pelo menos {minimum} palavras concretas",
                        suggested_fix=(
                            "Descreva o que se vê: quem, onde, fazendo o quê, com qual "
                            "objeto, sob qual luz."
                        ),
                    )
                )
        return issues

    def _check_narrative_function(self, segment: PromptSegment) -> list[ValidationIssue]:
        if count_words(segment.narrative.purpose) < 5:
            return [
                self._issue(
                    segment,
                    IssueCategory.TOO_ABSTRACT,
                    Severity.ERROR,
                    "O segmento não declara uma função narrativa compreensível.",
                    field_path="narrative.purpose",
                    suggested_fix="Explique o que muda entre o primeiro e o último quadro.",
                )
            ]
        return []

    def _check_characters(self, segment: PromptSegment) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for presence in segment.video.characters:
            if count_words(presence.appearance_anchor) < 10:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.CHARACTER_WITHOUT_IDENTITY,
                        Severity.ERROR,
                        (
                            f"O personagem {presence.display_name} aparece sem âncora "
                            "visual suficiente."
                        ),
                        field_path="video.characters[].appearance_anchor",
                        suggested_fix=(
                            "Reinjete a ficha de aparência da Bíblia de Personagens: idade, "
                            "estrutura facial, cabelo, olhos, traços distintivos."
                        ),
                    )
                )
            if not presence.wardrobe.strip():
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.CHARACTER_WITHOUT_IDENTITY,
                        Severity.ERROR,
                        f"O personagem {presence.display_name} aparece sem figurino definido.",
                        field_path="video.characters[].wardrobe",
                        suggested_fix="Defina o conjunto de figurino vigente neste ponto da história.",
                    )
                )
        return issues

    def _check_camera(self, segment: PromptSegment) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        camera = segment.video.camera
        movement = camera.movement.value.lower()
        descriptor = f"{movement} {camera.movement_speed}".lower()
        for static_token, motion_token in _IMPOSSIBLE_COMBINATIONS:
            if static_token in descriptor and motion_token in descriptor:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.IMPOSSIBLE_CAMERA,
                        Severity.ERROR,
                        (
                            "Direção de câmera contraditória: "
                            f"{static_token} e {motion_token} no mesmo segmento."
                        ),
                        field_path="video.camera.movement",
                        suggested_fix="Escolha um único comportamento de câmera para o segmento.",
                    )
                )
        if not camera.focus.strip() or not camera.depth_of_field.strip():
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_VIDEO_FIELD,
                    Severity.ERROR,
                    "Direção de câmera sem foco ou sem profundidade de campo.",
                    field_path="video.camera",
                    suggested_fix="Informe onde está o foco e qual é a profundidade de campo.",
                )
            )
        return issues

    def _check_provenance(self, segment: PromptSegment) -> list[ValidationIssue]:
        if not segment.source_references:
            return [
                self._issue(
                    segment,
                    IssueCategory.MISSING_PROVENANCE,
                    Severity.WARNING,
                    "O segmento não aponta para nenhum trecho da obra.",
                    field_path="source_references",
                    suggested_fix=(
                        "Referencie o capítulo e o trecho que sustentam a cena, ou registre "
                        "explicitamente que é uma ponte de adaptação."
                    ),
                )
            ]
        return []

    # -- agregação ---------------------------------------------------------

    def validate_many(self, segments: tuple[PromptSegment, ...]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        passed = 0
        for segment in segments:
            segment_issues = self.validate_segment(segment)
            if not segment_issues:
                passed += 1
            issues.extend(segment_issues)
        return ValidationReport(
            gate="prompt_completeness",
            issues=tuple(issues),
            checked_count=len(segments),
            passed_count=passed,
        )

    def _issue(
        self,
        segment: PromptSegment,
        category: IssueCategory,
        severity: Severity,
        message: str,
        *,
        field_path: str,
        suggested_fix: str = "",
        observed: str = "",
        expected: str = "",
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
            suggested_fix=suggested_fix,
            observed=observed,
            expected=expected,
        )
