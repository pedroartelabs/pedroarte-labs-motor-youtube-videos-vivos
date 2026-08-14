"""Compatibilidade entre o segmento canônico e as capacidades do provedor.

A duração narrativa é sagrada; a duração do provedor é negociável. Quando o
provedor não aceita dez segundos, este serviço escolhe *como* dividir, estender
ou sobrepor — e registra a decisão, em vez de silenciosamente encurtar a cena.
"""

from __future__ import annotations

from dataclasses import dataclass

from pedroarte_youtube_engine.domain.provider import (
    CompilationStrategy,
    ProviderCapability,
    ProviderModality,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import (
    AspectRatio,
    Duration,
    Severity,
)

AGENT = "PROVIDER_CAPABILITY_AGENT"


@dataclass(frozen=True, slots=True)
class CompilationDecision:
    """Como um segmento vira chamadas de provedor."""

    strategy: CompilationStrategy
    calls: int
    provider_duration: Duration
    uses_first_frame: bool
    uses_last_frame: bool
    rationale: str

    def describe(self) -> str:
        return (
            f"{self.strategy.value}: {self.calls} chamada(s) de "
            f"{self.provider_duration.seconds:.1f}s cobrindo "
            f"{self.calls * self.provider_duration.seconds:.1f}s de provedor. "
            f"{self.rationale}"
        )


class ProviderCapabilityMatchingService:
    """Escolhe a estratégia de compilação e reprova o que é incompatível."""

    def decide(
        self, *, target: Duration, capability: ProviderCapability
    ) -> CompilationDecision:
        """Decide como cobrir a duração narrativa com as chamadas disponíveis."""
        if capability.supports_duration(target):
            return CompilationDecision(
                strategy=CompilationStrategy.DIRECT,
                calls=1,
                provider_duration=target,
                uses_first_frame=capability.first_frame_reference,
                uses_last_frame=capability.last_frame_reference,
                rationale=(
                    "O provedor aceita a duração narrativa integral; nenhuma recompilação "
                    "é necessária."
                ),
            )

        if target.seconds > capability.max_duration_seconds:
            chunk = capability.best_fit_duration(target)
            calls = capability.calls_needed_for(target)
            if capability.video_extension:
                strategy = CompilationStrategy.EXTEND
                rationale = (
                    f"A duração alvo ({target.seconds:.0f}s) excede o máximo do provedor "
                    f"({capability.max_duration_seconds:.0f}s); a cena é estendida a partir "
                    "do último quadro gerado."
                )
            elif capability.last_frame_reference or capability.first_frame_reference:
                strategy = CompilationStrategy.FIRST_LAST_FRAME
                rationale = (
                    f"A cena é subdividida em {calls} chamadas encadeadas por quadro de "
                    "continuidade, preservando o timecode narrativo original."
                )
            else:
                strategy = CompilationStrategy.OVERLAP
                rationale = (
                    f"Sem referência de quadro, a cena é subdividida em {calls} chamadas com "
                    "sobreposição descritiva para manter a continuidade."
                )
            return CompilationDecision(
                strategy=strategy,
                calls=calls,
                provider_duration=chunk,
                uses_first_frame=capability.first_frame_reference,
                uses_last_frame=capability.last_frame_reference,
                rationale=rationale,
            )

        # A duração alvo é menor que o mínimo do provedor.
        minimum = Duration.from_seconds(capability.min_duration_seconds)
        return CompilationDecision(
            strategy=CompilationStrategy.EXTEND,
            calls=1,
            provider_duration=minimum,
            uses_first_frame=capability.first_frame_reference,
            uses_last_frame=capability.last_frame_reference,
            rationale=(
                f"A duração alvo ({target.seconds:.1f}s) fica abaixo do mínimo do provedor "
                f"({capability.min_duration_seconds:.1f}s); a geração é estendida e o "
                "excedente é aparado na montagem, preservando o timecode narrativo."
            ),
        )

    def validate_segment(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        fmt = segment.segment_format

        if not capability.supports_aspect_ratio(fmt.aspect_ratio):
            issues.append(
                self._issue(
                    segment,
                    f"Proporção {fmt.aspect_ratio} não suportada por "
                    f"{capability.provider}/{capability.model}.",
                    field_path="segment_format.aspect_ratio",
                    observed=str(fmt.aspect_ratio),
                    expected=", ".join(capability.supported_aspect_ratios),
                )
            )

        if not capability.supports_resolution(fmt.resolution.label):
            issues.append(
                self._issue(
                    segment,
                    f"Resolução {fmt.resolution.label} não suportada por "
                    f"{capability.provider}/{capability.model}.",
                    field_path="segment_format.resolution",
                    observed=fmt.resolution.label,
                    expected=", ".join(capability.supported_resolutions),
                    severity=Severity.WARNING,
                )
            )

        if (
            capability.modality is ProviderModality.VIDEO
            and segment.audio.has_spoken_words
            and not capability.dialogue_support
        ):
            issues.append(
                self._issue(
                    segment,
                    (
                        f"O segmento contém fala, mas {capability.provider}/{capability.model} "
                        "não gera diálogo nativo. O áudio precisa de um provedor de voz "
                        "separado."
                    ),
                    field_path="audio.dialogue",
                    severity=Severity.WARNING,
                    suggested_fix=(
                        "Configure um `VoiceGenerationProviderPort` e mantenha o pacote de "
                        "áudio separado do vídeo."
                    ),
                )
            )

        compilation = segment.provider_compilation
        if compilation is not None and compilation.compiled_prompt:
            if len(compilation.compiled_prompt) > capability.max_prompt_characters:
                issues.append(
                    self._issue(
                        segment,
                        (
                            f"Prompt compilado com {len(compilation.compiled_prompt)} "
                            f"caracteres excede o limite de "
                            f"{capability.max_prompt_characters}."
                        ),
                        field_path="provider_compilation.compiled_prompt",
                        suggested_fix="Compacte a descrição preservando os campos obrigatórios.",
                    )
                )

        return issues

    def validate_many(
        self, segments: tuple[PromptSegment, ...], capability: ProviderCapability
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        passed = 0
        for segment in segments:
            segment_issues = self.validate_segment(segment, capability)
            if not segment_issues:
                passed += 1
            issues.extend(segment_issues)
        return ValidationReport(
            gate="provider_capability",
            issues=tuple(issues),
            checked_count=len(segments),
            passed_count=passed,
        )

    def _issue(
        self,
        segment: PromptSegment,
        message: str,
        *,
        field_path: str,
        severity: Severity = Severity.ERROR,
        observed: str = "",
        expected: str = "",
        suggested_fix: str = "",
    ) -> ValidationIssue:
        return make_issue(
            category=IssueCategory.PROVIDER_INCOMPATIBILITY,
            severity=severity,
            message=message,
            responsible_agent=AGENT,
            variant=segment.production_variant,
            episode_id=segment.episode_id,
            segment_id=segment.segment_id,
            field_path=field_path,
            observed=observed,
            expected=expected,
            suggested_fix=suggested_fix,
        )

    @staticmethod
    def preferred_aspect_ratio(capability: ProviderCapability) -> AspectRatio:
        return AspectRatio.parse(capability.supported_aspect_ratios[0])
