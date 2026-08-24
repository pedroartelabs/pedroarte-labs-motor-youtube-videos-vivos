# YOUTUBE EXPERIENCE CONTRACT — SDD DESIGN REPORT

Status: **DESIGN ONLY**. Nenhum código de produção foi escrito, nenhum vídeo foi renderizado, nenhum asset foi gerado/regenerado, o Gate 3D.2 em andamento não foi tocado. Este relatório acompanha a atualização em [SDD_SPDD.md](SDD_SPDD.md) Part X (§88-119).

## 1. Executive Summary

Os Gates 3D.1 e 3D.2 produziram, sem planejar assim, duas descobertas empíricas que são na verdade lições de produto: (1) movimento tecnicamente configurado e mensurável (YAVG≈11, 100% de cobertura) não é o mesmo que movimento percebido como profundidade progressiva; (2) música tecnicamente presente na mixagem (diferença de nível médio > 0) não é o mesmo que música audível. Ambas as lições só existiam como correções ad-hoc de um vídeo específico. Esta revisão as formaliza — junto com hook, ritmo narrativo, performance de voz, experiência de legenda, sound design, pattern interrupts, branding e payoff — num `YouTubeExperienceContract` que resolve o "Watch Problem" (por que continuar assistindo?), complementar ao Click Package (Part IX, que resolve "por que clicar?"). Nada foi implementado; é especificação, com uma tabela explícita separando princípios permanentes de heurísticas experimentais revisáveis.

## 2. Current Experience Model

Antes desta revisão, o que existia era código funcional sem contrato de produto explícito: `retention.py` já implementa Retention Beats, push-in contínuo, e checagem de reset de escala (Gate 3D.2); `captions.py` já implementa estilo de legenda de formato longo; `audio_mix.py` já implementa música subordinada com QA stem-relativa; `experience_qa.py` já distingue Media QA de Experience QA. Ou seja: **a implementação já incorporou as lições corretas**, mas nenhum documento de produto declarava essas decisões como princípios generalizáveis — elas viviam só como comentários de código e relatórios de gate específicos (`GATE_3D2_CALIBRATION_REPORT.md`). Não havia, além disso, nenhuma especificação para hook, ritmo narrativo, performance de voz, pattern interrupts, branding ou payoff — esses conceitos simplesmente não existiam no vocabulário do produto.

## 3. Identified Product Gap

```text
JÁ IMPLEMENTADO (mas não formalizado como contrato):
  Retention Beat, push-in contínuo, motion QA em duas camadas,
  legenda de formato longo, música stem-relativa

NUNCA FORMALIZADO (nem em código nem em contrato):
  hook, primeiros 30s, ritmo narrativo/micro-hooks, performance de voz,
  sound design, pattern interrupts, branding/intro, payoff/ending
```

Sem esse vocabulário formal, cada nova produção corre o risco de redescobrir as mesmas lições (movimento configurado ≠ percebido; música presente ≠ audível) por tentativa e erro, em vez de partir de um contrato já informado pela evidência anterior.

## 4. Click vs. Watch Separation

Ver `SDD_SPDD.md` §89. Os dois problemas — clique (Click Package, Part IX) e permanência (Experience Contract, esta Parte) — são mantidos como contratos separados e complementares, nunca fundidos numa abstração única. O elo entre eles é a promessa: o Click Package cria uma promessa; o Hook Contract (esta Parte) exige que o vídeo a confirme imediatamente.

## 5. YouTubeExperienceContract

Ver `SDD_SPDD.md` §88/§115. Nomeado deliberadamente para não prometer viralidade — otimiza para atenção, retenção, compreensão, imersão, satisfação e prontidão de publicação; comportamento real de audiência é a validação definitiva (§26 abaixo).

## 6. Experience Timeline

Ver `SDD_SPDD.md` §91. **Decisão**: visão conceitual composta a partir das estruturas de timeline já existentes (Visual Beats, Retention Segments, Cues, plano de música) — não uma nova classe de dados. Uma nova estrutura duplicaria dados que já têm dono (`visual_beats.py`, `retention.py`, `captions.py`, `audio_mix.py`) sem nenhum consumidor real que precise da forma agregada hoje.

## 7. Hook Contract

Ver `SDD_SPDD.md` §92. `HOOK_BEFORE_BRANDING` como padrão; hook cria pergunta/anomalia/conflito/promessa/surpresa/consequência/lacuna de informação; deve honrar a promessa do Click Package (título+thumbnail → hook confirma → vídeo expande → payoff cumpre).

## 8. First-30-Seconds Contract

Ver `SDD_SPDD.md` §93. Região de retenção especial: minimizar exposição/branding/repetição/setup longo/meta-comentário; maximizar confirmação de promessa, movimento narrativo, curiosidade, valor antecipado, clareza visual. Sem cortes arbitrários por tempo — a regra é sobre conteúdo.

## 9. Narrative Rhythm

Ver `SDD_SPDD.md` §94. Modelo `HOOK → PERGUNTA → RESPOSTA PARCIAL → PERGUNTA MAIOR → COMPLICAÇÃO → REVELAÇÃO → CONSEQUÊNCIA → CLÍMAX → PAYOFF`, não um template rígido. Ritmo pergunta/resposta parcial evita tanto resolver tudo cedo demais quanto reter tudo até o fim.

## 10. Micro-Hooks

Ver `SDD_SPDD.md` §94. `MicroHook`: dispositivo de atenção recorrente ao longo do roteiro, sem frases hardcoded e sem exigir cliffhanger artificial a cada poucas frases — o princípio é renovação de curiosidade, não uma cadência fixa.

## 11. Visual Dynamics

Ver `SDD_SPDD.md` §95. Alvo: contação de história visual contínua, não slideshow narrado. Imagens estáticas permitidas; apresentação perceptualmente estática por intervalos longos desencorajada.

## 12. Visual Beat vs. Retention Beat

Ver `SDD_SPDD.md` §96. Distinção formalizada (já implementada em código desde o Gate 3D.1/3D.2, agora elevada a contrato de produto): Visual Beat é o intervalo narrativo/semântico; Retention Beat é a mudança perceptível dentro dele. Um Visual Beat pode conter múltiplos Retention Beats.

## 13. 7-Second Heuristic

Ver `SDD_SPDD.md` §97. Explicitamente rotulada como heurística experimental, não lei do YouTube nem garantia de viralidade — `TARGET_MAX_PERCEPTUAL_STATIC_WINDOW ≈ 7s`, tolerância ~10s, exceção documentada para holds contemplativos intencionais. `VISUAL_EVENT != NEW_IMAGE` — zoom, pan, reframe, corte, transição, elemento gráfico, ênfase textual ou animação também contam; mudança pura de texto de legenda não conta sozinha.

## 14. Motion Contract

Ver `SDD_SPDD.md` §98. A lição central desta revisão: `MOTION_CONFIGURED = TRUE` não é evidência de `MOTION_PERCEIVED = TRUE` — evidência empírica direta do próprio projeto (Gate 3D.1: 100% de cobertura configurada + YAVG≈11 real, e ainda assim feedback humano de movimento insuficiente; causa raiz: reset de escala entre Retention Segments, corrigida no Gate 3D.2). Distinção Motion Configuration QA vs. Motion Render QA mantida e agora formalizada como exigência de contrato, não só prática de um gate específico.

## 15. Progressive Depth

Ver `SDD_SPDD.md` §99. `CONTINUOUS_PUSH_IN` como opção de movimento padrão para narrativa atmosférica; estado de câmera cumulativo entre subsegmentos de retenção (já implementado, `build_continuous_push_in_plan`/`segments_share_continuous_trajectory`); zoom-in para mistério/descoberta/tensão, zoom-out para revelação/escala/isolamento/final — nunca alternância mecânica.

## 16. Image Density

Ver `SDD_SPDD.md` §100. Faixa de referência experimental de ~40-55 imagens/10min, não regra permanente. `MORE_IMAGES != BETTER_VIDEO` — densidade visual significativa preferida sobre contagem bruta.

## 17. Voice Performance

Ver `SDD_SPDD.md` §101. Distinção formal entre texto de narração e plano de performance (`pace`, `pause`, `emphasis`, `emotional_intent`) — contrato mínimo, não uma DSL de direção de voz. Pausas são conteúdo, não removidas automaticamente. Prioridade de áudio: narração > música > SFX.

## 18. Caption Experience

Ver `SDD_SPDD.md` §102. Legendas queimadas em português como padrão obrigatório (já implementado), sidecar `.srt` mantido. Estilo de formato longo (1-2 linhas, contraste forte, chunking confortável), não karaokê de Shorts. Ênfase textual seletiva permitida, não em toda legenda.

## 19. Background Music

Ver `SDD_SPDD.md` §103. A segunda lição central: `MUSIC_IN_MIX = TRUE` não prova `VIEWER_CAN_HEAR_MUSIC = TRUE` — evidência direta do projeto (Gate 3D.1: 0.30dB de diferença na mixagem final considerado suficiente pelo QA automatizado, mas feedback humano "som de fundo ainda está ausente"; corrigido no Gate 3D.2 com QA stem-relativa, comparando o stem de música pós-ganho contra o stem de narração isolado). Música de fundo é padrão obrigatório nesta narrativa; sempre subordinada; direitos de uso sempre conhecidos (licença desconhecida proibida na publicação final).

## 20. Sound Design

Ver `SDD_SPDD.md` §104. Opcional/seletivo no nível de maturidade atual, não implementado — poucos SFX significativos, não SFX constante; silêncio como efeito intencional permitido, não obrigatório.

## 21. Pattern Interrupts

Ver `SDD_SPDD.md` §105. Propósito: renovar atenção, não criar caos — correspondem preferencialmente a informação nova/revelação/mudança emocional/local/objeto importante/escalada. Alvo geral: dinâmico mas confortável, cinematográfico mas não estático — explicitamente não uma imitação de edição estilo TikTok/Shorts.

## 22. Branding / Intro

Ver `SDD_SPDD.md` §106. `LONG_INTRO_BEFORE_HOOK: FORBIDDEN` por padrão; micro-branding opcional e extremamente curto (~0.5-1.5s, experimental) se usado; branding tradicional nunca forçado pelo SDD.

## 23. Ending / Payoff

Ver `SDD_SPDD.md` §107. O final cumpre a promessa (Click Package → Hook → Escalada → Payoff); evita sinalizar o fim cedo demais; evita CTA genérico longo — prefere fechamento curto e ponte contextual opcional.

## 24. Experience QA

Ver `SDD_SPDD.md` §108. Duas categorias formalizadas: Media QA (arquivo tecnicamente correto) vs. Experience QA (a timeline satisfaz estruturalmente a experiência pretendida) — já implementadas como módulos separados desde o Gate 3D.1 (`lite/qa.py` vs. `lite/experience_qa.py`), agora com o vocabulário elevado a contrato de produto. QA automatizado nunca finge medir `ENGAGING`/`VIRAL`/`BEAUTIFUL`/`CINEMATIC`/`EMOTIONAL`.

## 25. Human Full Watch

Ver `SDD_SPDD.md` §109. Continua sendo o gate final autoritativo em E2 — pergunta central inalterada ("Eu publicaria este vídeo no YouTube sem editar o MP4?"). Checklist de 13 itens formalizado para orientar a revisão de experiência, sem substituir o julgamento humano.

## 26. Audience Evidence

Ver `SDD_SPDD.md` §110. Distinção formal entre heurísticas pré-publicação (este contrato) e evidência de audiência pós-publicação (CTR, retenção nos primeiros 30s, duração média, curva de retenção, quedas/picos, rewatches, engajamento, compartilhamentos). Nenhuma integração de analytics implementada agora.

## 27. Future Feedback Loop

Ver `SDD_SPDD.md` §111. `CONTRATO → PUBLICAÇÃO → AUDIÊNCIA REAL → DADOS DE RETENÇÃO → ATUALIZAÇÃO DE HIPÓTESE → PRÓXIMO VÍDEO` documentado como aprendizado E3 futuro, não construído agora.

## 28. Genre/Profile Considerations

Ver `SDD_SPDD.md` §113. Ponto de extensão documentado (`STORYTELLING`/`FINANCE`/`AI_NEWS`/`TIER_LIST`/`BOOK_SUMMARY`), não implementado. O experimento atual pertence a `CINEMATIC_STORYTELLING` — heurísticas descobertas nesse contexto não devem ser presumidas universais para gêneros futuros.

## 29. Engine/Operator Boundary

Ver `SDD_SPDD.md` §117. Mesma regra já estabelecida em Parts III/IX preservada sem alteração — engine define contratos/manifestos, operador materializa assets, nenhuma menção a provider específico na lógica de domínio.

## 30. SPDD Responsibilities

Ver `SDD_SPDD.md` §117. Engine/desenvolvimento: contratos, timeline, instruções de movimento/legenda/música, QA, empacotamento. Operador de execução: materializa assets de imagem/áudio necessários. Humano: calibra limiares subjetivos durante E2 (como já fez no Gate 3D.2 — bake-off de movimento e música), revisa o vídeo completo, aprova prontidão de publicação.

## 31. Permanent Principles

Ver a tabela completa em `SDD_SPDD.md` §114. Resumo: hook antes de branding desnecessário; movimento deve ser perceptível, não apenas configurado; inteligibilidade de narração tem prioridade; legendas devem ser legíveis; licenciamento de música deve ser conhecido; Human Full Watch obrigatório em E2; QA automatizado não prova engajamento; Visual Beat != Retention Beat != nova imagem.

## 32. Experimental Heuristics

Meta de janela estática ~7s (tolerância ~10s); faixa de ~40-55 imagens/10min; taxa de zoom específica (0.004/s); nível de ganho de música específico; duração de micro-branding; tamanho/estilo de legenda; frequência de pattern interrupts. Todos revisáveis por evidência real futura, sem exigir nova revisão de SDD a cada mudança.

## 33. Non-Goals

Predição de viralidade/CTR/retenção por IA, upload automático ao YouTube, ingestão de analytics, infraestrutura de A/B testing, busca de stock-video, geração de vídeo completo, personagens animados, lip sync, motor de composição musical, motor complexo de SFX, suite de motion graphics, substituto do After Effects, motor de edição estilo TikTok, arquitetura em nuvem, enxame de agentes.

## 34. SDD Changes Made

| Arquivo | Mudança |
|---|---|
| [SDD_SPDD.md](SDD_SPDD.md) | Nova Parte X (§88-119): terminologia, separação Click/Watch, princípio central, Experience Timeline (decisão: visão composta, não nova classe), Hook Contract, primeiros 30s, ritmo narrativo/micro-hooks, Visual Dynamics, Visual Beat vs. Retention Beat formalizado, heurística de 7s, Motion Contract (com as duas lições empíricas documentadas), push-in/movimento cumulativo, densidade de imagem, Voice Performance, Caption Experience, Background Music (com a lição stem-relativa documentada), Sound Design, Pattern Interrupts, Branding/Intro, Ending/Payoff, Experience QA, Human Full Watch, evidência de audiência, loop de feedback futuro, gênero/perfil, tabela permanente vs. experimental, sketch de contrato, artefatos/proveniência, fronteira engine/operador, não-objetivos, princípios registrados. Status header atualizado para v0.9. |

Nenhum arquivo de código (`src/pedroarte_youtube_engine/lite/`) foi criado ou modificado nesta tarefa. Nenhum vídeo foi renderizado, nenhum asset foi gerado. O Gate 3D.2 (`runs/2026...-gate3d2/`) não foi tocado.

## 35. Open Questions

- **`ExperienceTimeline` como visão composta** (§6) — a decisão foi tomada por ausência de consumidor real para uma nova estrutura, mas se um relatório de QA cruzado por timestamp aparecer como necessidade real, essa decisão deve ser revisitada.
- **Perfil de gênero (§28)** — ponto de extensão documentado, sem forma de dados definida; fica para quando um segundo gênero real (não hipotético) precisar de ritmo diferente.
- **Frequência de pattern interrupts** — classificada como heurística experimental (§32), mas nenhum valor de referência inicial foi proposto (diferente da janela estática de 7s ou da densidade de imagem) — nenhuma evidência do projeto ainda mede isso diretamente.
- **Artefatos de proveniência de experiência** (`experience_contract.json` etc., §116) — avaliados mas não decididos; ficam pendentes de um consumidor real (provavelmente o próprio Gate 3E ou um gate de experiência futuro).

## 36. Recommendation

Aprovar esta especificação como o contrato de experiência formal do YouTube Lite. A implementação real (schemas de dados leves para as subpolíticas do sketch, possivelmente um pequeno `ExperienceQaPolicy` que consolide os limiares hoje espalhados em constantes de `retention.py`/`audio_mix.py`, e os novos conceitos ainda não implementados — hook/ritmo narrativo/pattern interrupts/branding/payoff, hoje editoriais/roteirísticos e não verificados por código) deve ser proposta como trabalho subsequente, priorizada depois que o Gate 3D.2 receber `HUMAN_PASS` no Human Full Watch — nenhuma etapa mais cara antes de evidência da mais barata (`SDD_SPDD.md` §36, Cost of Failure Principle, já em vigor no projeto).

---

## Contract Sketches (documentação apenas — sem implementação)

```text
YouTubeExperienceContract
  hook_policy: HookPolicy
  narrative_rhythm: NarrativeRhythmPolicy
  visual_dynamics: VisualDynamicsPolicy
  motion_policy: MotionPolicy
  retention_policy: RetentionPolicy
  voice_policy: VoicePerformancePolicy
  caption_policy: CaptionExperiencePolicy
  music_policy: MusicPolicy
  sound_design_policy: SoundDesignPolicy
  branding_policy: BrandingPolicy
  ending_policy: EndingPolicy
  qa_policy: ExperienceQaPolicy

NarrativeRhythm
  hook_summary: str
  micro_hooks: list[str]          # descrições curtas, não frases hardcoded
  question_answer_pattern: str    # descrição textual do padrão pergunta/resposta parcial

VisualDynamicsPolicy
  min_visual_events_per_minute: float | None    # opcional — só se um consumidor real precisar
  static_slideshow_forbidden: bool

MotionPolicy
  target_max_static_window_seconds: float        # heurística experimental (~7s)
  tolerated_max_static_window_seconds: float      # ~10s
  min_zoom_rate_per_second: float                 # calibração experimental, não lei
  cumulative_camera_state_required: bool          # True — não resetar sem motivo
  push_in_default_for_atmospheric: bool

RetentionPolicy
  visual_beat_may_contain_multiple_retention_beats: bool   # True
  visual_event_requires_new_image: bool                     # False

VoicePerformancePolicy
  pace: str | None
  pause: str | None
  emphasis: str | None
  emotional_intent: str | None

CaptionExperiencePolicy
  burned_in_default: bool             # True
  srt_sidecar_retained: bool          # True
  max_lines: int                      # 2
  style: "long_form_storytelling" | "shorts_karaoke"   # default long_form_storytelling

MusicPolicy
  background_music_default: bool          # True
  perceptual_qa_required: bool             # True — stem-relativo, não mix-final-vs-narração
  narration_priority: bool                 # True
  rights_category: "licensed" | "royalty_free" | "cc0" | "original_generated" | "known_safe_local"

SoundDesignPolicy
  sfx_required: bool                  # False
  sfx_supported: bool                 # True
  silence_as_effect_supported: bool   # True

ExperienceQA
  hook_begins_promptly: bool
  max_perceptual_static_window_ok: bool
  motion_coverage_ok: bool
  motion_render_proof_ok: bool
  caption_burn_step_completed: bool
  caption_chunking_valid: bool
  music_stem_present: bool
  music_relative_level_valid: bool
  visual_density_ok: bool
  payoff_exists: bool                          # avaliação editorial, não automatizável hoje
  click_promise_reflected_in_opening: bool      # avaliação editorial, não automatizável hoje
```

## Worked Example — "O Relojoeiro de Vidro" (documentação apenas, vídeo NÃO modificado)

| Elemento do contrato | Aplicação conceitual ao vídeo existente |
|---|---|
| **Hook** | O vídeo já abre com `beat_A` (0.1s-21.9s, função HOOK): close-up do relógio de vidro com a inscrição impossível — já confirma a promessa de "objeto impossível" do Click Package sem branding antes. |
| **Primeiros 30s** | `beat_A` termina em 21.9s, imediatamente seguido de progressão narrativa — nenhuma introdução de canal ocupa essa janela. |
| **Micro-hooks** | Ao longo do roteiro de 30 beats, transições como a passagem de HOOK (beat_A) para ESTABLISHING (beat_B, oficina/Portovelho) e depois para DISCOVERY (beat_C, Mariana sozinha) funcionam como pontos de renovação de curiosidade — cada `narrative_function` já documentada no plano de 30 beats é, em retrospecto, um ponto de micro-hook em potencial. |
| **Visual beats** | Os 30 beats existentes (`GATE3D_FULL_VISUAL_PLAN`) já são exatamente o conceito de Visual Beat formalizado nesta revisão. |
| **Retention beats** | Os planos de `build_continuous_push_in_plan` (Gate 3D.2, variante E aprovada) já subdividem cada beat em Retention Beats com trajetória cumulativa. |
| **Zoom progressivo** | `beat_26` (36.5s, o beat mais longo) usa push-in contínuo com curva suave (`ease_in_out=True`), acumulando +22% de escala ao longo do beat inteiro — exatamente o padrão de "profundidade progressiva" descrito no Motion Contract. |
| **Pattern interrupts** | A alternância entre beats de personagem isolado (ex. beat_C, Mariana), multi-personagem (beat_D, confrontação) e ambiente (beat_B/beat_E, vitrine — payoff visual por callback) já funciona como interrupção de padrão natural, sem ter sido desenhada com esse vocabulário. |
| **Pausas/ênfase de voz** | A narração (Voz C, `pt-BR-AntonioNeural`) não foi produzida com um plano de performance explícito — oportunidade identificada, não implementada: pausas antes de nomes-chave (ex. "Elias") poderiam ser marcadas explicitamente num futuro `VoicePerformancePolicy`. |
| **Legendas** | Já seguem o Caption Experience Contract: 2 linhas, formato longo, burned-in + sidecar `.srt`. |
| **Arco de música** | A cama de música única e original (Gate 3D.2, redesenho sub+shimmer) cobre o vídeo inteiro sem variação de fase — consistente com "uma faixa apropriada pode bastar", sem exigir múltiplas faixas por fase narrativa. |
| **SFX** | Nenhum implementado — oportunidade identificada, não obrigatória: um tique-taque sutil no momento em que Mariana descobre a inscrição (beat_C/beat_18) seria um candidato coerente com o Sound Design Contract, se algum dia priorizado. |
| **Payoff/final** | `beat_E` (573.2s-588.3s, RESOLUTION) já é um callback direto ao `beat_B` (mesma vitrine) — o payoff visual já existe estruturalmente no plano de 30 beats, mesmo sem ter sido nomeado "Ending/Payoff Contract" até esta revisão. |

Nenhuma dessas observações altera o vídeo real ou o Gate 3D.2 em andamento — é só a aplicação retrospectiva do vocabulário formal a uma produção que, na prática, já seguia boa parte dele por bom senso editorial.

---

## Bloco de Decisão Final

```
YOUTUBE_EXPERIENCE_CONTRACT_REQUIRED: YES

CLICK_PACKAGE_SEPARATE: YES
WATCH_EXPERIENCE_SEPARATE: YES

HOOK_CONTRACT_REQUIRED: YES
HOOK_BEFORE_BRANDING_DEFAULT: YES
FIRST_30_SECONDS_SPECIAL_REGION: YES

NARRATIVE_RHYTHM_REQUIRED: YES
MICRO_HOOKS_SUPPORTED: YES

VISUAL_BEAT_CONCEPT: FORMALIZED (already implemented, visual_beats.py)
RETENTION_BEAT_CONCEPT: FORMALIZED (already implemented, retention.py)
VISUAL_EVENT_REQUIRES_NEW_IMAGE: NO

TARGET_MAX_PERCEPTUAL_STATIC_WINDOW: ~7 seconds (tolerated ~10s)
STATIC_WINDOW_CLASSIFICATION: EXPERIMENTAL_HEURISTIC

MOTION_MUST_BE_PERCEPTIBLE: YES
OUTPUT_LEVEL_MOTION_QA_REQUIRED: YES
CUMULATIVE_CAMERA_STATE_SUPPORTED: YES (already implemented, Gate 3D.2)
PUSH_IN_DEFAULT_FOR_ATMOSPHERIC_SCENES: YES

IMAGE_DENSITY_REFERENCE: ~40-55 images / ~10 minutes
IMAGE_DENSITY_CLASSIFICATION: EXPERIMENTAL_REFERENCE_RANGE

VOICE_PERFORMANCE_CONTRACT_REQUIRED: YES
PAUSES_SUPPORTED: YES

BURNED_CAPTIONS_DEFAULT: YES (already implemented)
SRT_SIDECAR_RETAINED: YES (already implemented)

BACKGROUND_MUSIC_DEFAULT: YES (already implemented)
MUSIC_PERCEPTUAL_QA_REQUIRED: YES (stem-relative, already implemented Gate 3D.2)
NARRATION_AUDIO_PRIORITY: YES

SFX_REQUIRED: NO
SFX_SUPPORTED: YES
SILENCE_AS_EFFECT_SUPPORTED: YES

PATTERN_INTERRUPTS_SUPPORTED: YES
PATTERN_INTERRUPTS_REQUIRED_FREQUENCY: NOT_SPECIFIED (open question, §35)

LONG_INTRO_BEFORE_HOOK_ALLOWED: NO
MICRO_BRANDING_SUPPORTED: YES (optional)

PAYOFF_CONTRACT_REQUIRED: YES
LONG_GENERIC_CTA_DEFAULT: NO

MEDIA_QA_SEPARATE: YES (already implemented)
EXPERIENCE_QA_REQUIRED: YES (already implemented, extended by this spec)
AUTOMATED_ENGAGEMENT_SCORE_ALLOWED: NO

HUMAN_FULL_WATCH_REQUIRED_AT_E2: YES
FINAL_PUBLICATION_QUESTION: "Eu publicaria este vídeo no YouTube sem editar o MP4?"

REAL_AUDIENCE_EVIDENCE_FUTURE: YES (E3, not implemented)
HEURISTICS_REVISABLE_FROM_REAL_DATA: YES

GENRE_PROFILE_EXTENSION_POINT: DOCUMENTED_NOT_IMPLEMENTED

ADVANCED_MODE_TOUCHED: NO
PRODUCTION_CODE_CHANGED: NO
IMPLEMENTATION_PERFORMED: NO

READY_FOR_EXPERIENCE_CONTRACT_IMPLEMENTATION: YES
RECOMMENDED_IMPLEMENTATION_GATE: Gate 3E ou posterior (após HUMAN_PASS do Gate 3D.2 no Human Full Watch)

SDD_VERDICT: YOUTUBE_EXPERIENCE_SDD_APPROVED
```
