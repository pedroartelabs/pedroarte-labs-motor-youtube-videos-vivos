"""Construção dos segmentos audiovisuais.

Este módulo reúne o trabalho de cinco agentes do catálogo — `SCREENWRITER`,
`CINEMATOGRAPHY`, `DIALOGUE_AND_PERFORMANCE`, `SOUND_DESIGN` e
`VISUAL_CONTINUITY` — porque eles produzem, juntos, uma única unidade
indivisível: o segmento. Separá-los em passes independentes exigiria um objeto
intermediário incompleto, e a especificação proíbe justamente isso — um segmento
sem áudio não pode existir nem por um instante.

Cada agente mantém contrato próprio e é testável isoladamente; o
`SegmentBuilderAgent` os compõe.
"""

from __future__ import annotations

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import (
    AudiovisualBible,
    CanonBible,
    EpisodePromptSet,
    PromptPackage,
)
from pedroarte_youtube_engine.domain.audiovisual import VoiceProfile
from pedroarte_youtube_engine.domain.canon import Character, NarrativeBeat
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.production import Episode, FormatProfile, Scene
from pedroarte_youtube_engine.domain.segment import (
    AmbientSound,
    AudioPlan,
    CameraPlan,
    CharacterPresence,
    ContinuitySnapshot,
    DialogueLine,
    MusicCue,
    NarrationLine,
    PromptSegment,
    SegmentDuration,
    SegmentFormat,
    SegmentNarrative,
    SilenceBeat,
    SoundEffect,
    SubtitleCue,
    SyncCue,
    VideoPlan,
    VocalDecision,
    VoicePlanEntry,
)
from pedroarte_youtube_engine.domain.value_objects import (
    CameraAngle,
    CameraMovement,
    ContinuityReference,
    Duration,
    EmotionalTone,
    MixLevel,
    NarrativeFunction,
    ProductionVariant,
    SegmentId,
    ShotType,
    TimeRange,
    Timecode,
    TransitionType,
)
from pedroarte_youtube_engine.shared.text import excerpt, max_words_for_duration, truncate_words

#: Fração do segmento reservada à fala. O resto é respiração, reação e ar —
#: sem isso, o áudio soa acelerado e o corte fica sem folga.
_SPEECH_WINDOW_RATIO = 0.70
_SPEECH_LEAD_IN_RATIO = 0.15

#: Margem de segurança sobre o limite teórico de palavras por janela.
_WORD_BUDGET_SAFETY = 0.80

#: Planos por função narrativa — a escolha de enquadramento serve ao drama.
_SHOT_BY_FUNCTION: dict[NarrativeFunction, ShotType] = {
    NarrativeFunction.HOOK: ShotType.EXTREME_CLOSE_UP,
    NarrativeFunction.SETUP: ShotType.WIDE,
    NarrativeFunction.INCITING_INCIDENT: ShotType.MEDIUM,
    NarrativeFunction.RISING_ACTION: ShotType.MEDIUM_CLOSE,
    NarrativeFunction.COMPLICATION: ShotType.MEDIUM,
    NarrativeFunction.CONFRONTATION: ShotType.OVER_THE_SHOULDER,
    NarrativeFunction.REVELATION: ShotType.CLOSE_UP,
    NarrativeFunction.REVERSAL: ShotType.CLOSE_UP,
    NarrativeFunction.CLIMAX: ShotType.MEDIUM_CLOSE,
    NarrativeFunction.FALLING_ACTION: ShotType.FULL,
    NarrativeFunction.RESOLUTION: ShotType.WIDE,
    NarrativeFunction.BREATHING: ShotType.WIDE,
    NarrativeFunction.TRANSITION: ShotType.INSERT,
    NarrativeFunction.CLIFFHANGER: ShotType.EXTREME_CLOSE_UP,
    NarrativeFunction.EPILOGUE: ShotType.EXTREME_WIDE,
    NarrativeFunction.CALL_TO_ACTION: ShotType.MEDIUM,
}

_MOVEMENT_BY_TENSION: tuple[tuple[int, CameraMovement, str], ...] = (
    (0, CameraMovement.STATIC, "imóvel, sem qualquer deriva"),
    (2, CameraMovement.DOLLY_IN, "aproximação quase imperceptível"),
    (4, CameraMovement.HANDHELD, "microtremor constante, sem correção"),
    (6, CameraMovement.TRACKING, "acompanhamento lateral firme"),
    (8, CameraMovement.PUSH_THROUGH, "avanço contínuo que não recua"),
)

_LENS_BY_SHOT: dict[ShotType, str] = {
    ShotType.EXTREME_WIDE: "24mm",
    ShotType.WIDE: "28mm",
    ShotType.FULL: "35mm",
    ShotType.MEDIUM_FULL: "40mm",
    ShotType.MEDIUM: "50mm",
    ShotType.MEDIUM_CLOSE: "65mm",
    ShotType.CLOSE_UP: "85mm",
    ShotType.EXTREME_CLOSE_UP: "100mm macro",
    ShotType.INSERT: "100mm macro",
    ShotType.OVER_THE_SHOULDER: "50mm",
    ShotType.POV: "35mm",
    ShotType.TWO_SHOT: "40mm",
}


class SegmentBuilderAgent(BaseAgent):
    """Compõe `SCREENWRITER`, `CINEMATOGRAPHY`, `SOUND_DESIGN` e continuidade."""

    _contract = AgentContract(
        name="SEGMENT_BUILDER_AGENT",
        responsibility=(
            "Produzir cada segmento audiovisual completo — plano visual, plano sonoro, "
            "decisão vocal explícita, legendas, continuidade de entrada e de saída e "
            "proveniência — respeitando a duração narrativa configurada."
        ),
        phase="WRITING_SEGMENTS",
        input_type="ProductionPlan",
        output_type="tuple[PromptPackage, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES, AgentTool.RAG_RETRIEVAL),
        memory=MemoryScope.CONTINUITY,
        prompt_name="writing.screenplay",
        completion_criteria=(
            "Todo segmento tem seção visual e seção sonora.",
            "Todo segmento declara uma decisão vocal explícita.",
            "Todo texto falado cabe na janela reservada.",
            "Quadro inicial e quadro final descrevem estados distintos.",
            "Segmentos consecutivos são contíguos no tempo.",
        ),
        failure_criteria=(
            "Um segmento seria criado sem plano sonoro.",
            "A soma das durações não fecha no alvo do perfil.",
        ),
    )

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        bible = context.require_bible()
        plan = context.require_plan()
        log = self._log(context)

        packages: list[PromptPackage] = []
        events: list[DomainEvent] = []

        for variant in plan.enabled_variants:
            episode_sets: list[EpisodePromptSet] = []
            for profile in plan.profiles_for(variant):
                for episode in plan.episodes_for(variant):
                    if not episode.episode_id.value.startswith(
                        _profile_prefix(profile.profile_id)
                    ):
                        continue
                    episode_sets.append(
                        self._build_episode_set(
                            context=context,
                            canon=canon,
                            bible=bible,
                            profile=profile,
                            episode=episode,
                        )
                    )

            packages.append(
                PromptPackage(
                    project_id=context.project_id,
                    variant=variant,
                    directory=variant.directory,
                    episodes=tuple(episode_sets),
                    adaptation_strategy=plan.adaptation_strategy,
                )
            )
            events.append(
                DomainEvent(
                    event_type=DomainEventType.SEGMENT_CREATED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "variant": variant.value,
                        "episodes": len(episode_sets),
                        "segments": sum(len(item.segments) for item in episode_sets),
                    },
                )
            )

        total = sum(package.segment_count for package in packages)
        log.info("Segmentos construídos", packages=len(packages), segments=total)
        context.metrics.set_gauge("segments_total", float(total))

        return AgentResult(
            agent=self.name, outputs={"packages": tuple(packages)}, events=tuple(events)
        )

    # -- episódio ----------------------------------------------------------

    def _build_episode_set(
        self,
        *,
        context: EngineContext,
        canon: CanonBible,
        bible: AudiovisualBible,
        profile: FormatProfile,
        episode: Episode,
    ) -> EpisodePromptSet:
        segments: list[PromptSegment] = []
        state = self._initial_state(canon, episode)
        number = 0
        subtitle_index = 0

        for scene in episode.all_scenes():
            beat = self._beat_for(canon, scene)
            ranges = self._segment_ranges_for(scene, profile.segment_duration)

            for position, window in enumerate(ranges):
                number += 1
                previous = segments[-1] if segments else None
                segment, state, subtitle_index = self._build_segment(
                    context=context,
                    canon=canon,
                    bible=bible,
                    profile=profile,
                    episode=episode,
                    scene=scene,
                    beat=beat,
                    window=window,
                    number=number,
                    position_in_scene=position,
                    scene_length=len(ranges),
                    incoming=state,
                    previous=previous,
                    subtitle_index=subtitle_index,
                )
                segments.append(segment)

        # O encadeamento `next_segment_id` só pode ser preenchido depois que
        # todos os segmentos existem.
        linked = self._link_segments(tuple(segments))

        return EpisodePromptSet(
            episode_id=episode.episode_id,
            profile_id=profile.profile_id,
            variant=profile.variant,
            title=episode.title,
            segments=linked,
            subtitles=tuple(cue for segment in linked for cue in segment.subtitles),
        )

    @staticmethod
    def _link_segments(segments: tuple[PromptSegment, ...]) -> tuple[PromptSegment, ...]:
        linked: list[PromptSegment] = []
        for index, segment in enumerate(segments):
            following = segments[index + 1].segment_id if index + 1 < len(segments) else None
            linked.append(
                segment.model_copy(
                    update={
                        "continuity_reference": segment.continuity_reference.model_copy(
                            update={"next_segment_id": following}
                        )
                    }
                )
            )
        return tuple(linked)

    @staticmethod
    def _segment_ranges_for(scene: Scene, segment_duration: Duration) -> tuple[TimeRange, ...]:
        step = segment_duration.milliseconds
        return tuple(
            TimeRange(
                start=Timecode(milliseconds=offset),
                end=Timecode(milliseconds=offset + step),
            )
            for offset in range(
                scene.range.start.milliseconds, scene.range.end.milliseconds, step
            )
        )

    @staticmethod
    def _beat_for(canon: CanonBible, scene: Scene) -> NarrativeBeat | None:
        if not scene.beat_ids:
            return None
        wanted = scene.beat_ids[0]
        for beat in canon.beats:
            if beat.beat_id == wanted:
                return beat
        return None

    def _initial_state(self, canon: CanonBible, episode: Episode) -> ContinuitySnapshot:
        """Estado de abertura: o que já é verdade antes do primeiro quadro."""
        leads = canon.leads()[:2]
        return ContinuitySnapshot(
            time_of_day="indefinido",
            weather="indefinido",
            wardrobe={
                character.canonical_name: (
                    character.default_wardrobe().description
                    if character.default_wardrobe()
                    else "figurino base"
                )
                for character in leads
            },
            wardrobe_condition={
                character.canonical_name: "íntegro" for character in leads
            },
            emotions={character.canonical_name: "neutro" for character in leads},
            hands_occupied={character.canonical_name: "mãos livres" for character in leads},
            music_intensity="silêncio",
            narrative_state=f"Abertura de {episode.title}.",
        )

    # -- segmento ----------------------------------------------------------

    def _build_segment(
        self,
        *,
        context: EngineContext,
        canon: CanonBible,
        bible: AudiovisualBible,
        profile: FormatProfile,
        episode: Episode,
        scene: Scene,
        beat: NarrativeBeat | None,
        window: TimeRange,
        number: int,
        position_in_scene: int,
        scene_length: int,
        incoming: ContinuitySnapshot,
        previous: PromptSegment | None,
        subtitle_index: int,
    ) -> tuple[PromptSegment, ContinuitySnapshot, int]:
        characters = self._characters_in(canon, scene, beat)
        location = canon.location(scene.location_id) if scene.location_id else None
        location_profile = (
            bible.location_profile(scene.location_id) if scene.location_id else None
        )

        is_first = position_in_scene == 0
        is_last = position_in_scene == scene_length - 1
        function = self._function_for(scene, position_in_scene, scene_length)

        video = self._build_video(
            canon=canon,
            bible=bible,
            scene=scene,
            beat=beat,
            characters=characters,
            location=location,
            location_profile=location_profile,
            incoming=incoming,
            function=function,
            is_first=is_first,
            is_last=is_last,
            position=position_in_scene,
        )
        audio, cues, subtitle_index = self._build_audio(
            bible=bible,
            profile=profile,
            scene=scene,
            beat=beat,
            characters=characters,
            location_profile=location_profile,
            window=window,
            function=function,
            is_first=is_first,
            is_last=is_last,
            position=position_in_scene,
            subtitle_index=subtitle_index,
        )
        outgoing = self._advance_state(
            incoming=incoming,
            scene=scene,
            video=video,
            audio=audio,
            characters=characters,
        )

        segment = PromptSegment(
            segment_id=SegmentId(
                value=f"{episode.episode_id.value}_s{number:04d}"
            ),
            project_id=context.project_id.value,
            production_variant=profile.variant,
            episode_id=episode.episode_id.value,
            sequence_id=scene.sequence_id,
            scene_id=scene.scene_id,
            segment_number=number,
            range=window,
            duration=SegmentDuration(target=profile.segment_duration),
            segment_format=SegmentFormat(
                aspect_ratio=profile.aspect_ratio,
                resolution=profile.resolution,
                frame_rate=profile.frame_rate,
            ),
            narrative=SegmentNarrative(
                purpose=self._purpose(scene, beat, function, is_first, is_last),
                beat=beat.beat_id if beat else scene.scene_id.value,
                function=function,
                emotional_start=scene.tone_start,
                emotional_end=scene.tone_end if is_last else scene.tone_start,
                information_revealed=beat.information_revealed if beat and is_last else (),
                information_withheld=self._withheld(profile.variant, beat),
                tension=beat.tension if beat else 0,
            ),
            continuity_reference=ContinuityReference(
                previous_segment_id=previous.segment_id if previous else None
            ),
            continuity_in=incoming,
            continuity_out=outgoing,
            video=video,
            audio=audio,
            subtitles=cues,
            source_references=self._references(scene, beat),
        )
        return segment, outgoing, subtitle_index

    # -- vídeo -------------------------------------------------------------

    def _build_video(
        self,
        *,
        canon: CanonBible,
        bible: AudiovisualBible,
        scene: Scene,
        beat: NarrativeBeat | None,
        characters: tuple[Character, ...],
        location: object,
        location_profile: object,
        incoming: ContinuitySnapshot,
        function: NarrativeFunction,
        is_first: bool,
        is_last: bool,
        position: int,
    ) -> VideoPlan:
        identity = bible.visual_identity
        shot = _SHOT_BY_FUNCTION.get(function, identity.default_shot_type)
        movement, movement_speed = self._movement_for(beat)
        lighting = self._lighting(location_profile, identity, scene)
        setting = self._setting(scene, location, location_profile, identity)

        presences = tuple(
            self._presence(character, bible, incoming, scene, position)
            for character in characters
        )

        return VideoPlan(
            initial_frame=self._frame(
                scene, characters, position, opening=True, function=function
            ),
            final_frame=self._frame(
                scene, characters, position, opening=False, function=function
            ),
            setting=setting,
            location_id=scene.location_id,
            characters=presences,
            action=self._action(scene, beat, characters, position, function),
            performance=self._performance(characters, scene, function),
            relevant_props=self._props_for(canon, scene, beat),
            time_of_day=scene.time_of_day if scene.time_of_day != "indefinido" else "fim de tarde",
            weather=scene.weather if scene.weather != "indefinido" else "céu encoberto, sem chuva",
            lighting=lighting,
            composition=self._composition(shot, presences, function),
            camera=CameraPlan(
                shot_type=shot,
                angle=self._angle_for(function, identity.default_angle),
                lens=_LENS_BY_SHOT.get(shot, "50mm"),
                height=(
                    "à altura dos olhos do personagem em foco"
                    if shot
                    not in {ShotType.EXTREME_WIDE, ShotType.WIDE}
                    else "à altura do peito, um pouco abaixo da linha do horizonte"
                ),
                distance=self._distance_for(shot),
                movement=movement,
                movement_speed=movement_speed,
                focus=self._focus(presences, scene),
                depth_of_field=(
                    "rasa, com o fundo dissolvido em manchas de luz"
                    if shot in {ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE_UP, ShotType.INSERT}
                    else "média, com o cenário legível atrás da figura"
                ),
            ),
            visual_rhythm=self._rhythm(beat, function),
            transition_in=self._transition_in(is_first, function),
            transition_out=self._transition_out(is_last, function),
            negative_constraints=self._negative_constraints(bible, characters),
        )

    def _presence(
        self,
        character: Character,
        bible: AudiovisualBible,
        incoming: ContinuitySnapshot,
        scene: Scene,
        position: int,
    ) -> CharacterPresence:
        wardrobe_set = character.wardrobe_for_chapter(scene.beat_ids and 0 or 0)
        wardrobe = incoming.wardrobe.get(
            character.canonical_name,
            wardrobe_set.description if wardrobe_set else "figurino base da obra",
        )
        emotion = incoming.emotions.get(character.canonical_name, scene.tone_start.value)
        hands = incoming.hands_occupied.get(character.canonical_name, "mãos livres")

        return CharacterPresence(
            character_id=character.character_id,
            display_name=character.canonical_name,
            appearance_anchor=character.appearance.anchor_text(),
            wardrobe=wardrobe,
            wardrobe_condition=incoming.wardrobe_condition.get(
                character.canonical_name, "íntegro"
            ),
            expression=self._expression(emotion, position),
            posture=character.appearance.default_posture,
            blocking=self._blocking(character, scene, position),
            hands_occupied_with=hands,
            gaze_direction=(
                "para o interlocutor" if len(scene.participants) > 1 else "para o objeto em foco"
            ),
            visible_injuries=tuple(
                value
                for name, value in incoming.injuries.items()
                if name == character.canonical_name
            ),
        )

    # -- áudio -------------------------------------------------------------

    def _build_audio(
        self,
        *,
        bible: AudiovisualBible,
        profile: FormatProfile,
        scene: Scene,
        beat: NarrativeBeat | None,
        characters: tuple[Character, ...],
        location_profile: object,
        window: TimeRange,
        function: NarrativeFunction,
        is_first: bool,
        is_last: bool,
        position: int,
        subtitle_index: int,
    ) -> tuple[AudioPlan, tuple[SubtitleCue, ...], int]:
        speech_window = self._speech_window(window)
        ambient = self._ambient(location_profile, scene)
        effects = self._effects(window, scene, beat, position)

        dialogue: list[DialogueLine] = []
        narration: list[NarrationLine] = []
        voice_plan: list[VoicePlanEntry] = []
        cues: list[SubtitleCue] = []

        line_text, speaker = self._pick_line(beat, characters, position)
        max_words = self._word_budget(speech_window)

        if line_text and speaker and profile.dialogue_enabled and max_words >= 3:
            voice = bible.voice_for_character(speaker.character_id)
            if voice is not None:
                text = truncate_words(line_text, max_words)
                dialogue.append(
                    DialogueLine(
                        voice_id=voice.voice_id,
                        character_id=speaker.character_id,
                        speaker_name=speaker.canonical_name,
                        text=text,
                        language=profile.language,
                        intention=self._intention(function),
                        emotion=scene.tone_start,
                        pace="medido",
                        pauses="pausa curta antes da última oração",
                        breathing="inspiração audível antes de falar",
                        range=speech_window,
                    )
                )
                voice_plan.append(
                    VoicePlanEntry(
                        decision=VocalDecision.DIALOGUE,
                        voice_id=voice.voice_id,
                        character_id=speaker.character_id,
                        description=(
                            f"{speaker.canonical_name} fala em {scene.tone_start.value}, "
                            f"com {voice.identity.texture}."
                        ),
                        range=speech_window,
                        intensity="média",
                    )
                )
                cues.append(
                    SubtitleCue(
                        index=subtitle_index + 1,
                        range=speech_window,
                        speaker=speaker.canonical_name,
                        text=text,
                    )
                )
                subtitle_index += 1

        elif profile.narration_enabled and beat is not None and max_words >= 3:
            narrator = bible.narrator_voice()
            if narrator is not None:
                text = truncate_words(
                    excerpt(beat.summary, max_chars=400), max_words
                )
                if text:
                    narration.append(
                        NarrationLine(
                            voice_id=narrator.voice_id,
                            narrator_name=narrator.display_name,
                            text=text,
                            language=profile.language,
                            intention=self._intention(function),
                            emotion=scene.tone_start,
                            pace="medido",
                            pauses="pausa longa antes do último termo",
                            breathing="inaudível",
                            rhythm="constante, sem pressa",
                            range=speech_window,
                        )
                    )
                    voice_plan.append(
                        VoicePlanEntry(
                            decision=VocalDecision.NARRATION,
                            voice_id=narrator.voice_id,
                            description=(
                                "Narração descritiva, sem coloração dramática, sobre a "
                                "imagem já em curso."
                            ),
                            range=speech_window,
                            intensity="baixa",
                        )
                    )
                    cues.append(
                        SubtitleCue(
                            index=subtitle_index + 1,
                            range=speech_window,
                            speaker=narrator.display_name,
                            text=text,
                        )
                    )
                    subtitle_index += 1

        if not voice_plan:
            voice_plan.append(self._non_verbal_decision(bible, characters, window, function))

        silence = self._silence(window, speech_window, voice_plan, function)

        audio = AudioPlan(
            voice_plan=tuple(voice_plan),
            dialogue=tuple(dialogue),
            narration=tuple(narration),
            ambient_sound=ambient,
            sound_effects=effects,
            music=self._music(bible, profile, window, function, beat, is_first, is_last),
            silence=silence,
            mixing_notes=self._mixing(bool(dialogue or narration)),
            synchronization_cues=self._sync_cues(window, effects, scene),
            audio_transition_out=self._audio_transition(is_last, function),
        )
        return audio, tuple(cues), subtitle_index

    @staticmethod
    def _speech_window(window: TimeRange) -> TimeRange:
        """Janela interna reservada à fala, com respiro antes e depois."""
        total = window.duration.milliseconds
        lead_in = int(total * _SPEECH_LEAD_IN_RATIO)
        span = int(total * _SPEECH_WINDOW_RATIO)
        start = Timecode(milliseconds=window.start.milliseconds + lead_in)
        end = Timecode(milliseconds=min(window.end.milliseconds, start.milliseconds + span))
        return TimeRange(start=start, end=end)

    @staticmethod
    def _word_budget(speech_window: TimeRange) -> int:
        """Palavras que cabem na janela, com margem de segurança."""
        theoretical = max_words_for_duration(speech_window.duration.seconds)
        return max(0, int(theoretical * _WORD_BUDGET_SAFETY))

    @staticmethod
    def _pick_line(
        beat: NarrativeBeat | None,
        characters: tuple[Character, ...],
        position: int,
    ) -> tuple[str, Character | None]:
        """Escolhe a fala deste segmento, alternando entre os interlocutores."""
        if beat is None or not beat.dialogue_excerpts or not characters:
            return "", None
        line = beat.dialogue_excerpts[position % len(beat.dialogue_excerpts)]
        speaker = characters[position % len(characters)]
        return line, speaker

    def _non_verbal_decision(
        self,
        bible: AudiovisualBible,
        characters: tuple[Character, ...],
        window: TimeRange,
        function: NarrativeFunction,
    ) -> VoicePlanEntry:
        """Decisão vocal quando não há palavras — nunca uma omissão."""
        narrator = bible.narrator_voice()
        voice_id = narrator.voice_id if narrator else "voice_ambiente_ptbr_v1"

        if characters:
            character = characters[0]
            voice = bible.voice_for_character(character.character_id)
            if voice is not None:
                voice_id = voice.voice_id

            if function in {NarrativeFunction.CLIMAX, NarrativeFunction.CONFRONTATION}:
                return VoicePlanEntry(
                    decision=VocalDecision.VOCAL_REACTION,
                    voice_id=voice_id,
                    character_id=character.character_id,
                    description=(
                        f"{character.canonical_name} solta uma reação curta e involuntária "
                        "— meio sopro, meio negação — sem articular palavra."
                    ),
                    range=window,
                    intensity="média-alta",
                )
            return VoicePlanEntry(
                decision=VocalDecision.BREATHING,
                voice_id=voice_id,
                character_id=character.character_id,
                description=(
                    f"Respiração audível de {character.canonical_name}, mais curta na "
                    "inspiração do que na expiração, revelando contenção."
                ),
                range=window,
                intensity="baixa",
            )

        return VoicePlanEntry(
            decision=VocalDecision.INTENTIONAL_SILENCE,
            voice_id=voice_id,
            description="Nenhuma voz humana neste segmento.",
            justification=(
                "O segmento mostra o espaço sem ninguém dentro. Qualquer voz aqui "
                "quebraria a solidão que a cena precisa estabelecer antes da entrada "
                "do personagem."
            ),
            range=window,
            intensity="nula",
        )

    @staticmethod
    def _ambient(location_profile: object, scene: Scene) -> tuple[AmbientSound, ...]:
        from pedroarte_youtube_engine.domain.audiovisual import LocationVisualProfile

        sounds: list[str] = []
        if isinstance(location_profile, LocationVisualProfile):
            sounds = list(location_profile.ambient_sound)
        if not sounds:
            sounds = ["ar parado de ambiente fechado, com zumbido elétrico muito baixo"]

        return tuple(
            AmbientSound(
                description=description,
                source=scene.location_name or "o próprio ambiente",
                spatiality="estéreo amplo, atrás do plano da voz",
                continuous=True,
                relative_db=-22.0 - index * 3.0,
            )
            for index, description in enumerate(sounds[:3])
        )

    @staticmethod
    def _effects(
        window: TimeRange,
        scene: Scene,
        beat: NarrativeBeat | None,
        position: int,
    ) -> tuple[SoundEffect, ...]:
        if beat is None:
            return ()
        anchor = Timecode(
            milliseconds=window.start.milliseconds + window.duration.milliseconds // 3
        )
        descriptions = (
            ("passo único sobre piso duro", "o personagem transfere o peso de um pé ao outro"),
            ("tecido roçando em movimento curto", "o braço se ergue dentro da manga"),
            ("objeto pousado sobre superfície de madeira", "a mão deixa o objeto na bancada"),
            ("porta ranger meio centímetro", "a corrente de ar move a folha da porta"),
        )
        description, action = descriptions[position % len(descriptions)]
        return (
            SoundEffect(
                description=description,
                at=anchor,
                duration=Duration.from_seconds(0.4),
                synced_to_action=action,
                spatiality="centro, próximo",
                relative_db=-14.0,
                off_screen=position % 4 == 3,
            ),
        )

    @staticmethod
    def _music(
        bible: AudiovisualBible,
        profile: FormatProfile,
        window: TimeRange,
        function: NarrativeFunction,
        beat: NarrativeBeat | None,
        is_first: bool,
        is_last: bool,
    ) -> MusicCue:
        if not profile.music_enabled:
            return MusicCue(enabled=False, description="", function="")

        tension = beat.tension if beat else 0
        if function is NarrativeFunction.BREATHING and tension == 0:
            return MusicCue(
                enabled=False,
                description="",
                function="",
                relationship_to_dialogue="—",
            )

        theme = (
            bible.theme_for_role("tensao")
            if tension >= 4
            else bible.theme_for_role("tema_principal")
        )
        if theme is None:
            theme = bible.music_themes[0] if bible.music_themes else None
        if theme is None:
            return MusicCue(enabled=False, description="", function="")

        return MusicCue(
            enabled=True,
            theme_id=theme.theme_id,
            description=theme.motif_description,
            function=(
                "sustentar a tensão sem antecipar a revelação"
                if tension >= 4
                else "manter a presença do tema sob a imagem"
            ),
            instrumentation=theme.instrumentation,
            tempo=theme.tempo_bpm_range,
            intensity_start="muito baixa" if is_first else "baixa",
            intensity_end="média" if is_last and tension >= 4 else "baixa",
            entry_timecode=window.start,
            exit_timecode=window.end,
            relationship_to_dialogue="recua 6 dB sob qualquer fala",
        )

    @staticmethod
    def _silence(
        window: TimeRange,
        speech_window: TimeRange,
        voice_plan: list[VoicePlanEntry],
        function: NarrativeFunction,
    ) -> tuple[SilenceBeat, ...]:
        """Silêncio deliberado no fecho dos segmentos de virada."""
        if function not in {
            NarrativeFunction.REVELATION,
            NarrativeFunction.REVERSAL,
            NarrativeFunction.CLIFFHANGER,
        }:
            return ()
        start = speech_window.end
        if start.milliseconds >= window.end.milliseconds:
            return ()
        return (
            SilenceBeat(
                range=TimeRange(start=start, end=window.end),
                kind="suspensão",
                justification=(
                    "O corte de todo o som depois da última sílaba força o espectador a "
                    "ocupar o vazio com a informação que acabou de receber."
                ),
            ),
        )

    @staticmethod
    def _mixing(has_speech: bool) -> tuple[MixLevel, ...]:
        if has_speech:
            return (
                MixLevel(element="voz", relative_db=0.0, priority=1),
                MixLevel(element="efeitos sonoros", relative_db=-10.0, priority=2),
                MixLevel(element="som ambiente", relative_db=-20.0, priority=3),
                MixLevel(element="música", relative_db=-16.0, priority=4),
            )
        return (
            MixLevel(element="som ambiente", relative_db=0.0, priority=1),
            MixLevel(element="efeitos sonoros", relative_db=-6.0, priority=2),
            MixLevel(element="música", relative_db=-9.0, priority=3),
            MixLevel(element="respiração", relative_db=-14.0, priority=4),
        )

    @staticmethod
    def _sync_cues(
        window: TimeRange, effects: tuple[SoundEffect, ...], scene: Scene
    ) -> tuple[SyncCue, ...]:
        return tuple(
            SyncCue(
                at=effect.at,
                visual_action=effect.synced_to_action,
                audio_event=effect.description,
            )
            for effect in effects
        )

    @staticmethod
    def _audio_transition(is_last: bool, function: NarrativeFunction) -> str:
        if function is NarrativeFunction.CLIFFHANGER:
            return (
                "Corte abrupto de todo o som um quadro antes do corte de imagem, "
                "deixando o próximo segmento começar em silêncio absoluto."
            )
        if is_last:
            return (
                "O som ambiente do próximo espaço entra dois segundos antes do corte "
                "de imagem — ponte sonora que atravessa a mudança de cena."
            )
        return (
            "O ambiente permanece contínuo através do corte; nenhum elemento sonoro "
            "é interrompido na passagem para o segmento seguinte."
        )

    # -- continuidade ------------------------------------------------------

    def _advance_state(
        self,
        *,
        incoming: ContinuitySnapshot,
        scene: Scene,
        video: VideoPlan,
        audio: AudioPlan,
        characters: tuple[Character, ...],
    ) -> ContinuitySnapshot:
        """Estado que o próximo segmento herda — o `Continuity Ledger`."""
        last_words = ""
        spoken = audio.all_spoken_lines()
        if spoken:
            last_words = spoken[-1].text[-200:]

        return incoming.model_copy(
            update={
                "time_of_day": video.time_of_day,
                "weather": video.weather,
                "location_id": video.location_id,
                "character_positions": {
                    presence.display_name: presence.blocking
                    for presence in video.characters
                }
                or incoming.character_positions,
                "emotions": {
                    presence.display_name: presence.expression
                    for presence in video.characters
                }
                or incoming.emotions,
                "hands_occupied": {
                    presence.display_name: presence.hands_occupied_with
                    for presence in video.characters
                }
                or incoming.hands_occupied,
                "wardrobe": {
                    presence.display_name: presence.wardrobe
                    for presence in video.characters
                }
                or incoming.wardrobe,
                "wardrobe_condition": {
                    presence.display_name: presence.wardrobe_condition
                    for presence in video.characters
                }
                or incoming.wardrobe_condition,
                "props_on_scene": video.relevant_props,
                "lighting_state": video.lighting,
                "music_intensity": (
                    audio.music.intensity_end if audio.music.enabled else "silêncio"
                ),
                "persistent_sounds": tuple(
                    ambient.description for ambient in audio.ambient_sound
                ),
                "last_spoken_words": last_words,
                "final_frame_description": video.final_frame,
                "narrative_state": scene.summary[:800],
            }
        )

    # -- geradores de texto ------------------------------------------------

    @staticmethod
    def _characters_in(
        canon: CanonBible, scene: Scene, beat: NarrativeBeat | None
    ) -> tuple[Character, ...]:
        ids = scene.participants or (beat.participants if beat else ())
        found = tuple(
            character
            for character in (canon.character(identifier) for identifier in ids)
            if character is not None
        )
        return found or canon.leads()[:1]

    @staticmethod
    def _function_for(
        scene: Scene, position: int, length: int
    ) -> NarrativeFunction:
        if length == 1:
            return scene.dramatic_function
        if position == 0:
            return (
                NarrativeFunction.HOOK
                if scene.dramatic_function is NarrativeFunction.HOOK
                else NarrativeFunction.SETUP
            )
        if position == length - 1:
            return scene.dramatic_function
        return NarrativeFunction.RISING_ACTION

    @staticmethod
    def _purpose(
        scene: Scene,
        beat: NarrativeBeat | None,
        function: NarrativeFunction,
        is_first: bool,
        is_last: bool,
    ) -> str:
        moment = (
            "abre a cena e estabelece o espaço"
            if is_first
            else ("fecha a cena e entrega o estado ao próximo bloco" if is_last else "sustenta a progressão")
        )
        subject = beat.summary if beat else scene.summary
        return (
            f"Este segmento {moment}. Função dramática: {function.value}. "
            f"O que muda entre o primeiro e o último quadro: "
            f"{excerpt(subject, max_chars=300)}"
        )

    @staticmethod
    def _withheld(
        variant: ProductionVariant, beat: NarrativeBeat | None
    ) -> tuple[str, ...]:
        if variant is ProductionVariant.TRAILERS:
            return (
                "o desfecho da obra",
                "a identidade por trás da revelação central",
                "o resultado do confronto final",
            )
        if beat and beat.information_revealed:
            return ()
        return ("a consequência do que acabou de acontecer",)

    @staticmethod
    def _setting(
        scene: Scene, location: object, location_profile: object, identity: object
    ) -> str:
        from pedroarte_youtube_engine.domain.audiovisual import LocationVisualProfile
        from pedroarte_youtube_engine.domain.canon import Location

        name = scene.location_name or "o espaço da cena"
        description = ""
        if isinstance(location, Location) and location.description:
            description = excerpt(location.description, max_chars=400)
        palette = ""
        if isinstance(location_profile, LocationVisualProfile) and location_profile.palette:
            palette = f" A paleta do lugar é dominada por {', '.join(location_profile.palette)}."

        base = (
            f"Interior de {name}, com superfícies gastas pelo uso diário e objetos "
            f"dispostos por hábito, não por arrumação."
            if not description
            else f"{name}. {description}"
        )
        return f"{base}{palette}"

    @staticmethod
    def _action(
        scene: Scene,
        beat: NarrativeBeat | None,
        characters: tuple[Character, ...],
        position: int,
        function: NarrativeFunction,
    ) -> str:
        who = characters[0].canonical_name if characters else "a figura em quadro"
        other = characters[1].canonical_name if len(characters) > 1 else ""
        core = excerpt(beat.summary if beat else scene.summary, max_chars=300)

        beats_of_action = (
            f"{who} interrompe o que estava fazendo e não retoma imediatamente",
            f"{who} desloca o peso do corpo e reorganiza a posição das mãos",
            f"{who} leva o olhar até o objeto em foco e o mantém ali por mais tempo do que seria natural",
            f"{who} baixa a cabeça um grau e respira antes de reagir",
        )
        physical = beats_of_action[position % len(beats_of_action)]
        interaction = (
            f" {other} percebe o gesto e ajusta a própria postura sem falar."
            if other
            else ""
        )
        return f"{physical}.{interaction} Contexto narrativo do bloco: {core}"

    @staticmethod
    def _performance(
        characters: tuple[Character, ...], scene: Scene, function: NarrativeFunction
    ) -> str:
        if not characters:
            return (
                "Sem figura humana em quadro: a atuação é do próprio espaço — a luz "
                "muda de intensidade e o ar carrega poeira visível."
            )
        primary = characters[0]
        temperament = ", ".join(primary.temperament) or "contido"
        return (
            f"{primary.canonical_name} atua por contenção: {temperament}. "
            f"A emoção ({scene.tone_start.value}) aparece no atraso entre o estímulo e "
            "a reação, não na expressão facial. O olhar chega ao alvo antes do corpo. "
            "Nenhum gesto é ilustrativo do que está sendo dito."
        )

    @staticmethod
    def _props_for(
        canon: CanonBible, scene: Scene, beat: NarrativeBeat | None
    ) -> tuple[str, ...]:
        return tuple(prop.canonical_name for prop in canon.props[:3])

    @staticmethod
    def _frame(
        scene: Scene,
        characters: tuple[Character, ...],
        position: int,
        *,
        opening: bool,
        function: NarrativeFunction,
    ) -> str:
        who = characters[0].canonical_name if characters else "o espaço vazio"
        if opening:
            return (
                f"{who} imóvel no terço esquerdo do quadro, olhar ainda fora do alvo, "
                "mãos na posição herdada do segmento anterior; a luz principal vem de "
                "trás e recorta o contorno."
            )
        return (
            f"{who} deslocado para o centro do quadro, olhar agora fixo no alvo, "
            "ombros meio grau mais baixos do que no início; a luz principal atinge "
            "metade do rosto e a outra metade permanece na sombra."
        )

    @staticmethod
    def _composition(
        shot: ShotType, presences: tuple[CharacterPresence, ...], function: NarrativeFunction
    ) -> str:
        if len(presences) >= 2:
            return (
                "Composição em duas massas desiguais: a figura em foco ocupa o terço "
                "direito, a outra aparece desfocada no primeiro plano à esquerda, "
                "criando profundidade sem competir pela atenção."
            )
        if shot in {ShotType.EXTREME_WIDE, ShotType.WIDE}:
            return (
                "Figura pequena no terço inferior do quadro, com o ambiente ocupando "
                "os dois terços superiores. O espaço domina a pessoa."
            )
        return (
            "Figura descentralizada à esquerda, com espaço vazio à frente do olhar. "
            "Linhas do cenário conduzem o olhar do espectador até o rosto."
        )

    @staticmethod
    def _lighting(location_profile: object, identity: object, scene: Scene) -> str:
        from pedroarte_youtube_engine.domain.audiovisual import LocationVisualProfile

        if isinstance(location_profile, LocationVisualProfile) and location_profile.lighting:
            return (
                f"{location_profile.lighting} Toda fonte é justificada em cena; "
                "nenhuma luz vem de origem invisível."
            )
        return (
            "Fonte quente única, baixa e lateral, justificada por um ponto de luz "
            "visível em quadro. O resto do espaço fica em penumbra com detalhe "
            "preservado nas sombras. Contraste médio-alto."
        )

    @staticmethod
    def _movement_for(beat: NarrativeBeat | None) -> tuple[CameraMovement, str]:
        tension = beat.tension if beat else 0
        chosen = _MOVEMENT_BY_TENSION[0]
        for threshold, movement, speed in _MOVEMENT_BY_TENSION:
            if tension >= threshold:
                chosen = (threshold, movement, speed)
        return chosen[1], chosen[2]

    @staticmethod
    def _angle_for(function: NarrativeFunction, default: CameraAngle) -> CameraAngle:
        return {
            NarrativeFunction.CLIMAX: CameraAngle.LOW,
            NarrativeFunction.REVELATION: CameraAngle.EYE_LEVEL,
            NarrativeFunction.EPILOGUE: CameraAngle.HIGH,
            NarrativeFunction.CLIFFHANGER: CameraAngle.LOW,
        }.get(function, default)

    @staticmethod
    def _distance_for(shot: ShotType) -> str:
        return {
            ShotType.EXTREME_WIDE: "muito distante, ambiente inteiro visível",
            ShotType.WIDE: "distante, corpo inteiro com folga",
            ShotType.CLOSE_UP: "próxima, rosto ocupando dois terços do quadro",
            ShotType.EXTREME_CLOSE_UP: "muito próxima, detalhe isolado",
            ShotType.INSERT: "muito próxima, objeto isolado",
        }.get(shot, "média, da cintura para cima")

    @staticmethod
    def _focus(presences: tuple[CharacterPresence, ...], scene: Scene) -> str:
        if presences:
            return f"nos olhos de {presences[0].display_name}"
        return "no objeto de maior peso narrativo em quadro"

    @staticmethod
    def _rhythm(beat: NarrativeBeat | None, function: NarrativeFunction) -> str:
        tension = beat.tension if beat else 0
        if tension >= 6:
            return "acelerado por dentro do plano, sem cortes internos"
        if function is NarrativeFunction.BREATHING:
            return "suspenso; o plano dura mais do que o confortável"
        return "constante, com uma única inflexão no meio do bloco"

    @staticmethod
    def _transition_in(is_first: bool, function: NarrativeFunction) -> TransitionType:
        if is_first and function is NarrativeFunction.HOOK:
            return TransitionType.FADE_IN
        if is_first:
            return TransitionType.CUT
        return TransitionType.CUT

    @staticmethod
    def _transition_out(is_last: bool, function: NarrativeFunction) -> TransitionType:
        if function is NarrativeFunction.CLIFFHANGER:
            return TransitionType.FADE_TO_BLACK
        if function is NarrativeFunction.EPILOGUE:
            return TransitionType.FADE_OUT
        if is_last:
            return TransitionType.SOUND_BRIDGE
        return TransitionType.CUT

    @staticmethod
    def _expression(emotion: str, position: int) -> str:
        variations = (
            f"{emotion}, com a musculatura do rosto quase parada",
            f"{emotion}, com uma contração breve entre as sobrancelhas",
            f"{emotion}, com o maxilar levemente travado",
            f"{emotion}, com o olhar chegando antes da expressão",
        )
        return variations[position % len(variations)]

    @staticmethod
    def _blocking(character: Character, scene: Scene, position: int) -> str:
        positions = (
            "de pé junto à superfície de trabalho, corpo em três quartos para a câmera",
            "meio passo à frente, ombros abertos para o interlocutor",
            "sentado, antebraços apoiados, tronco inclinado para a frente",
            "recuado meio passo, costas próximas da parede",
        )
        return positions[position % len(positions)]

    @staticmethod
    def _intention(function: NarrativeFunction) -> str:
        return {
            NarrativeFunction.HOOK: "abrir uma pergunta sem entregar a resposta",
            NarrativeFunction.REVELATION: "dizer o que não podia ser dito antes",
            NarrativeFunction.CONFRONTATION: "obrigar o outro a se posicionar",
            NarrativeFunction.CLIMAX: "assumir o custo da decisão",
            NarrativeFunction.CLIFFHANGER: "deixar a frase incompleta de propósito",
        }.get(function, "informar sem enfatizar")

    @staticmethod
    def _negative_constraints(
        bible: AudiovisualBible, characters: tuple[Character, ...]
    ) -> tuple[str, ...]:
        constraints = list(bible.visual_identity.visual_restrictions)
        for character in characters:
            constraints.extend(
                f"{character.canonical_name}: {variation}"
                for variation in character.forbidden_variations
            )
        return tuple(dict.fromkeys(constraints))

    @staticmethod
    def _references(scene: Scene, beat: NarrativeBeat | None) -> tuple:
        if beat and beat.references:
            return beat.references
        return scene.references


def _profile_prefix(profile_id: str) -> str:
    from pedroarte_youtube_engine.shared.text import safe_slug

    return safe_slug(profile_id, max_length=90)
