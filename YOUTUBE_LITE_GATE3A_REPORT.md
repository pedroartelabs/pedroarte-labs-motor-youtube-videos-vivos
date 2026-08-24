# YOUTUBE LITE — GATE 3A REPORT

## 1. Executive Summary

Gate 3A (Script Quality) foi implementado e executado com um **briefing real** e um **roteiro genuinamente autorado** para esse briefing — não uma fixture reaproveitada do Gate 2, não um texto hardcoded declarado "aprovado" sem geração real. A primeira execução (1274 palavras, ~509,6s) foi corretamente **reprovada** pelos validadores determinísticos por ficar abaixo do piso de 10 minutos — evidência de que o gate não é um carimbo automático. O roteiro foi então genuinamente expandido (não preenchido com padding) para 1684 palavras / ~673,6s (~11,2 min), dentro da faixa 10-15min, e passou em todos os checks bloqueantes na segunda execução. `HUMAN_REVIEW_REQUIRED` é `true` em ambas as execuções, por design — o veredito de qualidade editorial (Gate A humano) está pendente, roteiro e relatório já enviados ao usuário. Gate 3B/3C/3D permanecem **especificados, não implementados**, exatamente como restrito. Advanced legacy segue congelado; 160/160 testes passam.

## 2. Previous Gate Status

Confirmado por leitura e execução antes de qualquer alteração: `docs/youtube-lite/SDD_SPDD.md`, `OPERATOR_CONTRACT.md`, `ARTIFACT_CONTRACT.md` e `YOUTUBE_LITE_PHASE1_IMPLEMENTATION_REPORT.md` lidos integralmente; `src/pedroarte_youtube_engine/lite/` inspecionado; `pytest tests/ -q` → 145 passed (estado herdado do Gate 2) antes de qualquer mudança; `git status --short` e `git diff --stat` sobre `agents/`, `interfaces/`, `domain/` confirmaram Advanced intocado.

## 3. SDD/SPDD Changes

`docs/youtube-lite/SDD_SPDD.md` atualizado para v0.2: nova **PART V — GATE 3: QUALITY BEFORE SCALE** (§36-42), cobrindo o Cost of Failure Principle, a estrutura de subgates 3A-3D, o Briefing Contract completo, a Video Specification, a arquitetura de geração de roteiro, os validadores determinísticos, e as especificações (não implementadas) de Gate 3B/3C/3D. Tabela de Component Responsibilities (§14) e Ports (§16) atualizadas para refletir `BriefingSchema`, `VideoSpecification` e `ScriptGenerationPort` como implementados.

## 4. Briefing Contract

Implementado em `src/pedroarte_youtube_engine/lite/briefing.py` — `BriefingSchema` (Pydantic estrito, `frozen=True, extra="forbid"`), com `topic`, `objective`, `audience`, `language`, `tone`, `target_min_minutes`/`target_max_minutes`, `must_include`/`must_avoid` (tuplas), `references`, `additional_context`, `visual_direction`, `factuality_mode` (`CREATIVE`/`GENERAL_KNOWLEDGE`/`FACT_SENSITIVE`, default `GENERAL_KNOWLEDGE`). Crítica registrada no SDD (§38.1): nenhum campo do formulário hipotético original foi descartado sem motivo, e `visual_direction` + `factuality_mode` foram adicionados por necessidade real (o segundo exigido explicitamente pelo risco de factualidade, §16 do briefing de Gate 3).

## 5. Video Specification

`src/pedroarte_youtube_engine/lite/video_spec.py::normalize_briefing()` — função pura, deriva `estimated_word_range` (via `max_words_for_duration`, REUSE_AS_IS de `shared/text.py`) e repassa os demais campos como contrato editorial. Não inclui Visual Bible.

## 6. Script Generation Architecture

```text
ScriptGenerationRequest (VideoSpecification) → ScriptGenerationPort → OperatorAuthoredScriptStrategy
```
`ScriptGenerationPort` (Protocol) adicionado só porque há uma estratégia real por trás. `OperatorAuthoredScriptStrategy` (`src/pedroarte_youtube_engine/lite/script_generation/operator_authored.py`) empacota um texto **já autorado pelo operador** (o LLM conduzindo esta sessão) com a proveniência correta — não faz nenhuma chamada de API programática.

## 7. Actual Generation Method

`method="operator:claude_code"`, `model="claude-sonnet-5 (Claude Code, operator session)"`, `provider=None`, `input_tokens`/`output_tokens=None` (não observáveis de dentro da sessão que autora o texto — não estimados, para não fingir precisão que não existe). O texto do roteiro foi composto por mim como parte real do trabalho desta sessão, endereçando especificamente o briefing usado nesta execução (uma continuação com desfecho da história de exemplo já presente em `examples/sample_living_book/input/book.md`) — não é um template preenchido nem uma fixture genérica. Isso é `CONTENT_GENERATION_PASS`, não `INFRASTRUCTURE_PASS`.

## 8. Script Validators

Implementados em `src/pedroarte_youtube_engine/lite/script_validators.py`: `word_count`, `estimated_duration_seconds`/`duration_status` (via `speakable_duration_seconds`, REUSE_AS_IS), `must_include_coverage`, `must_avoid_violations`, `repetition` (heurística grosseira: parágrafo duplicado ou abertura consecutiva idêntica), `structure_present` (≥4 parágrafos — só existência, nunca qualidade), `non_empty_sections`. `human_review_required` é sempre `True`. `duration_status = TOO_SHORT` é bloqueante (reprova); `TOO_LONG` e `repetition`/`structure_present` são avisos não bloqueantes.

## 9. Tests

`tests/lite/test_gate3a_units.py` — 15 testes novos: schema (válido, campos extras rejeitados, `max < min` rejeitado, imutabilidade), `VideoSpecification` (faixa de palavras, propagação de `factuality_mode`), validadores (curto demais/bloqueia, dentro do alvo/passa, longo demais/aviso não bloqueante, vazio/bloqueia, repetição/aviso não bloqueante, `must_include` ausente/bloqueia, `must_avoid` presente/bloqueia, `human_review_required` sempre `True`). Nenhum teste tenta validar comportamento criativo do LLM como se fosse determinístico — isso é provado pela execução real (§10-11), não por unit test.

## 10. Real Briefing Used

```yaml
topic: "O mistério do Relojoeiro de Vidro: o que a inscrição impossível revela"
objective: "Contar uma história de mistério/fantástico completa e satisfatória, com desfecho..."
audience: "Adultos e jovens adultos interessados em ficção de mistério e fantástico, em português do Brasil."
tone: "misterioso, contido, levemente melancólico"
target_min_minutes: 10.0
target_max_minutes: 15.0
must_include: [Elias Varga, Mariana Duarte, relógio de vidro, inscrição]
must_avoid: [violência gráfica, marca registrada]
references: [examples/sample_living_book/input/book.md]
factuality_mode: creative
```
Não é "lorem ipsum": usa o exemplo já existente no próprio repositório como referência real, pedindo uma continuação com desfecho — um teste representativo do caso de uso central do projeto (livro → vídeo).

## 11. Generated Script

`runs/20260823T185859Z-gate3a-script/working/script.md` — continuação e resolução original de "O Relojoeiro de Vidro": a dívida temporal de Portovelho, a confrontação entre Elias e Mariana, e o desfecho em que Elias escolhe devolver em vez de tomar emprestado. Enviado ao usuário para o Gate A humano.

## 12. Word Count

**1684 palavras** (segunda execução, aprovada). Primeira execução: 1274 palavras — reprovada.

## 13. Estimated Duration

**673,6s (~11,2 minutos)**, dentro da faixa 10-15min. Nota: esta é a estimativa pré-TTS (`speakable_duration_seconds`, 150 wpm) — a duração real só será conhecida no Gate 3B, com síntese de voz de verdade.

## 14. Validation Results

Segunda execução: `status=PASS`, todos os 7 checks passaram (4 bloqueantes + 3 não bloqueantes), 0 avisos. Primeira execução: `status=FAIL`, bloqueado por `duration_within_target` (`TOO_SHORT`) — os demais 6 checks já passavam. Relatórios completos em `runs/<run_id>/working/validation_report.json` (ambas as execuções preservadas em `runs/`).

## 15. Factuality Classification

`factuality_mode = CREATIVE` — ficção derivada de um exemplo já existente no repositório. Risco factual mínimo por construção (não há alegação de fato verificável no roteiro), não por verificação de um sistema de fact-checking (fora de escopo do Gate 3A).

## 16. Costs

```text
external_api_cost: 0.00 USD
script_generation_method: operator:claude_code
external_api_used: NÃO
provider: N/A
model: claude-sonnet-5 (Claude Code, operator session)
input_tokens / output_tokens: não observáveis desta sessão, não estimados
generation_time: não medido separadamente (parte do trabalho desta sessão, não uma chamada isolada cronometrável)
```

## 17. Files Created

```text
docs/youtube-lite/SDD_SPDD.md (atualizado — ver §3)
src/pedroarte_youtube_engine/lite/briefing.py
src/pedroarte_youtube_engine/lite/video_spec.py
src/pedroarte_youtube_engine/lite/script_validators.py
src/pedroarte_youtube_engine/lite/script_generation/__init__.py
src/pedroarte_youtube_engine/lite/script_generation/ports.py
src/pedroarte_youtube_engine/lite/script_generation/operator_authored.py
scripts/lite/gate3a_script_source.md
scripts/lite/run_gate3a_script_proof.py
tests/lite/test_gate3a_units.py
YOUTUBE_LITE_GATE3A_REPORT.md (este arquivo)
```

## 18. Files Modified

`docs/youtube-lite/SDD_SPDD.md` (extensão documental, ver §3). **Nenhum arquivo do Advanced legacy foi modificado** (`git diff --stat` vazio para `agents/`, `interfaces/`, `domain/`).

## 19. Architecture Drift

```text
LEGACY_ORCHESTRATOR_USED: NÃO
UNUSED_ABSTRACTIONS_ADDED: NÃO (ScriptGenerationPort tem um consumidor real: o driver do Gate 3A)
```

## 20. Human Review Package

Enviado ao usuário: `script.md` (1684 palavras) + `validation_report.json` (status PASS, 0 avisos). Pergunta central: *"Este roteiro é bom o suficiente para justificar produzir voz e imagens?"* Veredito (`HUMAN_PASS`/`HUMAN_PASS_WITH_NOTES`/`HUMAN_FAIL`) pendente no momento deste relatório.

## 21. Limitations

- Os validadores de `must_include`/repetição são por correspondência literal/heurística grosseira — documentadamente incapazes de avaliar paráfrase ou repetição temática intencional (rotulado no próprio relatório de validação).
- `structure_present` só confirma contagem mínima de parágrafos, nunca qualidade de gancho, ritmo ou payoff — julgamento explicitamente reservado ao humano.
- Duração estimada é pré-TTS; a duração real será conhecida só no Gate 3B.
- `input_tokens`/`output_tokens` não puderam ser registrados por não serem observáveis de dentro da própria sessão que autora o texto (documentado, não omitido silenciosamente).

## 22. Gate Verdict

Ver bloco obrigatório abaixo.

---

## VEREDITO FINAL OBRIGATÓRIO

```text
GATE_2_STATUS: PASS (herdado, confirmado antes de iniciar — 145/145 testes na baseline)

SDD_SPDD_UPDATED: SIM (v0.1 → v0.2, PART V adicionada)

GATE_3A_IMPLEMENTED: SIM
REAL_BRIEFING_USED: SIM (não fixture genérica — referencia o exemplo real do repositório)
REAL_SCRIPT_GENERATED: SIM (autorado pelo operador desta sessão, não hardcoded, não reaproveitado do Gate 2)

BRIEFING_CONTRACT_STATUS: IMPLEMENTADO
VIDEO_SPEC_STATUS: IMPLEMENTADO
SCRIPT_GENERATION_STATUS: IMPLEMENTADO (estratégia operator-authored; API externa não usada nem necessária)
SCRIPT_VALIDATION_STATUS: IMPLEMENTADO, PASS na execução final

SCRIPT_GENERATION_METHOD: operator:claude_code
EXECUTION_ENVIRONMENT: claude_code
EXTERNAL_API_USED: NÃO
EXTERNAL_API_PROVIDER: N/A
EXTERNAL_API_MODEL: N/A
EXTERNAL_API_COST: 0.00 USD

SCRIPT_PATH: runs/20260823T185859Z-gate3a-script/working/script.md
VALIDATION_REPORT_PATH: runs/20260823T185859Z-gate3a-script/working/validation_report.json

SCRIPT_WORD_COUNT: 1684
ESTIMATED_DURATION_SECONDS: 673.6
DURATION_STATUS: WITHIN_TARGET

MUST_INCLUDE_STATUS: PASS (todos os itens encontrados)
MUST_AVOID_STATUS: PASS (nenhum padrão proibido encontrado)
REPETITION_STATUS: PASS (sem repetição grosseira detectada)
STRUCTURE_STATUS: PASS (21 parágrafos — estrutura mínima presente; qualidade do gancho/ritmo/payoff é julgamento humano, não medido aqui)
FACTUALITY_MODE: creative

AUTOMATED_VALIDATION: PASS
HUMAN_REVIEW_REQUIRED: SIM — pacote já enviado ao usuário, veredito pendente no momento deste relatório

ADVANCED_MODE_UNTOUCHED: SIM
LEGACY_ORCHESTRATOR_USED: NÃO
UNUSED_ABSTRACTIONS_ADDED: NÃO

TESTS_ADDED: 15
TESTS_PASSING: 160/160 (145 herdados de Gate 1/2 + 15 novos)

GATE_3B_STARTED_PREMATURELY: NÃO
GATE_3C_STARTED_PREMATURELY: NÃO
GATE_3D_STARTED_PREMATURELY: NÃO

BIGGEST_SCRIPT_QUALITY_RISK: julgamento editorial (gancho, ritmo, payoff, originalidade) permanece inteiramente humano — nenhum validador determinístico mede isso, por design; o roteiro pode passar em todos os checks e ainda ser editorialmente fraco
BIGGEST_FACTUALITY_RISK: baixo neste briefing específico (modo `creative`, ficção); risco reapareceria integralmente no primeiro briefing `fact_sensitive`, para o qual nenhum mecanismo de verificação foi construído (fora de escopo, deliberado)
BIGGEST_ARCHITECTURAL_RISK: nenhum crítico — `ScriptGenerationPort` já comporta uma futura estratégia de API externa sem mudança na engine; nenhuma abstração sem consumidor foi adicionada

READY_FOR_HUMAN_SCRIPT_REVIEW: SIM
READY_FOR_GATE_3B: CONDICIONAL — depende do veredito humano deste Gate A

RECOMMENDED_NEXT_ACTION: Aguardar HUMAN_PASS/HUMAN_PASS_WITH_NOTES/HUMAN_FAIL sobre o script.md enviado; se aprovado, iniciar Gate 3B com validação empírica de `edge-tts` sobre uma amostra de 60-90s deste mesmo roteiro, comparada à SAPI5 do Gate 2

GATE_VERDICT: GATE_3A_PASS_PENDING_HUMAN
```
