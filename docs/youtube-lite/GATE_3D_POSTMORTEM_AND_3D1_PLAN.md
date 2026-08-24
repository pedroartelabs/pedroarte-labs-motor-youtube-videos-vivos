# Gate 3D Postmortem + Gate 3D.1 Plan

Status: **DISCOVERY — nada implementado.** Nenhuma imagem gerada, nenhum MP4 alterado, nenhuma música adicionada, nenhuma legenda queimada, nenhum código de produção alterado. As únicas ações realizadas foram diagnósticas: leitura de código, extração de frames do vídeo/segmentos já existentes (`runs/20260823T223458Z-gate3d-planning/`) e testes de filtro FFmpeg isolados em arquivos de scratch, fora do repositório.

## 1. Executive Summary

O Gate 3D produziu um vídeo tecnicamente correto (`GATE_3D_TECHNICAL = PASS`, QA automatizada 10/10) mas a revisão humana devolveu `HUMAN_PASS_WITH_NOTES` com `WOULD_PUBLISH_WITHOUT_EDITING_MP4 = NO`. A investigação encontrou a causa raiz do problema mais crítico apontado — "Ken Burns implementado mas percebido como estático" — e ela é um **bug real e confirmado por evidência empírica**, não uma questão de gosto: a combinação `-loop 1 -framerate {fps} -i imagem.png` + `zoompan=...:d=1:...` usada em `render_silent_segment` (`lite/ffmpeg_assembler.py`) faz o zoom avançar de forma praticamente imperceptível (diferença de luminância média entre frames a 8s de distância: **0,013 em escala 0-255**, contra **25,19** na receita clássica do zoompan testada lado a lado com a mesma imagem). Mesmo corrigido o bug, o parâmetro `max_zoom=1.12` satura em ~8s para qualquer beat — e a duração média de beat é 21,7s, ou seja, ~60% de cada beat ficaria congelado mesmo com o zoom funcionando.

A proposta deste documento resolve os 3 gaps do humano com a menor mudança possível: (1) corrigir o bug do zoompan e recalcular o zoom dinamicamente por beat para durar a cena inteira (zero imagens novas); (2) subdividir os beats mais longos em "Retention Beats" com pan/reframe usando a MESMA imagem já aprovada, mais um número modesto de imagens genuinamente novas (~12-15, não 50) onde há valor narrativo real; (3) legendas queimadas via filtro `subtitles`/`ass` do próprio FFmpeg (já presente no build instalado), com rechunking determinístico dos 99 cues (45% deles têm mais de 100 caracteres — ilegíveis como bloco único); (4) uma faixa de música de fundo, com mixagem simples e ducking adiado. Nenhum componente aprovado (roteiro, narração, voz, Visual Bible, personagens) é tocado.

## 2. Gate 3D Evidence

```text
TITLE: O Relojoeiro de Vidro
DURATION: 650.3s (10:50)
VIDEO: 1920x1080, H.264/AAC
NARRATION: Voz C aprovada (pt-BR-AntonioNeural), completa
VISUALS: 30 imagens reais (5 do Gate 3C + 25 do handoff externo, custo zero)
CAPTIONS: sidecar .srt, 99 cues
CHAPTERS: 9
MUSIC: nenhuma
AUTOMATED_QA: 10/10 PASS
```
Artefatos preservados como linha de base em `runs/20260823T223458Z-gate3d-planning/` — **não sobrescritos** por este trabalho.

## 3. Human Review Findings

`HUMAN_PASS_WITH_NOTES`. Aprovado explicitamente: qualidade de imagem, qualidade visual, voz da narração, relação narração/imagem, qualidade geral de produção. Três gaps bloqueiam publicação: (1) sem legendas queimadas em português; (2) ritmo visual/movimento perceptível insuficiente (evento visual perceptível a cada ≤~7s, densidade maior, ~50 imagens como referência inicial); (3) sem música de fundo.

## 4. Finding Classification

| Achado | Classificação | Evidência |
|---|---|---|
| Legendas não queimadas | `MISSING_PRODUCT_REQUIREMENT` | Decisão de design do Gate 3, nunca planejada como burned-in |
| Sensação de estático apesar do Ken Burns configurado | **`BUG`** confirmado, mais `INSUFFICIENT_PARAMETER` secundário | §6-7 — diferença de pixel real medida, não subjetiva |
| Densidade de 30 imagens | `CONTENT_DENSITY_ISSUE` | §10-11 |
| Sem música | `MISSING_PRODUCT_REQUIREMENT` | Explicitamente adiada no Gate 3D, nunca implementada |

## 5. Current Timeline Analysis

A timeline atual (`GATE3D_FULL_VISUAL_PLAN`, 30 beats, `lite/visual_plan_gate3d.py`) cobre os 650,3s sem furos (validado por `validate_plan_coverage`, testado). Cada beat vira **um único segmento de vídeo silencioso** via `render_silent_segment` — uma imagem, um filtro de zoom, sem eventos intermediários. O único evento visual "duro" hoje é a **troca de imagem na fronteira do beat** — não há pan, não há reframe, não há crossfade, e o zoom (por causa do bug) não conta como evento real.

## 6. Ken Burns Root-Cause Analysis

**Hipótese testada:** a combinação de parâmetros usada em `render_silent_segment` não produz o zoom pretendido.

**Método:** renderizado um segmento real (`beat_26.mp4`, 36,5s, já existente) e extraídos frames em t=0,2,4,6,8,10,15,20,30,36. Diferença de pixel medida via `ffmpeg blend=difference + signalstats` (métrica `YAVG`, luminância média absoluta da imagem-diferença, escala 0-255 — 0 = frames idênticos).

| Comparação | YAVG | YMAX | Interpretação |
|---|---|---|---|
| t=0 vs t=4 | 0,036 | 9 | Imperceptível |
| t=4 vs t=8 | 0,002 | 2 | Imperceptível |
| t=10 vs t=15 | 0,006 | 10 | Imperceptível |
| t=20 vs t=30 | **0,0** | **0** | **Frames pixel-idênticos** |

Suspeita de artefato de medição (imagem de baixo contraste) descartada: o mesmo teste repetido com um padrão sintético de alto contraste (`testsrc`, mesma cadeia de filtro exata) deu **t=0 vs t=8 → YAVG=0,013** — igualmente imperceptível.

**Teste decisivo:** a mesma imagem sintética, com a receita **clássica** do zoompan (`-loop 1 -i imagem.png` **sem** `-framerate`, `zoompan=...:d=200:...` deixando o próprio filtro controlar a progressão ao longo de 200 frames/8s) produziu **t=0 vs t=7 → YAVG=25,19, YMAX=219** — diferença real e substancial, na mesma imagem, com o mesmo `zoom_per_frame`/`max_zoom`.

**Causa raiz confirmada:** `render_silent_segment` alimenta o zoompan com `-framerate {fps}` sobre um `-loop 1`, entregando {fps} "frames de entrada" já idênticos por segundo, com `d=1` (o filtro trata cada um como precisando de só 1 frame de saída). Essa combinação quebra a progressão esperada do estado interno `zoom` do filtro — o padrão correto e documentado do zoompan é **um único frame de entrada** + `d=<frames totais>`, deixando o filtro internamente repetir/zoomar o frame ao longo de `d` saídas. O código atual nunca seguiu esse padrão — o "Ken Burns" existiu como configuração desde o Gate 2, mas **nunca produziu movimento perceptível em nenhum vídeo já renderizado**, incluindo o clipe de 50s do Gate 2 (onde a duração curta provavelmente mascarou o problema aos olhos de quem revisou).

### Root Cause Record

```text
OBSERVATION: vídeo parece estático apesar de Ken Burns "implementado"
EXPECTED: zoom lento e contínuo, visível ao longo do beat
ACTUAL: frames pixel-idênticos após ~poucos segundos; diferença já imperceptível desde o início
ROOT CAUSE: -framerate {fps} + zoompan d=1 sobre entrada -loop 1 quebra a progressão do estado
            interno de zoom do filtro (uso incorreto da API do zoompan)
EVIDENCE: teste lado a lado com receita clássica (d=N, sem -framerate) na mesma imagem:
          YAVG 0,013 (atual, quebrado) vs YAVG 25,19 (clássico, correto)
SMALLEST FIX: trocar `-loop 1 -framerate {fps} -i imagem` + `d=1` por
              `-loop 1 -i imagem` + `zoompan=...:d=<duration_seconds*fps>:...`
              (mesmos parâmetros de zoom, só a forma de alimentar o filtro muda)
TEST: reproduzir o teste de diferença de pixel (t=0 vs t=N) como teste automatizado —
      exigir YAVG acima de um piso mínimo em vez de aceitar "comando não retornou erro"
REGRESSION_RISK: baixo — a mudança é isolada a uma função (`render_silent_segment`),
                 já teria sido pega por um teste de diferença de pixel se ele existisse
                 (não existia — gap de teste real do Gate 2/3D, registrado aqui)
```

## 7. Current Motion Metrics

**Tabela A — Segmentos Visuais Atuais** (todos os 30, ordenados pela timeline; `motion_type` configurado é uniforme — zoom-in centrado, sem pan, para todos):

| id | start | end | dur(s) | motion configurado | zoom 1.0→1.12 atinge o teto em | perceptível? |
|---|---|---|---|---|---|---|
| beat_A | 0.1 | 21.9 | 21.8 | zoom-in | ~8.0s (depois: congelado) | **NÃO** (bug) |
| beat_02 | 21.9 | 35.9 | 14.0 | zoom-in | ~8.0s | **NÃO** |
| beat_03 | 35.9 | 65.5 | 29.6 | zoom-in | ~8.0s | **NÃO** |
| beat_B | 65.5 | 80.5 | 15.0 | zoom-in | ~8.0s | **NÃO** |
| beat_04 | 80.5 | 100.6 | 20.1 | zoom-in | ~8.0s | **NÃO** |
| beat_05 | 100.6 | 117.2 | 16.6 | zoom-in | ~8.0s | **NÃO** |
| beat_06 | 117.2 | 147.7 | 30.5 | zoom-in | ~8.0s | **NÃO** |
| beat_07 | 147.7 | 165.7 | 18.0 | zoom-in | ~8.0s | **NÃO** |
| beat_C | 165.7 | 184.3 | 18.6 | zoom-in | ~8.0s | **NÃO** |
| beat_08 | 184.3 | 208.2 | 23.9 | zoom-in | ~8.0s | **NÃO** |
| beat_09 | 208.2 | 232.0 | 23.8 | zoom-in | ~8.0s | **NÃO** |
| beat_10 | 232.1 | 254.8 | 22.7 | zoom-in | ~8.0s | **NÃO** |
| beat_D | 254.8 | 266.4 | 11.6 | zoom-in | ~8.0s | **NÃO** |
| beat_11 | 266.4 | 283.2 | 16.8 | zoom-in | ~8.0s | **NÃO** |
| beat_12 | 283.2 | 308.1 | 24.9 | zoom-in | ~8.0s | **NÃO** |
| beat_13 | 308.1 | 342.0 | 33.9 | zoom-in | ~8.0s | **NÃO** |
| beat_14 | 342.0 | 370.7 | 28.7 | zoom-in | ~8.0s | **NÃO** |
| beat_15 | 370.7 | 396.3 | 25.6 | zoom-in | ~8.0s | **NÃO** |
| beat_16 | 396.3 | 415.6 | 19.3 | zoom-in | ~8.0s | **NÃO** |
| beat_17 | 415.6 | 436.7 | 21.1 | zoom-in | ~8.0s | **NÃO** |
| beat_18 | 436.7 | 460.6 | 23.9 | zoom-in | ~8.0s | **NÃO** |
| beat_19 | 460.6 | 482.2 | 21.6 | zoom-in | ~8.0s | **NÃO** |
| beat_20 | 482.2 | 497.5 | 15.3 | zoom-in | ~8.0s | **NÃO** |
| beat_21 | 497.5 | 519.6 | 22.1 | zoom-in | ~8.0s | **NÃO** |
| beat_22 | 519.6 | 538.5 | 18.9 | zoom-in | ~8.0s | **NÃO** |
| beat_23 | 538.5 | 558.6 | 20.1 | zoom-in | ~8.0s | **NÃO** |
| beat_24 | 558.6 | 573.2 | 14.6 | zoom-in | ~8.0s | **NÃO** |
| beat_E | 573.2 | 588.3 | 15.1 | zoom-in | ~8.0s | **NÃO** |
| beat_25 | 588.3 | 613.7 | 25.4 | zoom-in | ~8.0s | **NÃO** |
| beat_26 | 613.7 | 650.2 | 36.5 | zoom-in | ~8.0s | **NÃO** |

(Coluna "start_scale"/"end_scale"/"pan_delta"/"transition" omitidas por linha — são idênticas em todas: `start_scale=1.0`, `end_scale configurado=1.12` mas `end_scale real ≈ 1.0` por causa do bug, `pan_delta=0` sempre, `transition=hard cut` sempre.)

**Resumo:**
```text
TOTAL_VISUAL_SEGMENTS: 30
STATIC_SEGMENTS (percebidos): 30
MOTION_SEGMENTS (configurados): 30
MOTION_SEGMENTS (perceptíveis, medido): 0
ZOOM_IN_SEGMENTS: 30 (configurado) / 0 (perceptível)
ZOOM_OUT_SEGMENTS: 0
PAN_SEGMENTS: 0

AVERAGE_SEGMENT_DURATION: 21.68s
MEDIAN_SEGMENT_DURATION: 21.35s
MAX_SEGMENT_DURATION: 36.5s (beat_26)
MIN_SEGMENT_DURATION: 11.6s (beat_D)

AVERAGE_SECONDS_BETWEEN_VISUAL_EVENTS: 21.68s (só troca de imagem conta hoje)
MAX_SECONDS_WITHOUT_VISUAL_EVENT: 36.5s (beat_26)

PERCENT_TIMELINE_WITH_PERCEPTIBLE_MOTION_ESTIMADO: ~0% (configurado: 100%; real: ~0%, por bug confirmado)
```

## 8. Perceptible Motion Gap

Alvo humano: evento perceptível a cada ≤~7s. Atual real: só a cada ~21,7s em média (troca de imagem), com zero movimento intra-beat. Gap: **cada beat precisa de pelo menos 2-4 eventos perceptíveis internos**, não só a correção do bug.

## 9. Visual Beat vs Retention Beat

Distinção adotada exatamente como proposta: um **Visual Beat** (os 30 já existentes) é o intervalo semântico onde a composição permanece narrativamente válida; um **Retention Beat** é um evento audiovisual perceptível dentro dele. Tipos de evento adotados (determinísticos, sem framework novo): `NEW_IMAGE`, `ZOOM_IN`, `ZOOM_OUT`, `PAN` (reframe simples, deslocando o centro do crop), `CROSSFADE` (transição suave entre dois Retention Beats consecutivos em vez de corte duro). `CAPTION_CHANGE` não é contado como evento visual de retenção (é experiência de leitura, não de imagem) — mantido separado.

Representação escolhida: **campos dentro do `VisualBeat` existente**, não um contrato novo — cada beat ganha uma lista opcional de `retention_segments` (sub-intervalos com seu próprio zoom start/end e pan), sem quebrar o consumidor atual (`render_silent_segment` passa a iterar sub-segmentos quando presentes, e cai no comportamento de 1-segmento-por-beat quando não há).

## 10. Current Image Density

```text
CURRENT_UNIQUE_IMAGES: 30
REUSABLE_IMAGES: 30 (todas aprovadas, nenhuma rejeitada)
VISUAL_BEATS: 30
LONGEST_HOLDS (>25s): beat_26 (36.5s), beat_13 (33.9s), beat_06 (30.5s), beat_03 (29.6s), beat_14 (28.7s)
NARRATIVELY_UNDERSERVED_BEATS: beat_06 (cobre DOIS momentos narrativos distintos — achar a caixa E descrever o relógio),
  beat_03 (cobre a cidade inteira em um só plano por quase 30s), beat_26 (fechamento longo sem variação)
```

## 11. Proposed Image Density

Não adoto 50 como meta rígida. Análise: a maior parte do gap de cadência (§8) é resolvida por **Retention Beats sobre imagens já existentes** (pan/zoom/crossfade), que não custam nada. Imagens novas só onde há valor narrativo real (§13). Proposta:

```text
TARGET_UNIQUE_IMAGES: ~42-45 (30 atuais + 12-15 novas)
```
50 permanece como teto de referência experimental do humano, não uma meta a perseguir cegamente — se a revisão do próximo Human Full Watch ainda achar a cadência insuficiente com ~45, subir para mais perto de 50 é a próxima iteração, não um salto imediato sem evidência.

## 12. New Image Requirements

```text
CURRENT_IMAGES: 30
TARGET_IMAGES: ~42-45
NEW_IMAGES_REQUIRED: ~12-15
EXPECTED_RETRIES: baixo (0/30 no Gate 3D; 0/5 no Gate 3C — histórico real de 0% de falha)
```
**Caminho de execução:** mesmo modelo do Gate 3D — handoff de manifesto de imagem a custo zero para esta sessão (o usuário já demonstrou preferência por esse caminho). Se um dia a geração nativa do ambiente estiver disponível, ela seria preferida (Separation Principle inalterado). **Nenhuma imagem será gerada nesta discovery.**

## 13. Prioritize Where New Images Matter

| Beat | Duração | Por que precisa de imagem nova (não só pan/zoom) |
|---|---|---|
| beat_03 | 29.6s | Cobre "Portovelho" inteira — cidade, rio, serra, casas — um único plano não sustenta 30s sem repetir o mesmo enquadramento; split em 2 planos distintos da cidade |
| beat_06 | 30.5s | Narração muda de assunto no meio (achar a caixa → descrever o relógio) — são 2 ideias visuais, não 1 |
| beat_13 | 33.9s | Beat simbólico/conceitual mais longo do vídeo — 2 variações da metáfora evitam repetição |
| beat_08 | 23.9s | Mariana fotografando — um segundo plano (close nas mãos/documento) reforça a tensão sem nova composição do zero |
| beat_09 | 23.8s | Revelação das assinaturas forjadas — um close-up de uma assinatura específica adiciona informação visual nova |
| beat_12 | 24.9s | Monólogo longo de Elias sobre a dívida — variar o enquadramento evita "cabeça falante" estática |
| beat_18 | 23.9s | Momento de maior vulnerabilidade de Elias — vale um segundo close ainda mais próximo |
| beat_21 | 22.1s | Elias examina o relógio com a lupa — sequência de duas ações (girar o relógio, depois encontrar o espaço vazio) |
| beat_25 | 25.4s | Mariana sozinha na calçada — um segundo plano (mais próximo dela) reforça o momento emocional |
| beat_26 | 36.5s | Plano de fechamento mais longo — 2 imagens numa progressão de luz (entardecer → anoitecer) dão ao encerramento uma sensação de passagem de tempo |

Isso soma **10 pares candidatos = até 10 imagens novas**; os 2-5 restantes até a faixa de 12-15 ficam como margem para o que a implementação real revelar necessário — não decidido a priori sem evidência.

## 14. Burned Caption Analysis

```text
CURRENT_CAPTION_COUNT: 99
AVERAGE_CAPTION_LENGTH: 97.6 caracteres
MAX_CAPTION_LENGTH: 446 caracteres
LONG_CAPTIONS_COUNT (>100 chars): 45 (45% do total)
VERY_LONG (>150 chars): 26 (26% do total)
```
Um cue de 446 caracteres mantido como bloco único na tela por sua duração inteira é ilegível — confirma a necessidade de rechunking antes de queimar.

**Tabela D — Exemplos de Problema:**

| Cue | Duração | Caracteres | Problema | Split proposto |
|---|---|---|---|---|
| #1 | 6.8s | 111 | Acima do confortável para 1 tela | 2 blocos, ~55 chars cada |
| #3 | 13.1s | 210 | Muito longo | 3-4 blocos |
| #7 | 13.0s | 201 | Muito longo | 3 blocos |
| (o de 446 chars) | variável | 446 | Extremamente longo | 6-8 blocos |

## 15. Caption Rendering Strategy

**Reaproveitar 100% os dados de timing existentes** (`narration_full.timing.json`, 99 `SentenceBoundary` já usados para `captions.srt`). Nenhuma nova transcrição, nenhuma chamada de speech-to-text.

**Rechunking determinístico:** para cues acima de ~84 caracteres (2 linhas × 42 chars), dividir em N blocos por contagem de palavras (não por caractere cru, para não cortar no meio de uma palavra), distribuindo a duração do cue original **proporcionalmente à contagem de palavras de cada bloco** — a mesma técnica de "menor abordagem aceitável" já usada no Gate 3 (`build_proportional_timeline`, `lite/timeline.py`) para o problema análogo de sincronizar texto sem timestamp por palavra. **Não inventa precisão de palavra que não existe** — é uma aproximação proporcional, documentada como tal.

**Renderização:** filtro `subtitles` do FFmpeg (biblioteca `libass`, presente no build `Gyan.FFmpeg` já instalado — a verificar na Gate 1 técnica do 3D.1, não presumida) sobre um arquivo `.ass` gerado a partir dos blocos rechunked, com estilo forçado via `force_style`. Uma única chamada de filtro adicional na cadeia FFmpeg já existente — não um novo sistema.

## 16. Caption Chunking

Coberto em §14-15. Resumo da regra: cue > 84 caracteres → dividir por contagem de palavras em blocos de ~2 linhas/~84 chars, tempo redistribuído proporcionalmente.

## 17. Caption Safe Area / Estilo

Contrato mínimo proposto (não um sistema de design):
```text
max_lines: 2
chars_per_line: ~42
position: inferior, margem de ~8% da altura a partir da base (safe area para controles do YouTube/mobile)
font_size: ~4.5% da altura do frame
color: branco, contorno preto (outline) + leve sombra para contraste em qualquer fundo
background_box: nenhum (outline já garante legibilidade sobre o visual existente sem tampar composição)
```

## 18. Background Music Strategy

**Não selecionada nesta discovery** (regra explícita — só um asset local já aprovado poderia ser usado, e não existe nenhum). O plano define o requisito e a estratégia de origem, não a faixa em si:

```text
MUSIC_SOURCE_STRATEGY: faixa royalty-free/licença compatível com publicação no YouTube (ex.: CC0, ou
  biblioteca de áudio do próprio YouTube, ou faixa gerada com direitos de uso claros) — sourcing é um
  passo humano explícito antes da implementação do Gate 3D.1, não decidido/baixado automaticamente aqui.
TRACK_COUNT: 1 (suficiente para 10:50 com loop seguro, conforme o próprio roteiro não muda de tom
  drasticamente — é uma história contida, atmosférica do início ao fim)
```

## 19. Audio Mix Strategy

FFmpeg resolve sozinho (já é o assembler). Cadeia mínima proposta:
```text
narração (já normalizada, ~-20.9dB mean, sem clipping — medido no Gate 3D)
     +
música (volume fixo baixo, ex. -26 a -30dB relativo — abaixo da narração o suficiente para nunca competir)
     ↓
amix + afade in/out na música (2-3s cada ponta) + loop/trim para 650.3s
     ↓
mesma verificação de audibilidade/no-clipping já usada (audio_qa.py, reaproveitado)
```
```text
NARRATION_GAIN: inalterado (já aprovado)
MUSIC_GAIN: fixo, baixo (faixa a calibrar por audição humana antes de finalizar o número exato)
PEAK_HEADROOM: manter max_volume final ≤ -1dBTP (mesmo padrão já usado)
```

## 20. Ducking

**Adiado**, conforme autorizado explicitamente pela regra 22 do briefing — nível fixo baixo de música é aceitável para o Gate 3D.1. Ducking dinâmico (sidechain) só se a revisão humana do próximo render ainda apontar a música como intrusiva em momentos de fala.

## 21. Experience QA

Cada candidato do briefing, criticado antes de adotar:

| Check | Adotar? | Motivo |
|---|---|---|
| `BURNED_CAPTIONS_PRESENT` | **Adotar, mas como check de processo, não de pixel** | Verificar deteção de pixel exigiria heurística de OCR/CV, fora de escopo (regra 24/38). Verificação real: o comando FFmpeg incluiu o filtro `subtitles` e terminou com sucesso, e o tamanho do arquivo final mudou de forma consistente com a queima. |
| `BACKGROUND_MUSIC_PRESENT` | **Adotar, como comparação de nível de áudio** | Comparar `mean_volume`/espectro do áudio final contra uma referência "só narração" já conhecida (do próprio Gate 3D) — se o nível/energia média subiu de forma consistente com uma faixa musical, é evidência suficiente sem fingerprinting de áudio. |
| `TOTAL_UNIQUE_IMAGES >= alvo` | Adotar | Trivial — contagem de arquivos. |
| `MAX_SECONDS_WITHOUT_VISUAL_EVENT <= limiar` | **Adotar** | Computável diretamente da configuração da timeline (Retention Beats), antes mesmo de renderizar — determinístico. |
| `MOTION_SEGMENT_COVERAGE >= limiar` | **Adotar** | Proxy de parâmetro (§25) — computável sem renderizar. |
| `TIMELINE_VISUAL_COVERAGE = 100%` | Adotar (já existe) | `validate_plan_coverage`, reaproveitado sem mudança. |
| `CAPTION_SAFE_AREA_VALID` | Adotar, como validação de configuração | Checar que os parâmetros de estilo (margem, tamanho) estão dentro dos limites definidos em §17 — não detecção de pixel. |
| `AUDIO_MIX_VALID` | Adotar (extensão do já existente) | Reaproveita `audio_qa.py`; adiciona checagem de que o nível final está dentro da faixa esperada. |

## 22. Do Not Fake Aesthetic QA

Nenhum check acima tenta provar "bonito"/"envolvente"/"cinematográfico". O Human Full Watch continua sendo a única autoridade sobre isso.

## 23. Perceptible Motion QA — Proxy Determinístico

Proposta central, derivada diretamente da evidência empírica deste postmortem (§6):
```text
zoom_rate_per_second = abs(end_scale - start_scale) / segment_duration_seconds
```
No teste decisivo (§6), a receita **quebrada** tinha `zoom_rate_per_second` nominal de `0,015` (0,0006×25fps) mas produzia `YAVG≈0,01` (imperceptível); a receita **corrigida**, com o mesmo `zoom_per_frame`, produziu `YAVG≈25` porque a progressão realmente aconteceu. Ou seja, o proxy de parâmetro só é confiável **depois** de corrigir o bug de alimentação do filtro (§6) — não é suficiente sozinho, mas passa a ser um bom proxy uma vez que a causa raiz esteja corrigida (validado por este mesmo teste lado a lado).

**Piso mínimo proposto:** `zoom_rate_per_second >= 0,004` (0,4%/s) por Retention Beat — calibrado para produzir, num beat de 7s, um delta de zoom de ~2,8%, próximo da faixa que o teste da receita clássica mostrou claramente perceptível em 7-8s.

## 24. Do Not Add Computer Vision

Nenhum CLIP/embedding/reconhecimento facial/crítico de visão computacional foi proposto — todos os checks de §21/§23 operam sobre parâmetros de configuração ou métricas de sinal já usadas no projeto (`ffprobe`/`volumedetect`/`signalstats`), consistente com o padrão já estabelecido desde o Gate 2.

## 25. Motion Floor

```text
MIN_ZOOM_RATE_PER_SECOND: 0.004 (0.4%/s) — ver §23
MAX_TOTAL_ZOOM_PER_RETENTION_BEAT: ~15-18% — acima disso o movimento deixa de parecer "contido" (evidência
  qualitativa: um zoom de 1.0→1.3+ ao longo de 30s+ tende a ficar dramático demais para o tom melancólico
  da história — por isso beats >25s são candidatos a split em vez de zoom esticado)
RETENTION_BEAT_TARGET_DURATION: ~7-10s (não uma regra rígida — beats emocionais/contemplativos podem manter
  um único Retention Beat mais longo se o zoom cobrir toda a duração dentro do teto de 15-18%)
```
Esses números partem diretamente da evidência do vídeo atual (§6-7), não são arbitrários.

## 26. Reuse Plan

| Ativo | Reuso |
|---|---|
| Roteiro aprovado, narração completa, Voz C | 100% reaproveitados, intocados |
| Visual Bible (v2 endurecida) | 100% reaproveitada, intocada |
| 30 imagens já aprovadas | 100% reaproveitadas — nenhuma regeneração |
| `narration_full.timing.json` (99 boundaries) | Reaproveitado para captions rechunked, sem nova transcrição |
| `GATE3D_FULL_VISUAL_PLAN` (30 beats) | Reaproveitado como esqueleto — ganha `retention_segments` opcionais, sem quebrar a forma atual |
| `render_silent_segment`/`concat_segments`/`mux_video_audio` | Reaproveitados; só `render_silent_segment` recebe a correção de causa raiz + suporte a sub-segmentos |
| `image_qa.py`, `audio_qa.py`, `qa.py` | Reaproveitados como estão |
| Pipeline de handoff de imagem (Gate 3D) | Reaproveitado para as ~12-15 imagens novas |

## 27. Minimal Code Changes (não implementadas nesta discovery)

1. `render_silent_segment`: trocar a alimentação do zoompan (remover `-framerate`, usar `d=duration*fps`) — corrige o bug.
2. `render_silent_segment` (ou uma nova função irmã): aceitar uma lista de Retention Beats por Visual Beat, cada um com seu próprio zoom start/end e crop offset (pan), concatenando internamente antes do beat inteiro entrar no concat global.
3. `visual_beats.py`/`visual_plan_gate3d.py`: campo opcional `retention_segments` em `VisualBeat` (não quebra os consumidores atuais).
4. `captions.py`: função de rechunking proporcional por contagem de palavras + geração de `.ass` com o estilo de §17.
5. Novo módulo pequeno para mixagem de música (chamada FFmpeg `amix`+`afade`, reaproveitando o padrão já usado).
6. Extensão de `qa.py`/novo `experience_qa.py` com os checks de §21/§23.

Nenhuma dessas mudanças toca `agents/`, `interfaces/`, `domain/` (Advanced permanece congelado).

## 28. Tests (a adicionar na implementação, não agora)

- Teste de regressão do bug do zoompan: medir diferença de pixel real entre t=0 e t=N de um segmento renderizado, exigir acima do piso do §23 (o teste que **não existia** e teria pego este bug).
- Teste de rechunking de legenda: cues > 84 chars são divididos; nenhuma palavra cortada; soma das durações dos blocos = duração do cue original.
- Teste de `retention_segments`: soma das durações dos sub-segmentos = duração do beat; zoom contínuo entre sub-segmentos (sem salto brusco de escala).
- Teste de nível de música: `mean_volume` da música isolada fica abaixo de um teto relativo à narração.
- Teste de Experience QA: cada check novo, testado isoladamente com fixtures pequenas (mesmo padrão já usado em `test_gate3b2_units.py`/`test_gate3c_units.py`).

## 29. Cost Estimate

```text
NEW_IMAGES_REQUIRED: ~12-15
IMAGE_GENERATION_METHOD: handoff a custo zero para esta sessão (mesmo modelo do Gate 3D),
  a menos que geração nativa do ambiente seja confirmada disponível
EXTERNAL_API_COST (se chamada direta desta sessão for escolhida no futuro): ~US$0,24-3,00
  (mesma faixa por imagem do Gate 3D, 12-15 unidades) — só se o usuário optar por não usar handoff
MUSIC_COST: US$0 esperado (fontes royalty-free/CC0) — a confirmar na etapa de sourcing humano
```
Nenhuma chamada paga foi feita nesta discovery.

## 30. Risks

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Correção do zoompan introduzir instabilidade de encode (mudança de forma de alimentar o filtro) | Baixa | Média | Testar com o mesmo par de imagens de teste deste postmortem antes de aplicar aos 30 beats reais |
| Retention Beats tornarem o vídeo "hiperativo" | Baixa-média | Alta (tom da história é contido) | Teto de 15-18% de zoom total por Retention Beat (§25), sem cortes a cada 2s |
| Legendas queimadas cobrirem composição importante | Baixa | Média | Safe area de 8% + outline sem caixa de fundo opaca (§17) |
| Música competir com narração | Média (é o risco central de qualquer mixagem) | Alta | Nível fixo baixo + verificação objetiva de mix (§19/§21); ducking como próxima iteração se necessário |
| ~12-15 imagens não bastarem para o próximo Human Full Watch | Média | Baixa (é barato iterar) | Registrar explicitamente que 50 é o teto de referência, não descartado — próxima rodada pode subir a densidade se a evidência pedir |

## 31. Gate 3D.1 Acceptance Criteria

```text
Legendas queimadas em português: OBRIGATÓRIO
SRT sidecar: MANTIDO no bundle
Música de fundo: OBRIGATÓRIA, volume claramente abaixo da narração
Inteligibilidade da narração: OBRIGATÓRIA (sem clipping, sem mascaramento pela música)
Movimento visual perceptível: OBRIGATÓRIO, medido via proxy de §23
Cadência de evento visual: MAX_SECONDS_WITHOUT_VISUAL_EVENT <= ~7-10s (ver §25 sobre exceções contemplativas)
Contagem de imagens únicas: ~42-45 (não < 40), 50 como teto de referência
Resolução final: 1920x1080 (inalterado)
Duração: ~igual à narração aprovada, 650.3s (inalterado)
Human Full Watch: OBRIGATÓRIO, mesma pergunta do §35 do briefing
```

## 32. Implementation Plan (ordem recomendada, não executada agora)

1. Corrigir o bug do zoompan isoladamente; provar com o mesmo teste de diferença de pixel deste postmortem.
2. Estender `VisualBeat`/render para Retention Beats; re-renderizar os 30 beats existentes (zero imagens novas) e medir a cobertura de movimento.
3. Handoff das ~12-15 imagens novas (mesmo modelo de custo zero); inserir nos beats identificados em §13.
4. Implementar rechunking de legenda + renderização `.ass` queimada.
5. Sourcing humano da faixa de música (fora do escopo de código) + mixagem.
6. Implementar os novos checks de Experience QA.
7. Rerender completo → novo `runs/<id>-gate3d1/` (Gate 3D preservado como linha de base).
8. Human Full Watch novamente.

## 33. Explicit Non-Goals

Upload no YouTube, analytics, SEO engine, múltiplas thumbnails, motor de efeitos sonoros, vídeo generativo, personagens animados, lip sync, busca de B-roll/stock, infraestrutura cloud, integração com o Advanced, agent swarm, Music Agent/Composer/Swarm, sistema de design de legendas, CV/reconhecimento facial.

## 34. Recommendation

Prosseguir para a implementação do Gate 3D.1 na ordem do §32, começando pela correção do bug (item 1) — é a mudança de menor risco e maior impacto, e pode ser validada isoladamente antes de tocar em qualquer outro componente.

---

## VEREDITO FINAL OBRIGATÓRIO

```text
GATE_3D_TECHNICAL_STATUS: PASS
GATE_3D_HUMAN_STATUS: PASS_WITH_NOTES
YOUTUBE_LITE_E2_STATUS: NOT_PROVEN_YET

CURRENT_VIDEO_DURATION: 650.3s (10:50)
CURRENT_UNIQUE_IMAGES: 30
CURRENT_AVG_SECONDS_PER_IMAGE: 21.68s

KEN_BURNS_CONFIGURED: SIM
KEN_BURNS_PRESENT_IN_FINAL_RENDER: SIM (comando executado sem erro, "zoom" tecnicamente presente na config)
KEN_BURNS_PERCEPTIBLE: NÃO (medido: YAVG≈0.01-0.03 entre frames distantes, vs. YAVG≈25 numa receita correta com os mesmos parâmetros)
KEN_BURNS_ROOT_CAUSE: uso incorreto do filtro zoompan — `-framerate {fps}` sobre `-loop 1` combinado com `d=1`
  quebra a progressão do estado interno de zoom; o padrão correto é frame único de entrada + `d=<frames totais>`

CURRENT_MOTION_COVERAGE: ~0% perceptível (100% configurado, 0% real)
CURRENT_MAX_SECONDS_WITHOUT_VISUAL_EVENT: 36.5s (beat_26)
CURRENT_AVG_SECONDS_BETWEEN_VISUAL_EVENTS: 21.68s

RETENTION_BEAT_CONCEPT_REQUIRED: SIM
RETENTION_BEAT_IMPLEMENTATION_RECOMMENDATION: campo opcional `retention_segments` dentro do `VisualBeat`
  existente (sem contrato novo separado); eventos determinísticos NEW_IMAGE/ZOOM_IN/ZOOM_OUT/PAN/CROSSFADE

TARGET_MAX_SECONDS_WITHOUT_VISUAL_EVENT: ~7-10s (exceções contemplativas justificadas caso a caso)

CURRENT_UNIQUE_IMAGE_COUNT: 30
RECOMMENDED_UNIQUE_IMAGE_COUNT: ~42-45 (50 como teto de referência, não meta rígida)
NEW_IMAGES_REQUIRED: ~12-15
NEW_IMAGES_COST_ESTIMATE: US$0 se via handoff (recomendado, mesmo modelo do Gate 3D); ~US$0,24-3,00 se API direta
PAID_GENERATION_AUTHORIZATION_REQUIRED: SIM, se a API direta for escolhida no lugar do handoff

CURRENT_CAPTIONS_SIDECAR: SIM (99 cues, mantido no bundle)
BURNED_CAPTIONS_REQUIRED: SIM
CAPTION_RECHUNKING_REQUIRED: SIM (45% dos cues >100 chars, 26% >150 chars — ilegíveis como bloco único)
PROPOSED_CAPTION_STYLE: 2 linhas, ~42 chars/linha, margem inferior ~8%, branco com contorno preto, sem caixa opaca

BACKGROUND_MUSIC_REQUIRED: SIM
MUSIC_SOURCE_STRATEGY: royalty-free/licença compatível — sourcing humano explícito antes da implementação, não decidido nesta discovery
DUCKING_REQUIRED: NÃO (adiado — nível fixo baixo é aceitável para o Gate 3D.1)
PROPOSED_MUSIC_LEVEL_STRATEGY: nível fixo baixo (-26 a -30dB relativo), fade in/out, sem sidechain

EXISTING_IMAGES_REUSABLE: SIM (30/30)
EXISTING_NARRATION_REUSABLE: SIM (100%)
EXISTING_TIMINGS_REUSABLE: SIM (99 boundaries, base do rechunking de legenda)
EXISTING_TIMELINE_REUSABLE: SIM (GATE3D_FULL_VISUAL_PLAN como esqueleto, estendido com retention_segments)
CURRENT_MP4_PRESERVED: SIM (runs/20260823T223458Z-gate3d-planning/ intocado, linha de base para comparação)

MINIMAL_CODE_CHANGES: 6 pontos, listados em §27 — todos isolados em `lite/`, nenhum toca Advanced
NEW_TESTS_REQUIRED: SIM — 5 áreas listadas em §28, incluindo o teste de regressão do bug do zoompan
EXPERIENCE_QA_CHECKS: 8 candidatos avaliados em §21, todos adotados com implementação determinística (sem CV/fingerprinting de áudio)

GATE_3D1_SCOPE: legendas queimadas + movimento perceptível real + cadência de retenção + densidade de imagem
  ampliada + música de fundo + mixagem + Experience QA + rerender + Human Full Watch — nada além disso
GATE_3D1_ACCEPTANCE_CRITERIA: §31

READY_TO_IMPLEMENT_GATE_3D1: SIM
BLOCKERS: sourcing humano da faixa de música (não pode ser decidido/baixado automaticamente); decisão sobre
  handoff vs. API direta para as ~12-15 imagens novas (mesma escolha já feita uma vez no Gate 3D)

BIGGEST_MOTION_RISK: a correção do zoompan, sem o teste de regressão de pixel, pode voltar a quebrar
  silenciosamente em uma mudança futura — por isso o teste de §28 é P0, não opcional
BIGGEST_CAPTION_RISK: rechunking por contagem de palavras é uma aproximação, não timing real por palavra —
  pode ocasionalmente cortar em um ponto levemente antecipado/atrasado dentro de uma frase longa
BIGGEST_MUSIC_RISK: nível calibrado sem audição humana prévia pode ficar alto ou baixo demais na primeira tentativa
BIGGEST_RETENTION_RISK: over-correção (movimento demais) contradiria o tom "contido" da história — mitigado pelo teto de §25
BIGGEST_COST_RISK: baixo — handoff a custo zero já provado funcionar uma vez; risco só existe se a API direta for escolhida

RECOMMENDED_NEXT_ACTION: implementar a correção do bug do zoompan primeiro e isoladamente (§32, item 1),
  validá-la com o teste de diferença de pixel, e só então prosseguir para Retention Beats/imagens novas/legendas/música

DISCOVERY_VERDICT: READY_FOR_GATE_3D1_IMPLEMENTATION
```
