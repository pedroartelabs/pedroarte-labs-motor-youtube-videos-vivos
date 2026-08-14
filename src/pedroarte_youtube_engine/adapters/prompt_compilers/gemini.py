"""Compiladores de exemplo para o ecossistema Gemini.

Estes adaptadores **não importam nenhum SDK** e **não fazem rede**. Eles apenas
formatam o prompt no estilo que os modelos de vídeo e imagem do Google
costumam responder melhor: uma sentença densa e contínua para a cena, seguida de
blocos rotulados para câmera, áudio e restrições.

As capacidades concretas (duração aceita, proporções, áudio nativo) **não estão
aqui**: elas vivem em `config/provider_capabilities/gemini_ecosystem.example.yaml`,
porque mudam a cada release e o código não deve envelhecer junto.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.provider import (
    ProviderCapability,
    ProviderModality,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment
from pedroarte_youtube_engine.domain.services.provider_capability import (
    ProviderCapabilityMatchingService,
)
from pedroarte_youtube_engine.domain.services.segment_compilation import (
    SegmentCompilationService,
)


class GeminiVideoPromptAdapter:
    """Formata o segmento no estilo descritivo contínuo + blocos rotulados."""

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
        return "GeminiVideoPromptAdapter"

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]:
        decision = self._matching.decide(
            target=segment.duration.target, capability=capability
        )
        negative = "; ".join(self._compilation.negative_constraints(segment))[
            : capability.max_negative_prompt_characters
        ]

        prompts: list[ProviderPrompt] = []
        slice_ms = segment.range.duration.milliseconds // decision.calls

        for index in range(decision.calls):
            start_ms = segment.range.start.milliseconds + index * slice_ms
            end_ms = (
                segment.range.end.milliseconds
                if index == decision.calls - 1
                else start_ms + slice_ms
            )
            body = self._render(segment, capability, index, decision.calls)
            prompts.append(
                ProviderPrompt(
                    segment_id=segment.segment_id,
                    provider=capability.provider,
                    model=capability.model,
                    modality=ProviderModality.VIDEO,
                    call_index=index + 1,
                    call_total=decision.calls,
                    strategy=decision.strategy,
                    narrative_timecode_start=_format_ms(start_ms),
                    narrative_timecode_end=_format_ms(end_ms),
                    provider_duration_seconds=decision.provider_duration.seconds,
                    prompt_text=body[: capability.max_prompt_characters],
                    negative_prompt=negative,
                    parameters={
                        "aspectRatio": str(segment.segment_format.aspect_ratio),
                        "resolution": segment.segment_format.resolution.label,
                        "durationSeconds": decision.provider_duration.seconds,
                        "generateAudio": capability.native_audio,
                        "personGeneration": "allow_adult",
                    },
                    reference_frames=(
                        (segment.video.initial_frame,)
                        if capability.first_frame_reference and index == 0
                        else ()
                    ),
                    audio_prompt=(
                        self._compilation.build_audio_prompt(segment)
                        if capability.native_audio
                        else ""
                    ),
                    decision_log=(
                        decision.describe(),
                        (
                            "Áudio embutido no prompt (o modelo gera trilha nativa)."
                            if capability.native_audio
                            else "Áudio exportado separadamente: o modelo não gera som."
                        ),
                    ),
                )
            )
        return tuple(prompts)

    def _render(
        self,
        segment: PromptSegment,
        capability: ProviderCapability,
        index: int,
        total: int,
    ) -> str:
        video = segment.video
        header = (
            f"[Chamada {index + 1}/{total} · timecode narrativo "
            f"{segment.range.start}–{segment.range.end}]"
            if total > 1
            else ""
        )

        # Sentença densa e contínua: o formato a que estes modelos respondem melhor.
        subjects = (
            "; ".join(presence.descriptor() for presence in video.characters)
            or "nenhuma figura humana em quadro"
        )
        scene_sentence = (
            f"{video.camera.shot_type.value} em {video.camera.angle.value}, "
            f"lente {video.camera.lens}, {video.camera.movement.value} "
            f"({video.camera.movement_speed}). {video.setting} "
            f"Horário: {video.time_of_day}. Clima: {video.weather}. "
            f"Iluminação: {video.lighting}. Composição: {video.composition}. "
            f"Ação: {video.action} Interpretação: {video.performance} "
            f"Foco em {video.camera.focus}, profundidade {video.camera.depth_of_field}. "
            f"Ritmo visual: {video.visual_rhythm}."
        )

        blocks = [
            header,
            scene_sentence,
            "",
            f"PERSONAGENS (manter idênticos em todas as chamadas): {subjects}",
            "",
            f"PRIMEIRO QUADRO: {video.initial_frame}",
            f"ÚLTIMO QUADRO: {video.final_frame}",
            "",
            self._compilation.build_audio_prompt(segment)
            if capability.native_audio
            else "ÁUDIO: gerado por provedor separado; não sintetizar som nesta chamada.",
            "",
            self._compilation.build_continuity_block(segment),
        ]
        return "\n".join(block for block in blocks if block is not None)


class GeminiImagePromptAdapter:
    """Formata quadros-chave e thumbnails no estilo do ecossistema Gemini."""

    modality = ProviderModality.IMAGE

    @property
    def name(self) -> str:
        return "GeminiImagePromptAdapter"

    def compile(
        self, segment: PromptSegment, capability: ProviderCapability
    ) -> tuple[ProviderPrompt, ...]:
        video = segment.video
        subjects = (
            "; ".join(presence.descriptor() for presence in video.characters)
            or "cenário sem figuras humanas"
        )
        frames = (
            ("primeiro_quadro", video.initial_frame, segment.range.start),
            ("ultimo_quadro", video.final_frame, segment.range.end),
        )

        prompts: list[ProviderPrompt] = []
        for index, (label, description, moment) in enumerate(frames, start=1):
            body = (
                f"Fotografia cinematográfica, {video.camera.shot_type.value}, "
                f"{video.camera.angle.value}, lente {video.camera.lens}. "
                f"{description} {video.setting} "
                f"Iluminação: {video.lighting}. Composição: {video.composition}. "
                f"Horário: {video.time_of_day}. Clima: {video.weather}.\n\n"
                f"PERSONAGENS: {subjects}"
            )
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
                    negative_prompt=(
                        "texto sobreposto, marca d'água, logotipo, membros deformados, "
                        "rosto de pessoa pública real, alteração de idade ou etnia"
                    )[: capability.max_negative_prompt_characters],
                    parameters={
                        "aspectRatio": str(segment.segment_format.aspect_ratio),
                        "frame": label,
                        "sampleCount": 1,
                    },
                    decision_log=("Quadro fixo derivado do segmento canônico.",),
                )
            )
        return tuple(prompts)


def _format_ms(milliseconds: int) -> str:
    total, millis = divmod(milliseconds, 1000)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
