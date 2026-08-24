# GATE 3D.1 — RETENTION & PUBLICATION POLISH — IMPLEMENTATION REPORT

## 1. Contexto e autoridade

Este gate implementa exatamente o escopo autorizado em
`docs/youtube-lite/GATE_3D_POSTMORTEM_AND_3D1_PLAN.md`
(`DISCOVERY_VERDICT: READY_FOR_GATE_3D1_IMPLEMENTATION`), que por sua vez
diagnosticou cinco gaps P0 e um gap P1 no vídeo do Gate 3D (tecnicamente
válido — Media QA 10/10 — mas `HUMAN_PASS_WITH_NOTES` /
`WOULD_PUBLISH_WITHOUT_EDITING_MP4: NO`). Nenhum componente já aprovado
(roteiro, narração, Voice C, Visual Bible v2, as 30 imagens) foi redesenhado.
O diretório baseline `runs/20260823T223458Z-gate3d-planning/` permanece
intacto e não foi sobrescrito.

## 2. Escopo implementado

| Slice | Item | Status |
|---|---|---|
| A | Correção do bug de movimento Ken Burns + teste de regressão permanente | ✅ Completo |
| B | Retention Segments (subdivisão de Visual Beat) | ✅ Completo |
| C | Legendas em português queimadas no vídeo (burn-in) | ✅ Completo |
| D | Trilha de fundo original + mixagem subordinada à narração | ✅ Completo |
| E | Imagens adicionais para reduzir densidade estática | ⏸️ Adiado (ver §14) |
| F | Experience QA (nova camada, distinta de Media QA) | ✅ Completo |
| G | Integração final em novo diretório de run | ✅ Completo |

Nada fora deste escopo foi tocado: sem upload ao YouTube, sem analytics/SEO,
sem múltiplas thumbnails, sem motor de efeitos sonoros, sem vídeo generativo,
sem personagens animados/lip sync, sem busca de B-roll, sem infraestrutura em
nuvem, sem integração com o Advanced, sem enxame de agentes, sem Music
Agent/Composer/Swarm, sem sistema de design de legendas, sem juízes
CV/OCR/LLM.

## 3. SLICE A — Bug de movimento: diagnóstico e correção

**Causa raiz confirmada** (já provada no postmortem, reconfirmada aqui): a
receita `-loop 1 -framerate {fps} -i image` combinada com
`zoompan=...:d=1:...` quebra a progressão interna de estado de zoom do
filtro `zoompan` — cada frame de saída reinicia o zoom em vez de progredir.
A receita correta usa um único frame de entrada estático
(`-loop 1 -i image`, sem `-framerate` multiplicando) com
`zoompan=...:d=<frames_totais_de_saída>:...`.

**Implementação**: `render_retention_clip()` em
[ffmpeg_assembler.py](../../src/pedroarte_youtube_engine/lite/ffmpeg_assembler.py)
substitui a lógica anterior. `render_silent_segment()` é mantida como wrapper
compatível, delegando para a nova função com um segmento padrão.

**Prova permanente**: [tests/lite/test_motion_regression.py](../../tests/lite/test_motion_regression.py)
reproduz o experimento de diff de pixel do postmortem (`ffmpeg
blend=difference,signalstats` → `YAVG`) como teste automatizado permanente
(`MIN_PERCEPTIBLE_YAVG = 1.0`). 4 testes, todos passando.

**Prova em produção real**: `beat_26.mp4` (36.5s), medido no Motion Proof —
YAVG≈11 sustentado ao longo do beat inteiro, contra ≈0 antes da correção.

## 4. SLICE B — Retention Segments

Novo módulo [retention.py](../../src/pedroarte_youtube_engine/lite/retention.py).
Não é um novo subsistema — é uma subdivisão opcional de `VisualBeat` em
`RetentionSegment`s, usando apenas os quatro tipos autorizados
(`ZOOM_IN`, `ZOOM_OUT`, `PAN`, `REFRAME`) mais os dois tipos de transição
(`HARD_CUT`, `CROSSFADE`, já existentes).

Constantes experimentais (explicitamente rotuladas como tal, não
constitucionais):
- `GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND = 0.004`
- `MAX_TOTAL_ZOOM_DELTA = 0.16`
- `TARGET_MAX_STATIC_WINDOW_SECONDS = 7.0`
- `TOLERATED_MAX_STATIC_WINDOW_SECONDS = 10.0`
- escape hatch `INTENTIONAL_CONTEMPLATIVE_HOLD` (campo `contemplative`) para
  janelas estáticas propositais mais longas, isentas do teto.

`build_default_retention_plan`: beats ≤10s → 1 segmento; beats >10s →
`max(2, round(duração/7))` segmentos, alternando o ciclo
`[ZOOM_IN, PAN, ZOOM_OUT, REFRAME]`. Pan é expresso como fração da margem de
corte disponível (não da largura do frame), garantindo enquadramento válido
em qualquer nível de zoom.

**Resultado medido nos 30 beats reais**: pior janela estática = 8.4s em
`beat_11` — dentro do teto tolerado de 10s, ainda que acima da meta de 7s (o
que Slice E existe para reduzir, ver §14).

12 testes de lógica pura em
[tests/lite/test_retention.py](../../tests/lite/test_retention.py), todos
passando.

## 5. SLICE C — Legendas queimadas (burn-in)

Reaproveita os mesmos dados de timing já usados na narração (nenhuma nova
transcrição/alinhamento). Novo rechunking determinístico em
[captions.py](../../src/pedroarte_youtube_engine/lite/captions.py):

- Contrato de rechunk: `MAX_LINES=2`, `~42` caracteres/linha,
  `~84` caracteres de exibição no máximo, quebra apenas em limite de
  palavra, redistribuição de duração proporcional quando não há timestamp
  por palavra (`PROPORTIONAL_CAPTION_TIMING_APPROXIMATION = True` —
  explicitamente sinalizado como aproximação, nunca alegado como preciso).
- Contrato de estilo (`CaptionStyle`): 2 linhas, margem inferior ~8% da
  altura, fonte ~4.5% da altura do frame, branco com contorno preto, sem
  caixa opaca por padrão.
- Queima via filtro `ass`/libass do FFmpeg (`burn_captions()` em
  `ffmpeg_assembler.py`), confirmado disponível no build `Gyan.FFmpeg`
  instalado (`--enable-libass`). `-c:a copy` evita reencode de áudio nesta
  etapa.

**Resultado real**: 99 cues originais (mesmos da narração) → 173 cues de
exibição após rechunk. Renderizado com sucesso sobre o vídeo real de 650.3s.

9 testes em [tests/lite/test_caption_burn_in.py](../../tests/lite/test_caption_burn_in.py),
incluindo um teste de queima real ponta a ponta, todos passando.

## 6. SLICE D — Trilha de fundo e mixagem

Novo módulo [audio_mix.py](../../src/pedroarte_youtube_engine/lite/audio_mix.py).
Nenhum Music Agent/Composer/Swarm: uma cama ambiente original é sintetizada
via `sine` + `amix` + `tremolo` + `lowpass` do próprio FFmpeg — asset 100%
gerado por código, sem qualquer fonte de terceiros, na categoria
explicitamente aceita pelo postmortem ("original/generated asset with
publication rights"), evitando por completo o risco de licenciamento de
música comercial de origem desconhecida.

Mixagem narração-dominante, sem ducking (adiado, conforme autorizado): nível
de música fixo e baixo, com fade-in/out de 3s.

**Calibração empírica do nível** (não uma constante congelada às cegas —
conforme exigido em §17 do briefing): a cama sintetizada nasce quieta por
construção (mean_volume medido ≈ -48.3dB). Uma primeira tentativa com
`DEFAULT_MUSIC_GAIN_DB = -28.0` produziu um nível efetivo de ≈-76dB —
musicalmente indetectável — e foi capturada exatamente pelo Experience QA
(ver §12, achado real). Recalibrado para `DEFAULT_MUSIC_GAIN_DB = 12.0`
(ajuste positivo *a partir* da cama já quieta, não erro de sinal), medido em
produção real:

| Métrica | Valor |
|---|---|
| Narração sozinha (mean) | -20.9 dB |
| Cama de música bruta (mean) | -48.3 dB |
| Mixagem final (mean) | -20.6 dB |
| Diferença mensurável | 0.30 dB |
| Clipping (max_volume) | -2.4 dB (sem clipping) |

O nível final calibrado está exposto em `bundle/manifest.json` →
`music_gain_db_final` e em `run_manifest.json`.

5 testes em [tests/lite/test_audio_mix.py](../../tests/lite/test_audio_mix.py),
todos passando (testam propriedades relativas, não o valor exato em dB, por
isso continuaram válidos antes e depois da recalibração).

**Dois bugs de engenharia adicionais corrigidos durante o desenvolvimento**
(ver §11):
- `tremolo=f=0.07` estava fora do intervalo válido do FFmpeg → corrigido
  para `f=0.15`.
- `afade=t=out:st=-1` não é sintaxe válida (sem tempo relativo/negativo) →
  corrigido para calcular `fade_out_start` absoluto via `probe_audio`.
- `amix` normaliza por padrão dividindo o nível pelo número de entradas,
  atenuando silenciosamente a narração → corrigido com `normalize=0`.

## 7. SLICE E — Imagens adicionais (densidade)

**Adiado nesta entrega** — ver §14 para justificativa e proposta de próximo
passo. Nenhuma chamada a API paga foi feita.

## 8. SLICE F — Experience QA

Nova camada em [experience_qa.py](../../src/pedroarte_youtube_engine/lite/experience_qa.py),
distinta da Media QA (validade técnica do arquivo) e do Human Full Watch
(única fonte de verdade estética/publicável) — nenhuma das duas camadas
automatizadas pergunta "é bonito?"/"é envolvente?".

10 checks implementados, incluindo as duas camadas de QA de movimento
exigidas:
1. `timeline_visual_coverage` — sem lacunas na cobertura visual da timeline.
2. `total_unique_images` — contagem de imagens únicas ≥ alvo.
3. `max_seconds_without_visual_event` — pior janela estática ≤ teto tolerado.
4. `motion_configuration_coverage` — **Camada 1 (parâmetro)**: config de
   movimento acima do piso, calculada sem renderizar. Insuficiente sozinha —
   não teria pego o bug original do Gate 3D.
5. `motion_render_regression_sample` — **Camada 2 (pixel real)**: agrega
   medições reais de `YAVG` sobre uma amostra renderizada. Camada decisiva.
6. `caption_rechunk_valid` — sem cues longas demais ou não-monotônicas.
7. `caption_style_config_valid` — estilo dentro dos limites de legibilidade.
8. `burned_caption_render_step_completed` — etapa de queima concluída com
   sucesso (verificação de processo, não de pixel/OCR — fora de escopo).
9. `background_music_mix_step_completed` — nível médio da mixagem
   mensuravelmente diferente da narração pura.
10. `final_audio_no_clipping` — sem clipping no áudio final.

18 testes em [tests/lite/test_experience_qa.py](../../tests/lite/test_experience_qa.py),
todos passando (após correção de tolerância de ponto flutuante, ver §11).

## 9. SLICE G — Integração final

Driver mestre: [scripts/lite/run_gate3d1_final.py](../../scripts/lite/run_gate3d1_final.py).
Novo diretório de run `runs/20260824T043945Z-gate3d1/` — o baseline do
Gate 3D nunca foi sobrescrito.

Fluxo: verifica hashes de roteiro/Visual Bible congelados → calcula planos
de retenção para os 30 beats → renderiza 92 clipes `RetentionSegment` →
concatena → sintetiza música → mixa → mux → rechunk + queima de legendas →
reaproveita `beat_A.png` como thumbnail (Slice E adiado) → constrói
metadata/bundle → roda Media QA + Experience QA → escreve
`bundle/manifest.json` e `run_manifest.json`.

**Achado real de produção e correção** (ver detalhe completo em §11 e §6):
a primeira execução completa (532.7s de render, 92 segmentos) passou 10/10
em Media QA mas só 9/10 em Experience QA — `background_music_mix_step_completed`
falhou com diferença de nível 0.00dB. Em vez de re-renderizar os 92
segmentos (caros), foi escrito um script de patch,
[scripts/lite/run_gate3d1_remix.py](../../scripts/lite/run_gate3d1_remix.py),
que reaproveita `working/silent_full_video.mp4` (o vídeo de movimento, que
não precisava mudar) e refaz apenas música → mix → mux → rechunk/queima de
legendas → Media QA + Experience QA, com o `DEFAULT_MUSIC_GAIN_DB`
recalibrado. Resultado: **10/10 Media QA, 10/10 Experience QA** na segunda
passada, sem re-renderizar o movimento.

## 10. Vídeo final

Caminho: `runs/20260824T043945Z-gate3d1/output/youtube_bundle/video.mp4`

| Métrica | Valor |
|---|---|
| Duração | 650.30s (~10min50s) |
| Resolução | 1920x1080 |
| Codec vídeo | h264 |
| Codec áudio | aac |
| Tamanho do arquivo | 97.9 MB |
| Nível médio de áudio | -20.6dB |
| Clipping | Nenhum (max -2.4dB) |
| Legendas queimadas | 173 cues (de 99 cues originais rechunked) |
| Segmentos de movimento (Retention Segments) | 92, sobre as 30 imagens aprovadas |
| Música de fundo | Cama original sintetizada, diferença de nível 0.30dB vs. narração pura |

## 11. Erros encontrados e correções

| # | Erro | Causa | Correção |
|---|---|---|---|
| 1 | `tremolo=f=0.07` inválido | Fora do intervalo `[0.1, 20000]` do FFmpeg | `f=0.15` |
| 2 | `afade=t=out:st=-1` inválido | `afade` não suporta tempo relativo/negativo | `fade_out_start` absoluto via `probe_audio` |
| 3 | `amix` atenuava a narração | Normalização padrão divide pelo nº de entradas | `normalize=0` |
| 4 | Falso-negativo em `check_motion_configuration` no limiar exato | Ruído de ponto flutuante | Tolerância `rate < min_rate * 0.999` |
| 5 (real, produção) | `background_music_mix_step_completed` falhou (0.00dB) no render completo de 650.3s | Cama sintetizada nasce a ≈-48.3dB; corte de -28dB a levava a ≈-76dB, efetivamente inaudível | `DEFAULT_MUSIC_GAIN_DB` recalibrado de -28.0 para +12.0 (ajuste a partir da base quieta, não erro de sinal); reverificado com patch de remix, resultado 0.30dB de diferença mensurável, 10/10 Experience QA |

## 12. Testes

| Suíte | Testes | Resultado |
|---|---|---|
| `tests/lite/` (todos os módulos Gate 3D.1 + preexistentes) | 155 | ✅ 155 passed |
| Suíte completa do repositório (`tests/`) | 281 | ✅ 281 passed |

Nenhuma regressão. Suíte completa executada uma última vez após todas as
correções, conforme exigido ("Nenhuma regressão é aceitável").

## 13. Verificação do Advanced (frozen)

```
git diff --stat -- src/pedroarte_youtube_engine/agents src/pedroarte_youtube_engine/interfaces src/pedroarte_youtube_engine/domain
```

Saída: **vazia**. O Advanced (`agents/`, `interfaces/`, `domain/`) não foi
tocado em nenhum momento deste gate.

## 14. Slice E — decisão de adiamento

Slice E (imagens adicionais para reduzir densidade estática, lista
priorizada: beat_03, beat_06, beat_13, beat_08, beat_09, beat_12, beat_18,
beat_21, beat_25, beat_26) foi explicitamente adiado nesta entrega:

- A "prova de movimento" (mandatória antes de qualquer nova imagem) foi
  cumprida usando apenas as 30 imagens já aprovadas — ver §15 (Motion
  Proof).
- Com a correção de movimento, a pior janela estática real medida nos 30
  beats caiu para 8.4s (`beat_11`) — dentro do teto tolerado de 10s, mas
  acima da meta de 7s.
- Gerar novas imagens via handoff/geração nativa (preferido) ou API paga
  (requer STOP-antes-do-gasto e autorização explícita, conforme mandato)
  é um item P1 que envolve um novo round-trip humano, distinto dos itens
  P0 já endereçados. Nenhuma chamada de API paga foi feita.
- **Proposta de próximo passo** (não executada, aguardando decisão): gerar
  o manifesto concreto de ~12-15 imagens adicionais para os beats
  priorizados acima, via handoff/geração nativa sem custo, como uma
  submissão separada e pequena, após este vídeo passar por Human Full
  Watch — para não acoplar um adiamento explicitamente autorizado a uma
  decisão que só o usuário pode tomar.

## 15. Motion Proof

Antes de qualquer consideração de Slice E, a prova de movimento exigida foi
executada com [scripts/lite/run_gate3d1_motion_proof.py](../../scripts/lite/run_gate3d1_motion_proof.py),
usando **apenas** as 30 imagens já aprovadas (nenhuma geração nova),
renderizando 5 excertos representativos com narração real:

| Excerto | Beat | Tipo |
|---|---|---|
| Curto | beat_D | curto |
| Médio | beat_A | médio |
| Longo | beat_26 | longo (36.5s) |
| Emocional | beat_18 | emocional |
| Atmosférico | beat_B | atmosférico |

Saídas em `runs/gate3d1-motion-proof/output/`. `beat_26.mp4` mostrou
YAVG≈11 sustentado ao longo dos 36.5s — movimento real e perceptível,
confirmando `MOVEMENT_NOW_PERCEPTIBLE = YES` antes de prosseguir para o
render completo.

## 16. Custos

| Item | Custo |
|---|---|
| Geração de imagem (nova) | $0.00 — nenhuma imagem nova gerada |
| API de música de terceiros | $0.00 — música sintetizada localmente via FFmpeg |
| Renderização (tempo local) | 532.7s (render completo) + patch de remix (música/mux/legendas, sem re-renderizar movimento) |
| Custo externo total | **$0.00** |

## 17. Comparação Gate 3D (baseline) vs. Gate 3D.1

| Métrica | Gate 3D (baseline) | Gate 3D.1 |
|---|---|---|
| Duração | 650.30s | 650.30s (inalterada — narração é autoridade) |
| Imagens únicas | 30 | 30 (Slice E adiado) |
| Movimento perceptível | Não (bug zoompan) | Sim (YAVG≈11 em amostra real) |
| Pior janela estática | Não medida (movimento quebrado tornava a métrica sem sentido) | 8.4s (beat_11), dentro do teto de 10s |
| Legendas queimadas em PT | Não | Sim, 173 cues |
| Música de fundo | Não | Sim, cama original, diferença de nível 0.30dB |
| Tamanho do arquivo | 33.0 MB | 97.9 MB |
| Testes automatizados | (suíte anterior) | 281 passed (155 em `tests/lite/`) |
| Custo externo | $0.00 | $0.00 |
| Advanced tocado | Não | Não (confirmado, §13) |
| Media QA | 10/10 PASS | 10/10 PASS |
| Experience QA | (camada não existia) | 10/10 PASS |
| Veredito humano anterior | `HUMAN_PASS_WITH_NOTES` / `WOULD_PUBLISH_WITHOUT_EDITING_MP4: NO` | Pendente (ver §18) |

## 18. Condições de STOP — status

Nenhuma condição de STOP definida no mandato foi acionada:
- ✅ Bug de movimento foi corrigido e provado (não bloqueou).
- ✅ Retention Beat implementado sem exigir nova arquitetura.
- ✅ Legendas não exigiram substituir timing/narração aprovados.
- ✅ Licenciamento de música resolvido por síntese original (sem
  licenciamento de terceiros a resolver).
- ✅ Nenhuma API paga de imagem foi necessária (Slice E adiado antes de
  qualquer gasto).
- ✅ Advanced não precisou de modificação.
- ✅ Testes de regressão passam (281/281).

## 19. Pacote de revisão humana

**Vídeo final para revisão**:
`runs/20260824T043945Z-gate3d1/output/youtube_bundle/video.mp4`

Ao assistir, avalie especificamente estas 10 dimensões:
1. O movimento Ken Burns é perceptível e natural (não abrupto, não ausente)?
2. As janelas estáticas incomodam ou parecem intencionais/contemplativas?
3. As legendas em português são legíveis, bem posicionadas e sincronizadas?
4. A música de fundo é perceptível sem competir com a narração?
5. Há algum ponto de silêncio ou volume desequilibrado?
6. A densidade de imagens (30 únicas) sustenta o vídeo inteiro ou cansa em
   algum trecho?
7. Cortes/transições entre segmentos parecem abruptos ou bem calibrados?
8. A thumbnail (reaproveitada de `beat_A.png`) é apropriada?
9. Existe algum artefato visual ou de áudio perceptível (blocos, clipping,
   dessincronia)?
10. Você publicaria este vídeo hoje, sem qualquer edição adicional do MP4?

## 20. Pergunta final de gate

**Eu publicaria este vídeo no YouTube sem editar o MP4?**

Responda apenas **YES** ou **NO**.

- **YES** → `YOUTUBE_LITE_E2 = PROVEN`
- **NO** → `YOUTUBE_LITE_E2 = NOT_PROVEN`

Nenhuma ação além desta pergunta será tomada sem nova instrução do usuário.

---

## Bloco de métricas finais (resumo)

```
DURATION_BASELINE_S: 650.30
DURATION_GATE3D1_S: 650.30
IMAGE_COUNT_BASELINE: 30
IMAGE_COUNT_GATE3D1: 30
MAX_STATIC_WINDOW_S: 8.4
MOTION_COVERAGE_PCT: 100.0
CAPTION_CUES_ORIGINAL: 99
CAPTION_CUES_DISPLAY: 173
MUSIC_LEVEL_DIFF_DB: 0.30
AUDIO_CLIPPING_MAX_DB: -2.4
TEST_COUNT_LITE: 155
TEST_COUNT_TOTAL: 281
TEST_RESULT: 281_PASSED_0_FAILED
EXTERNAL_COST_USD: 0.00
ADVANCED_TOUCHED: NO
MEDIA_QA: 10_OF_10_PASS
EXPERIENCE_QA: 10_OF_10_PASS
READINESS: READY_FOR_HUMAN_FULL_WATCH
```
