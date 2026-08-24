# YOUTUBE LITE — GATE 3B.2 FULL NARRATION REPORT

## 1. Executive Summary

Gate 3B.2 provou, tecnicamente, que a Voz C (edge-tts, `pt-BR-AntonioNeural`) sustenta a narração **completa** do roteiro aprovado — não só os 95s do bake-off. Nenhum novo bake-off foi feito; a configuração exata da voz C (rate/pitch/volume padrão, sem alteração) foi preservada e verificada. O hash do roteiro aprovado foi recalculado e conferido contra o hash registrado no Gate 3B antes de qualquer síntese — sem drift. A narração completa foi gerada numa única chamada (sem necessidade de segmentação): **650,3s (~10,84 min) reais**, dentro da faixa 10-15min, **155 palavras/minuto reais** (a estimativa do Gate 3A previa 673,6s — diferença de apenas ~3,5%). Completeness check: 99 `SentenceBoundary` == 99 sentenças do roteiro, primeira e última sentença confirmadas presentes, último boundary alinhado à duração real do arquivo — nenhum truncamento silencioso. Três recortes de revisão distribuída (início/meio/fim, ~75-77s cada) foram extraídos **do áudio completo real** via FFmpeg (nunca resintetizados), alinhados a fronteiras de sentença. `edge-tts` foi formalizado em `pyproject.toml` como dependência **E2-approved**, explicitamente **não** E4/produção, com risco registrado. Gate 3C permanece bloqueado; nenhuma imagem foi gerada; nenhum vídeo foi montado. Advanced legacy intocado; 178/178 testes passam.

## 2. Human Voice Selection

Registrada formalmente: `HUMAN_SELECTED_VOICE = C` (edge-tts, `pt-BR-AntonioNeural`), decisão humana do Gate 3B, não reaberta nesta execução. Nenhuma nova voz foi testada, nenhum novo provider foi adicionado, nenhuma comparação A/B/C foi refeita.

## 3. Selected Voice Configuration

```json
{
  "provider": "external_api:edge_tts",
  "voice": "pt-BR-AntonioNeural",
  "rate": "+0%",
  "pitch": "+0Hz",
  "volume": "+0%",
  "boundary": "SentenceBoundary",
  "output_format": "mp3 (edge-tts default)"
}
```
Idêntica à usada para `voice_C.mp3` no Gate 3B — nenhum parâmetro alterado silenciosamente.

## 4. Approved Script Integrity

Hash recalculado (`content_hash`) do `script_approved.md` e comparado ao `APPROVED_SCRIPT_HASH` registrado no `run_manifest.json` do Gate 3B (`sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1`) **antes** de qualquer síntese — coincidência confirmada, execução prosseguiu. Nenhuma reescrita, expansão, resumo, correção ou alteração de pontuação foi feita.

## 5. TTS Normalization

Investigado: o roteiro aprovado não contém headers, ênfase Markdown, listas ou links — é texto falável desde a origem. Decisão registrada: **nenhuma transformação criada** (`speakable_script.txt` não gerado), evitando trabalho desnecessário, conforme instruído.

## 6. Full Narration Generation

Síntese numa única chamada (`EdgeTtsNarrationStrategy(voice="pt-BR-AntonioNeural").synthesize`), 1684 palavras, sem segmentação — não foi necessária. Tempo de geração: ~56s (streaming de rede, não tempo real de fala). Artefato: `narration_full.mp3`.

## 7. Segmentation, if any

**Não houve segmentação.** O texto completo foi sintetizado numa única requisição `edge-tts`, sem necessidade de dividir em chunks.

## 8. Real Duration

**650,3 segundos (~10,84 minutos)**, medidos via `ffprobe` — fonte de verdade, substituindo a estimativa pré-TTS do Gate 3A.

## 9. Words Per Minute

- Estimativa do Gate 3A: 150 wpm (assumido).
- Real: **155 wpm** (1684 palavras / 10,84 min).
- Diferença de duração: -23,3s em relação à estimativa (673,6s → 650,3s), **-3,5%** — bem dentro de qualquer margem razoável, sem necessidade de decisão editorial sobre duração.

## 10. Timing Data

`narration_full.timing.json`: 99 eventos `SentenceBoundary`, cada um com `index`, `text`, `offset_100ns`/`duration_100ns` (formato nativo do provider, preservado) e `start_seconds`/`end_seconds` (derivados, não inventando precisão além da fornecida). Preservado como patrimônio para consumidores futuros (captions, visual beats, timeline) — **nenhum desses consumidores foi implementado nesta execução**.

## 11. Completeness Validation

| Check | Resultado |
|---|---|
| Contagem de boundaries vs. sentenças do roteiro (`sentence_split`) | 99 == 99 |
| Primeira sentença do roteiro presente no primeiro boundary | SIM |
| Última sentença do roteiro presente no último boundary | SIM |
| Último boundary (650,25s) alinhado à duração real do arquivo (650,30s) | SIM (diferença 0,06s, bem dentro da tolerância) |
| **Veredito de completude** | **PASS — sem truncamento silencioso** |

## 12. Objective Audio QA

```json
{
  "duration_seconds": 650.3,
  "sample_rate": "medido via ffprobe",
  "channels": 1,
  "codec": "mp3",
  "mean_volume_db": "acima do limiar de silêncio",
  "max_volume_db": "≤ 0dB — sem clipping",
  "audible": true,
  "no_obvious_clipping": true
}
```
Valores completos em `runs/20260823T200332Z-gate3b2-full-narration/working/audio_qa.json`. Nenhum "quality score" algorítmico — só descarte de falha técnica óbvia (nenhuma ocorreu).

## 13. Distributed Review Samples

`review_beginning.mp3` (~75,5s), `review_middle.mp3` (~77,0s), `review_end.mp3` (~77,0s) — todos **recortes reais** de `narration_full.mp3` via FFmpeg (`-c:a libmp3lame`, sem re-síntese), com pontos de corte alinhados às fronteiras de sentença mais próximas dos alvos (nunca cortando no meio de uma frase). O áudio completo também foi disponibilizado para quem preferir ouvir tudo.

## 14. Costs

```text
external_api_cost: 0.00 USD
network_required: SIM (edge-tts)
direct_paid_api_used: NÃO
observable_external_api_cost: 0.00 USD
execution_environment: claude_code (local) + rede (síntese)
```

## 15. Dependencies

`edge-tts` **formalizado em `pyproject.toml`** sob o novo extra `lite` (`edge-tts>=7.2,<8`), com comentário explícito classificando-a como dependência **E2-approved**, não E4/produção. Nenhuma dependência transitiva foi adicionada manualmente (`pip` resolveu as próprias, já instaladas no Gate 3B). `Advanced` não foi afetado — o extra `lite` é isolado dos demais grupos (`api`, `parsers`, `dev`, `docs`) e não está incluído em `all`.

## 16. Tests

`tests/lite/test_gate3b2_units.py` — 10 testes novos, todos auditando a execução real mais recente (via glob dinâmico, não um `run_id` hardcoded frágil): integridade de hash, configuração da voz preservada, existência e duração do áudio completo, timing parseável e monotônico, alinhamento último-boundary/duração, completude (primeira/última sentença, contagem de boundaries), recortes de revisão existentes e não vazios, e confirmação de que nenhum artefato de imagem/vídeo/bundle foi produzido. Nenhum teste tenta medir naturalidade.

## 17. Risks

```text
RISK: edge-tts depende de um serviço de rede não contratual da Microsoft (não é uma API pública documentada/garantida).
E2: ACCEPTED — custo zero observável, qualidade validada por bake-off + prova de escala.
E4: MUST_REEVALUATE — antes de produção, considerar uma API com SLA formal (ex.: Azure Cognitive Services Speech, mesmo motor de voz, contrato pago).
```
Registrado em `docs/youtube-lite/SDD_SPDD.md` §43.10, não resolvido (por design — fora de escopo deste gate).

## 18. Human Review Package

`HUMAN_FULL_NARRATION_REVIEW.md` + 3 recortes + áudio completo enviados ao usuário. Pergunta central: *"Essa mesma voz continua boa quando deixa de narrar 95 segundos e passa a carregar a história inteira?"* Veredito pendente no momento deste relatório.

## 19. Architecture Drift

```text
LEGACY_ORCHESTRATOR_USED: NÃO
GATE_3C_STARTED_PREMATURELY: NÃO
IMAGES_GENERATED_PREMATURELY: NÃO
FULL_VIDEO_GENERATED_PREMATURELY: NÃO
```

## 20. Gate Verdict

Ver bloco obrigatório abaixo.

---

## VEREDITO FINAL OBRIGATÓRIO

```text
GATE_3A_STATUS: PASS
GATE_3B_BAKEOFF_STATUS: PASS
GATE_3B_HUMAN_SELECTION: C

SELECTED_CANDIDATE: C
SELECTED_PROVIDER: external_api:edge_tts
SELECTED_VOICE: pt-BR-AntonioNeural
SELECTED_CONFIGURATION_PRESERVED: SIM (rate=+0%, pitch=+0Hz, volume=+0%, boundary=SentenceBoundary — idêntico ao bake-off)

APPROVED_SCRIPT_PATH: runs/20260823T185859Z-gate3a-script/working/script.md
APPROVED_SCRIPT_HASH: sha256:c7a0209f470f1f8677e05ac77639ea7fefae14278f95722270bea7cc8fc979d1
SCRIPT_HASH_VERIFIED: SIM

FULL_NARRATION_GENERATED: SIM
FULL_NARRATION_PATH: runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.mp3

FULL_NARRATION_DURATION_SECONDS: 650.3
FULL_NARRATION_DURATION_FORMATTED: 10:50
SCRIPT_WORD_COUNT: 1684
ACTUAL_WORDS_PER_MINUTE: 155
GATE_3A_ESTIMATED_DURATION_SECONDS: 673.6
ESTIMATE_ERROR_PERCENT: -3.5
DURATION_STATUS: WITHIN_TARGET

TTS_SEGMENTED: NÃO
TTS_SEGMENT_COUNT: 1 (chamada única)

TIMING_DATA_PRESERVED: SIM
TIMING_BOUNDARY_COUNT: 99
TIMING_LAST_BOUNDARY_SECONDS: 650.25
TIMING_AUDIO_ALIGNMENT_STATUS: PASS (diferença de 0.06s frente à duração real do arquivo)

COMPLETENESS_CHECK: PASS (99/99 sentenças; primeira e última sentença confirmadas; sem truncamento)
AUDIO_QA_STATUS: PASS
MEAN_VOLUME_DB: acima do limiar de silêncio (ver audio_qa.json)
MAX_VOLUME_DB: ≤ 0dB (sem clipping)
SAMPLE_RATE: ver audio_qa.json
CHANNELS: 1
CODEC: mp3

REVIEW_BEGINNING_PATH: runs/20260823T200332Z-gate3b2-full-narration/assets/narration/review_beginning.mp3
REVIEW_MIDDLE_PATH: runs/20260823T200332Z-gate3b2-full-narration/assets/narration/review_middle.mp3
REVIEW_END_PATH: runs/20260823T200332Z-gate3b2-full-narration/assets/narration/review_end.mp3
HUMAN_FULL_NARRATION_REVIEW_PATH: runs/20260823T200332Z-gate3b2-full-narration/output/HUMAN_FULL_NARRATION_REVIEW.md

EDGE_TTS_DEPENDENCY_STATUS: E2-approved narration dependency (formalizada em pyproject.toml, extra `lite`); NÃO E4/produção
NETWORK_REQUIRED: SIM
DIRECT_PAID_API_USED: NÃO
EXTERNAL_API_COST: 0.00 USD

TESTS_ADDED: 10
TESTS_PASSING: 178/178 (168 herdados + 10 novos)

ADVANCED_MODE_UNTOUCHED: SIM
LEGACY_ORCHESTRATOR_USED: NÃO
GATE_3C_STARTED_PREMATURELY: NÃO
IMAGES_GENERATED_PREMATURELY: NÃO
FULL_VIDEO_GENERATED_PREMATURELY: NÃO

TECHNICAL_FULL_NARRATION_PASS: SIM
HUMAN_REVIEW_REQUIRED: SIM — pacote já enviado ao usuário, veredito pendente no momento deste relatório

READY_FOR_HUMAN_FULL_NARRATION_REVIEW: SIM
READY_TO_CLOSE_GATE_3B: CONDICIONAL — depende do veredito humano deste gate
READY_FOR_GATE_3C: NÃO — BLOCKED_PENDING_HUMAN_VOICE_SCALE_PASS

BIGGEST_VOICE_SCALE_RISK: fadiga de escuta ao longo de 10+ minutos não pode ser totalmente extrapolada de 3 recortes de ~75s cada — o áudio integral foi disponibilizado para quem quiser confirmar ouvindo tudo
BIGGEST_TIMING_RISK: granularidade é por sentença (SentenceBoundary), não por palavra — suficiente para captions/timeline básicos no futuro, mas não para sincronização fina se algum dia for exigida
BIGGEST_DEPENDENCY_RISK: edge-tts continua sendo um serviço não contratual — aceito para E2, precisa reavaliação antes de qualquer decisão de E4 (registrado, não resolvido)

RECOMMENDED_NEXT_ACTION: Aguardar HUMAN_PASS/HUMAN_PASS_WITH_NOTES/HUMAN_FAIL sobre a narração completa; se aprovada, Gate 3C (Visual Bible Lite + 5 imagens reais) pode ser autorizado

GATE_VERDICT: GATE_3B2_PASS_PENDING_HUMAN
```
