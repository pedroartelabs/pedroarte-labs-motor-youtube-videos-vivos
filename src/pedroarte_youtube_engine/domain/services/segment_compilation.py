"""Compilação do segmento canônico em texto de prompt.

O texto produzido aqui é *autossuficiente*: um gerador externo que receba apenas
esta string precisa conseguir produzir o segmento sem consultar o resto do
pacote. Por isso as âncoras de personagem, o estado herdado e a decisão vocal
são reinjetados por inteiro em cada segmento, e não referenciados por id.

O módulo é puro: sem Jinja, sem I/O, sem provedor. A renderização em Markdown
para leitura humana fica em `adapters/renderers`.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.provider import (
    CompilationStrategy,
    ProviderCapability,
    ProviderModality,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import PromptSegment, VocalDecision
from pedroarte_youtube_engine.domain.services.provider_capability import (
    CompilationDecision,
)
from pedroarte_youtube_engine.domain.value_objects import Duration, Timecode

#: Restrições negativas aplicadas a todo segmento, independentemente do conteúdo.
UNIVERSAL_NEGATIVE_CONSTRAINTS: tuple[str, ...] = (
    "sem texto, legenda ou marca d'água sobrepostos",
    "sem logotipos ou marcas registradas",
    "sem semelhança com pessoas públicas reais",
    "sem mãos, dedos ou membros deformados",
    "sem mudança de idade, etnia aparente, estrutura facial ou cor dos olhos",
    "sem troca de figurino não justificada",
    "sem objetos que aparecem ou desaparecem entre quadros",
    "sem alteração de horário, clima ou fonte de luz dentro do segmento",
    "sem câmera atravessando paredes ou objetos sólidos",
    "sem imitação de artista, intérprete ou obra protegida identificável",
)


class SegmentCompilationService:
    """Converte um `PromptSegment` em texto de prompt e em `ProviderPrompt`."""

    def build_video_prompt(self, segment: PromptSegment) -> str:
        """Bloco visual completo, em prosa estruturada."""
        video = segment.video
        lines: list[str] = []

        lines.append(
            f"SEGMENTO {segment.segment_number:03d} | {segment.range.start}–{segment.range.end} "
            f"| duração narrativa {segment.duration.target.seconds:.1f}s "
            f"| {segment.segment_format.descriptor()}"
        )
        lines.append(f"FUNÇÃO NARRATIVA: {segment.narrative.purpose}")
        lines.append(
            f"ARCO EMOCIONAL: de {segment.narrative.emotional_start.value} "
            f"para {segment.narrative.emotional_end.value} "
            f"(tensão {segment.narrative.tension}/10)"
        )
        lines.append("")

        lines.append("QUADRO INICIAL: " + video.initial_frame)
        lines.append("QUADRO FINAL: " + video.final_frame)
        lines.append("")

        lines.append(f"CENÁRIO: {video.setting}")
        lines.append(f"HORÁRIO: {video.time_of_day} | CLIMA: {video.weather}")
        lines.append(f"ILUMINAÇÃO: {video.lighting}")
        lines.append(f"COMPOSIÇÃO: {video.composition}")
        if video.relevant_props:
            lines.append("OBJETOS RELEVANTES: " + ", ".join(video.relevant_props))
        lines.append("")

        if video.characters:
            lines.append("PERSONAGENS EM CENA:")
            for presence in video.characters:
                lines.append(f"  - {presence.descriptor()}")
            lines.append("")

        lines.append(f"AÇÃO PRINCIPAL: {video.action}")
        lines.append(f"INTERPRETAÇÃO: {video.performance}")
        lines.append("")

        lines.append(f"CÂMERA: {video.camera.descriptor()}")
        lines.append(f"RITMO VISUAL: {video.visual_rhythm}")
        lines.append(
            f"TRANSIÇÃO DE ENTRADA: {video.transition_in.value} | "
            f"TRANSIÇÃO DE SAÍDA: {video.transition_out.value}"
        )
        return "\n".join(lines)

    def build_audio_prompt(self, segment: PromptSegment) -> str:
        """Bloco sonoro completo — nunca opcional."""
        audio = segment.audio
        lines: list[str] = ["PLANO SONORO"]

        lines.append("")
        lines.append("DECISÕES VOCAIS:")
        for entry in audio.voice_plan:
            justification = f" — justificativa: {entry.justification}" if entry.justification else ""
            lines.append(
                f"  - [{entry.range.start}–{entry.range.end}] {entry.decision.value} "
                f"({entry.voice_id}, intensidade {entry.intensity}): "
                f"{entry.description}{justification}"
            )

        if audio.dialogue:
            lines.append("")
            lines.append("DIÁLOGO:")
            for line in audio.dialogue:
                lines.append(
                    f"  - [{line.range.start}–{line.range.end}] {line.speaker_name} "
                    f"({line.voice_id}, {line.emotion.value}, {line.pace}): «{line.text}»"
                )
                lines.append(
                    f"      intenção: {line.intention} | pausas: {line.pauses} | "
                    f"respiração: {line.breathing} | {line.lip_sync_note}"
                )

        if audio.narration:
            lines.append("")
            lines.append("NARRAÇÃO:")
            for line in audio.narration:
                lines.append(
                    f"  - [{line.range.start}–{line.range.end}] {line.narrator_name} "
                    f"({line.voice_id}, {line.emotion.value}): «{line.text}»"
                )
                lines.append(f"      intenção: {line.intention} | ritmo: {line.rhythm}")

        lines.append("")
        lines.append("SOM AMBIENTE:")
        for ambient in audio.ambient_sound:
            lines.append(
                f"  - {ambient.description} (fonte: {ambient.source}, "
                f"{ambient.spatiality}, {ambient.relative_db:+.1f} dB)"
            )

        if audio.sound_effects:
            lines.append("")
            lines.append("EFEITOS SONOROS:")
            for effect in audio.sound_effects:
                position = "fora de quadro" if effect.off_screen else "em quadro"
                lines.append(
                    f"  - [{effect.at}] {effect.description} ({position}, "
                    f"{effect.spatiality}, {effect.relative_db:+.1f} dB) "
                    f"sincronizado com: {effect.synced_to_action}"
                )

        lines.append("")
        if audio.music.enabled:
            music = audio.music
            entry = music.entry_timecode or segment.range.start
            exit_at = music.exit_timecode or segment.range.end
            lines.append(
                f"MÚSICA: {music.description} | função: {music.function} | "
                f"instrumentação: {', '.join(music.instrumentation)} | "
                f"andamento: {music.tempo} | intensidade {music.intensity_start} → "
                f"{music.intensity_end} | entrada {entry}, saída {exit_at} | "
                f"{music.relationship_to_dialogue}"
            )
        else:
            lines.append("MÚSICA: ausente por decisão dramática neste segmento.")

        if audio.silence:
            lines.append("")
            lines.append("SILÊNCIO INTENCIONAL:")
            for beat in audio.silence:
                lines.append(
                    f"  - [{beat.range.start}–{beat.range.end}] {beat.kind}: {beat.justification}"
                )

        lines.append("")
        lines.append("MIXAGEM (prioridade decrescente):")
        for level in sorted(audio.mixing_notes, key=lambda item: item.priority):
            lines.append(f"  - {level}")

        if audio.synchronization_cues:
            lines.append("")
            lines.append("SINCRONIZAÇÃO AUDIOVISUAL:")
            for cue in audio.synchronization_cues:
                lines.append(f"  - [{cue.at}] {cue.visual_action} ↔ {cue.audio_event}")

        lines.append("")
        lines.append(f"TRANSIÇÃO SONORA DE SAÍDA: {audio.audio_transition_out}")
        return "\n".join(lines)

    def build_continuity_block(self, segment: PromptSegment) -> str:
        """Estado herdado e estado entregue, explícitos no próprio prompt."""
        incoming = segment.continuity_in
        outgoing = segment.continuity_out
        lines = ["CONTINUIDADE DE ENTRADA (estado herdado — respeitar integralmente):"]
        lines.extend(_render_snapshot(incoming))
        lines.append("")
        lines.append("CONTINUIDADE DE SAÍDA (estado a entregar ao próximo segmento):")
        lines.extend(_render_snapshot(outgoing))
        return "\n".join(lines)

    def negative_constraints(self, segment: PromptSegment) -> tuple[str, ...]:
        """União das restrições universais com as específicas do segmento."""
        merged: list[str] = list(UNIVERSAL_NEGATIVE_CONSTRAINTS)
        for constraint in segment.video.negative_constraints:
            if constraint not in merged:
                merged.append(constraint)
        return tuple(merged)

    def build_full_prompt(self, segment: PromptSegment) -> str:
        """Prompt completo: vídeo + áudio + continuidade + restrições."""
        blocks = [
            self.build_video_prompt(segment),
            "",
            self.build_audio_prompt(segment),
            "",
            self.build_continuity_block(segment),
            "",
            "RESTRIÇÕES NEGATIVAS:",
            *(f"  - {constraint}" for constraint in self.negative_constraints(segment)),
        ]
        if segment.source_references:
            blocks.append("")
            blocks.append("PROVENIÊNCIA:")
            blocks.extend(
                f"  - {reference.citation()} (confiança {reference.confidence})"
                for reference in segment.source_references
            )
        return "\n".join(blocks)

    def compile_for_provider(
        self,
        segment: PromptSegment,
        *,
        capability: ProviderCapability,
        decision: CompilationDecision,
    ) -> tuple[ProviderPrompt, ...]:
        """Traduz o segmento em uma ou mais chamadas concretas de provedor."""
        full_prompt = self.build_full_prompt(segment)
        negative = "; ".join(self.negative_constraints(segment))[
            : capability.max_negative_prompt_characters
        ]
        audio_prompt = self.build_audio_prompt(segment)

        prompts: list[ProviderPrompt] = []
        slice_ms = segment.range.duration.milliseconds // decision.calls

        for index in range(decision.calls):
            start_ms = segment.range.start.milliseconds + index * slice_ms
            end_ms = (
                segment.range.end.milliseconds
                if index == decision.calls - 1
                else start_ms + slice_ms
            )
            header = self._call_header(segment, decision, index)
            body = f"{header}\n\n{full_prompt}"
            prompts.append(
                ProviderPrompt(
                    segment_id=segment.segment_id,
                    provider=capability.provider,
                    model=capability.model,
                    modality=capability.modality,
                    call_index=index + 1,
                    call_total=decision.calls,
                    strategy=decision.strategy,
                    narrative_timecode_start=Timecode(milliseconds=start_ms).formatted(),
                    narrative_timecode_end=Timecode(milliseconds=end_ms).formatted(),
                    provider_duration_seconds=decision.provider_duration.seconds,
                    prompt_text=body[: capability.max_prompt_characters],
                    negative_prompt=negative,
                    parameters=self._parameters(segment, capability, decision),
                    reference_frames=self._reference_frames(segment, decision, index),
                    audio_prompt=(
                        audio_prompt
                        if capability.native_audio and capability.modality is ProviderModality.VIDEO
                        else ""
                    ),
                    decision_log=(decision.describe(),),
                )
            )
        return tuple(prompts)

    # -- auxiliares --------------------------------------------------------

    def _call_header(
        self, segment: PromptSegment, decision: CompilationDecision, index: int
    ) -> str:
        if decision.calls == 1:
            return (
                f"[CHAMADA ÚNICA — duração de provedor "
                f"{decision.provider_duration.seconds:.1f}s | "
                f"timecode narrativo preservado: {segment.range.start}–{segment.range.end}]"
            )
        return (
            f"[CHAMADA {index + 1} de {decision.calls} — estratégia "
            f"{decision.strategy.value} | duração de provedor "
            f"{decision.provider_duration.seconds:.1f}s | timecode narrativo do segmento "
            f"preservado: {segment.range.start}–{segment.range.end}]\n"
            f"Esta chamada cobre uma fração do segmento. Mantenha personagens, figurino, "
            f"iluminação e câmera idênticos às demais chamadas do mesmo segmento."
        )

    def _parameters(
        self,
        segment: PromptSegment,
        capability: ProviderCapability,
        decision: CompilationDecision,
    ) -> dict[str, str | int | float | bool]:
        return {
            "aspect_ratio": str(segment.segment_format.aspect_ratio),
            "resolution": segment.segment_format.resolution.label,
            "frame_rate": segment.segment_format.frame_rate.fps,
            "duration_seconds": decision.provider_duration.seconds,
            "native_audio": capability.native_audio,
            "strategy": decision.strategy.value,
        }

    def _reference_frames(
        self, segment: PromptSegment, decision: CompilationDecision, index: int
    ) -> tuple[str, ...]:
        frames: list[str] = []
        if decision.uses_first_frame:
            frames.append(
                segment.video.initial_frame
                if index == 0
                else "último quadro gerado pela chamada anterior deste mesmo segmento"
            )
        if decision.uses_last_frame and index == decision.calls - 1:
            frames.append(segment.video.final_frame)
        return tuple(frames)

    @staticmethod
    def voice_decision_summary(segment: PromptSegment) -> str:
        """Uma linha resumindo a decisão vocal — usada em relatórios e logs."""
        decisions = {entry.decision for entry in segment.audio.voice_plan}
        if VocalDecision.DIALOGUE in decisions:
            return "diálogo"
        if VocalDecision.NARRATION in decisions:
            return "narração"
        if decisions == {VocalDecision.INTENTIONAL_SILENCE}:
            return "silêncio vocal intencional"
        return ", ".join(sorted(decision.value for decision in decisions))

    @staticmethod
    def provider_seconds_total(prompts: tuple[ProviderPrompt, ...]) -> Duration:
        return Duration.from_seconds(
            sum(prompt.provider_duration_seconds for prompt in prompts)
        )

    @staticmethod
    def strategy_of(prompts: tuple[ProviderPrompt, ...]) -> CompilationStrategy:
        return prompts[0].strategy if prompts else CompilationStrategy.DIRECT


def _render_snapshot(snapshot: object) -> list[str]:
    """Serializa um `ContinuitySnapshot` em linhas legíveis, omitindo o vazio."""
    from pedroarte_youtube_engine.domain.segment import ContinuitySnapshot

    assert isinstance(snapshot, ContinuitySnapshot)
    lines: list[str] = []
    data = snapshot.model_dump(mode="json")
    for key, value in data.items():
        if not value:
            continue
        if isinstance(value, dict):
            rendered = "; ".join(f"{name}: {item}" for name, item in value.items())
        elif isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        lines.append(f"  - {key}: {rendered}")
    return lines or ["  - (estado inicial vazio)"]
