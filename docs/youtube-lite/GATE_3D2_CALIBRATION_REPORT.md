# GATE 3D.2 — DEPTH MOTION + AUDIBLE MUSIC CALIBRATION — REPORT (STOP 1/2)

Este relatório cobre a fase de calibração (Parts A+B do mandato). Nenhum
render completo de 650.3s foi feito. Este documento termina em um STOP
explícito, aguardando duas seleções humanas (movimento e música) antes de
qualquer aplicação ao vídeo completo.

## 1. Feedback humano do Gate 3D.1

```
GATE_3D1_TECHNICAL: PASS
MEDIA_QA: PASS
EXPERIENCE_QA: PASS
GATE_3D1_HUMAN: FAIL_PUBLICATION_GATE
WOULD_PUBLISH_WITHOUT_EDITING_MP4: NO
YOUTUBE_LITE_E2: NOT_PROVEN
```

Feedback textual:
1. "Melhorou um pouco, mas o zoom precisa aproximar gradativamente, dando a
   sensação ao usuário que ele está adentrando no cenário."
2. "O som de fundo ainda está ausente."

Lição adotada: presença técnica ≠ presença perceptual. Media QA/Experience
QA automatizados do Gate 3D.1 mediram corretamente "existe movimento" e
"existe música na mixagem" — mas não mediram "a profundidade se acumula" nem
"a música é perceptualmente audível isoladamente". Este gate corrige ambos
os critérios de medição, não apenas os parâmetros.

## 2. Análise do movimento atual (Gate 3D.1)

Medido diretamente em `build_default_retention_plan` sobre os beats reais
`beat_D` (curto), `beat_A` (médio) e `beat_26` (longo, 36.5s):

| Beat | Seg | Tipo | Duração | start_scale | end_scale | delta | taxa/s |
|---|---|---|---|---|---|---|---|
| beat_D (11.6s) | 0 | zoom_in | 5.80s | 1.0000 | 1.0232 | +0.0232 | 0.00400 |
| beat_D | 1 | pan | 5.80s | 1.0500 | 1.0500 | +0.0000 | 0.00000 |
| beat_A (21.8s) | 0 | zoom_in | 7.27s | 1.0000 | 1.0291 | +0.0291 | 0.00400 |
| beat_A | 1 | pan | 7.27s | 1.0500 | 1.0500 | +0.0000 | 0.00000 |
| beat_A | 2 | zoom_out | 7.27s | 1.0291 | 1.0000 | -0.0291 | 0.00400 |
| beat_26 (36.5s) | 0 | zoom_in | 7.30s | 1.0000 | 1.0292 | +0.0292 | 0.00400 |
| beat_26 | 1 | pan | 7.30s | 1.0500 | 1.0500 | +0.0000 | 0.00000 |
| beat_26 | 2 | zoom_out | 7.30s | 1.0292 | 1.0000 | -0.0292 | 0.00400 |
| beat_26 | 3 | reframe | 7.30s | 1.0500 | 1.0500 | +0.0000 | 0.00000 |
| beat_26 | 4 | zoom_in | 7.30s | 1.0000 | 1.0292 | +0.0292 | 0.00400 |

**Por que o movimento parece insuficiente apesar de YAVG≈11 e cobertura de
movimento configurado de 100%:**

- `YAVG` mede diferença de pixel **quadro a quadro** (movimento local, real)
  — não mede acúmulo de profundidade ao longo do beat inteiro. O bug do
  Gate 3D (zoom quebrado) media YAVG≈0.01; o Gate 3D.1 corrigiu para
  YAVG≈11 — real, mas isso só prova que "algo se move a cada frame", não que
  "a câmera avança na cena".
- O delta de zoom é calculado **por chunk** (`compute_zoom_delta`), não pelo
  **beat inteiro**. Mesmo em `beat_26` (36.5s, 5 segmentos), nenhum segmento
  individual ultrapassa ~2.9% de zoom.
- A escala **reseta entre segmentos** em vez de continuar (ver §3): o beat
  inteiro nunca acumula mais que ~2.9% líquidos de zoom, porque zoom_in e
  zoom_out se cancelam e pan/reframe ficam num platô fixo de 1.05.
- Resultado: em 36.5 segundos de vídeo, a câmera aparenta avançar e recuar
  repetidamente sem nunca progredir — exatamente o padrão
  "aproxima/retrocede/aproxima" citado como indesejável no mandato (§7/§8).

## 3. Investigação de reset de escala

**Confirmado**: `build_default_retention_plan` reseta a escala entre
Retention Segments consecutivos.

Sequência real em `beat_26`: `1.0 → 1.029` (zoom_in) — **salto** para
`1.05` constante (pan) — **salto para baixo** `1.029 → 1.0` (zoom_out,
começando de 1.029, não de 1.05) — **salto** para `1.05` constante
(reframe) — **salto para baixo** `1.0 → 1.029` (zoom_in de novo).

Nova função de teste `segments_share_continuous_trajectory()` (Gate 3D.2,
[retention.py](../../src/pedroarte_youtube_engine/lite/retention.py))
confirma isso automaticamente: `segments_share_continuous_trajectory(build_default_retention_plan(36.5))
== False`. Este é exatamente o motivo raiz por trás do feedback humano.

## 4. Estratégia de profundidade progressiva

Nova função `build_continuous_push_in_plan(duration, total_zoom_ratio)`:

- Uma única trajetória de escala cobre o beat **inteiro**:
  `1.0 → 1.0 + total_zoom_ratio`.
- Retention Segments passam a ser apenas fatias de **tempo** dessa mesma
  trajetória — `segment[i+1].start_scale == segment[i].end_scale` sempre
  (verificado por `segments_share_continuous_trajectory`, agora `True`).
- Pan leve é camadado nos chunks intermediários (não substitui o zoom, não
  reseta a escala).
- Direção padrão: push-in contínuo (sem zoom_out mecânico). Reservar
  zoom_out/pull-back para casos narrativamente justificados (revelação,
  isolamento, final) é tratado como refinamento pós-seleção (§23 do
  mandato), aplicado apenas depois que o perfil de movimento for aprovado —
  não foi necessário para o excerto de calibração em si.

## 5. Bake-off de movimento

Excerto de calibração: `beat_18` ("emocional", 23.90s), imagem já aprovada
`beat_18.png`, narração real correspondente (23.90s, mean=-21.1dB).
Nenhuma imagem nova gerada (`NEW_IMAGES_GENERATED = 0`).

| Variante | Descrição | Trajetória contínua? | Δ escala líquido no beat |
|---|---|---|---|
| A | Comportamento atual do Gate 3D.1 (`build_default_retention_plan`) | **Não** (reset confirmado) | +0.0000 (zoom_in +0.032 cancelado por zoom_out -0.032) |
| B | Push-in contínuo moderado (`total_zoom_ratio=0.12`) | Sim | +0.1200 |
| C | Push-in contínuo forte (`total_zoom_ratio=0.22`) | Sim | +0.2200 |

Cada variante muxada apenas com a narração real do excerto (sem música,
para isolar o julgamento visual do movimento).

## 6. Seleção humana de movimento

**PENDENTE.** Ver bloco de STOP (§ final) para os caminhos dos 3 arquivos.

## 7. Análise da música atual

```
NARRATION_MEAN (Gate 3D.1, vídeo completo): -20.9 dB
RAW_MUSIC_MEAN (cama sintetizada): -48.3 dB
FINAL_MIX_MEAN: -20.6 dB
FINAL_DIFFERENCE (critério antigo): 0.30 dB
```

O critério antigo (`FINAL_MIX_MEAN - NARRATION_ONLY_MEAN`) foi considerado
suficiente pelo QA automatizado, mas a narração domina o nível médio da
mixagem — uma diferença de 0.30dB no nível médio total **não prova** que a
música é perceptualmente audível isoladamente. O critério foi substituído
(ver §25 do mandato) por uma comparação no nível do **stem**, não da
mixagem final.

## 8. Medições em nível de stem

Medido diretamente sobre o excerto de calibração (`beat_18`, 23.90s):

```
NARRATION_STEM_MEAN_DB: -21.1
RAW_MUSIC_STEM_MEAN_DB (antes do ganho): -48.3
```

Três variantes derivadas por MEDIÇÃO (não presets absolutos — Gate 3D.2
§17): o ganho de cada variante é calculado por
`compute_gain_for_relative_offset()`, resolvendo o ganho necessário a partir
do nível bruto REAL medido da cama para atingir um deslocamento relativo
alvo (não um dB absoluto adivinhado):

| Variante | Alvo relativo | Ganho aplicado | Stem pós-ganho (mean) | Relativo real à narração | Pico da mixagem final |
|---|---|---|---|---|---|
| LOW | -16.0 dB | +11.20 dB | -37.9 dB | -16.80 dB | -3.5 dB |
| MEDIUM | -11.0 dB | +16.20 dB | -32.9 dB | -11.80 dB | -3.4 dB |
| HIGH | -7.0 dB | +20.20 dB | -28.9 dB | -7.80 dB | -3.4 dB |

Todas as três permanecem subordinadas à narração (stem de música sempre
mais silencioso que o stem de narração) e nenhuma produz clipping (pico
final ≤ -3.4dB, bem abaixo de 0dB).

## 9. Bake-off de música

Mesmo excerto de calibração (`beat_18`), mesma narração, mesma cama de
música — apenas o ganho muda entre as três variantes. Arquivos são MP3
independentes (narração + música mixadas), prontos para audição direta.

## 10. Seleção humana de música

**PENDENTE.** Ver bloco de STOP abaixo para os caminhos dos 3 arquivos.

## 11–17. Perfis selecionados, mudanças de implementação, testes, render completo, Media QA, Experience QA, revisão humana final

**Todos pendentes** — dependem das seleções humanas de §6 e §10. Serão
completados em uma submissão subsequente, após a resposta do usuário.

---

## 18. Round 2 — resposta ao feedback humano sobre o round 1

Feedback recebido sobre as variantes A/B/C/LOW/MEDIUM/HIGH do round 1:

> "Você parece estar confundindo o som da voz do narrador com a música. O
> som da voz é uma coisa e a música de fundo é outra. E o zoom deve se
> aproximar nos dando uma sensação de movimento, ou seja, que está
> animando. Verifique se você consegue fazer um nível mais profissional de
> animação."

### 18.1 Investigação: voz vs. música

Não foi encontrado bug de troca/mistura de sinal no código (`mix_narration_with_music`
mapeia `[0:a]`=narração pura e `[1:a]`=música com ganho corretamente, sem
inversão). A causa real, confirmada por medição espectral direta sobre a
narração real do excerto de calibração:

```
Banda                  Nível médio    Nível de pico
Faixa completa          -21.1 dB        -3.6 dB
80-300Hz (fundamental)   -26.1 dB        -9.4 dB
300-3000Hz (formantes)   -23.1 dB        -3.5 dB   <- banda dominante da voz
<80Hz (sub)              -40.7 dB       -25.1 dB
>3000Hz (agudo)          -36.3 dB       -12.6 dB
```

A narração concentra praticamente toda sua energia entre 80-3000Hz. O
desenho de música do round 1 (3 tons em 110/164.5/220Hz, todos dentro dessa
faixa) ocupava exatamente o mesmo espaço espectral da voz — por isso, mesmo
em nível audível (diferença de 0.30dB a 7.8dB conforme a variante), a
música se misturava perceptualmente com a narração em vez de ser
reconhecida como uma camada distinta. Isso é consistente com o feedback:
não era "confusão de rótulo", era colisão espectral real.

**Correção**: [audio_mix.py](../../src/pedroarte_youtube_engine/lite/audio_mix.py)
`generate_ambient_bed` redesenhado para ocupar as duas faixas onde a
narração está quase ausente — um sub-grave a 55Hz (abaixo do piso medido de
80Hz) e um shimmer agudo a 3520/4698.63Hz (acima do teto medido de 3000Hz),
com `highpass=f=3000` reforçando o isolamento do shimmer e `chorus` dando
textura de pad sem introduzir melodia. Confirmado por medição pós-mudança:
o "bolso vocal" (80-3000Hz) da nova cama caiu para -47.8dB — a banda mais
silenciosa do sinal, em vez da mais dominante.

Produzido: [`music_only_isolated_high.mp3`](../../runs/gate3d2-calibration/output/music_only_isolated_high.mp3) —
a música pura, SEM narração, no nível HIGH — para que a avaliação de "isso
soa como música?" seja feita sem nenhuma interferência da voz, resolvendo a
ambiguidade do round 1 diretamente. Mais as 3 variantes remixadas
(`music_variant_v2_{low,medium,high}.mp3`) com o novo desenho, nos mesmos
três deslocamentos relativos do round 1.

### 18.2 Investigação: "zoom mais profissional"

As variantes B/C do round 1 usavam progressão **linear** dentro de cada
Retention Segment (`z0+(z1-z0)*t`, `t` proporcional ao frame). Interpolação
linear em Ken Burns tende a parecer mecânica — a câmera "liga" a uma
velocidade constante e "desliga" abruptamente, sem a aceleração/desaceleração
suave que ferramentas de edição profissionais aplicam por padrão.

**Correção**: nova curva `_smoothstep(t) = 3t²-2t³` (derivada zero em t=0 e
t=1 — acelera suavemente a partir do repouso, desacelera suavemente até o
repouso), aplicada à trajetória **global** do beat inteiro em
`build_continuous_push_in_plan(..., ease_in_out=True)` — não por
Retention Segment individual. Aplicar a curva por segmento foi considerado e
descartado: como cada segmento é renderizado como um clipe FFmpeg
independente, uma curva suave por segmento faria a velocidade cair a zero a
cada ~7-8s (a cada fronteira de chunk), produzindo um movimento "pulsante"
em vez de um único avanço contínuo do início ao fim do beat — o oposto do
efeito pedido. Com a curva aplicada no nível global, os LIMITES de escala de
cada chunk já refletem os pontos correspondentes na curva suave; a
renderização de cada chunk continua linear internamente, e a sequência
concatenada aproxima a curva suave inteira sem paradas de velocidade
intermediárias.

Produzidas duas novas variantes sobre o MESMO excerto (`beat_18`):

| Variante | Descrição | Δ escala total | Curva |
|---|---|---|---|
| D | Push-in contínuo moderado + smoothstep | +0.1200 (igual a B) | Suave (acelera/desacelera) |
| E | Push-in contínuo forte + smoothstep | +0.2200 (igual a C) | Suave (acelera/desacelera) |

D/E têm exatamente a mesma magnitude de zoom que B/C — a única variável
isolada é a curva de progressão (linear vs. suave), para permitir uma
comparação direta e não confundir "mais forte" com "mais profissional".

### 18.3 Testes adicionados no round 2

| Teste | Arquivo | Propósito |
|---|---|---|
| `TestContinuousPushInPlanEasing` (4 testes) | [test_retention.py](../../tests/lite/test_retention.py) | Curva suave não reseta trajetória, atinge o mesmo alvo final, começa mais devagar que a linear, permanece monotônica |

Suíte completa após o round 2: **299 passed** (era 295 ao final do round 1
— 4 novos testes, zero regressões). Advanced confirmado intocado.

---

## Testes adicionados

| Teste | Arquivo | Propósito |
|---|---|---|
| `TestSegmentsShareContinuousTrajectory` (3 testes) | [test_retention.py](../../tests/lite/test_retention.py) | Confirma reset no plano antigo, continuidade no plano novo |
| `TestContinuousPushInPlan` (6 testes) | [test_retention.py](../../tests/lite/test_retention.py) | Trajetória contínua, monotônica, soma de durações, comparação moderate/strong |
| `TestComputeGainForRelativeOffset` (3 testes) | [test_audio_mix.py](../../tests/lite/test_audio_mix.py) | Ganho derivado de medição real, não de preset absoluto |
| `TestRenderMusicStem` (2 testes) | [test_audio_mix.py](../../tests/lite/test_audio_mix.py) | Stem isolado reflete o ganho aplicado; duração casa com a narração |

Suíte completa: **295 passed** (era 281 antes deste gate — 14 novos testes,
zero regressões). `tests/lite/test_motion_regression.py` (regressão de pixel
do bug original) continua passando sem alteração.

Advanced confirmado intocado:
`git diff --stat -- src/pedroarte_youtube_engine/agents src/pedroarte_youtube_engine/interfaces src/pedroarte_youtube_engine/domain`
→ vazio.

Nenhuma imagem nova foi gerada. Nenhum custo externo. Nenhum diretório de
run anterior foi sobrescrito (`runs/20260824T043945Z-gate3d1/` e
`runs/20260823T223458Z-gate3d-planning/` intactos; este gate escreve apenas
em `runs/gate3d2-calibration/`).

---

## STOP — Relatório round 2 (obrigatório antes de qualquer render completo)

Round 1 (A/B/C, música LOW/MEDIUM/HIGH) permanece disponível para
referência, mas as variantes abaixo o SUPERSEDEM — são a resposta direta ao
feedback humano ("confundindo voz com música", "zoom mais profissional").
Avalie as variantes de round 2.

```
CURRENT_GATE3D1_ZOOM_MODEL: por-chunk, independente, sem trajetória compartilhada
CURRENT_SCALE_RESET_BEHAVIOR: SIM — escala reseta entre Retention Segments (confirmado, §3)
CURRENT_ZOOM_START: 1.0 (a cada segmento zoom_in/zoom_out, não a cada beat)
CURRENT_ZOOM_END: 1.0 + delta_do_chunk (delta líquido do beat ≈ 0.00 a 0.03, cancela entre zoom_in/zoom_out)
CURRENT_ZOOM_RATE: 0.004/s (piso experimental do Gate 3D.1), aplicado por chunk, não pelo beat inteiro

WHY_CURRENT_ZOOM_FEELS_INSUFFICIENT: YAVG mede movimento quadro-a-quadro local, não acúmulo de profundidade; o delta de zoom é recalculado por chunk (~7s) em vez de pelo beat inteiro, e a escala reseta entre segmentos; resultado líquido: câmera aparenta avançar/recuar repetidamente sem nunca progredir cumulativamente na cena.

MOTION_VARIANT_A_PATH (round 1, linear, referência): runs/gate3d2-calibration/output/motion_variant_A_current_gate3d1.mp4
MOTION_VARIANT_B_PATH (round 1, linear moderado): runs/gate3d2-calibration/output/motion_variant_B_moderate_continuous.mp4
MOTION_VARIANT_C_PATH (round 1, linear forte): runs/gate3d2-calibration/output/motion_variant_C_strong_continuous.mp4
MOTION_VARIANT_D_PATH (round 2, curva suave moderada, mesma magnitude de B): runs/gate3d2-calibration/output/motion_variant_D_moderate_eased.mp4
MOTION_VARIANT_E_PATH (round 2, curva suave forte, mesma magnitude de C): runs/gate3d2-calibration/output/motion_variant_E_strong_eased.mp4

MOTION_SELECTION_REQUIRED: YES (recomenda-se comparar D e E; A/B/C ficam como referência do que foi rejeitado)

NARRATION_STEM_MEAN_DB: -21.1
RAW_MUSIC_STEM_MEAN_DB_V1 (rejeitado — colidia com a faixa vocal 80-3000Hz): -48.3
RAW_MUSIC_STEM_MEAN_DB_V2 (novo desenho, sub+shimmer fora da faixa vocal): -40.3

MUSIC_ONLY_ISOLATED_PATH (música pura, SEM narração, nível HIGH — para julgar "isso soa como música?" sem interferência de voz): runs/gate3d2-calibration/output/music_only_isolated_high.mp3

MUSIC_LOW_MEAN_DB (v2): -37.9
MUSIC_MEDIUM_MEAN_DB (v2): -32.9
MUSIC_HIGH_MEAN_DB (v2): -28.9

LOW_RELATIVE_TO_NARRATION_DB: -16.80
MEDIUM_RELATIVE_TO_NARRATION_DB: -11.80
HIGH_RELATIVE_TO_NARRATION_DB: -7.80

MUSIC_LOW_PATH (round 2, novo desenho espectral): runs/gate3d2-calibration/output/music_variant_v2_low.mp3
MUSIC_MEDIUM_PATH (round 2, novo desenho espectral): runs/gate3d2-calibration/output/music_variant_v2_medium.mp3
MUSIC_HIGH_PATH (round 2, novo desenho espectral): runs/gate3d2-calibration/output/music_variant_v2_high.mp3

MUSIC_SELECTION_REQUIRED: YES (ouça primeiro MUSIC_ONLY_ISOLATED_PATH sozinho, depois LOW/MEDIUM/HIGH v2 misturados com a narração)

YOUTUBE_LITE_E2: NOT_PROVEN
```

**STOP.** Nenhum render completo será feito até as duas seleções humanas
acima (movimento: D ou E, ou A/B/C se preferir o comportamento anterior;
música: LOW/MEDIUM/HIGH v2 ou NONE_ACCEPTABLE).
