# YOUTUBE LITE — GATE 3B VOICE BAKE-OFF REPORT

## 1. Executive Summary

Gate 3B (Voice Quality) foi implementado como um bake-off real de 3 candidatos narrando **exatamente o mesmo trecho** (238 palavras, extraído literalmente do roteiro aprovado no Gate 3A). O roteiro foi congelado com hash (`script_approved.md`) antes de qualquer síntese. Investigação prática de candidatos: SAPI5 Desktop (baseline, já conhecido do Gate 2), Windows OneCore (**investigado e rejeitado** — vozes listadas no registro do Windows, mas sem os pacotes de dados neurais instalados, confirmado via a API real, não por suposição) e `edge-tts` (instalado, testado, 2 vozes pt-BR usadas). Os 3 candidatos foram sintetizados com sucesso, medidos objetivamente via `ffprobe`/`volumedetect`, e nomeados de forma cega (`voice_A/B/C`) para reduzir viés. Nenhuma escolha foi feita automaticamente — o pacote foi enviado ao usuário para audição comparativa real, aguardando `HUMAN_PASS`/`HUMAN_PASS_WITH_NOTES`/`HUMAN_FAIL`. O roteiro completo **não** foi sintetizado; nenhuma imagem foi gerada; Gate 3C permanece bloqueado. Advanced legacy segue congelado; 167/167 testes passam.

## 2. Gate 3A Human Approval

Confirmado antes de qualquer implementação: `GATE_3A_HUMAN = PASS` registrado em `docs/youtube-lite/SDD_SPDD.md` §38.7. O roteiro aprovado (`runs/20260823T185859Z-gate3a-script/working/script.md`) foi lido integralmente e usado, sem alteração substancial, como fonte única do trecho de teste.

## 3. SDD/SPDD Updates

`docs/youtube-lite/SDD_SPDD.md` atualizado para v0.3: `GATE_3A_HUMAN = PASS` registrado (§38.7); backlog técnico P1 "Editorial / Causal Consistency Critic" registrado (§38.8, não implementado); nova **PART VI — GATE 3B: VOICE BAKE-OFF** (§43), incluindo a formalização de `LOCAL_FIRST != OFFLINE_ONLY` com tabela de proveniência por candidato, investigação de candidatos (incluindo a rejeição documentada do Windows OneCore), composição final do bake-off, extensão do `NarrationPort`, timing data e QA objetiva.

## 4. Approved Script Preservation

`script_approved.md` (cópia byte-idêntica do roteiro do Gate 3A) escrito em `runs/<gate3b_run_id>/input/script_approved.md`, com hash `content_hash` (SHA-256, prefixado `sha256:`) registrado no `run_manifest.json`. Nenhuma reescrita foi feita.

## 5. Test Excerpt

Extraído literalmente (parágrafos 9, 11, 13, 15, 17 do roteiro aprovado — contíguos, índices `[4:9]` na lista separada por linha em branco), salvo em `voice_test_excerpt.txt`: 238 palavras, ~95,2s estimados. Cobertura confirmada: descrição de cena, transição narrativa, diálogo curto ("Elias não negou.") e longo, suspense, nomes próprios (Elias, Mariana, Portovelho), número (1986), pausa natural entre parágrafos, pergunta final. Nenhuma reescrita, resumo ou remoção para favorecer qualquer candidato.

## 6. Candidate Discovery

| Candidato investigado | Resultado | Evidência |
|---|---|---|
| SAPI5 Desktop (`Microsoft Maria Desktop`) | Disponível (já confirmado no Gate 2) | Usado como baseline (A) |
| Windows OneCore (`Microsoft Maria`, `Microsoft Daniel`, pt-BR) | **Investigado e rejeitado** | Tokens existem em `HKLM:\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens`, mas `Windows.Media.SpeechSynthesis.SpeechSynthesizer.AllVoices.Count = 0` via WinRT real — pacotes de voz não instalados, só o registro |
| `edge-tts` | Disponível | `pip install edge-tts` (7.2.8), `python -m edge_tts --list-voices` → 3 vozes pt-BR (`AntonioNeural`, `FranciscaNeural`, `ThalitaMultilingualNeural`); 2 usadas (B, C) |

Não foi feito benchmark de dez providers — 3 candidatos totais, conforme escopo do gate.

## 7. Candidate Generation

Todos os 3 candidatos sintetizaram o **mesmo texto** (hash idêntico, verificado programaticamente — `test_all_candidates_used_the_same_text`) com sucesso:

| Candidato | Provider real (não revelado no pacote humano) | Duração real | Tempo de geração |
|---|---|---|---|
| A | `local:sapi5`, voz `Microsoft Maria Desktop` | 128,34s | medido, ver `voice_candidates.json` |
| B | `external_api:edge_tts`, voz `pt-BR-FranciscaNeural` | 86,18s | idem |
| C | `external_api:edge_tts`, voz `pt-BR-AntonioNeural` | 102,10s | idem |

Nota: a mesma quantidade de palavras produziu durações bem diferentes por candidato — informação relevante para a decisão editorial de ritmo, não uma falha.

## 8. Objective Audio QA

Via `ffprobe`/`volumedetect` (`src/pedroarte_youtube_engine/lite/audio_qa.py`):

```json
{
  "A": {"duration_seconds": 128.34, "sample_rate": 22050, "channels": 1, "codec": "pcm_s16le", "file_size_bytes": 5659842, "mean_volume_db": -23.5, "max_volume_db": -4.3},
  "B": {"duration_seconds": 86.18, "sample_rate": 24000, "channels": 1, "codec": "mp3", "file_size_bytes": 517104, "mean_volume_db": -18.7, "max_volume_db": -3.1},
  "C": {"duration_seconds": 102.1, "sample_rate": 24000, "channels": 1, "codec": "mp3", "file_size_bytes": 612576, "mean_volume_db": -21.1, "max_volume_db": -3.6}
}
```
Nenhum "quality score" foi calculado — essas métricas só descartariam falha técnica óbvia (nenhuma ocorreu). Todos os 3 arquivos abrem, têm áudio, volume audível (`mean_volume_db` bem acima do limiar de silêncio) e sem clipping (`max_volume_db < 0dB` em todos).

## 9. Timing Capabilities

`edge-tts` forneceu `SentenceBoundary` events para B e C, salvos em `voice_B.timing.json`/`voice_C.timing.json` (offset/duração/texto por sentença). SAPI5 (A) não forneceu nada equivalente pelo caminho usado (subprocess via `System.Speech`, que descarta eventos de progresso). Não foi um critério de eliminação — só registrado quando disponível, como instruído.

## 10. Costs

```text
external_api_cost: 0.00 USD (edge-tts não usa API key nem cobra)
network_required: SIM para B e C (edge-tts); NÃO para A (SAPI5)
external_api_direct_call: NÃO (edge-tts é um serviço público sem autenticação — não uma "API key" chamada diretamente)
execution_environment: claude_code (local) + rede (só para B/C)
```
Nenhuma API paga foi necessária nem usada — o objetivo de encontrar 2-3 candidatos sem custo observável foi atingido sem precisar do STOP-BEFORE-SPENDING (§9 do briefing do gate).

## 11. Dependencies

**Nova dependência Python: `edge-tts` (7.2.8)**, com suas dependências transitivas (`aiohttp`, `yarl`, etc.) — justificada porque testar `edge-tts` concretamente é o objetivo explícito deste gate (regra 33: "esta dependência é necessária para produzir um candidato real deste Gate?" → sim). `pyproject.toml` **não foi modificado** (a instalação foi feita diretamente no venv para o experimento; formalizar como dependência declarada do projeto é uma decisão a tomar só se a voz vencedora vier do `edge-tts`, evitando comprometer o `pyproject.toml` antes da escolha humana).

## 12. Tests

`tests/lite/test_gate3b_units.py` — 7 testes novos: contrato de `NarrationRequest`/`NarrationResult` (campo `voice` opcional, defaults), `probe_audio` sobre um WAV sintético gerado em memória (sem depender de SAPI5/edge-tts reais — determinístico, rápido), e 3 testes que auditam o `voice_candidates.json` da execução real mais recente (3 letras presentes, mesmo hash de texto em todos os candidatos, nomes de arquivo sem vazar o provider). Nenhum teste tenta medir "naturalidade" — isso é Human Gate, não unit test.

## 13. Human Review Package

`HUMAN_VOICE_REVIEW.md` + `voice_A.wav`/`voice_B.mp3`/`voice_C.mp3` enviados ao usuário. Mapeamento provider↔letra preservado só em `voice_candidates.json` (interno, não enviado). Pergunta central no pacote: *"Would you listen to this voice for 10+ minutes?"* Veredito pendente no momento deste relatório.

## 14. Limitations

- O trecho de teste ficou em ~95s, levemente acima da faixa "~60-90s" sugerida (aceito por não ser requisito rígido; a cobertura de desafios narrativos foi priorizada).
- `edge-tts` depende de rede — se a rede cair, B/C não podem ser regenerados sem re-teste; A (SAPI5) continua funcionando offline.
- Terceira voz `edge-tts` disponível (`ThalitaMultilingualNeural`) não foi testada — decisão consciente de manter 3 candidatos totais, não 4.
- OneCore poderia, em tese, se tornar viável se os pacotes de voz forem baixados manualmente (Configurações do Windows) — não tentado aqui, fora do escopo de "inspeção local gratuita" automatizável.

## 15. Architecture Drift Check

```text
LEGACY_ORCHESTRATOR_USED: NÃO
UNUSED_ABSTRACTIONS_ADDED: NÃO (NarrationPort já existia do Gate 2; ganhou seu segundo consumidor real, não uma abstração nova especulativa)
FULL_SCRIPT_SYNTHESIZED_PREMATURELY: NÃO
GATE_3C_STARTED_PREMATURELY: NÃO
```

## 16. Gate Status

Ver bloco obrigatório abaixo.

---

## VEREDITO FINAL OBRIGATÓRIO

```text
GATE_3A_STATUS: PASS
GATE_3A_HUMAN_STATUS: PASS

APPROVED_SCRIPT_PATH: runs/20260823T185859Z-gate3a-script/working/script.md
APPROVED_SCRIPT_HASH: sha256:c7a0209f4… (completo em run_manifest.json do Gate 3B)

GATE_3B_IMPLEMENTED: SIM
VOICE_BAKEOFF_COMPLETED: SIM (geração + QA objetiva; escolha humana pendente)

TEST_EXCERPT_PATH: runs/20260823T191619Z-gate3b-voice/input/voice_test_excerpt.txt
TEST_EXCERPT_HASH: registrado em voice_candidates.json (campo text_sha256, idêntico nos 3 candidatos)
TEST_EXCERPT_WORD_COUNT: 238

CANDIDATE_COUNT: 3

VOICE_A_PATH: runs/20260823T191619Z-gate3b-voice/assets/voice/voice_A.wav
VOICE_A_DURATION: 128.34s
VOICE_A_METHOD: local:sapi5

VOICE_B_PATH: runs/20260823T191619Z-gate3b-voice/assets/voice/voice_B.mp3
VOICE_B_DURATION: 86.18s
VOICE_B_METHOD: external_api:edge_tts

VOICE_C_PATH: runs/20260823T191619Z-gate3b-voice/assets/voice/voice_C.mp3
VOICE_C_DURATION: 102.10s
VOICE_C_METHOD: external_api:edge_tts

ALL_CANDIDATES_SAME_TEXT: SIM (verificado por hash, testado)

SAPI_BASELINE_INCLUDED: SIM (candidato A)
EDGE_TTS_TESTED: SIM (candidatos B e C)
OTHER_TTS_TESTED: Windows OneCore investigado e rejeitado (pacotes de voz não instalados, confirmado via API real)

NETWORK_REQUIRED: SIM para B/C (edge-tts); NÃO para A (SAPI5) — LOCAL_FIRST != OFFLINE_ONLY formalizado no SDD
EXTERNAL_API_DIRECTLY_USED: NÃO (edge-tts não usa API key/autenticação direta)
EXTERNAL_API_COST: 0.00 USD

TIMING_DATA_AVAILABLE: SIM para B e C (SentenceBoundary via edge-tts); NÃO para A (SAPI5 via subprocess não expõe eventos)
TIMING_DATA_TYPE: SentenceBoundary (offset/duração/texto por sentença)

AUTOMATED_AUDIO_QA: PASS para os 3 candidatos (arquivo abre, áudio presente, audível, sem clipping)
HUMAN_VOICE_REVIEW_PATH: runs/20260823T191619Z-gate3b-voice/output/HUMAN_VOICE_REVIEW.md
HUMAN_REVIEW_REQUIRED: SIM — pacote já enviado ao usuário, veredito pendente no momento deste relatório

FULL_SCRIPT_SYNTHESIZED_PREMATURELY: NÃO
GATE_3C_STARTED_PREMATURELY: NÃO
GATE_3D_STARTED_PREMATURELY: NÃO

ADVANCED_MODE_UNTOUCHED: SIM
LEGACY_ORCHESTRATOR_USED: NÃO
UNUSED_ABSTRACTIONS_ADDED: NÃO

TESTS_ADDED: 7
TESTS_PASSING: 167/167 (160 herdados de Gate 1/2/3A + 7 novos)

READY_FOR_HUMAN_VOICE_REVIEW: SIM
READY_FOR_FULL_NARRATION: CONDICIONAL — depende do veredito humano deste bake-off
READY_FOR_GATE_3C: NÃO — `BLOCKED_PENDING_HUMAN_VOICE_PASS`, conforme SDD_SPDD.md §43.9

BIGGEST_VOICE_QUALITY_RISK: julgamento de naturalidade/fadiga de escuta ao longo de 10+ minutos não pode ser extrapolado de uma amostra de 95s — a voz vencedora ainda precisa provar-se na narração completa (próximo passo, condicionado à aprovação)
BIGGEST_DEPENDENCY_RISK: se B ou C vencer, o produto passa a depender de um serviço de rede não contratual (edge-tts é um serviço não documentado oficialmente pela Microsoft como API pública — risco de descontinuação sem aviso, a registrar como ADR se for a escolha final)
BIGGEST_ARCHITECTURAL_RISK: nenhum crítico — `NarrationPort` absorveu um segundo provider sem mudança de forma, confirmando a decisão de desenho do Gate 2

RECOMMENDED_NEXT_ACTION: Aguardar HUMAN_PASS/HUMAN_PASS_WITH_NOTES/HUMAN_FAIL sobre os candidatos A/B/C; se aprovado, sintetizar o script_approved.md completo com a voz escolhida, medir a duração real, e só então avaliar liberar Gate 3C

GATE_VERDICT: GATE_3B_PASS_PENDING_HUMAN
```
