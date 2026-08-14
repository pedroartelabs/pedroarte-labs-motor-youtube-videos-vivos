"""Definições dos prompts do catálogo de agentes.

Os prompts descrevem *a instrução* de cada agente. No caminho padrão, o
`DeterministicLLMProvider` executa a instrução por código; com um LLM plugado,
a mesma instrução é enviada ao modelo. Ter os dois caminhos partindo do mesmo
texto é o que mantém o comportamento comparável.
"""

from __future__ import annotations

from datetime import date

from pedroarte_youtube_engine.domain.value_objects import PromptVersion
from pedroarte_youtube_engine.prompts.registry import PromptDefinition

_V1 = PromptVersion(major=1, minor=0, patch=0)
_CHANGED = date(2026, 8, 6)

_COMMON_RULES = """
REGRAS INEGOCIÁVEIS DO MOTOR:
1. Nunca invente fatos que a obra não sustenta. Se algo não está no texto,
   declare a lacuna em vez de preenchê-la.
2. Todo prompt de vídeo tem seção visual E seção sonora. Um prompt mudo é
   inválido, mesmo quando ninguém fala.
3. Toda afirmação canônica aponta para o trecho da obra que a sustenta.
4. Nenhum personagem muda de rosto, corpo, voz, idade ou etnia aparente entre
   segmentos sem justificativa narrativa explícita.
5. Nunca use nome de ator, celebridade ou artista vivo como atalho visual ou
   sonoro. Descreva; não referencie pessoas reais.
6. Nunca peça cópia ou imitação de obra musical protegida.
7. Placeholders são proibidos. O prompt precisa bastar-se sozinho.
""".strip()


def _prompt(
    *,
    name: str,
    agent: str,
    objective: str,
    template: str,
    input_schema: dict[str, str],
    output_schema: dict[str, str],
    criteria: tuple[str, ...],
    temperature: float = 0.2,
    notes: str = "",
) -> PromptDefinition:
    return PromptDefinition(
        name=name,
        version=_V1,
        agent=agent,
        objective=objective,
        input_schema=input_schema,
        output_schema=output_schema,
        template=f"{_COMMON_RULES}\n\n{template.strip()}",
        changed_at=_CHANGED,
        recommended_model="deterministic-local",
        recommended_temperature=temperature,
        evaluation_criteria=criteria,
        notes=notes,
    )


ALL_PROMPTS: tuple[PromptDefinition, ...] = (
    _prompt(
        name="director.plan_run",
        agent="DIRECTOR_OF_LIVING_VIDEO",
        objective=(
            "Selecionar o fluxo de execução, ordenar os agentes e definir os gates "
            "que bloqueiam a publicação de artefatos inválidos."
        ),
        input_schema={"configuration": "ProjectConfiguration", "input_files": "list[str]"},
        output_schema={"stages": "list[str]", "gates": "list[str]"},
        template="""
Você coordena a adaptação audiovisual de uma obra literária.

ENTRADA
- Formatos habilitados: {formats}
- Duração de segmento: {segment_seconds}s
- Documentos encontrados: {document_count}

TAREFA
Determine a sequência de etapas e os portões de qualidade. Impeça que qualquer
artefato reprovado chegue ao export. Emita o relatório final com evidências.
""",
        criteria=(
            "A sequência cobre da descoberta de entrada até a exportação.",
            "Nenhum gate obrigatório é omitido.",
            "Artefatos reprovados nunca são exportados como aprovados.",
        ),
    ),
    _prompt(
        name="discovery.classify_inputs",
        agent="INPUT_DISCOVERY_AGENT",
        objective=(
            "Classificar cada documento de `input/`, eleger o arquivo principal e "
            "registrar proveniência e ambiguidades."
        ),
        input_schema={"files": "list[FileDescriptor]"},
        output_schema={"documents": "list[SourceDocument]", "primary": "SourceId"},
        template="""
Analise os arquivos encontrados e classifique cada um.

ARQUIVOS
{file_list}

TAREFA
1. Determine a natureza de cada documento (livro, roteiro, bíblia de universo,
   notas, fichas de personagem, configuração).
2. Eleja o documento principal — o de maior volume narrativo.
3. Registre o hash de cada arquivo.
4. Sinalize ambiguidades em vez de resolvê-las silenciosamente.
""",
        criteria=(
            "Exatamente um documento principal é eleito.",
            "Todo documento tem hash e motivo de classificação.",
            "Ambiguidades aparecem no relatório.",
        ),
    ),
    _prompt(
        name="ingestion.normalize",
        agent="BOOK_INGESTION_AGENT",
        objective=(
            "Extrair texto preservando capítulos, títulos e ordem, e produzir o "
            "documento canônico com mapa de fontes."
        ),
        input_schema={"documents": "list[SourceDocument]"},
        output_schema={"book": "BookSource"},
        template="""
Normalize o material bruto em um documento canônico único.

DOCUMENTOS: {document_count}
DOCUMENTO PRINCIPAL: {primary_path}

TAREFA
Preserve a ordem e os títulos dos capítulos. Normalize a codificação e o espaço
em branco sem alterar o conteúdo. Produza o mapa de fontes com deslocamentos.
""",
        criteria=(
            "A ordem dos capítulos é preservada.",
            "Nenhum trecho do texto original é perdido.",
            "Cada capítulo tem deslocamento inicial e final.",
        ),
    ),
    _prompt(
        name="canon.extract",
        agent="CANON_EXTRACTOR_AGENT",
        objective=(
            "Extrair fatos, personagens, locais, objetos, relações, regras, "
            "cronologia, mistérios e contradições, com confiança e proveniência."
        ),
        input_schema={"book": "BookSource"},
        output_schema={"canon": "CanonBible"},
        template="""
Extraia o cânone da obra "{title}".

CAPÍTULOS: {chapter_count}
PALAVRAS: {word_count}

TAREFA
Para cada fato extraído registre: a afirmação, o tipo, os sujeitos envolvidos, o
nível de confiança e a referência ao trecho de origem. Contradições aparentes
não são resolvidas por invenção: elas viram questões em aberto.
""",
        criteria=(
            "Todo fato tem referência ao texto de origem.",
            "Fatos incertos são marcados com confiança baixa.",
            "Contradições aparecem em unresolved_questions.",
        ),
    ),
    _prompt(
        name="canon.world_bible",
        agent="WORLD_BIBLE_AGENT",
        objective="Construir a Bíblia de Mundo com regras, limites e contexto do universo.",
        input_schema={"canon": "CanonBible"},
        output_schema={"world_rules": "list[str]", "prohibitions": "list[str]"},
        template="""
Construa a Bíblia de Mundo de "{title}".

TAREFA
Registre geografia, sociedade, tecnologia, política, economia, cultura, regras
físicas, regras sobrenaturais e limites narrativos. Distinga o que a obra afirma
do que ela apenas sugere.
""",
        criteria=(
            "Regras do mundo são distinguidas de hábitos de personagem.",
            "Proibições do universo são explícitas.",
        ),
    ),
    _prompt(
        name="canon.character_bible",
        agent="CHARACTER_BIBLE_AGENT",
        objective=(
            "Produzir a ficha de cada personagem com âncoras de consistência "
            "visual, comportamental e de figurino."
        ),
        input_schema={"canon": "CanonBible", "retrieval": "RetrievalResult"},
        output_schema={"characters": "list[Character]"},
        template="""
Crie a ficha completa de cada personagem de "{title}".

PERSONAGENS DETECTADOS: {character_names}

TAREFA
Para cada um: aparência, idade aparente, voz, temperamento, gestos, postura,
roupas, objetos, relações, evolução e restrições. Use referências visuais
abstratas — jamais nomes de atores ou celebridades.

Quando a obra não descrever um traço, deixe-o explicitamente em aberto para
decisão autoral, em vez de inventá-lo.
""",
        criteria=(
            "Nenhuma ficha usa nome de pessoa real como referência.",
            "Traços não descritos pela obra são marcados como lacuna.",
            "Cada ficha produz uma âncora reinjetável em prompt.",
        ),
    ),
    _prompt(
        name="audiovisual.bible",
        agent="AUDIOVISUAL_BIBLE_AGENT",
        objective="Converter o cânone em decisões de fotografia, som, voz e música.",
        input_schema={"canon": "CanonBible"},
        output_schema={"bible": "AudiovisualBible"},
        template="""
Traduza o cânone de "{title}" em linguagem audiovisual.

TEMAS DOMINANTES: {themes}
TOM PREDOMINANTE: {dominant_tone}

TAREFA
Defina estilo cinematográfico próprio, fotografia, enquadramentos, iluminação,
linguagem de câmera, identidade sonora, vozes, música, ambientes, motivos
recorrentes, transições, intensidade e restrições.

O estilo precisa ser original e derivado da obra — não de um filme existente.
""",
        criteria=(
            "O estilo deriva dos temas da obra, não de referências externas.",
            "Toda decisão visual tem contrapartida sonora.",
        ),
        temperature=0.4,
    ),
    _prompt(
        name="audiovisual.voice_casting",
        agent="VOICE_CASTING_AGENT",
        objective="Definir uma identidade vocal reutilizável por personagem.",
        input_schema={"characters": "list[Character]"},
        output_schema={"voices": "list[VoiceProfile]"},
        template="""
Defina a Bíblia de Vozes de "{title}".

PERSONAGENS: {character_names}

TAREFA
Para cada voz: identificador estável, idade vocal, timbre, textura, sotaque,
velocidade, pausas, intensidade, faixa emocional e dicionário de pronúncia dos
nomes do universo. A mesma pessoa mantém o mesmo `voice_id` em todos os
episódios e formatos.
""",
        criteria=(
            "Cada personagem falante tem exatamente um voice_id.",
            "Nomes próprios do universo têm pronúncia declarada.",
            "Nenhuma voz imita pessoa real identificável.",
        ),
    ),
    _prompt(
        name="adaptation.strategy",
        agent="ADAPTATION_ARCHITECT_AGENT",
        objective=(
            "Decidir o que preservar, condensar e reorganizar, sem perder a tese "
            "central da obra."
        ),
        input_schema={"canon": "CanonBible", "formats": "list[ProductionVariant]"},
        output_schema={"decisions": "list[AdaptationDecision]"},
        template="""
Defina a estratégia de adaptação de "{title}" para os formatos {formats}.

TESE CENTRAL: {thesis}

TAREFA
Cada formato exige uma estratégia própria. O vídeo longo não pode ser o vídeo de
dez minutos esticado; o trailer não pode ser um recorte mecânico do vídeo
principal. Documente toda mudança relevante e por que ela preserva o espírito
da obra.
""",
        criteria=(
            "Cada formato tem estratégia distinta e justificada.",
            "A tese central sobrevive em todos os formatos.",
            "Mudanças relevantes ficam registradas.",
        ),
        temperature=0.3,
    ),
    _prompt(
        name="planning.formats",
        agent="FORMAT_PLANNER_AGENT",
        objective="Calcular durações, quantidade de segmentos, proporção e idioma por formato.",
        input_schema={"configuration": "ProjectConfiguration"},
        output_schema={"profiles": "list[FormatProfile]"},
        template="""
Planeje os formatos habilitados.

CONFIGURAÇÃO
- Segmento: {segment_seconds}s
- Formatos: {formats}

TAREFA
Calcule a duração total e a quantidade exata de segmentos de cada formato. A
duração precisa fechar em segmentos inteiros — sem arredondamento.
""",
        criteria=(
            "Toda duração é múltipla exata da duração de segmento.",
            "Proporção e resolução são coerentes com o formato.",
        ),
    ),
    _prompt(
        name="planning.season",
        agent="SEASON_ARCHITECT_AGENT",
        objective="Distribuir a obra em episódios com arcos, ganchos e progressão.",
        input_schema={"canon": "CanonBible", "profile": "FormatProfile"},
        output_schema={"season": "SeasonPlan"},
        template="""
Construa a temporada de "{title}".

BEATS DISPONÍVEIS: {beat_count}
EPISÓDIOS: entre {min_episodes} e {max_episodes}

TAREFA
Distribua os capítulos entre episódios, crie arcos e ganchos, e evite episódios
redundantes. Cada episódio precisa avançar a temporada.
""",
        criteria=(
            "Nenhum episódio repete o conteúdo de outro.",
            "Cada episódio termina com gancho ou cliffhanger.",
        ),
        temperature=0.3,
    ),
    _prompt(
        name="planning.episode",
        agent="EPISODE_ARCHITECT_AGENT",
        objective="Estruturar começo, meio e fim de cada episódio, controlando duração.",
        input_schema={"beats": "list[NarrativeBeat]", "profile": "FormatProfile"},
        output_schema={"episode": "Episode"},
        template="""
Estruture o episódio {episode_number} de "{title}".

DURAÇÃO: {duration_minutes} minutos ({segment_count} segmentos)
BEATS ATRIBUÍDOS: {beat_count}

TAREFA
Organize os beats em sequências com função dramática. Toda cena precisa ter uma
razão de existir. Controle a duração para fechar exatamente no alvo.
""",
        criteria=(
            "As sequências são contíguas e somam a duração exata.",
            "Cada cena tem função dramática declarada.",
        ),
    ),
    _prompt(
        name="decomposition.scenes",
        agent="SCENE_DECOMPOSER_AGENT",
        objective="Decompor episódios em sequências, cenas e segmentos temporizados.",
        input_schema={"episode": "Episode"},
        output_schema={"segments": "list[PromptSegment]"},
        template="""
Decomponha o episódio em segmentos de {segment_seconds}s.

TAREFA
Mantenha os timecodes contíguos e crescentes. Evite cortes incoerentes. Nenhuma
ação pode ser maior do que cabe na duração do segmento.
""",
        criteria=(
            "Timecodes crescentes e sem lacunas.",
            "Ações fisicamente possíveis no tempo disponível.",
        ),
    ),
    _prompt(
        name="writing.screenplay",
        agent="SCREENWRITER_AGENT",
        objective="Adaptar prosa em ação audiovisual, diálogo e narração dimensionados.",
        input_schema={"beat": "NarrativeBeat", "duration": "Duration"},
        output_schema={"action": "str", "dialogue": "list[DialogueLine]"},
        template="""
Adapte este beat para {duration_seconds} segundos de tela.

BEAT: {beat_summary}
PERSONAGENS: {participants}

TAREFA
Escreva a ação visível, não o pensamento. Elimine exposição desnecessária.
Preserve o subtexto. O texto falado precisa caber no tempo: no máximo
{max_words} palavras.
""",
        criteria=(
            "O texto falado cabe na duração a 150 palavras por minuto.",
            "A ação é visível, não interior.",
            "O subtexto da obra é preservado.",
        ),
        temperature=0.5,
    ),
    _prompt(
        name="writing.retention",
        agent="RETENTION_AND_HOOK_AGENT",
        objective="Avaliar promessa inicial e progressão, sem manipulação enganosa.",
        input_schema={"segments": "list[PromptSegment]"},
        output_schema={"assessment": "RetentionAssessment"},
        template="""
Avalie a retenção de {variant}.

PRIMEIROS SEGMENTOS: {opening_summary}

TAREFA
Verifique se os primeiros segundos criam uma promessa narrativa verdadeira.
Identifique quedas de ritmo. Melhore a retenção sem prometer o que a obra não
entrega — clickbait desconectado da obra é reprovado.
""",
        criteria=(
            "A promessa inicial corresponde ao conteúdo real.",
            "Quedas de ritmo são localizadas por segmento.",
        ),
    ),
    _prompt(
        name="visual.cinematography",
        agent="CINEMATOGRAPHY_AGENT",
        objective="Definir plano, lente, câmera, movimento, luz e quadros de cada segmento.",
        input_schema={"scene": "Scene", "bible": "AudiovisualBible"},
        output_schema={"video": "VideoPlan"},
        template="""
Fotografe o segmento.

FUNÇÃO NARRATIVA: {narrative_function}
TENSÃO: {tension}/10
DOUTRINA DE CÂMERA: {camera_doctrine}

TAREFA
Escolha plano, ângulo, lente, altura, distância, movimento, foco e profundidade
coerentes com a função dramática. Descreva o quadro inicial e o quadro final —
eles precisam ser diferentes: todo segmento registra uma mudança.
""",
        criteria=(
            "Quadro inicial e final descrevem estados distintos.",
            "O movimento de câmera é fisicamente possível.",
            "A escolha de plano serve à função dramática.",
        ),
        temperature=0.4,
    ),
    _prompt(
        name="audio.sound_design",
        agent="SOUND_DESIGN_AGENT",
        objective="Projetar ambiente, efeitos, espacialidade e silêncio de cada segmento.",
        input_schema={"video": "VideoPlan", "bible": "AudiovisualBible"},
        output_schema={"ambient": "list[AmbientSound]", "effects": "list[SoundEffect]"},
        template="""
Projete o som do segmento.

AMBIENTE: {location}
AÇÃO: {action}

TAREFA
Nenhum lugar do mundo é mudo. Descreva o ambiente contínuo, os efeitos ancorados
em ações visíveis, os sons fora de quadro e — quando houver — o silêncio
intencional com sua função dramática.
""",
        criteria=(
            "Existe pelo menos um som ambiente contínuo.",
            "Cada efeito aponta para a ação que o produz.",
            "Silêncio, quando usado, é justificado.",
        ),
    ),
    _prompt(
        name="audio.music",
        agent="MUSIC_SUPERVISOR_AGENT",
        objective="Definir temas, motivos, instrumentação e curva de intensidade.",
        input_schema={"canon": "CanonBible"},
        output_schema={"themes": "list[MusicTheme]"},
        template="""
Componha a identidade musical de "{title}".

TEMAS DA OBRA: {themes}

TAREFA
Crie temas originais com instrumentação, andamento, progressão e relação com o
diálogo. Descreva o efeito pretendido — nunca peça cópia ou imitação de obra
protegida ou de artista específico.
""",
        criteria=(
            "Nenhum tema referencia obra ou artista existente.",
            "Cada tema tem função dramática declarada.",
            "A música recua sob o diálogo.",
        ),
        temperature=0.5,
    ),
    _prompt(
        name="compilation.provider",
        agent="MULTIMODAL_PROMPT_COMPILER_AGENT",
        objective="Traduzir o segmento canônico em prompt de provedor sem perder intenção.",
        input_schema={"segment": "PromptSegment", "capability": "ProviderCapability"},
        output_schema={"prompts": "list[ProviderPrompt]"},
        template="""
Compile o segmento para {provider}/{model}.

DURAÇÃO NARRATIVA: {target_seconds}s
DURAÇÃO ACEITA PELO PROVEDOR: {provider_seconds}s
ESTRATÉGIA: {strategy}

TAREFA
Preserve a intenção e o timecode narrativo original. Adapte a sintaxe ao
provedor. Inclua vídeo E áudio. Gere as restrições negativas. Registre a decisão
de recompilação no manifesto.
""",
        criteria=(
            "O timecode narrativo é preservado mesmo quando há subdivisão.",
            "O prompt contém seção visual e seção sonora.",
            "As restrições negativas estão presentes.",
        ),
    ),
    _prompt(
        name="validation.canon_guardian",
        agent="CANON_GUARDIAN_AGENT",
        objective="Detectar invenção indevida, contradição e violação de regra do mundo.",
        input_schema={"segments": "list[PromptSegment]", "canon": "CanonBible"},
        output_schema={"report": "ValidationReport"},
        template="""
Compare os prompts com a obra.

SEGMENTOS: {segment_count}
PERSONAGENS CANÔNICOS: {character_names}

TAREFA
Detecte personagens inventados, contradições de cronologia, violações das regras
do universo e objetos sem lastro. Bloqueie violações graves.
""",
        criteria=(
            "Todo personagem em cena existe no cânone.",
            "Nenhuma proibição do universo é violada.",
        ),
    ),
    _prompt(
        name="validation.audiovisual_quality",
        agent="AUDIOVISUAL_QUALITY_GUARDIAN_AGENT",
        objective="Verificar completude visual e sonora, duração e ausência de placeholder.",
        input_schema={"segments": "list[PromptSegment]"},
        output_schema={"report": "ValidationReport"},
        template="""
Audite a completude dos prompts.

SEGMENTOS: {segment_count}

TAREFA
Reprove: prompt sem áudio; prompt sem decisão vocal; personagem sem identidade;
fala longa demais; câmera impossível; ação maior que a duração; mudança de
ambiente sem transição; objeto que desaparece; placeholder; prompt abstrato
demais; duração total incorreta.
""",
        criteria=(
            "Nenhum segmento aprovado carece de áudio.",
            "Nenhum segmento aprovado contém placeholder.",
            "A duração total fecha exatamente no alvo.",
        ),
    ),
    _prompt(
        name="packaging.youtube",
        agent="YOUTUBE_PACKAGING_AGENT",
        objective="Gerar títulos, descrições, capítulos, tags e prompts de thumbnail.",
        input_schema={"package": "PromptPackage"},
        output_schema={"metadata": "PublicationMetadata"},
        template="""
Empacote {variant} de "{title}" para publicação.

DURAÇÃO: {duration}
SEGMENTOS: {segment_count}

TAREFA
Produza título (até 100 caracteres), descrição, capítulos com timestamps,
palavras-chave, hashtags, prompt de thumbnail, comentário fixado e ordem de
publicação. O título precisa corresponder ao conteúdo real.
""",
        criteria=(
            "O título tem no máximo 100 caracteres.",
            "Os capítulos apontam para timecodes existentes.",
            "Nenhuma promessa no título excede o conteúdo.",
        ),
        temperature=0.4,
    ),
    _prompt(
        name="validation.final_qa",
        agent="FINAL_QA_AGENT",
        objective="Consolidar gates, emitir score e aprovar ou reprovar o pacote.",
        input_schema={"reports": "list[ValidationReport]"},
        output_schema={"assessment": "QualityAssessment"},
        template="""
Consolide os portões de qualidade.

GATES AVALIADOS: {gate_count}
SCORE MÍNIMO EXIGIDO: {minimum_score}

TAREFA
Bloqueie artefatos incompletos. Emita score, lista de erros e lista de
advertências. Aprove somente o que passou em todos os gates bloqueantes.
""",
        criteria=(
            "Um problema crítico sempre reprova o pacote.",
            "O score reflete a proporção real de verificações aprovadas.",
        ),
    ),
)
