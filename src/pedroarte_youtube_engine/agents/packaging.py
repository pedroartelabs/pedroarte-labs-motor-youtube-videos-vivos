"""Agentes de empacotamento, acessibilidade, direitos e custo.

Cobre 9.14, 9.21, 9.22, 9.27, 9.28, 9.29 e 9.30.
"""

from __future__ import annotations

import re

from pedroarte_youtube_engine.adapters.renderers.subtitles import (
    build_cues,
    render_srt,
    render_transcript,
    render_vtt,
)
from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import EpisodePromptSet, PromptPackage
from pedroarte_youtube_engine.domain.artifacts import (
    AccessibilityPackage,
    ChapterMarker,
    CostReport,
    PublicationMetadata,
    RightsRisk,
    ThumbnailPrompt,
)
from pedroarte_youtube_engine.domain.production import RetentionAssessment
from pedroarte_youtube_engine.domain.value_objects import (
    NarrativeFunction,
    ProductionVariant,
    Timecode,
)
from pedroarte_youtube_engine.shared.text import excerpt, truncate_words

#: Marcas e pessoas públicas que exigem sinalização de direitos.
_BRAND_PATTERN = re.compile(
    r"\b(coca-?cola|pepsi|nike|adidas|apple|google|microsoft|netflix|disney|marvel|"
    r"star\s?wars|harry\s?potter|batman|superman|spotify|youtube|instagram|tiktok)\b",
    re.IGNORECASE,
)

#: Pedidos de imitação de pessoa real.
_LIKENESS_PATTERN = re.compile(
    r"\b(no estilo de|parecido com|semelhante a|imitando|como o ator|como a atriz|"
    r"sósia de|igual ao cantor|voz de)\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]",
)


class RetentionAndHookAgent(BaseAgent):
    """`RETENTION_AND_HOOK_AGENT` — avalia promessa inicial e ritmo."""

    _contract = AgentContract(
        name="RETENTION_AND_HOOK_AGENT",
        responsibility=(
            "Avaliar os primeiros segundos, criar promessa narrativa verdadeira, "
            "manter progressão, identificar quedas de ritmo e impedir clickbait "
            "desconectado da obra."
        ),
        phase="VALIDATING",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[RetentionAssessment, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        prompt_name="writing.retention",
        completion_criteria=(
            "A promessa inicial corresponde ao conteúdo real.",
            "Quedas de ritmo são localizadas por segmento.",
        ),
        failure_criteria=("Nenhum pacote foi produzido.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        assessments: list[RetentionAssessment] = []

        for package in packages:
            for episode in package.episodes:
                if not episode.segments:
                    continue
                assessments.append(self._assess(package.variant, episode))

        self._log(context).info("Retenção avaliada", assessments=len(assessments))
        return self._ok(retention=tuple(assessments))

    def _assess(
        self, variant: ProductionVariant, episode: EpisodePromptSet
    ) -> RetentionAssessment:
        opening = episode.segments[0]
        tensions = [segment.narrative.tension for segment in episode.segments]

        # Segmentos de baixa energia cercados por baixa energia matam a retenção.
        low_energy = tuple(
            segment.segment_id.value
            for index, segment in enumerate(episode.segments)
            if segment.narrative.tension == 0
            and (index == 0 or tensions[index - 1] == 0)
            and index > 0
        )

        first_score = min(
            1.0,
            0.5
            + 0.05 * opening.narrative.tension
            + (0.2 if opening.narrative.function is NarrativeFunction.HOOK else 0.0)
            + (0.15 if opening.audio.has_spoken_words else 0.0),
        )
        pacing = max(
            0.0, min(1.0, 1.0 - len(low_energy) / max(1, len(episode.segments)))
        )

        recommendations: list[str] = []
        if first_score < 0.7:
            recommendations.append(
                "Antecipe o momento de maior tensão para os primeiros dez segundos, "
                "sem prometer o que a obra não entrega."
            )
        if low_energy:
            recommendations.append(
                f"{len(low_energy)} segmentos consecutivos sem tensão: intercale um "
                "beat de conflito ou encurte a sequência."
            )
        if variant is ProductionVariant.SHORTS and len(episode.segments) > 6:
            recommendations.append(
                "Short longo demais para o gancho escolhido: reduza para um único pico."
            )

        return RetentionAssessment(
            variant=variant,
            episode_id=episode.episode_id,
            opening_promise=excerpt(opening.narrative.purpose, max_chars=560),
            first_seconds_score=round(first_score, 4),
            pacing_score=round(pacing, 4),
            low_energy_segments=low_energy[:20],
            recommendations=tuple(recommendations),
            clickbait_risk=False,
        )


class YouTubePackagingAgent(BaseAgent):
    """`YOUTUBE_PACKAGING_AGENT` — títulos, descrições, capítulos e thumbnails."""

    _contract = AgentContract(
        name="YOUTUBE_PACKAGING_AGENT",
        responsibility=(
            "Gerar títulos, descrições, capítulos, timestamps, palavras-chave, "
            "hashtags, prompts de thumbnail, comentário fixado, playlist, ordem de "
            "publicação e as conexões entre Shorts e vídeos longos."
        ),
        phase="EXPORTING",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[PublicationMetadata, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        prompt_name="packaging.youtube",
        completion_criteria=(
            "Todo título tem no máximo 100 caracteres.",
            "Os capítulos apontam para timecodes existentes.",
            "Shorts referenciam o vídeo principal.",
        ),
        failure_criteria=("Nenhum pacote foi produzido.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        canon = context.require_canon()
        metadata: list[PublicationMetadata] = []
        order = 1

        main_title = ""
        for package in packages:
            if package.variant is ProductionVariant.MAIN_10_MINUTES and package.episodes:
                main_title = package.episodes[0].title
                break

        for package in packages:
            for episode in package.episodes:
                if not episode.segments:
                    continue
                metadata.append(
                    self._build(canon.title, package, episode, order, main_title)
                )
                order += 1

        self._log(context).info("Metadados de publicação gerados", items=len(metadata))
        return self._ok(publication=tuple(metadata))

    def _build(
        self,
        work_title: str,
        package: PromptPackage,
        episode: EpisodePromptSet,
        order: int,
        main_title: str,
    ) -> PublicationMetadata:
        duration = episode.total_duration
        title = truncate_words(episode.title, 14)[:100]

        chapters = self._chapters(episode)
        description = self._description(work_title, package, episode, duration, main_title)

        return PublicationMetadata(
            variant=package.variant,
            episode_id=episode.episode_id.value,
            primary_title=title,
            alternative_titles=self._alternatives(work_title, package, episode),
            description=description,
            chapters=chapters,
            keywords=self._keywords(work_title, package),
            hashtags=self._hashtags(package.variant),
            thumbnail_prompts=self._thumbnails(episode),
            pinned_comment=(
                f"Este vídeo faz parte da adaptação audiovisual de «{work_title}». "
                "Os prompts que originaram cada segmento estão documentados no "
                "pacote de produção."
            ),
            playlist=f"{work_title} — {_variant_playlist(package.variant)}",
            publication_order=order,
            linked_long_form=main_title if package.variant is ProductionVariant.SHORTS else "",
            duration=duration,
        )

    @staticmethod
    def _chapters(episode: EpisodePromptSet) -> tuple[ChapterMarker, ...]:
        """Um marcador por sequência dramática, sempre começando em 00:00."""
        markers: list[ChapterMarker] = []
        seen: set[str] = set()
        for segment in episode.segments:
            key = segment.sequence_id.value
            if key in seen:
                continue
            seen.add(key)
            markers.append(
                ChapterMarker(
                    at=segment.range.start
                    if markers
                    else Timecode.zero(),
                    title=truncate_words(
                        segment.narrative.function.value.replace("_", " ").capitalize(), 6
                    )[:120],
                )
            )
        return tuple(markers[:20])

    @staticmethod
    def _description(
        work_title: str,
        package: PromptPackage,
        episode: EpisodePromptSet,
        duration: object,
        main_title: str,
    ) -> str:
        from pedroarte_youtube_engine.domain.value_objects import Duration

        assert isinstance(duration, Duration)
        lines = [
            f"{episode.title}",
            "",
            f"Adaptação audiovisual de «{work_title}».",
            f"Duração: {duration.human()} · {len(episode.segments)} segmentos narrativos.",
            "",
        ]
        if package.variant is ProductionVariant.SHORTS and main_title:
            lines += [f"▶ Versão completa: {main_title}", ""]
        if episode.segments:
            lines += [
                "Neste episódio:",
                excerpt(episode.segments[0].narrative.purpose, max_chars=400),
                "",
            ]
        lines += [
            "—",
            "Produzido com PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE.",
        ]
        return "\n".join(lines)[:5000]

    @staticmethod
    def _alternatives(
        work_title: str, package: PromptPackage, episode: EpisodePromptSet
    ) -> tuple[str, ...]:
        return (
            f"{work_title} — {episode.title}"[:100],
            f"{episode.title} | adaptação audiovisual"[:100],
        )

    @staticmethod
    def _keywords(work_title: str, package: PromptPackage) -> tuple[str, ...]:
        base = [work_title.lower(), "adaptação literária", "audiolivro visual", "ficção"]
        base.append(_variant_playlist(package.variant).lower())
        return tuple(dict.fromkeys(base))

    @staticmethod
    def _hashtags(variant: ProductionVariant) -> tuple[str, ...]:
        common = ("#ficcao", "#adaptacao", "#literatura")
        if variant is ProductionVariant.SHORTS:
            return (*common, "#shorts")
        if variant is ProductionVariant.TRAILERS:
            return (*common, "#trailer")
        return common

    @staticmethod
    def _thumbnails(episode: EpisodePromptSet) -> tuple[ThumbnailPrompt, ...]:
        if not episode.segments:
            return ()
        peak = max(episode.segments, key=lambda segment: segment.narrative.tension)
        return (
            ThumbnailPrompt(
                label="thumbnail_principal",
                prompt=(
                    f"Imagem fixa cinematográfica. {peak.video.final_frame} "
                    f"{peak.video.lighting} Enquadramento: "
                    f"{peak.video.camera.shot_type.value}, lente {peak.video.camera.lens}."
                ),
                negative_prompt=(
                    "sem texto sobreposto, sem marca d'água, sem logotipo, sem rosto de "
                    "pessoa pública real, sem membros deformados"
                ),
                aspect_ratio=str(peak.segment_format.aspect_ratio),
                rationale=(
                    "Deriva do segmento de maior tensão, para que a capa corresponda ao "
                    "conteúdo real do vídeo."
                ),
            ),
        )


class AccessibilityAgent(BaseAgent):
    """`ACCESSIBILITY_AGENT` — legendas, transcrição e notas de audiodescrição."""

    _contract = AgentContract(
        name="ACCESSIBILITY_AGENT",
        responsibility=(
            "Produzir legendas com identificação de falante, descrição de sons "
            "importantes, arquivos SRT e VTT, transcrição e notas preparadas para "
            "audiodescrição futura."
        ),
        phase="EXPORTING",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[AccessibilityPackage, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "Toda legenda identifica o falante.",
            "Sons relevantes aparecem na transcrição.",
        ),
        failure_criteria=("Nenhum pacote foi produzido.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        results: list[AccessibilityPackage] = []

        for package in packages:
            for episode in package.episodes:
                if not episode.segments:
                    continue
                cues = build_cues(episode.segments)
                speakers = tuple(
                    dict.fromkeys(cue.speaker for cue in cues if cue.speaker)
                )
                sounds = tuple(
                    dict.fromkeys(
                        effect.description
                        for segment in episode.segments
                        for effect in segment.audio.sound_effects
                    )
                )[:30]
                results.append(
                    AccessibilityPackage(
                        variant=package.variant,
                        episode_id=episode.episode_id.value,
                        srt_content=render_srt(cues),
                        vtt_content=render_vtt(cues),
                        transcript=render_transcript(episode.segments, title=episode.title),
                        speaker_labels=speakers,
                        important_sound_descriptions=sounds,
                        audio_description_notes=self._audio_description(episode),
                        plain_language_summary=self._plain_summary(episode),
                    )
                )

        self._log(context).info("Pacotes de acessibilidade gerados", items=len(results))
        return self._ok(accessibility=tuple(results))

    @staticmethod
    def _audio_description(episode: EpisodePromptSet) -> tuple[str, ...]:
        """Janelas sem fala onde a audiodescrição pode entrar."""
        return tuple(
            f"{segment.range.start}: {excerpt(segment.video.action, max_chars=200)}"
            for segment in episode.segments
            if not segment.audio.has_spoken_words
        )[:40]

    @staticmethod
    def _plain_summary(episode: EpisodePromptSet) -> str:
        if not episode.segments:
            return ""
        return excerpt(
            f"{episode.title}. "
            + " ".join(
                segment.narrative.beat for segment in episode.segments[:3]
            ),
            max_chars=1800,
        )


class LegalAndRightsAgent(BaseAgent):
    """`LEGAL_AND_RIGHTS_AGENT` — sinaliza riscos sem oferecer parecer jurídico."""

    _contract = AgentContract(
        name="LEGAL_AND_RIGHTS_AGENT",
        responsibility=(
            "Registrar a origem do material, solicitar confirmação de direitos, "
            "sinalizar celebridades, marcas e material protegido, impedir imitação "
            "direta de artistas vivos e gerar relatório de riscos."
        ),
        phase="VALIDATING",
        input_type="tuple[PromptPackage, ...]",
        output_type="tuple[RightsRisk, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "A confirmação de direitos foi verificada.",
            "Marcas e pessoas reais mencionadas foram sinalizadas.",
        ),
        failure_criteria=("Um prompt pede imitação direta de artista vivo.",),
        blocking=False,
    )

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        book = context.require_book()
        rights = context.configuration.rights
        risks: list[RightsRisk] = []

        if not rights.user_confirms_adaptation_rights:
            risks.append(
                RightsRisk(
                    risk_id="rights_not_confirmed",
                    category="direitos_de_adaptacao",
                    description=(
                        "O operador não confirmou possuir os direitos de adaptação "
                        "audiovisual da obra processada."
                    ),
                    evidence=f"rights.user_confirms_adaptation_rights = false",
                    severity="erro",
                    recommendation=(
                        "Defina `rights.user_confirms_adaptation_rights: true` em "
                        "`project.yaml` apenas se você realmente detém ou licenciou "
                        "esses direitos."
                    ),
                )
            )

        risks.append(
            RightsRisk(
                risk_id="rights_provenance",
                category="proveniencia",
                description=(
                    f"A adaptação deriva de «{book.title}», de "
                    f"{book.author or 'autoria não declarada'}, ingerido a partir de "
                    f"{len(book.documents)} documento(s) fornecidos pelo operador."
                ),
                evidence=book.canonical_hash.value,
                severity="info",
                recommendation="Mantenha o registro de origem junto ao material publicado.",
            )
        )

        risks.extend(self._scan_prompts(packages))

        blocking = [risk for risk in risks if risk.severity == "erro"]
        self._log(context).info(
            "Relatório de direitos",
            risks=len(risks),
            blocking=len(blocking),
            rights_confirmed=rights.user_confirms_adaptation_rights,
        )
        return self._ok(rights_risks=tuple(risks))

    def _scan_prompts(self, packages: tuple[PromptPackage, ...]) -> list[RightsRisk]:
        risks: list[RightsRisk] = []
        seen: set[str] = set()

        for package in packages:
            for segment in package.all_segments():
                haystack = " ".join(
                    (
                        segment.video.action,
                        segment.video.setting,
                        segment.video.performance,
                        segment.audio.music.description,
                    )
                )
                for match in _BRAND_PATTERN.finditer(haystack):
                    token = match.group(0).lower()
                    if token in seen:
                        continue
                    seen.add(token)
                    risks.append(
                        RightsRisk(
                            risk_id=f"brand_{token.replace(' ', '_')}",
                            category="marca_registrada",
                            description=(
                                f"A marca «{match.group(0)}» aparece em um prompt gerado."
                            ),
                            evidence=str(segment.segment_id),
                            severity="advertencia",
                            recommendation=(
                                "Substitua por descrição genérica ou obtenha autorização "
                                "de uso da marca."
                            ),
                        )
                    )
                if _LIKENESS_PATTERN.search(haystack):
                    risks.append(
                        RightsRisk(
                            risk_id=f"likeness_{segment.segment_id.value}",
                            category="semelhanca_com_pessoa_real",
                            description=(
                                "Um prompt parece pedir semelhança com pessoa real "
                                "identificável."
                            ),
                            evidence=str(segment.segment_id),
                            severity="erro",
                            recommendation=(
                                "Descreva traços físicos diretamente; nunca referencie "
                                "uma pessoa real como atalho visual ou vocal."
                            ),
                        )
                    )
        return risks


class CostAndQuotaAgent(BaseAgent):
    """`COST_AND_QUOTA_AGENT` — estima chamadas, lotes e custo."""

    _contract = AgentContract(
        name="COST_AND_QUOTA_AGENT",
        responsibility=(
            "Calcular a quantidade de segmentos, estimar chamadas e custo quando há "
            "tabela configurada, criar lotes, respeitar cotas e permitir retomada."
        ),
        phase="EXPORTING",
        input_type="tuple[PromptPackage, ...]",
        output_type="CostReport",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.RUN,
        completion_criteria=(
            "A contagem de chamadas cobre todos os segmentos.",
            "O custo só é estimado quando há tabela configurada.",
        ),
        failure_criteria=("Nenhum pacote foi produzido.",),
        blocking=False,
    )

    #: Tamanho de lote que permite retomada sem reprocessar tudo.
    BATCH_SIZE = 25

    def run(self, context: EngineContext) -> AgentResult:
        packages: tuple[PromptPackage, ...] = context.scratch["packages"]
        provider_prompts: dict[str, tuple] = context.scratch.get("provider_prompts", {})

        total_segments = sum(package.segment_count for package in packages)
        calls_by_variant = {
            package.variant.value: sum(
                len(provider_prompts.get(segment.segment_id.value, ()))
                for segment in package.all_segments()
            )
            for package in packages
        }
        total_calls = sum(calls_by_variant.values())

        models = tuple(
            dict.fromkeys(
                prompt.model.value
                for prompts in provider_prompts.values()
                for prompt in prompts
            )
        )

        batches = tuple(
            f"lote_{index + 1:03d}: chamadas {start + 1}–{min(start + self.BATCH_SIZE, total_calls)}"
            for index, start in enumerate(range(0, total_calls, self.BATCH_SIZE))
        )

        report = CostReport(
            total_segments=total_segments,
            estimated_provider_calls=total_calls,
            calls_by_variant=calls_by_variant,
            models_used=models,
            currency="USD",
            estimated_cost=0.0,
            cost_table_configured=False,
            batches=batches[:200],
            notes=(
                "Nenhuma tabela de preços foi configurada: o custo monetário não é "
                "estimado, apenas o volume de chamadas.",
                f"Lotes de {self.BATCH_SIZE} chamadas permitem retomar a geração sem "
                "reprocessar o que já foi concluído.",
                "Modo padrão `execute_generation: false`: nenhuma chamada paga foi feita.",
            ),
        )

        self._log(context).info(
            "Custo e cotas estimados",
            segments=total_segments,
            provider_calls=total_calls,
            batches=len(batches),
        )
        return self._ok(cost_report=report)


def _variant_playlist(variant: ProductionVariant) -> str:
    return {
        ProductionVariant.MAIN_10_MINUTES: "Vídeo principal",
        ProductionVariant.SHORTS: "Shorts",
        ProductionVariant.LONG_FORM: "Versão longa",
        ProductionVariant.SERIES: "Série",
        ProductionVariant.MINI_NOVELA: "Mini-novela",
        ProductionVariant.TRAILERS: "Trailers",
    }[variant]
