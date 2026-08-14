"""Agentes de compilação para provedor (9.23 e 9.24)."""

from __future__ import annotations

from pedroarte_youtube_engine.adapters.prompt_compilers import PromptCompilerRegistry
from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import EpisodePromptSet, PromptPackage
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.provider import (
    ProviderCapability,
    ProviderModality,
    ProviderPrompt,
)
from pedroarte_youtube_engine.domain.segment import ProviderCompilation, PromptSegment
from pedroarte_youtube_engine.domain.services.provider_capability import (
    ProviderCapabilityMatchingService,
)


class ProviderCapabilityAgent(BaseAgent):
    """`PROVIDER_CAPABILITY_AGENT` — lê as capacidades e escolhe o compilador."""

    _contract = AgentContract(
        name="PROVIDER_CAPABILITY_AGENT",
        responsibility=(
            "Ler as capacidades configuradas — duração, proporção, resolução, áudio, "
            "referências de quadro, extensão e limites — e escolher o compilador "
            "adequado, sem jamais codificar capacidades voláteis no domínio."
        ),
        phase="COMPILING_PROMPTS",
        input_type="ProvidersSection",
        output_type="ProviderCapability",
        authorized_tools=(AgentTool.CAPABILITY_REGISTRY,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "Existe capacidade registrada para o alvo configurado.",
            "O compilador escolhido cobre a modalidade pedida.",
        ),
        failure_criteria=("O provedor configurado não tem capacidade declarada.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        target = context.configuration.providers.prompt_target
        capability = context.capabilities.require(
            provider=target, modality=ProviderModality.VIDEO
        )
        image = context.capabilities.get(provider=target, modality=ProviderModality.IMAGE)
        voice = context.capabilities.get(provider=target, modality=ProviderModality.VOICE)

        self._log(context).info(
            "Capacidades resolvidas",
            provider=target,
            model=str(capability.model),
            max_duration=capability.max_duration_seconds,
            native_audio=capability.native_audio,
        )
        return self._ok(
            video_capability=capability,
            image_capability=image,
            voice_capability=voice,
        )


class MultimodalPromptCompilerAgent(BaseAgent):
    """`MULTIMODAL_PROMPT_COMPILER_AGENT` — traduz o segmento para o provedor."""

    _contract = AgentContract(
        name="MULTIMODAL_PROMPT_COMPILER_AGENT",
        responsibility=(
            "Converter o segmento canônico em prompt de provedor preservando a "
            "intenção e o timecode narrativo, adaptando a sintaxe e a duração, "
            "incluindo áudio e vídeo e gerando restrições negativas."
        ),
        phase="COMPILING_PROMPTS",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[PromptPackage, ...]",
        authorized_tools=(AgentTool.PROMPT_COMPILER, AgentTool.CAPABILITY_REGISTRY),
        memory=MemoryScope.RUN,
        prompt_name="compilation.provider",
        completion_criteria=(
            "Todo segmento tem um prompt compilado.",
            "O timecode narrativo é preservado mesmo com subdivisão.",
            "Nenhum prompt compilado perde a seção sonora.",
        ),
        failure_criteria=("Nenhum compilador cobre o provedor configurado.",),
    )

    def __init__(
        self,
        *,
        compilers: PromptCompilerRegistry | None = None,
        matching: ProviderCapabilityMatchingService | None = None,
    ) -> None:
        self._compilers = compilers or PromptCompilerRegistry()
        self._matching = matching or ProviderCapabilityMatchingService()

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        capability: ProviderCapability = context.scratch["video_capability"]
        target = context.configuration.providers.prompt_target
        compiler = self._compilers.require(target, ProviderModality.VIDEO)
        image_capability = context.scratch.get("image_capability")
        voice_capability = context.scratch.get("voice_capability")

        provider_prompts: dict[str, tuple[ProviderPrompt, ...]] = {}
        compiled_packages: list[PromptPackage] = []
        subdivided = 0

        for package in packages:
            episodes: list[EpisodePromptSet] = []
            for episode in package.episodes:
                segments: list[PromptSegment] = []
                for segment in episode.segments:
                    prompts = compiler.compile(segment, capability)
                    provider_prompts[segment.segment_id.value] = prompts
                    if prompts and prompts[0].call_total > 1:
                        subdivided += 1
                    segments.append(
                        self._apply(segment, prompts, capability)
                    )
                episodes.append(episode.model_copy(update={"segments": tuple(segments)}))
            compiled_packages.append(package.model_copy(update={"episodes": tuple(episodes)}))

        # Pacotes auxiliares: quadros-chave e vozes, quando o alvo os suporta.
        keyframe_prompts = self._compile_side_channel(
            compiled_packages, target, ProviderModality.IMAGE, image_capability
        )
        voice_prompts = self._compile_side_channel(
            compiled_packages, target, ProviderModality.VOICE, voice_capability
        )

        total = sum(len(prompts) for prompts in provider_prompts.values())
        self._log(context).info(
            "Prompts compilados",
            provider=target,
            model=str(capability.model),
            segments=len(provider_prompts),
            provider_calls=total,
            subdivided_segments=subdivided,
        )
        context.metrics.increment("provider_calls", total)

        return AgentResult(
            agent=self.name,
            outputs={
                "packages": tuple(compiled_packages),
                "provider_prompts": provider_prompts,
                "keyframe_prompts": keyframe_prompts,
                "voice_prompts": voice_prompts,
            },
            events=(
                DomainEvent(
                    event_type=DomainEventType.PROMPT_COMPILED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "provider": target,
                        "model": str(capability.model),
                        "segments": len(provider_prompts),
                        "provider_calls": total,
                        "subdivided_segments": subdivided,
                    },
                ),
            ),
        )

    def _apply(
        self,
        segment: PromptSegment,
        prompts: tuple[ProviderPrompt, ...],
        capability: ProviderCapability,
    ) -> PromptSegment:
        if not prompts:
            return segment
        head = prompts[0]
        decision = self._matching.decide(
            target=segment.duration.target, capability=capability
        )
        return segment.with_provider_compilation(
            ProviderCompilation(
                provider=capability.provider.value,
                model=capability.model.value,
                calls=head.call_total,
                strategy=head.strategy.value,
                compiled_prompt=head.prompt_text,
                negative_prompt=head.negative_prompt,
                parameters=head.parameters,
                notes=(decision.describe(),),
            )
        ).model_copy(
            update={
                "duration": segment.duration.model_copy(
                    update={
                        "provider": decision.provider_duration,
                        "provider_call_count": decision.calls,
                        "recompilation_strategy": decision.strategy.value,
                    }
                )
            }
        )

    def _compile_side_channel(
        self,
        packages: tuple[PromptPackage, ...] | list[PromptPackage],
        target: str,
        modality: ProviderModality,
        capability: ProviderCapability | None,
    ) -> dict[str, tuple[ProviderPrompt, ...]]:
        """Compila canais auxiliares (quadros-chave, voz) quando disponíveis."""
        if capability is None:
            return {}
        compiler = self._compilers.get(target, modality)
        if compiler is None:
            return {}

        result: dict[str, tuple[ProviderPrompt, ...]] = {}
        for package in packages:
            for episode in package.episodes:
                for segment in episode.segments:
                    prompts = compiler.compile(segment, capability)
                    if prompts:
                        result[segment.segment_id.value] = prompts
        return result
