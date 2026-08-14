"""Agentes da Bíblia Audiovisual (9.7, 9.17 e 9.20)."""

from __future__ import annotations

from pedroarte_youtube_engine.agents.base import (
    AgentContract,
    AgentResult,
    AgentTool,
    BaseAgent,
    EngineContext,
    MemoryScope,
)
from pedroarte_youtube_engine.domain.aggregates import AudiovisualBible, CanonBible
from pedroarte_youtube_engine.domain.audiovisual import (
    CharacterVisualProfile,
    ContinuityAnchor,
    LocationVisualProfile,
    MusicRole,
    MusicTheme,
    SoundMotif,
    VisualIdentity,
    VoiceProfile,
)
from pedroarte_youtube_engine.domain.canon import Character
from pedroarte_youtube_engine.domain.events import DomainEvent, DomainEventType
from pedroarte_youtube_engine.domain.value_objects import (
    CameraAngle,
    CameraMovement,
    EmotionalTone,
    Language,
    ShotType,
    TransitionType,
    VoiceIdentity,
)
from pedroarte_youtube_engine.shared.text import safe_slug, strip_accents

#: Paletas conceituais por tema dominante da obra.
_PALETTES: dict[str, tuple[str, ...]] = {
    "tempo": ("latão envelhecido", "vidro fosco", "azul-ardósia", "branco de mostrador"),
    "memória": ("sépia lavado", "cinza-pérola", "âmbar baixo", "verde-musgo"),
    "culpa": ("carvão", "vermelho-tijolo apagado", "ocre sujo", "branco-osso"),
    "verdade": ("azul-noite", "branco clínico", "prata frio", "preto profundo"),
    "perda": ("cinza-chumbo", "azul-inverno", "bege desbotado", "preto úmido"),
    "identidade": ("espelho prateado", "azul-aço", "creme", "grafite"),
    "justiça": ("verde-garrafa", "marrom-couro", "dourado sóbrio", "preto"),
    "amor": ("terracota", "rosa-poeira", "dourado quente", "castanho"),
    "medo": ("preto azulado", "verde-doente", "branco de flash", "vermelho escuro"),
    "poder": ("bordô", "dourado escuro", "preto lacado", "cinza-concreto"),
    "herança": ("madeira escura", "latão", "linho envelhecido", "verde-garrafa"),
}

#: Doutrinas de câmera associadas ao tom predominante.
_CAMERA_DOCTRINES: dict[str, str] = {
    "tenso": (
        "Câmera próxima e levemente instável, sempre um passo mais perto do que o "
        "confortável. Cortes internos raros: a tensão vem da permanência no plano."
    ),
    "melancolico": (
        "Câmera parada, planos longos, personagem descentralizado no quadro. O espaço "
        "vazio ao lado da figura carrega o que ela não diz."
    ),
    "sombrio": (
        "Câmera baixa e lenta, com movimento contínuo de aproximação. O enquadramento "
        "revela o ambiente antes de revelar quem está nele."
    ),
    "neutro": (
        "Câmera à altura do olhar, movimento discreto e motivado pela ação. Nenhum "
        "movimento acontece sem razão dramática."
    ),
}


class AudiovisualBibleAgent(BaseAgent):
    """`AUDIOVISUAL_BIBLE_AGENT` — converte o cânone em decisões de tela e som."""

    _contract = AgentContract(
        name="AUDIOVISUAL_BIBLE_AGENT",
        responsibility=(
            "Converter o cânone em decisões audiovisuais: estilo cinematográfico "
            "próprio, fotografia, enquadramentos, iluminação, linguagem de câmera, "
            "identidade sonora, vozes, música, ambientes, motivos e transições."
        ),
        phase="BUILDING_BIBLES",
        input_type="CanonBible",
        output_type="AudiovisualBible",
        authorized_tools=(AgentTool.DOMAIN_SERVICES, AgentTool.RAG_RETRIEVAL),
        memory=MemoryScope.CANON,
        prompt_name="audiovisual.bible",
        completion_criteria=(
            "O estilo deriva dos temas da obra, não de uma referência externa.",
            "Toda voz tem identidade estável e reutilizável.",
            "Cada ambiente tem paleta, luz e assinatura sonora.",
        ),
        failure_criteria=("O cânone não contém personagens nem locais.",),
    )

    def __init__(
        self,
        *,
        voice_agent: "VoiceCastingAgent | None" = None,
        music_agent: "MusicSupervisorAgent | None" = None,
    ) -> None:
        self._voice_agent = voice_agent or VoiceCastingAgent()
        self._music_agent = music_agent or MusicSupervisorAgent()

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        log = self._log(context)

        themes = self._themes_of(context)
        identity = self._build_identity(canon, themes)
        voices = self._voice_agent.build_voices(canon, context.configuration.audio.spoken_language)
        themes_music = self._music_agent.build_themes(canon, themes)

        bible = AudiovisualBible(
            project_id=context.project_id,
            visual_identity=identity,
            character_profiles=self._character_profiles(canon),
            location_profiles=self._location_profiles(canon),
            voices=voices,
            music_themes=themes_music,
            sound_motifs=self._sound_motifs(canon),
            continuity_anchors=self._anchors(canon),
            transitions_doctrine=self._transitions_doctrine(canon),
            restrictions=identity.visual_restrictions,
        )

        log.info(
            "Bíblia Audiovisual construída",
            voices=len(bible.voices),
            music_themes=len(bible.music_themes),
            anchors=len(bible.continuity_anchors),
        )

        return AgentResult(
            agent=self.name,
            outputs={"audiovisual_bible": bible},
            events=(
                DomainEvent(
                    event_type=DomainEventType.AUDIOVISUAL_BIBLE_CREATED,
                    occurred_at=context.clock.now(),
                    run_id=context.run_id.value,
                    project_id=context.project_id.value,
                    emitted_by=self.name,
                    payload={
                        "voices": len(bible.voices),
                        "music_themes": len(bible.music_themes),
                        "continuity_anchors": len(bible.continuity_anchors),
                    },
                ),
            ),
        )

    # -- construção --------------------------------------------------------

    @staticmethod
    def _themes_of(context: EngineContext) -> tuple[str, ...]:
        analysis = context.analysis
        return analysis.themes if analysis else ()

    def _build_identity(self, canon: CanonBible, themes: tuple[str, ...]) -> VisualIdentity:
        palette: list[str] = []
        for theme in themes:
            palette.extend(_PALETTES.get(theme, ()))
        if not palette:
            palette = ["cinza-chumbo", "âmbar baixo", "branco-osso", "preto profundo"]

        dominant = self._dominant_tone(canon)
        doctrine = _CAMERA_DOCTRINES.get(dominant.value, _CAMERA_DOCTRINES["neutro"])
        theme_text = ", ".join(themes) if themes else "os conflitos centrais da obra"

        return VisualIdentity(
            style_statement=(
                f"A gramática visual de «{canon.title}» nasce de {theme_text}. "
                "A imagem observa mais do que comenta: o quadro se mantém quando o "
                "personagem hesita, e só se move quando alguma coisa muda de fato. "
                "A textura é material — vidro, metal, papel, tecido gasto — porque a "
                "obra trata de objetos que carregam história."
            ),
            conceptual_palette=tuple(dict.fromkeys(palette))[:8],
            lighting_doctrine=(
                "Fonte de luz sempre justificada em cena (lampião, janela, vitrine, "
                "tela). Nenhuma luz vem de lugar nenhum. Contraste médio-alto, sombras "
                "com detalhe preservado, temperatura fria nos exteriores e quente nos "
                "interiores de trabalho."
            ),
            lens_language=(
                "35mm como lente base para cenas de convivência; 50mm para diálogo a "
                "dois; 85mm para primeiros planos de decisão; 24mm apenas quando o "
                "ambiente precisa esmagar o personagem."
            ),
            camera_doctrine=doctrine,
            texture_and_grain="Grão fino e constante, halação suave nas fontes de luz.",
            default_shot_type=ShotType.MEDIUM,
            default_angle=CameraAngle.EYE_LEVEL,
            default_movement=CameraMovement.STATIC,
            default_transition=TransitionType.CUT,
            recurring_motifs=self._motifs(canon, themes),
        )

    @staticmethod
    def _dominant_tone(canon: CanonBible) -> EmotionalTone:
        if not canon.beats:
            return EmotionalTone.NEUTRAL
        counts: dict[EmotionalTone, int] = {}
        for beat in canon.beats:
            counts[beat.tone_end] = counts.get(beat.tone_end, 0) + 1
        return max(counts.items(), key=lambda item: (item[1], item[0].value))[0]

    @staticmethod
    def _motifs(canon: CanonBible, themes: tuple[str, ...]) -> tuple[str, ...]:
        motifs = [
            f"reaparição do objeto «{prop.canonical_name}» em momentos de decisão"
            for prop in canon.props[:3]
        ]
        motifs += [f"o tema de {theme} aparece antes de ser nomeado" for theme in themes[:2]]
        return tuple(motifs)

    @staticmethod
    def _character_profiles(canon: CanonBible) -> tuple[CharacterVisualProfile, ...]:
        profiles: list[CharacterVisualProfile] = []
        for index, character in enumerate(canon.characters):
            lead = character.is_lead
            profiles.append(
                CharacterVisualProfile(
                    character_id=character.character_id,
                    preferred_shot_types=(
                        (ShotType.MEDIUM_CLOSE, ShotType.CLOSE_UP)
                        if lead
                        else (ShotType.MEDIUM, ShotType.MEDIUM_FULL)
                    ),
                    lighting_note=(
                        "Luz lateral baixa, deixando metade do rosto na sombra."
                        if lead
                        else "Luz ambiente uniforme, sem destaque."
                    ),
                    color_association=(
                        "âmbar quente" if index % 2 == 0 else "azul-ardósia frio"
                    ),
                    framing_note=(
                        "Espaço vazio à frente do olhar quando escuta; enquadramento "
                        "apertado quando decide."
                    ),
                    forbidden_variations=character.forbidden_variations,
                )
            )
        return tuple(profiles)

    @staticmethod
    def _location_profiles(canon: CanonBible) -> tuple[LocationVisualProfile, ...]:
        return tuple(
            LocationVisualProfile(
                location_id=location.location_id,
                palette=(
                    ("madeira escura", "latão", "vidro")
                    if location.interior
                    else ("cinza úmido", "verde-musgo", "céu chumbo")
                ),
                lighting=(
                    "Fonte pontual quente, resto do espaço em penumbra."
                    if location.interior
                    else "Luz difusa de céu encoberto, sem sombra dura."
                ),
                ambient_sound=location.ambient_sound_signature,
                camera_note=(
                    "Planos fechados; o espaço aperta a cena."
                    if location.interior
                    else "Planos abertos; o espaço isola a figura."
                ),
                default_lens="50mm" if location.interior else "35mm",
            )
            for location in canon.locations
        )

    @staticmethod
    def _sound_motifs(canon: CanonBible) -> tuple[SoundMotif, ...]:
        motifs: list[SoundMotif] = []
        for prop in canon.props[:4]:
            motifs.append(
                SoundMotif(
                    motif_id=f"motif_{safe_slug(prop.canonical_name, max_length=60)}",
                    name=f"assinatura de {prop.canonical_name}",
                    description=(
                        f"Timbre curto e reconhecível associado a «{prop.canonical_name}»: "
                        "material puro, sem reverberação artificial."
                    ),
                    trigger=(
                        f"Toda vez que «{prop.canonical_name}» entra em quadro ou muda "
                        "de mão."
                    ),
                    spatiality="centro, próximo, seco",
                )
            )
        for character in canon.characters[:2]:
            motifs.append(
                SoundMotif(
                    motif_id=f"motif_{safe_slug(character.canonical_name, max_length=60)}",
                    name=f"respiração de {character.canonical_name}",
                    description=(
                        "Respiração audível e contida, usada como marcador de presença "
                        "mesmo quando o personagem está fora de quadro."
                    ),
                    trigger="Antes de cada decisão que o personagem hesita em tomar.",
                    spatiality="muito próximo, quase íntimo",
                    associated_character_id=character.character_id,
                )
            )
        return tuple(motifs)

    @staticmethod
    def _anchors(canon: CanonBible) -> tuple[ContinuityAnchor, ...]:
        anchors: list[ContinuityAnchor] = []
        for character in canon.characters:
            anchors.append(
                ContinuityAnchor(
                    anchor_id=f"anchor_face_{safe_slug(character.canonical_name, max_length=60)}",
                    subject=character.canonical_name,
                    category="aparência",
                    statement=character.appearance.anchor_text(),
                    hard_constraint=True,
                )
            )
            wardrobe = character.default_wardrobe()
            if wardrobe:
                anchors.append(
                    ContinuityAnchor(
                        anchor_id=(
                            f"anchor_wardrobe_{safe_slug(character.canonical_name, max_length=52)}"
                        ),
                        subject=character.canonical_name,
                        category="figurino",
                        statement=f"{wardrobe.description} — estado: {wardrobe.condition}",
                        hard_constraint=True,
                    )
                )
        for rule in canon.world_rules[:6]:
            anchors.append(
                ContinuityAnchor(
                    anchor_id=f"anchor_rule_{safe_slug(rule[:40], max_length=60)}",
                    subject="universo",
                    category="regra",
                    statement=rule,
                    hard_constraint=True,
                )
            )
        return tuple(anchors)

    @staticmethod
    def _transitions_doctrine(canon: CanonBible) -> str:
        return (
            "Corte seco é o padrão. Dissolução apenas em elipse temporal declarada. "
            "Fade para preto reservado ao fim de ato. Ponte sonora quando o som de uma "
            "cena precisa contaminar a seguinte — é o recurso preferido desta obra, "
            "porque o som carrega a continuidade que a imagem interrompe. "
            f"Nenhuma transição contradiz as {len(canon.world_rules)} regras do universo."
        )


class VoiceCastingAgent(BaseAgent):
    """`VOICE_CASTING_AGENT` — define a identidade vocal de cada personagem."""

    _contract = AgentContract(
        name="VOICE_CASTING_AGENT",
        responsibility=(
            "Definir identidade vocal, idade vocal, timbre, textura, sotaque, "
            "velocidade, pausas, intensidade, emoção, pronúncia de nomes e "
            "consistência entre episódios."
        ),
        phase="BUILDING_BIBLES",
        input_type="CanonBible",
        output_type="tuple[VoiceProfile, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.CANON,
        prompt_name="audiovisual.voice_casting",
        completion_criteria=(
            "Cada personagem falante tem exatamente um voice_id.",
            "Existe uma voz de narrador e apenas uma.",
            "Nomes do universo têm pronúncia declarada.",
        ),
        failure_criteria=("Nenhum personagem falante foi identificado.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        voices = self.build_voices(canon, context.configuration.audio.spoken_language)
        self._log(context).info("Bíblia de Vozes construída", voices=len(voices))
        return self._ok(voices=voices)

    def build_voices(self, canon: CanonBible, language: Language) -> tuple[VoiceProfile, ...]:
        """Constrói a `voice_bible`, incluindo a voz de narração."""
        pronunciation = self._pronunciation_dictionary(canon)
        voices: list[VoiceProfile] = [
            VoiceProfile(
                identity=VoiceIdentity(
                    voice_id=f"voice_narrador_{_language_token(language)}_v1",
                    language=language,
                    apparent_age_range="40-55",
                    pitch="médio-grave",
                    texture="seca, sem ênfase dramática",
                    accent_region="neutro brasileiro",
                    pace="medido, com pausas longas",
                    articulation="precisa",
                    breathing="inaudível",
                ),
                display_name="Narrador",
                is_narrator=True,
                emotional_range=(EmotionalTone.NEUTRAL, EmotionalTone.CALM),
                intensity_default="baixa",
                pauses="pausa longa entre parágrafos, curta entre orações",
                pronunciation_dictionary=pronunciation,
                reference_notes=(
                    "A narração descreve; não interpreta. Nenhuma coloração de trailer."
                ),
            )
        ]

        for index, character in enumerate(canon.characters):
            if character.dialogue_line_count == 0 and not character.is_lead:
                continue
            voices.append(self._voice_for(character, language, index, pronunciation))

        return tuple(voices)

    def _voice_for(
        self,
        character: Character,
        language: Language,
        index: int,
        pronunciation: dict[str, str],
    ) -> VoiceProfile:
        age = character.appearance.apparent_age
        pitch, texture = self._timbre_for(character, index)
        return VoiceProfile(
            identity=VoiceIdentity(
                voice_id=(
                    f"voice_{safe_slug(character.canonical_name, max_length=40).replace('-', '_')}"
                    f"_{_language_token(language)}_v1"
                ),
                language=language,
                apparent_age_range=_age_range(age),
                pitch=pitch,
                texture=texture,
                accent_region="neutro brasileiro",
                pace="medido" if character.is_lead else "natural",
                articulation="precisa",
                breathing="contida",
            ),
            character_id=character.character_id,
            display_name=character.canonical_name,
            is_narrator=False,
            emotional_range=(
                EmotionalTone.NEUTRAL,
                EmotionalTone.TENSE,
                EmotionalTone.SUSPICIOUS,
                EmotionalTone.TENDER,
            ),
            intensity_default="média",
            pauses="pausa curta antes de responder; hesitação audível quando mente",
            pronunciation_dictionary=pronunciation,
            reference_notes=(
                f"Voz derivada do temperamento registrado: "
                f"{', '.join(character.temperament)}."
            ),
        )

    @staticmethod
    def _timbre_for(character: Character, index: int) -> tuple[str, str]:
        """Distribui timbres distintos para que duas vozes não se confundam."""
        options = (
            ("médio-grave", "seca e controlada"),
            ("médio-agudo", "clara, com ataque rápido"),
            ("grave", "encorpada, ressonante no peito"),
            ("médio", "levemente rouca, com ar"),
        )
        return options[index % len(options)]

    @staticmethod
    def _pronunciation_dictionary(canon: CanonBible) -> dict[str, str]:
        """Nomes próprios do universo que um sintetizador erraria."""
        entries: dict[str, str] = {}
        for character in canon.characters:
            for part in character.canonical_name.split():
                if len(part) > 3 and strip_accents(part) != part:
                    entries[part] = f"{part} (manter acentuação original)"
        for location in canon.locations:
            name = location.canonical_name
            if name and name[0].isupper() and len(name) > 4:
                entries[name] = f"{name} (topônimo do universo, não traduzir)"
        return entries


class MusicSupervisorAgent(BaseAgent):
    """`MUSIC_SUPERVISOR_AGENT` — cria a identidade musical original da obra."""

    _contract = AgentContract(
        name="MUSIC_SUPERVISOR_AGENT",
        responsibility=(
            "Definir temas, motivos, instrumentação, progressão, andamento, "
            "intensidade, entradas, saídas e a relação entre música e diálogo."
        ),
        phase="BUILDING_BIBLES",
        input_type="CanonBible",
        output_type="tuple[MusicTheme, ...]",
        authorized_tools=(AgentTool.DOMAIN_SERVICES,),
        memory=MemoryScope.CANON,
        prompt_name="audio.music",
        completion_criteria=(
            "Nenhum tema referencia obra ou artista existente.",
            "Cada tema tem função dramática declarada.",
            "A música recua sob o diálogo.",
        ),
        failure_criteria=("Um tema pediu imitação de obra protegida.",),
    )

    def run(self, context: EngineContext) -> AgentResult:
        canon = context.require_canon()
        analysis = context.analysis
        themes = self.build_themes(canon, analysis.themes if analysis else ())
        self._log(context).info("Identidade musical construída", themes=len(themes))
        return self._ok(music_themes=themes)

    def build_themes(
        self, canon: CanonBible, themes: tuple[str, ...]
    ) -> tuple[MusicTheme, ...]:
        instrumentation = self._instrumentation_for(themes)
        results: list[MusicTheme] = [
            MusicTheme(
                theme_id="theme_main",
                name=f"Tema de «{canon.title}»",
                role=MusicRole.MAIN_THEME,
                instrumentation=instrumentation,
                tempo_bpm_range="58-72",
                key_character="modo menor, cadência suspensa, sem resolução tonal",
                motif_description=(
                    "Uma célula de quatro notas descendentes que nunca completa a "
                    "frase. Repete em intervalos irregulares, sempre um pouco mais "
                    "grave, como algo que se aproxima sem chegar."
                ),
                intensity_curve=(
                    "Entra em nível baixo sob a imagem, cresce até a metade do bloco, "
                    "recua 6 dB no primeiro diálogo e só retorna no quadro final."
                ),
                associated_tone=EmotionalTone.OMINOUS,
            ),
            MusicTheme(
                theme_id="theme_tension",
                name="Tensão",
                role=MusicRole.TENSION,
                instrumentation=("cordas graves em tremolo", "percussão de metal fino"),
                tempo_bpm_range="76-96",
                key_character="cluster estreito, sem centro tonal definido",
                motif_description=(
                    "Sustentação de cordas em intervalo de segunda menor, com atrito "
                    "constante. Nenhum ataque percussivo até o ponto de virada."
                ),
                intensity_curve="Crescimento linear e lento; corte abrupto no clímax.",
                associated_tone=EmotionalTone.TENSE,
            ),
            MusicTheme(
                theme_id="theme_closing",
                name="Encerramento",
                role=MusicRole.CLOSING,
                instrumentation=("piano preparado", "cordas em harmônicos"),
                tempo_bpm_range="52-64",
                key_character="modo maior instável, resolvido apenas na última nota",
                motif_description=(
                    "Inversão do tema principal: as mesmas quatro notas, agora "
                    "ascendentes, tocadas uma única vez e deixadas ressoar até o "
                    "silêncio."
                ),
                intensity_curve="Entra no último quarto e desaparece por decaimento natural.",
                associated_tone=EmotionalTone.MELANCHOLIC,
            ),
        ]

        for character in canon.characters[:2]:
            results.append(
                MusicTheme(
                    theme_id=f"theme_{safe_slug(character.canonical_name, max_length=60)}",
                    name=f"Tema de {character.canonical_name}",
                    role=MusicRole.CHARACTER_THEME,
                    instrumentation=instrumentation[:2],
                    tempo_bpm_range="60-80",
                    key_character="linha melódica única, sem acompanhamento harmônico",
                    motif_description=(
                        f"Melodia solitária associada a {character.canonical_name}: "
                        "um só instrumento, sem base, para que a presença dele soe "
                        "sempre um pouco isolada do resto da trilha."
                    ),
                    intensity_curve="Baixa e constante; nunca compete com a fala.",
                    associated_character_id=character.character_id,
                )
            )

        return tuple(results)

    @staticmethod
    def _instrumentation_for(themes: tuple[str, ...]) -> tuple[str, ...]:
        base = ["violoncelo solo", "piano com abafador", "sinos de vidro"]
        if "tempo" in themes:
            base.append("mecanismo de relojoaria amplificado")
        if "perda" in themes or "memória" in themes:
            base.append("harmônio respirando")
        if "medo" in themes:
            base.append("cordas em sul ponticello")
        return tuple(base)


def _language_token(language: Language) -> str:
    return str(language).lower().replace("-", "")


def _age_range(declared: str) -> str:
    """Converte a idade declarada em faixa vocal utilizável."""
    import re

    match = re.search(r"(\d+)", declared)
    if match:
        age = int(match.group(1))
        return f"{max(12, age - 5)}-{age + 5}"

    words = {
        "sessenta e dois": 62,
        "trinta e quatro": 34,
        "quarenta": 40,
        "cinquenta": 50,
        "vinte": 20,
        "trinta": 30,
        "sessenta": 60,
        "setenta": 70,
    }
    lowered = declared.lower()
    for word, value in words.items():
        if word in lowered:
            return f"{max(12, value - 5)}-{value + 5}"
    return "30-50"
