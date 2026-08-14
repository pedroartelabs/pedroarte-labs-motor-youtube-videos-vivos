"""Compiladores genéricos — o alvo padrão do motor.

O alvo `generic` não imita nenhum produto: ele produz um prompt completo,
estruturado e legível, adequado tanto para colar num gerador quanto para servir
de base a um adaptador específico.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.provider import (
    ProviderCapability,
    ProviderModality,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services.provider_capability import (
    CompilationDecision,
    ProviderCapabilityMatchingService,
)
from pedroarte_youtube_engine.domain.services.segment_compilation import (
    SegmentCompilationService,
)


class GenericVideoPromptAdapter:
    """Compila o segmento para um alvo de vídeo neutro."""

    modality = ProviderModality.VIDEO

    def __init__(
        self,
        *,
        compilation: SegmentCompilationService | None = None,
        matching: ProviderCapabilityMatchingService | None = None,
    ) -> None:
        self._compilation = compilation or SegmentCompilationService()
        self._matching = matching or ProviderCapabilityMatchingService()

    @property
    def name(self) -> str:
        return "GenericVideoPromptAdapter"

    def decide(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> CompilationDecision:
        return self._matching.decide(
            target=segment.duration.target, capability=capability
        )

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]:
        decision = self.decide(segment, capability)
        return self._compilation.compile_for_provider(
            segment, capability=capability, decision=decision
        )


class GenericImagePromptAdapter:
    """Compila quadros-chave: um prompt de imagem fixa por quadro relevante.

    Imagem não é vídeo: aqui não há duração, movimento de câmera ao longo do
    tempo nem áudio. O adaptador extrai apenas o que uma imagem fixa pode
    carregar, e diz explicitamente o que ficou de fora.
    """

    modality = ProviderModality.IMAGE

    def __init__(self, *, compilation: SegmentCompilationService | None = None) -> None:
        self._compilation = compilation or SegmentCompilationService()

    @property
    def name(self) -> str:
        return "GenericImagePromptAdapter"

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]:
        frames = (
            ("quadro_inicial", segment.video.initial_frame, segment.range.start),
            ("quadro_final", segment.video.final_frame, segment.range.end),
        )
        negative = "; ".join(self._compilation.negative_constraints(segment))[
            : capability.max_negative_prompt_characters
        ]
        prompts: list[ProviderPrompt] = []

        for index, (label, description, moment) in enumerate(frames, start=1):
            body = self._render(segment, label, description)
            prompts.append(
                ProviderPrompt(
                    segment_id=segment.segment_id,
                    provider=capability.provider,
                    model=capability.model,
                    modality=ProviderModality.IMAGE,
                    call_index=index,
                    call_total=len(frames),
                    narrative_timecode_start=moment.formatted(),
                    narrative_timecode_end=moment.formatted(),
                    provider_duration_seconds=capability.min_duration_seconds,
                    prompt_text=body[: capability.max_prompt_characters],
                    negative_prompt=negative,
                    parameters={
                        "aspect_ratio": str(segment.segment_format.aspect_ratio),
                        "resolution": segment.segment_format.resolution.label,
                        "frame": label,
                    },
                    decision_log=(
                        "Imagem fixa: movimento de câmera, som e progressão temporal "
                        "não são representáveis nesta modalidade e foram omitidos "
                        "deliberadamente.",
                    ),
                )
            )
        return tuple(prompts)

    def _render(self, segment: PromptSegment, label: str, description: str) -> str:
        video = segment.video
        characters = "\n".join(
            f"  - {presence.descriptor()}" for presence in video.characters
        )
        return "\n".join(
            (
                f"QUADRO FIXO ({label}) — segmento {segment.segment_number:03d}",
                f"MOMENTO: {description}",
                "",
                f"CENÁRIO: {video.setting}",
                f"HORÁRIO: {video.time_of_day} | CLIMA: {video.weather}",
                f"ILUMINAÇÃO: {video.lighting}",
                f"COMPOSIÇÃO: {video.composition}",
                f"ENQUADRAMENTO: {video.camera.shot_type.value}, "
                f"ângulo {video.camera.angle.value}, lente {video.camera.lens}, "
                f"foco {video.camera.focus}, profundidade {video.camera.depth_of_field}",
                "",
                "PERSONAGENS:" if characters else "PERSONAGENS: nenhum em quadro.",
                characters,
                "",
                f"PROPORÇÃO: {segment.segment_format.aspect_ratio} · "
                f"{segment.segment_format.resolution}",
            )
        )


class GenericVoicePromptAdapter:
    """Compila o plano vocal em pedidos de síntese de voz, um por linha falada."""

    modality = ProviderModality.VOICE

    @property
    def name(self) -> str:
        return "GenericVoicePromptAdapter"

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]:
        lines = segment.audio.all_spoken_lines()
        if not lines:
            return ()

        prompts: list[ProviderPrompt] = []
        for index, line in enumerate(lines, start=1):
            body = "\n".join(
                (
                    f"SÍNTESE DE VOZ — {line.voice_id}",
                    f"IDIOMA: {line.language}",
                    f"EMOÇÃO: {line.emotion.value} | INTENÇÃO: {line.intention}",
                    f"RITMO: {line.pace} | PAUSAS: {line.pauses}",
                    f"RESPIRAÇÃO: {line.breathing}",
                    f"JANELA: {line.range.start}–{line.range.end} "
                    f"({line.range.duration.seconds:.1f}s para {line.word_count} palavras)",
                    "",
                    f"TEXTO: «{line.text}»",
                )
            )
            prompts.append(
                ProviderPrompt(
                    segment_id=segment.segment_id,
                    provider=capability.provider,
                    model=capability.model,
                    modality=ProviderModality.VOICE,
                    call_index=index,
                    call_total=len(lines),
                    narrative_timecode_start=line.range.start.formatted(),
                    narrative_timecode_end=line.range.end.formatted(),
                    provider_duration_seconds=max(
                        capability.min_duration_seconds, line.range.duration.seconds
                    ),
                    prompt_text=body[: capability.max_prompt_characters],
                    parameters={
                        "voice_id": line.voice_id,
                        "language": str(line.language),
                        "target_seconds": line.range.duration.seconds,
                    },
                    decision_log=(
                        f"Fala estimada em {line.estimated_speech_seconds:.1f}s; "
                        f"janela reservada de {line.range.duration.seconds:.1f}s.",
                    ),
                )
            )
        return tuple(prompts)
