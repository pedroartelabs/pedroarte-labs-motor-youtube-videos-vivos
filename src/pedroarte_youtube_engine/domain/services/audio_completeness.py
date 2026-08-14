"""Completude de áudio — o gate que sustenta a regra 3.1.

Um prompt de vídeo sem áudio não passa daqui. E "com áudio" não significa
"tem um campo de áudio preenchido": significa plano vocal explícito, ambiente,
mixagem, e falas que cabem no tempo disponível.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.production import FormatProfile
from pedroarte_youtube_engine.domain.segment import PromptSegment, VocalDecision
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Severity

AGENT = "AUDIOVISUAL_QUALITY_GUARDIAN_AGENT"


class AudioCompletenessService:
    """Verifica que cada segmento soa, e soa de forma executável."""

    def __init__(self, *, speech_rate_wpm: float = 150.0) -> None:
        self._speech_rate = speech_rate_wpm

    def validate_segment(
        self, segment: PromptSegment, *, profile: FormatProfile | None = None
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        audio = segment.audio

        # 1. Plano vocal explícito — a invariante estrutural já garante que ele
        #    existe; aqui checamos que ele é *significativo*.
        if not audio.voice_plan:
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_VOICE,
                    Severity.CRITICAL,
                    "O segmento não declara nenhuma decisão vocal.",
                    field_path="audio.voice_plan",
                    suggested_fix=(
                        "Declare ao menos uma decisão vocal: fala, narração, respiração, "
                        "murmúrio, reação, choro, riso, grito distante, vocalização ou "
                        "silêncio vocal intencional justificado."
                    ),
                )
            )

        for entry in audio.voice_plan:
            if entry.decision is VocalDecision.INTENTIONAL_SILENCE and not entry.justification:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.MISSING_VOICE,
                        Severity.ERROR,
                        "Silêncio vocal declarado sem justificativa narrativa.",
                        field_path="audio.voice_plan[].justification",
                        suggested_fix="Explique por que a ausência de voz serve à cena.",
                    )
                )

        # 2. Som ambiente — nenhum lugar do mundo é mudo.
        if not audio.ambient_sound:
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_AUDIO,
                    Severity.ERROR,
                    "O segmento não descreve som ambiente.",
                    field_path="audio.ambient_sound",
                    suggested_fix="Descreva os sons persistentes do local.",
                )
            )

        # 3. Mixagem — sem prioridade, o gerador decide sozinho e erra.
        if not audio.mixing_notes:
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_AUDIO,
                    Severity.ERROR,
                    "O segmento não define prioridades de mixagem.",
                    field_path="audio.mixing_notes",
                    suggested_fix="Defina a prioridade relativa entre voz, ambiente, efeitos e música.",
                )
            )

        # 4. Falas cabem no tempo — a causa nº 1 de áudio acelerado.
        for line in audio.all_spoken_lines():
            if not line.fits_in_range:
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.SPEECH_TOO_LONG,
                        Severity.ERROR,
                        (
                            f"Fala de {line.word_count} palavras não cabe em "
                            f"{line.range.duration.seconds:.1f}s "
                            f"(≈{line.estimated_speech_seconds:.1f}s a "
                            f"{self._speech_rate:.0f} palavras por minuto)."
                        ),
                        field_path="audio.dialogue[].text",
                        observed=f"{line.estimated_speech_seconds:.1f}s de fala",
                        expected=f"até {line.range.duration.seconds * 1.15:.1f}s",
                        suggested_fix="Reduza o texto ou amplie a janela reservada à fala.",
                    )
                )

        # 5. Música coerente com o perfil do formato.
        if profile is not None and not profile.music_enabled and audio.music.enabled:
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_AUDIO,
                    Severity.WARNING,
                    "Música habilitada em um formato que a desabilitou na configuração.",
                    field_path="audio.music.enabled",
                    suggested_fix="Desative a música ou revise a configuração do formato.",
                )
            )

        # 6. Efeitos sonoros ancorados em ações visíveis.
        for effect in audio.sound_effects:
            if not effect.synced_to_action.strip():
                issues.append(
                    self._issue(
                        segment,
                        IssueCategory.MISSING_AUDIO,
                        Severity.WARNING,
                        "Efeito sonoro sem ação correspondente.",
                        field_path="audio.sound_effects[].synced_to_action",
                        suggested_fix="Amarre o efeito a uma ação visível ou marque-o como fora de quadro.",
                    )
                )

        # 7. Transição sonora de saída.
        if not audio.audio_transition_out.strip():
            issues.append(
                self._issue(
                    segment,
                    IssueCategory.MISSING_AUDIO,
                    Severity.ERROR,
                    "O segmento não descreve como o áudio conduz ao próximo.",
                    field_path="audio.audio_transition_out",
                    suggested_fix="Descreva a ponte sonora, o corte seco ou o silêncio de passagem.",
                )
            )

        return issues

    def validate_many(
        self,
        segments: tuple[PromptSegment, ...],
        *,
        profile: FormatProfile | None = None,
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        passed = 0
        for segment in segments:
            segment_issues = self.validate_segment(segment, profile=profile)
            if not segment_issues:
                passed += 1
            issues.extend(segment_issues)
        return ValidationReport(
            gate="audio_completeness",
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
