# YOUTUBE LITE — SDD/SPDD

Status: **v0.9 — Gates 1/2/3A/3B/3C concluídos; Gate 3D/3D.1/3D.2 executados de ponta a ponta (planejamento → handoff de imagens a custo zero → montagem completa → correção de retenção/movimento/música pós-feedback humano) — Click Package/Thumbnail Contract (Part IX) e YouTube Experience Contract (Part X) adicionados nesta e na revisão anterior como especificação (não implementados)**
Baseline: [YOUTUBE_LITE_DISCOVERY_REPORT.md](../../YOUTUBE_LITE_DISCOVERY_REPORT.md), [DISCOVERY_REPORT_YOUTUBE_ENGINE.md](../../DISCOVERY_REPORT_YOUTUBE_ENGINE.md)

Este documento funde SDD (System Design) e SPDD (Product Design) num único arquivo, por decisão explícita do discovery anterior (§28): nesta fase, decisão de sistema e decisão de produto são tomadas pelas mesmas pessoas, sobre o mesmo escopo pequeno. Separar os dois documentos agora seria burocracia sem consumidor real.

---

# PART I — SPDD (Product)

## 1. Context

O motor `pedroarte_youtube_engine` ("Advanced"/legacy) é um compilador de pré-produção textual: 27 agentes, máquina de estados de 15 fases, RAG local, QA narrativo — mas **nunca produz um arquivo de vídeo**. Nenhum adaptador real de geração de vídeo/imagem/voz/música existe no código; a flag `execute_generation` é validada mas nunca lida por nenhum agente para agir. Pior: as três interfaces (CLI/API/MCP) compartilham a mesma função `bootstrap()`, que quebra com `TypeError` antes de qualquer execução completar — comprovado por execução real, não suposição (ver discovery forense, §11).

YouTube Lite existe porque continuar consertando/estendendo essa arquitetura de 27 agentes seria o pior uso do próximo ciclo — ela nunca terminou uma execução, e seu produto real sempre foi texto, não mídia. Advanced fica **congelado**: não é removido, não é refatorado, não é integrado ao Lite. Fica disponível para retomada futura, se e quando fizer sentido.

## 2. Problem Statement

> Transformar um briefing simples em um vídeo publicável no YouTube sem exigir edição manual obrigatória do MP4.

## 3. User Outcome

```text
briefing  →  youtube_bundle/  (com um vídeo pronto para avaliação/publicação manual)
```

## 4. Product Definition

YouTube Lite é um pipeline linear, pequeno e local-first que recebe um briefing curto e produz um `video.mp4` real (imagens estáticas de alta qualidade + Ken Burns/pan/zoom + narração + música opcional + captions), acompanhado de thumbnail e metadados, revisável por um humano antes de publicação manual. Não é cinematográfico, não gera vídeo generativo, não publica automaticamente.

## 5. Experience

```text
Briefing → Run → Intermediate artifacts → MP4 → Human review → Manual publication
```

## 6. Duration Policy

```text
target_min_minutes = 10
target_max_minutes = 15
```

Defaults iniciais, validados **pós-TTS** (a duração real do áudio sintetizado é a fonte da verdade — a estimativa pré-TTS via `speakable_duration_seconds` só serve para dimensionar o roteiro antes de sintetizar). Nunca atingir a duração-alvo por silêncio artificial, repetição, redução artificial de velocidade de narração ou prolongamento visual sem conteúdo. Se a duração real ficar abaixo do mínimo, o gate de QA falha e exige mais roteiro real — não padding.

**Esta política não se aplica ao Gate 2** (§32-35), cujo alvo é 30-60 segundos, deliberadamente pequeno para provar o cano antes de escalar.

## 7. Definition of Done

```text
briefing → video.mp4 >= ~10min → automated QA → human full-watch → HUMAN_PASS → E2_PROVEN
```

## 8. Human Gates

- **Gate A — Script Review:** obrigatório antes da geração cara de assets no vídeo completo (Gate 3+). Não aplicável ao Gate 2, que usa um script fixture curto e controlado.
- **Gate B — Visual Spot Check:** amostragem dos assets (Gate 3+, quando houver 15-30+ imagens). Não aplicável ao Gate 2 (uma única imagem).
- **Gate C — Final Video:** obrigatório, vídeo assistido integralmente. Aplica-se também ao Gate 2, em escala reduzida (30-60s).

Vereditos: `HUMAN_PASS` / `HUMAN_PASS_WITH_NOTES` / `HUMAN_FAIL`.

## 9. Scope

Briefing, roteiro, imagens, narração, timeline, montagem, captions, thumbnail, metadata, manifest, QA, MP4, bundle.

## 10. Non-Scope

Upload no YouTube, gestão de canal, analytics, Shorts, séries, mini-novelas, trailers, modo cinematográfico, modo profissional, vídeo generativo, planejamento avançado de câmera, seleção automática de modo, otimização de CTR.

## 11. Maturity Model

```text
CURRENT: YouTube Engine legacy ≈ E1
TARGET:  YouTube Lite → E2 Functional Local
```

---

# PART II — SDD (System)

## 12. Architectural Decision

```text
STRATEGY = HYBRID
```

Vertical slice novo (`src/pedroarte_youtube_engine/lite/`) + reutilização cirúrgica de funções/padrões pequenos e comprovados do legacy (importados diretamente, nunca através do orquestrador). O Lite **não** é inserido no `PipelineOrchestrator` dos 27 agentes, **não** chama `bootstrap()`, **não** depende da máquina de estados de 15 fases.

## 13. High-Level Architecture

```text
                 BRIEFING
                    │
                    ▼
              VIDEO SPEC
                    │
                    ▼
             SCRIPT PLANNER
                    │
                    ▼
                 SCRIPT
                    │
           ┌────────┴────────┐
           ▼                 ▼
      NARRATION         VISUAL PLAN
           │                 │
           │           IMAGE GENERATION
           │                 │
           └────────┬────────┘
                    ▼
                 TIMELINE
                    │
                    ▼
                  FFMPEG
                    │
                    ▼
                   MP4
                    │
                    ▼
                   QA
                    │
                    ▼
             YOUTUBE BUNDLE
                    │
                    ▼
              HUMAN REVIEW
```

Nenhuma simplificação adicional identificada além do que já é o desenho mínimo do discovery — este é o menor grafo que cobre as junções reais (roteiro, dois ramos de asset, timeline, render, QA, empacotamento, revisão).

## 14. Component Responsibilities

| Componente | Responsabilidade mínima | Status nesta fase |
|---|---|---|
| `BriefingSchema` | Validar o briefing (Pydantic estrito) | **Implementado no Gate 3A** (ver Part V) |
| `VideoSpecification` | Derivar duração-alvo/idioma/etc. do briefing | **Implementado no Gate 3A** |
| `ScriptGenerationPort` + `OperatorAuthoredScriptStrategy` | Contrato de geração de roteiro; estratégia real usa a capacidade operacional do LLM que está conduzindo a sessão (Claude Code), sem chamada de API programática | **Implementado no Gate 3A** — substitui o `ScriptPlanner` genérico da hipótese original (nenhum consumidor real para um "planner" abstrato ainda; um port + uma estratégia concreta bastam) |
| `ScriptValidator` | Checagens determinísticas do roteiro (contagem de palavras, duração estimada, cobertura, repetição, estrutura mínima) | **Implementado no Gate 3A** |
| `VisualPlan` | Lista de beats visuais e prompts de imagem | Reduzido a um único beat fixo no Gate 2 |
| `ImageGenerationPort` | `generate(request) -> ImageResult` | Implementado — uma estratégia local (`local_gdi`) para o Gate 2 |
| `NarrationPort` | `synthesize(text) -> NarrationResult` | Implementado — uma estratégia SAPI5 (`sapi5`) para o Gate 2 |
| `TimelineBuilder` | Mapear script/beats → janelas de tempo reais (pós-TTS) | Implementado, versão mínima (um beat = a narração inteira) |
| `FFmpegAssembler` | Compor imagem(ns) + narração + (música) + Ken Burns em `.mp4` | Implementado, versão mínima |
| `MediaQA` | Checks automatizados via `ffprobe` sobre o `.mp4` | Implementado, checks do Gate 2 (§34 do discovery) |
| `Packager` | Organizar artefatos em `runs/<run_id>/output/` | Implementado, versão mínima (sem bundle completo — isso é Gate 3) |

Cada um é uma função ou um dataclass pequeno — nenhuma classe abstrata, nenhum framework de injeção de dependência. Um consumidor real (o script de prova do Gate 2) existe para cada um.

## 15. Legacy Reuse Matrix

| Componente legacy | Classificação | Motivo (evidência em Gate 1, §32) |
|---|---|---|
| `shared/text.py` (`count_words`, `speakable_duration_seconds`, `sentence_split`, `slugify`, `safe_slug`, `normalize_whitespace`, `excerpt`) | **REUSE_AS_IS** | Puro, zero dependência de domínio/agentes |
| `shared/paths.py` (`PathPolicy`, `write_text_atomic`, `ensure_directory`) | **REUSE_AS_IS** | Puro, só depende de `shared/errors.py` |
| `observability/logging.py` (`RunLogger`, `get_logger`) | **REUSE_AS_IS** | Puro, só depende de `observability/redaction.py`; usar com a assinatura correta (sem `verbose=`, que é um bug só em `_bootstrap.py`, não na classe) |
| Padrão `ConfigModel` (`frozen=True, extra="forbid", str_strip_whitespace=True`) | **REUSE_AS_IS** (padrão, não a classe) | Uma linha de `ConfigDict`; replicar no schema do Lite |
| `domain/artifacts.py::PublicationMetadata` (forma de dados) | **REUSE_SIMPLIFIED** | Forma de campos útil (título/descrição/capítulos/hashtags); a classe real importa `ProductionVariant` (6 formatos legacy) irrelevante ao Lite |
| `adapters/renderers/subtitles.py` (`render_srt`, `render_vtt`, `build_cues`) + `domain/segment.py::SubtitleCue` | **REPLACE** | Exigem construir `PromptSegment`/`SubtitleCue` (modelos pesados do domínio de 10s-por-segmento); o formato SRT/VTT em si é trivial (~15 linhas) — reimplementado no Lite para manter isolamento do pacote `domain/segment.py` |
| `PipelineOrchestrator` / `EngineContext` / `bootstrap()` | **FREEZE** | Quebrado (discovery forense §11); mesmo se corrigido, não é o formato de execução do Lite |
| Máquina de estados de 15 fases (`domain/state.py`) | **FREEZE** | Desenhada para o pipeline de compilação de prompts; Lite usa um status de execução muito mais simples (§19) |
| 27 agentes | **FREEZE** | Fora de escopo — é o Advanced |
| RAG, continuidade cinematográfica, retry/circuit breaker, provedores fake | **FREEZE** | Sem consumidor real no Lite v0.1 |

## 16. Ports

Ports existem só onde há variação operacional real:

```python
class NarrationPort(Protocol):
    def synthesize(self, text: str, *, language: str) -> NarrationResult: ...

class ImageGenerationPort(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...

class ScriptGenerationPort(Protocol):  # a partir do Gate 3A — ver Part V
    def generate(self, request: ScriptGenerationRequest) -> ScriptGenerationResult: ...
```

`ScriptGenerationPort` foi adicionado no Gate 3A porque passou a existir variação operacional real: a estratégia usada é `OperatorAuthoredScriptStrategy` (o LLM que conduz a sessão — Claude Code — autora o texto como parte do trabalho da própria sessão, sem chamada de API programática), mas o contrato já comporta uma futura estratégia de API externa sem exigir mudança na engine (Separation Principle, §21). Nenhum outro port é criado nesta fase — timeline e montagem continuam com FFmpeg como única implementação prevista, sem alternativa a abstrair ainda.

## 17. FFmpeg

FFmpeg é o renderer/assembler do Lite. Não se constrói um renderer próprio. Confirmado ausente do `PATH` do ambiente nesta sessão e instalado via `winget install Gyan.FFmpeg` como pré-requisito do Gate 2 (evidência em §32 do relatório de implementação). Não adicionar MoviePy ou qualquer camada intermediária sem evidência de necessidade — não surgiu nenhuma neste v0.1.

## 18. Filesystem

```text
runs/
└── <run_id>/
    ├── input/            (briefing.yaml ou fixture do Gate 2)
    ├── working/           (script.md, timeline.json)
    ├── assets/
    │   ├── narration.wav
    │   └── images/
    ├── output/             (clip.mp4 no Gate 2; youtube_bundle/ completo no Gate 3)
    ├── run_manifest.json
    └── pending_tasks.json
```

`runs/` já está no `.gitignore` do repositório (herdado da convenção `outputs/`) — nenhuma alteração necessária ali. Ver [ARTIFACT_CONTRACT.md](ARTIFACT_CONTRACT.md) para o schema completo.

## 19. State

Não se reutiliza a máquina de estados legacy de 15 fases. O Lite usa um enum de status mínimo, suficiente para o que existe hoje:

```python
class RunStatus(StrEnum):
    STARTED = "started"
    SCRIPT_READY = "script_ready"
    NARRATION_READY = "narration_ready"
    IMAGES_READY = "images_ready"
    ASSEMBLED = "assembled"
    QA_PASSED = "qa_passed"
    QA_FAILED = "qa_failed"
    FAILED = "failed"
```

Sem repair loop, sem transições complexas — só um registro linear de progresso em `run_manifest.json`.

## 20. Failure Policy

Para v0.1: falhar explicitamente, registrar erro em `run_manifest.json`, preservar artefatos já produzidos, permitir diagnóstico manual. **Não implementado**: circuit breaker, retry distribuído, orquestração genérica de provedor, sistema complexo de recuperação — nenhum tem consumidor real nesta fase (poucas chamadas, todas locais no Gate 2).

---

# PART III — EXECUTION DESIGN (Claude Code × Codex × External Capabilities)

## 21. Separation Principle

```text
ENGINE CAPABILITY != EXECUTION ENVIRONMENT CAPABILITY
```

A engine expressa "preciso desta imagem/narração com estas características" via `ImageGenerationRequest`/texto de narração — nunca "chame obrigatoriamente o provider X". A escolha de estratégia (nativa do ambiente vs. API externa vs. local) é decidida fora do domínio da engine, por uma função de seleção pequena e explícita (§27).

## 22. Claude Code

Papel primário: **BUILDER** — arquitetura, implementação, testes, refatoração, contratos, debugging, documentação, execução técnica quando necessário (incluindo operar/testar o Lite, como nesta própria sessão).

## 23. Codex

Papel primário: **OPERATOR** — runs locais, geração de assets quando capability nativa existir, smoke/E2E, inspeção, validação, evidências, atualização de manifests. **Capacidade nativa de geração de imagem do Codex não pôde ser verificada nesta sessão** (Claude Code) — permanece `UNKNOWN` até verificação em ambiente Codex real.

## 24. Operator Ownership Rule

Uma execução (`run_id`) tem um único escritor por vez. Se Claude estiver operando `runs/<run_id>/`, Codex não escreve simultaneamente nela, e vice-versa. A propriedade é sinalizada no `run_manifest.json` (`owner`, `status`).

## 25. Handoff

`run_manifest.json` + `pending_tasks.json` + artefatos no filesystem — nunca memória de conversa. Ver [OPERATOR_CONTRACT.md](OPERATOR_CONTRACT.md).

## 26. Local-First Policy

```text
1. processamento determinístico local
2. ferramentas já instaladas no ambiente
3. capacidades nativas do ambiente de execução
4. capacidades gratuitas/locais compatíveis
5. APIs externas quando justificadas
```

Não é dogma de "zero API": para o Gate 2, a imagem usa estratégia local (decisão explícita do operador humano, registrada em `provenance`); para roteiro real (Gate 3+), LLM externo é justificado porque a alternativa determinística comprovadamente não gera prosa nova de qualidade (discovery Lite, §11).

## 27. Image Generation Policy

```text
ImageGenerationRequest → ImageGenerationPort → Execution Strategy
```

```text
IF operando em Codex E geração nativa de imagem disponível:
    usar geração nativa
ELSE IF operador (humano) autorizou explicitamente uma API externa configurada:
    usar o provider autorizado
ELSE:
    usar estratégia local (Gate 2: `local_gdi`)
```

Nunca presumir capability sem verificar. Nunca tratar `ANTHROPIC_API_KEY` como indicador de capacidade de geração de imagem (§28).

## 28. Provider Rule

A Anthropic não é automaticamente um provider de geração de imagem só porque `ANTHROPIC_API_KEY` existe no `.env` — a API da Anthropic não oferece esse endpoint (confirmado no discovery Lite, §15/§25). Entre as chaves presentes no `.env` real deste projeto, apenas `OPENAI_API_KEY` corresponde a um provider com endpoint de imagem documentado — e mesmo essa só é usada mediante autorização explícita do operador humano para a chamada específica (não uma autorização geral e ilimitada). Nenhum valor de secret é lido, exibido ou registrado em nenhum momento — só os nomes das variáveis foram inspecionados.

## 29. TTS Policy

```text
GATE_2_TTS != GATE_3_TTS
```

Gate 2: SAPI5 (`Microsoft Maria Desktop`, pt-BR) — permitido porque o objetivo é provar o cano, não a qualidade de publicação. Gate 3: TTS de qualidade de publicação obrigatório; candidato inicial `edge-tts` (discovery Lite, §19), a validar antes de cristalizar como dependência permanente.

## 30. Unit Economics

Cada run registra, em `run_manifest.json`:
```text
external_api_cost, generation_time_seconds, human_review_time_seconds,
asset_count, render_time_seconds, retry_count,
execution_environment, generation_method
```
Sem sistema de analytics — só o registro dos dados, conforme §34 do discovery Lite.

---

# PART IV — DEVELOPMENT & QA GATES

## 31. Gate 0 — Discovery

Status: **DONE** ([DISCOVERY_REPORT_YOUTUBE_ENGINE.md](../../DISCOVERY_REPORT_YOUTUBE_ENGINE.md), [YOUTUBE_LITE_DISCOVERY_REPORT.md](../../YOUTUBE_LITE_DISCOVERY_REPORT.md)).

## 32. Gate 1 — Core Health

Objetivo: validar isoladamente só os componentes legacy que serão de fato reutilizados (§15). Resultados em [YOUTUBE_LITE_PHASE1_IMPLEMENTATION_REPORT.md](../../YOUTUBE_LITE_PHASE1_IMPLEMENTATION_REPORT.md).

## 33. Gate 2 — Single Asset Proof

Objetivo: **PROVE THE PIPE**. Produzir localmente um `.mp4` real de ~30-60 segundos:

```text
short script → real narration → real image → simple timeline →
Ken Burns/movement → FFmpeg → clip.mp4
```

## 34. Gate 2 — Success Criteria

Automatizado: `clip.mp4` existe; `ffprobe` abre; duração ≥ mínimo esperado; stream de vídeo existe; stream de áudio existe; resolução válida; codec válido; áudio audível; sem clipping óbvio.

Humano: imagem aceitável; narração compreensível; movimento funciona; sincronia áudio/vídeo aceitável; clipe é assistível.

## 35. Gate 2 — Important Restriction

**Não implementado nesta fase:** geração de 10 minutos, pipeline completo de briefing, 30 imagens, Visual Bible completa, thumbnail, metadata completo, bundle completo, sistema de música, captions avançadas, QA avançado, infraestrutura de retry, resume/checkpoint. Gate 2 é propositalmente pequeno.

---

## P0-EVIDENCE vs. P0-PRODUCT

**P0-EVIDENCE (necessário para Gate 2, nada além disso bloqueia):** script curto, narração real, imagem real, timeline, FFmpeg, `clip.mp4`, QA básico de mídia.

**P0-PRODUCT (só depois de Gate 2 PASS):** briefing completo, video spec, script planner real, validadores de roteiro, Visual Bible Lite, visual manifest, 15-30+ imagens conforme necessário, TTS de qualidade de publicação, captions completas, thumbnail, metadata completo, manifest/provenance completo, QA completo, youtube bundle, vídeo ≥10min, Gates humanos A/B/C completos.

Esta distinção é obrigatória e foi respeitada nesta implementação — nada de P0-Product foi antecipado para o Gate 2 (ver Architecture Drift Check no relatório de implementação).

---

# PART V — GATE 3: QUALITY BEFORE SCALE

Gate 2 respondeu "conseguimos produzir um MP4 real?" (SIM). Gate 3 responde uma pergunta diferente e mais difícil: **"conseguimos produzir conteúdo que uma pessoa realmente consideraria publicável e assistível por ~10 minutos?"** Isso não é escala temporal (50s → 10min) — é qualidade de conteúdo, voz e imagem, provadas em ordem crescente de custo, cada uma com seu próprio gate humano.

## 36. Cost of Failure Principle

> **O custo da próxima etapa só deve crescer depois de haver evidência.** Quanto mais cara a etapa seguinte, mais evidência deve existir antes de executá-la.

Aplicação concreta no Gate 3:
```text
briefing + roteiro          (barato: texto)
      ↓ PASS?
60-90s de voz                (barato: uma amostra)
      ↓ PASS?
5 imagens                     (médio: um punhado de assets)
      ↓ PASS?
15-30+ imagens conforme necessário   (caro: escala completa)
      ↓ PASS?
render completo
```
Nunca gerar o próximo nível de asset (mais caro) antes do nível anterior (mais barato) ter sido aprovado por um humano.

## 37. Gate 3 — Estrutura em Subgates

```text
GATE 3A — SCRIPT QUALITY     (implementado nesta fase)
GATE 3B — VOICE QUALITY      (especificado, não implementado)
GATE 3C — VISUAL QUALITY     (especificado, não implementado)
GATE 3D — FULL PRODUCTION    (especificado, não implementado)
```

Cada subgate tem seu próprio `HUMAN_PASS`/`HUMAN_PASS_WITH_NOTES`/`HUMAN_FAIL`. A sequência é estritamente `3A → HUMAN PASS → 3B → HUMAN PASS → 3C → HUMAN PASS → 3D`. Se um gate exigir julgamento humano — e todos exigem — a execução **para**, produz os artefatos, reporta os caminhos, e espera. Nunca assume aprovação para avançar automaticamente.

## 38. Gate 3A — Script Quality (implementado)

Objetivo:
```text
BRIEFING → VIDEO SPECIFICATION → SCRIPT GENERATION → DETERMINISTIC VALIDATORS → HUMAN REVIEW
```
Resultado esperado: um roteiro que justificaria produzir um vídeo de ~10-15 minutos.

### 38.1 Briefing Contract

```yaml
topic: str                       # obrigatório
objective: str                   # obrigatório — o que o espectador deve sentir/aprender/fazer
audience: str = ""
language: str = "pt-BR"
tone: str = ""
target_min_minutes: float = 10.0
target_max_minutes: float = 15.0
must_include: list[str] = []
must_avoid: list[str] = []
references: list[str] = []       # caminhos de arquivo, opcionais
additional_context: str = ""
visual_direction: str = ""       # opcional — não é a Visual Bible completa (isso é Gate 3C)
factuality_mode: "creative" | "general_knowledge" | "fact_sensitive" = "general_knowledge"
```

Crítica ao formulário hipotético original: `topic` e `objective` são mantidos como campos distintos (o quê vs. para quê — servem propósitos diferentes na geração e na validação). `visual_direction` foi adicionado como campo opcional de texto livre (não uma Visual Bible estruturada — isso permanece exclusivo do Gate 3C). `factuality_mode` foi adicionado porque §16 do briefing de Gate 3 exige que o contrato deixe explícito quando fact-checking humano é obrigatório; o default `general_knowledge` é uma escolha conservadora deliberada — briefings de risco factual real devem declarar `fact_sensitive` explicitamente. Nenhum campo do tipo formulário-gigante (sem SEO, sem parâmetros de estilo visual detalhados, sem configuração de provedor) foi adicionado.

### 38.2 Video Specification

`VideoSpecification` é derivado do briefing por uma função pura (`normalize_briefing`), não por um agente: adiciona `estimated_word_range` (calculado a partir da faixa de duração e da taxa de fala padrão, reaproveitando `speakable_duration_seconds`/`DEFAULT_SPEECH_RATE_WPM` de `shared/text.py` — REUSE_AS_IS) e repassa os demais campos do briefing como contrato editorial. Não inclui Visual Bible.

### 38.3 Script Generation Architecture

```text
ScriptGenerationRequest (VideoSpecification + texto de referência opcional)
        ↓
ScriptGenerationPort
        ↓
OperatorAuthoredScriptStrategy
```

Princípio obrigatório: **LLM CREATES → CODE VALIDATES → HUMAN JUDGES.** O código nunca tenta escrever criatividade — só verifica propriedades mensuráveis (§38.5). A política de execução (§26) prioriza a capacidade operacional já disponível: como esta própria sessão é conduzida por um LLM (Claude Code) com capacidade real de composição textual, o roteiro do Gate 3A foi **de fato gerado por esse LLM como parte do trabalho desta sessão** — não por uma chamada de API programática adicional, e não por um texto hardcoded reaproveitado do Gate 2. Isso é `CONTENT_GENERATION_PASS`, não `INFRASTRUCTURE_PASS` (distinção exigida pelo briefing de Gate 3, §40): o texto é composição original, endereçando o briefing real usado nesta execução.

Não foi criado um "framework genérico de providers" — `ScriptGenerationPort` tem hoje um único consumidor real (o driver do Gate 3A) e uma única estratégia concreta.

### 38.4 Script Artifact

`script.md` (artefato editorial, para leitura humana) + `validation_report.json` (saída dos validadores). Nenhum `script.json` foi necessário nesta fase — não há consumidor real que precise da forma estruturada ainda (a validação lê o Markdown diretamente).

### 38.5 Deterministic Script Validators

| Check | O que mede | O que NÃO finge medir |
|---|---|---|
| `word_count` | Contagem de palavras (`count_words`, REUSE_AS_IS) | — |
| `estimated_duration_seconds` / `duration_status` | `TOO_SHORT` / `WITHIN_TARGET` / `TOO_LONG` contra `target_min/max_minutes` (via `speakable_duration_seconds`, REUSE_AS_IS) | Duração real (isso só existe pós-TTS, Gate 3B/3D) |
| `must_include_coverage` | Presença de cada item por correspondência textual (case-insensitive) | Cobertura *semântica* — marca `human_review_required=True` quando algo não é encontrado literalmente, em vez de reprovar automaticamente uma paráfrase válida |
| `must_avoid_violations` | Ausência de cada padrão proibido | — (é uma checagem de presença/ausência, determinística por natureza) |
| `repetition` | Sentenças quase idênticas repetidas, parágrafos consecutivos com abertura idêntica | Repetição *temática* intencional (refrão, callback) — heurística grosseira, não um motor semântico |
| `structure_present` | Existência de ao menos abertura, desenvolvimento e uma seção final reconhecível por proporção de tamanho/posição | **Não** julga se o gancho é bom, se o ritmo funciona ou se a resolução é satisfatória — isso é humano, sinalizado como `human_review_required=True` sempre |
| `non_empty_sections` | Nenhum parágrafo vazio/malformado | — |

Saída:
```json
{
  "status": "PASS | PASS_WITH_WARNINGS | FAIL",
  "word_count": 0,
  "estimated_duration_seconds": 0.0,
  "duration_status": "TOO_SHORT | WITHIN_TARGET | TOO_LONG",
  "checks": [{"name": "...", "passed": true, "detail": "..."}],
  "warnings": [],
  "human_review_required": true
}
```
`human_review_required` é **sempre `true`** neste v0.1 — nenhuma combinação de checks determinísticos substitui o julgamento humano sobre interesse, emoção, ritmo, curiosidade, retenção, originalidade ou qualidade editorial (regra 44 do briefing de Gate 3).

### 38.6 Factuality

`factuality_mode` do briefing é repassado ao `VideoSpecification` e registrado no manifesto. Nenhum sistema de fact-checking/pesquisa foi construído (fora de escopo do Gate 3A). Para o briefing real usado nesta execução, `factuality_mode = "creative"` (ficção derivada do exemplo já existente no repositório) — risco factual mínimo por construção, não por verificação.

### 38.7 Human Gate A

Ao final do Gate 3A, a execução **para**. Entrega ao humano: briefing, video specification, `script.md`, relatório de validação, duração estimada, avisos. Pergunta central: **"Este roteiro é bom o suficiente para justificar produzir voz e imagens?"** Não avança para 3B sem essa decisão.

**Status: `GATE_3A_HUMAN = PASS`.** O roteiro de `runs/20260823T185859Z-gate3a-script/working/script.md` foi revisado e aprovado. Esse texto (hash `content_hash`, registrado no `run_manifest.json` do Gate 3B) é a versão canônica e imutável usada por todos os gates seguintes — nenhuma reescrita silenciosa é permitida (§43.4).

### 38.8 Aprendizado registrado (backlog técnico, não implementado)

```text
P1 CANDIDATE: Editorial / Causal Consistency Critic
```
Motivo: os validadores determinísticos do Gate 3A (§38.5) passaram integralmente, mas a revisão humana do roteiro identificou uma questão de coerência causal/cronológica que nenhum check automatizado poderia ter pego (por design — nenhum validador determinístico avalia lógica causal entre eventos). Isso não é implementado agora e não é um novo agente — é só um registro de que, se o Lite crescer, um crítico determinístico de consistência causal/cronológica (não semântico, não um LLM-juiz) seria um candidato razoável de P1, sem inventar escopo além do que a evidência já mostrou ser necessário.

## 39. Gate 3B — Voice Quality (implementado — bake-off; escolha humana pendente)

```text
APPROVED SCRIPT → VOICE TEST EXCERPT → 2-3 CANDIDATES (mesmo texto) →
AUDIO SAMPLES → OBJECTIVE QA → HUMAN LISTENING TEST → SELECTED VOICE
```
`GATE_2_TTS != GATE_3_TTS` continua valendo — a SAPI5 do Gate 2 entra aqui só como **baseline** de comparação, não como candidata a produção. Detalhes completos em §43.

## 40. Gate 3C — Visual Quality (especificado, NÃO implementado)

```text
APPROVED SCRIPT → VISUAL BIBLE LITE → 5 VISUAL BEATS → 5 REAL GENERATED IMAGES → HUMAN VISUAL REVIEW
```
Visual Bible Lite implementada **só** neste gate, e só com os campos relevantes ao briefing (`characters`/`historical_period` etc. só existem se o briefing os justificar — nunca um schema genericamente grande). Um "visual beat" é uma unidade narrativa que justifica mudança visual — não `1 parágrafo = 1 imagem` nem `X segundos = 1 imagem`. Este é o gate apropriado para testar formalmente a hipótese de geração nativa de imagem do Codex via `image_manifest.json` (discovery Lite §14, §23 do briefing de Gate 3) — sem acoplar o domínio ao Codex. Só depois de aprovação humana das 5 imagens ("estas imagens parecem pertencer à mesma produção?") a geração em escala (15-30+, quantidade determinada por ritmo narrativo, não por meta fixa) é autorizada.

## 41. Gate 3D — Full Production (especificado, NÃO implementado)

Só após 3A + 3B + 3C `PASS`. Pipeline completo: briefing → video spec → roteiro aprovado → estratégia de voz aprovada → Visual Bible → plano visual → assets conforme necessário → narração → timeline → captions (sidecar `.srt`, versão Lite isolada — não reutilizar `render_srt`/`SubtitleCue` legacy, decisão já tomada no Gate 1) → música opcional (background only, volume conservador, sem Music Agent) → FFmpeg → QA completo (incluindo captions parseáveis, thumbnail, metadata, manifesto fechado, todos os assets obrigatórios contabilizados) → `youtube_bundle/` → assistida humana integral. `HUMAN_PASS` sozinho prova E2 plenamente; `HUMAN_PASS_WITH_NOTES` deve registrar exatamente que edições seriam necessárias e se exigem editar o MP4.

## 42. P0-Evidence vs. P0-Product — Gate 3A

**P0-Evidence do Gate 3A (nada além disso bloqueia):** `BriefingSchema`, `VideoSpecification`, `ScriptGenerationPort` + `OperatorAuthoredScriptStrategy`, validadores determinísticos, `script.md` + `validation_report.json`, manifesto do run.

**P0-Product (fora do Gate 3A, não implementado nesta execução):** Gate 3B (TTS de publicação), Gate 3C (Visual Bible Lite + imagens reais), Gate 3D (captions, thumbnail, metadata, música, bundle completo, QA completo). Nenhum desses foi antecipado — ver Architecture Drift Check no relatório de implementação do Gate 3A.

---

# PART VI — GATE 3B: VOICE BAKE-OFF (implementado)

## 43. Voice Bake-off Architecture

### 43.1 LOCAL_FIRST != OFFLINE_ONLY

Princípio formalizado por exigência direta do Gate 3B: **uma ferramenta pode ser operada localmente e ainda depender de serviço remoto.** `edge-tts` roda a partir desta máquina, mas cada síntese é uma chamada de rede real ao serviço de voz da Microsoft (`speech.platform.bing.com`) — sem API key, sem custo monetário observável, **com** dependência de rede. Nunca declarar `network_required=False` para essa estratégia só porque nenhuma variável de ambiente de credencial foi usada. Cada `NarrationResult`/entrada de proveniência registra, no mínimo: `execution_location`, `network_required`, `external_api_direct_call`, `observable_api_cost`, `provider/service dependency` — nunca apenas "local" como rótulo binário.

| Candidato | `execution_location` | `network_required` | `external_api_direct_call` | `observable_api_cost` |
|---|---|---|---|---|
| SAPI5 (`Microsoft Maria Desktop`) | local | NÃO | NÃO | 0.00 USD |
| edge-tts (`pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural`) | local (processo) + remoto (síntese) | **SIM** | NÃO (sem API key; é um serviço público sem autenticação) | 0.00 USD observável, mas não "offline" |

### 43.2 Candidatos Investigados

Investigação prática (não hipotética) antes de escolher os 2-3 candidatos finais:

1. **SAPI5 Desktop** (`System.Speech`) — confirmado disponível desde o Gate 2 (`Microsoft Maria Desktop`, pt-BR). Usado como **baseline obrigatório**.
2. **Windows OneCore** (`Microsoft Maria`/`Microsoft Daniel`, pt-BR) — **investigado e rejeitado nesta execução**: os tokens de voz existem no registro (`HKLM:\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens`), mas a API WinRT (`Windows.Media.SpeechSynthesis.SpeechSynthesizer`) reporta `AllVoices.Count = 0` — os pacotes de voz reais não estão instalados (só o registro, sem os dados neurais baixados via Configurações → Hora e Idioma → Voz). Não presumido disponível só por aparecer no registro (regra "verificar capabilities reais antes de afirmar que existem").
3. **edge-tts** — instalado (`pip install edge-tts`, justificado: é o alvo explícito de investigação deste gate), testado com sucesso, 3 vozes pt-BR descobertas via `python -m edge_tts --list-voices`: `pt-BR-AntonioNeural` (M), `pt-BR-FranciscaNeural` (F), `pt-BR-ThalitaMultilingualNeural` (F). Duas usadas no bake-off (Francisca e Antonio) — terceira não testada, sem prejuízo (§5 do briefing: "2-3 candidatos", não benchmark exaustivo).

### 43.3 Composição Final do Bake-off

```text
Candidate A — SAPI5 baseline (Microsoft Maria Desktop, local:sapi5)
Candidate B — edge-tts (pt-BR-FranciscaNeural, external_api:edge_tts)
Candidate C — edge-tts (pt-BR-AntonioNeural, external_api:edge_tts)
```
Mapeamento real preservado em `voice_candidates.json` (por run); nomes de arquivo (`voice_A.*`/`voice_B.*`/`voice_C.*`) não revelam provider, para reduzir viés na revisão humana.

### 43.4 Trecho de Teste

Extraído **literalmente** (sem reescrita) do `script_approved.md` congelado — parágrafos 9, 11, 13, 15 e 17 (contíguos), cobrindo descrição de cena, transição narrativa, diálogo curto e longo, suspense, nomes próprios (Elias, Mariana, Portovelho), um número (1986), pausa natural entre parágrafos e uma pergunta final. 238 palavras, ~95,2s estimados — levemente acima da faixa "~60-90s" sugerida, aceito porque a diretriz é explicitamente não rígida e a cobertura de desafios narrativos era mais importante que o alvo exato de duração.

### 43.5 NarrationPort — Primeiro Consumidor Real de Qualidade

`NarrationRequest` ganhou um campo `voice: str | None` (para permitir A/B/C sobre o mesmo texto); `NarrationResult` ganhou `generation_time_seconds` e `timing_data_available`. Nenhum outro parâmetro (rate/pitch/volume) foi adicionado — não haveria teste real deles neste gate (regra "teste apenas os que tenham efeito perceptível"). `EdgeTtsNarrationStrategy` é a segunda implementação real do port (a primeira foi `Sapi5NarrationStrategy`, Gate 2) — o contrato já provou suportar 2 estratégias sem mudança de forma, validando a decisão de tê-lo criado no Gate 2.

### 43.6 Timing Data

`edge-tts` fornece `SentenceBoundary` events (offset/duração/texto por sentença) — capturados e salvos como `.timing.json` ao lado do áudio quando disponíveis. SAPI5 não fornece nada equivalente por este caminho (`System.Speech` via subprocess descarta eventos de progresso). Não é requisito para vencer o bake-off — só registrado quando existe.

### 43.7 Objective Audio QA

Por candidato, via `ffprobe`/`volumedetect` (reaproveita o padrão do `qa.py` do Gate 2, generalizado para áudio solto em `audio_qa.py`): `duration_seconds`, `sample_rate`, `channels`, `codec`, `file_size_bytes`, `mean_volume_db`, `max_volume_db`. Nenhum "quality score" algorítmico foi inventado — essas métricas não escolhem a voz, só descartam falhas técnicas óbvias (arquivo não abre, sem áudio, silêncio). A escolha é sempre humana (§16 do briefing do Gate 3B).

### 43.8 Human Gate B (Voice)

`HUMAN_VOICE_REVIEW.md` gerado por run, sem revelar o mapeamento provider↔letra no corpo principal. Pergunta central: **"Eu ouviria esta voz voluntariamente por mais de dez minutos?"** Vereditos possíveis por candidato: `HUMAN_PASS` / `HUMAN_PASS_WITH_NOTES` / `HUMAN_FAIL`. Se todos falharem, o resultado válido é `GATE_3B_FAIL_REVISE` — nunca escolher "a menos ruim" só para avançar.

### 43.8.1 GATE_3B_HUMAN_SELECTION = PASS (Voz C)

Registrado formalmente: a Voz C (edge-tts, `pt-BR-AntonioNeural`) foi aprovada pelo bake-off humano como a melhor candidata entre A/B/C. Essa decisão não é reaberta nos gates seguintes sem evidência nova de problema.

### 43.9 Full Narration — implementado (Gate 3B.2)

Após `GATE_3B_HUMAN = PASS` (voz C selecionada), o roteiro aprovado foi sintetizado **por inteiro** com a configuração exata da voz C (`pt-BR-AntonioNeural`, `rate=+0%`, `pitch=+0Hz`, `volume=+0%`, `boundary=SentenceBoundary` — nenhum parâmetro alterado em relação ao bake-off), numa única chamada (sem segmentação — desnecessária, o texto de ~1684 palavras foi sintetizado de uma vez). Resultado: **650,3s (~10,84min) reais**, `WITHIN_TARGET` (10-15min), 155 palavras/minuto reais (vs. 150 wpm assumido no Gate 3A — diferença de ~3,5% em relação à estimativa de 673,6s). Duração real passa a ser a fonte de verdade, substituindo a estimativa de palavras do Gate 3A.

**Completeness check:** 99 `SentenceBoundary` == 99 sentenças detectadas no roteiro (`sentence_split`, REUSE_AS_IS); primeira e última sentença do roteiro confirmadas presentes no primeiro/último boundary; último boundary (650,25s) alinhado à duração real do arquivo (650,30s) dentro da tolerância — nenhum truncamento silencioso.

**Human Gate B (escala)** — pergunta central: *"Essa mesma voz continua boa quando deixa de narrar 95 segundos e passa a carregar a história inteira?"* Pacote de revisão distribuída (início/meio/fim, ~75-77s cada, **recortados do áudio completo real via FFmpeg, nunca resintetizados**, com cortes alinhados a fronteiras de sentença) enviado ao usuário.

**Status: `GATE_3B2_HUMAN = PASS`.** A narração completa (650,3s) foi aprovada. `GATE_3B` fecha como `PASS` — a Voz C é a narração aprovada para o vídeo completo. Gate 3C foi autorizado com base nessa decisão.

### 43.10 Status da Dependência `edge-tts`

```text
GATE_3B (bake-off): experimental dependency (instalada no venv, pyproject.toml não alterado)
GATE_3B.2 (escala completa, prova técnica bem-sucedida): E2-approved narration dependency
                                                          (formalizada em pyproject.toml, extra `lite`)
E4 (produção): NÃO decidido — precisa reavaliação (ver risco abaixo)
```

**Risco registrado, não resolvido:**
```text
RISK: edge-tts depende de um serviço de rede não contratual (não é uma API pública documentada/garantida pela Microsoft).
E2: ACCEPTED — custo zero observável, qualidade validada por bake-off + prova de escala humana.
E4: MUST_REEVALUATE — antes de qualquer decisão de produção, avaliar se um contrato de API formal (ex.: Azure Cognitive Services Speech, que usa o mesmo motor de voz sob um SLA pago) é necessário.
```
`LOCAL_FIRST != OFFLINE_ONLY` (§43.1) continua valendo: a dependência é operada localmente, mas com síntese remota — `network_required=true`, `direct_paid_api=false`, `observable_external_api_cost=0.00 USD`.

---

# PART VII — GATE 3C: VISUAL QUALITY & CONSISTENCY (implementado)

## 44. Fluxo Implementado

```text
APPROVED SCRIPT + FULL NARRATION + REAL SENTENCE TIMINGS (99 boundaries, 650.3s)
   ↓ (hashes verificados, sem drift)
VISUAL BIBLE LITE (RELOJOEIRO_VISUAL_BIBLE)
   ↓
5 VISUAL BEATS (timestamps reais, não estimados por word count)
   ↓
IMAGE GENERATION MANIFEST (image_manifest.json — fronteira engine/operador)
   ↓
verificação de capacidade nativa do ambiente (Claude Code: NÃO disponível, verificado)
   ↓
autorização humana explícita para chamada paga específica (OpenAI, ~US$0,10-1,00)
   ↓
5 IMAGENS REAIS (gpt-image-1, 1 tentativa cada, sem retry necessário)
   ↓
QA objetiva de arquivo (ffprobe) + Human Visual Review package
```

## 45. Visual Bible Lite — Campos Usados e Descartados

Implementada em `src/pedroarte_youtube_engine/lite/visual_bible.py`. Campos incluídos porque a história os exige: `overall_style`, `realism_level`, `color_language`, `lighting`, `environment_language`, `mood`, `characters` (Elias, Mariana), `hero_object` (o relógio de vidro), `forbidden_elements`, `continuity_constraints`. Campos da hipótese original **descartados por falta de necessidade real**: `camera_language`/`composition` como campo global (a composição é decidida por beat, não globalmente), `period_language` separado (dobrado em `continuity_constraints` — a história é deliberadamente atemporal), `recurring_objects` genérico (só há um hero object real nesta história).

## 46. Visual Beat Contract

`src/pedroarte_youtube_engine/lite/visual_beats.py`: `id`, `start_seconds`, `end_seconds`, `script_excerpt`, `narrative_function` (enum de 10 valores, Gate 3C §8), `subject`, `environment`, `action`, `visual_intent`, `continuity_refs`. Campo `importance` da hipótese original **descartado** — nenhum consumidor real nesta fase (nada lê esse campo para decidir nada ainda); adicionar só se um consumidor real aparecer.

## 47. Cinco Beats Selecionados (timing real, Gate 3B.2)

| Beat | Tempo real | Função | Testa |
|---|---|---|---|
| A | 0.1s–21.9s | HOOK | Objeto (relógio de vidro), close-up |
| B | 65.5s–80.5s | ESTABLISHING | Ambiente (oficina/vitrine/Portovelho) |
| C | 165.7s–184.3s | DISCOVERY | Personagem sozinha (Mariana) |
| D | 254.8s–266.4s | CONFRONTATION | Multi-personagem (Elias + Mariana) + objeto |
| E | 573.2s–588.3s | RESOLUTION | Payoff — callback direto ao Beat B (mesma vitrine) |

Não são os 5 primeiros beats nem escolhidos por espaçamento uniforme — selecionados para testar simultaneamente continuidade de objeto, de ambiente, de personagem isolado, composição multi-personagem e o payoff visual (Gate 3C §20-21).

## 48. Image Generation Manifest & Separation Principle

`image_manifest.json` contém 5 `ImageGenerationRequest` (reaproveitando o port do Gate 2 sem nenhuma mudança de forma — mais um consumidor real do mesmo contrato). O prompt segue a fórmula do §29 do briefing: `GLOBAL VISUAL LANGUAGE (style_prefix) + SCENE REQUIREMENTS + CHARACTER/OBJECT CONTINUITY + COMPOSITION`, com `negative_constraints` derivado de `forbidden_elements`. A engine nunca menciona "OpenAI"/"Codex"/"DALL-E" — o manifesto é a fronteira, materializável por qualquer operador.

## 49. Execution Environment — Verificado, Não Presumido

```text
execution_environment: claude_code
native_image_generation_available: false (nenhuma ferramenta de geração de imagem
                                            disponível nas ferramentas desta sessão —
                                            verificado por ausência real, não suposição)
```
A hipótese "Codex pode materializar via geração nativa sem chamada externa" **não pôde ser testada nesta execução** (esta sessão é Claude Code) — permanece em aberto para uma sessão Codex real, exatamente como já registrado no discovery Lite e no Gate 3B.

## 50. Autorização Humana para API Externa

Antes de qualquer chamada paga, o operador humano foi consultado explicitamente (Separation Principle + Cost of Failure — nunca presumir autorização de gasto). Escolha registrada: gerar via OpenAI (`gpt-image-1`), custo estimado ~US$0,10-1,00 total para as 5 imagens. `ANTHROPIC_API_KEY` não entrou em nenhum momento nessa decisão — não é candidata a provider de imagem (regra já registrada nos gates anteriores).

## 51. Resultado da Geração

5/5 imagens geradas com sucesso, **1 tentativa cada** (nenhum retry necessário). Tamanho real retornado pela API: **1536×1024** — o maior "landscape" nativo do `gpt-image-1`, que é **3:2 (1,5)**, não verdadeiramente 16:9 (1,778). Registrado como limitação real, não escondida: o pipeline de montagem (Gate 3D, FFmpeg) precisará recortar/preencher para o 16:9 final — consistente com a instrução de que a geração pode usar resolução nativa diferente, desde que registrada.

## 52. Achados de Continuidade (para o Human Visual Review, não decididos aqui)

Observados antes do envio ao humano, sinalizados explicitamente, não escondidos:
- **Elias Varga** varia de aparência entre o Beat A (mais jovem/sem barba) e o Beat D (barbado, mais idoso) — possível falha de continuidade de personagem.
- As vitrines dos Beats B e E mostram ~15 relógios (grade 5×3), não os 17 especificados na Visual Bible/roteiro.
- O Beat B/E renderizaram texto legível ("OFICINA DE ELIAS", "PORTOVELHO") apesar da política de não depender de texto gerado corretamente (§19 do briefing) — um bônus não garantido, não um requisito atingido por design.

Nenhum desses achados foi corrigido automaticamente — são exatamente o tipo de evidência que o Human Visual Review deve julgar.

## 53. Objective Image QA

Via `ffprobe` (reaproveitado, sem adicionar Pillow): arquivo existe, abre, dimensões, formato, tamanho não-zero. 5/5 imagens PASS. Aspect ratio real (1536×1024, 3:2) sinalizado como fora da tolerância de 16:9 — não escondido, registrado como limitação (§51).

## 54. Dependência `openai`

Formalizada em `pyproject.toml`, extra `lite` (`openai>=3.0,<4`), mesma classificação de risco do `edge-tts`: **E2-approved**, não E4/produção. Chave lida exclusivamente de `OPENAI_API_KEY` (ambiente/`.env`), nunca impressa ou registrada em log/proveniência.

## 55. Gate 3D Continua Bloqueado

```text
GATE_3D = BLOCKED_PENDING_HUMAN_VISUAL_PASS
```
Nenhuma escala para dezenas de imagens, nenhum thumbnail, nenhuma legenda final, nenhuma montagem de vídeo, nenhuma música — todos adiados até decisão humana sobre as 5 imagens do Gate 3C.

## 56. `GATE_3C_HUMAN` e Revisão de Endurecimento de Continuidade

**Status: `GATE_3C_HUMAN = PASS_WITH_NOTES`.** A direção artística da Visual Bible foi aprovada — **não redesenhada**. A aprovação veio com duas notas empíricas (não hipotéticas, observadas nas 5 imagens reais do Gate 3C): variação na aparência de Elias entre imagens, e o relógio de vidro gerado com caixa metálica visível.

Antes de qualquer geração em escala do Gate 3D, foi feita **uma única revisão de endurecimento de continuidade** da Visual Bible (`src/pedroarte_youtube_engine/lite/visual_bible.py::RELOJOEIRO_VISUAL_BIBLE_HARDENED`, campo `version="v2_gate3d_hardened"`). A v1 original (`version="v1_gate3c"`) é preservada inalterada no código como registro histórico/auditável.

**O que NÃO mudou** (idêntico entre v1 e v2, verificado por teste): `overall_style`, `realism_level`, `color_language`, `lighting`, `environment_language`, `mood`, e o personagem Mariana Duarte por inteiro (nenhuma falha de continuidade foi observada nela).

**O que foi reforçado:**
- **Elias Varga:** idade aparente travada em "sempre 62 anos, nunca mais jovem, nunca mais velho"; estrutura facial e silhueta descritas explicitamente; cabelo com comprimento/recuo fixos; vestuário reduzido a uma única combinação; **política de barba travada — sempre sem barba, adicionado a `forbidden_elements`** (causa raiz da variação observada: a v1 nunca definia isso).
- **Relógio de vidro:** descrição reforçada para "SEM NENHUMA caixa, aro, moldura ou coroa de corda metálica visível", com **"caixa/aro/moldura metálica visível" adicionado a `forbidden_elements`**; geometria circular reconhecível adicionada; explicitamente registrado que a inscrição não precisa ser legível (já era política, agora mais explícita).
- **Contagem de relógios:** formalizada como intenção narrativa/melhor esforço — 15 a 18 relógios aceitável, **não é motivo de nova geração**, conforme instrução explícita de não perseguir perfeição num detalhe secundário.

```text
GATE_3C_VISUAL_BIBLE_HASH: sha256:d732097056a83a03160fc0e8fa2b9a553a158a094bbf002a86c13b37723c7d64
  (hash original registrado no run_manifest.json do Gate 3C — método de hash da época,
  sem campo `version`; preservado como valor histórico, não recalculado)

GATE_3D_HARDENED_VISUAL_BIBLE_HASH: sha256:2406658b4d0a33e77ddbd7393b71d385a8d8b1dd1de14ff6f3676521f1c1ee75
  (structural_hash de RELOJOEIRO_VISUAL_BIBLE_HARDENED.to_dict(), método novo,
  inclui version="v2_gate3d_hardened")

HARDENING_REASON: Gate 3C gerou 5 imagens reais; revisão humana (com achados já
  sinalizados antes do julgamento) confirmou duas fraquezas de continuidade reais:
  (1) Elias variou em idade aparente/presença de barba entre as imagens A e D — a v1
  não travava política de barba nem descrição facial explícita; (2) o relógio de
  vidro foi gerado com caixa metálica visível — a v1 dizia "inteiramente de vidro"
  mas não proibia explicitamente uma caixa metálica em forbidden_elements. Esta é
  uma revisão de ENDURECIMENTO, não um redesenho: nenhum campo de estilo, paleta,
  iluminação, realismo, ambiente ou humor foi alterado; Mariana foi mantida idêntica.
```

`tests/lite/test_visual_bible_hardening.py` (10 testes) confirma programaticamente que os campos não-relacionados permanecem idênticos, que as duas falhas específicas agora são proibições explícitas, e que a tolerância de contagem de relógios está registrada — evitando que uma futura geração em escala rejeite imagens boas só por causa de 15 ou 16 relógios em vez de 17.

`GATE_3D` permanece `BLOCKED` — esta revisão prepara a Visual Bible para quando a geração em escala for autorizada, mas não a autoriza por si só.

---

# PART VIII — GATE 3D: PLANNING & MASS GENERATION COST GATE

**Estado autoritativo (override humano explícito):** `GATE_3C = PASS` (`GATE_3C_TECHNICAL = PASS`, `GATE_3C_HUMAN = PASS_WITH_NOTES`, notas resolvidas pelo endurecimento §56). `GATE_3D = AUTHORIZED` — mas só para planejamento; a autorização de gastar em 5 imagens no Gate 3C **não** se estende à geração em escala (regra explícita, não presumida).

## 57. Plano Visual Completo

`src/pedroarte_youtube_engine/lite/visual_plan_gate3d.py::GATE3D_FULL_VISUAL_PLAN` — **30 beats**, cobrindo os 650,3s inteiros da narração aprovada sem furos nem sobreposição (`validate_plan_coverage`, testado). A contagem não é uma meta fixa: nasceu de agrupar as 99 sentenças reais em unidades visuais coerentes (mudança de assunto/lugar/personagem em foco/função dramática = novo beat; diálogo rápido no mesmo momento = mesmo beat). Média resultante: ~21,7s de duração por beat.

Os 5 beats do Gate 3C (`beat_A`..`beat_E`) permanecem nas mesmas posições da timeline, marcados `reuse_of=<próprio id>` — não regenerados.

## 58. Política de Reuso dos Assets do Gate 3C

`GATE3C_ASSET_REUSE_DECISIONS` — as 5 imagens aprovadas **não são rejeitadas automaticamente** por exibirem um dos desvios históricos que motivaram o endurecimento. Decisão registrada por asset:

| Beat | Decisão | Flag | Motivo |
|---|---|---|---|
| beat_A | REUSE | monitorar | Relógio com caixa metálica visível — é a âncora visual do hero object (primeira aparição); reavaliar na montagem final. |
| beat_B | REUSE | nenhum | Sem desvio observado. |
| beat_C | REUSE | nenhum | Sem desvio observado. |
| beat_D | REUSE | monitorar | Instância real da variação de barba de Elias — cena de confrontação, não âncora do personagem; reavaliar se o corte próximo a beats sem barba (ex. beat_10, beat_12) torna a inconsistência perceptível. |
| beat_E | REUSE | nenhum | Contagem de relógios tolerada por política — não é motivo de regeneração. |

Nenhuma decisão de regenerar foi tomada agora — só na montagem final, se a inconsistência se mostrar materialmente perceptível (critério explícito do briefing de Gate 3D).

## 59. Normalização 3:2 → 16:9 (registrado, não implementado nesta execução)

Confirmado no Gate 3C: `gpt-image-1` retorna 1536×1024 (3:2), não 16:9 nativo. Política registrada para quando a montagem (FFmpeg) for implementada: recorte "composition-safe" para 1920×1080, nunca esticar a imagem; permitir informação mínima de foco/recorte só onde um corte central removeria conteúdo importante. Não implementado nesta execução de planejamento — fica para a fase de montagem do Gate 3D.

## 60. Mass Generation Cost Gate

```text
TOTAL_VISUAL_BEATS: 30
GATE_3C_ASSETS_REUSABLE: 5 (beat_A, beat_B, beat_C, beat_D, beat_E)
NEW_IMAGES_REQUIRED: 25
NATIVE_IMAGE_GENERATION_AVAILABLE: false (verificado nesta sessão Claude Code — mesma checagem do Gate 3C)
IMAGE_GENERATION_METHOD: external_api:openai (necessário — nativa indisponível)
ESTIMATED_IMAGE_GENERATION_COST: US$0,58–US$6,60 (estimativa, não garantida pela API; considera ~15% de retries assumidos, não observados)
```

Conforme instruído: **STOP explícito antes de qualquer geração nova.** A autorização anterior (5 imagens do Gate 3C) não se estende a esta geração em escala — autorização humana explícita solicitada separadamente para este gasto maior.

## 61. Reforço da Separação Engine/Operador

`GATE3D_FULL_VISUAL_PLAN` e `image_manifest.json` (quando gerado) continuam sendo a fronteira — nenhuma menção a "OpenAI"/"Codex"/"Claude" no domínio. A hipótese de geração nativa via Codex permanece não testável nesta sessão.

## 62. Handoff de Imagem a Custo Zero (execução real)

O usuário optou por não autorizar a chamada paga direta desta sessão (§60) e, em vez disso, solicitou o pacote de handoff (`scripts/lite/run_gate3d_handoff.py`) — `image_manifest_gate3d.json` (25 requests) + `GENERATE_THESE_IMAGES.md` (pacote humano-legível com prompt completo e caminho de destino por beat). As 25 imagens foram materializadas **fora desta sessão** (`external_api_cost_this_session = 0.00 USD`) e devolvidas no diretório esperado. Achado técnico registrado: o operador usado para a geração retornou imagens em **1672×941 (≈16:9 real, 1.7768)**, diferente do 1536×1024 (3:2) que a OpenAI retornou no Gate 3C — evidência de que o método de geração usado no handoff foi diferente do `gpt-image-1` via API direta (não identificado nem necessário identificar; a engine não depende de saber qual foi).

## 63. Montagem Completa — Resultado Real

```text
FULL_VIDEO_PATH: runs/20260823T223458Z-gate3d-planning/output/youtube_bundle/video.mp4
DURATION: 650.30s (~10.84 min) — idêntica à narração aprovada no Gate 3B.2
RESOLUTION: 1920x1080 (16:9 verdadeiro em TODAS as 30 imagens, incluindo as 5 do
            Gate 3C em 3:2 e as 25 do handoff em ~16:9 — normalização
            "scale...force_original_aspect_ratio=increase,crop" embutida no
            mesmo passe do Ken Burns, sem arquivo intermediário separado)
VIDEO_CODEC: h264 | AUDIO_CODEC: aac
RENDER_TIME: 431.6s (30 segmentos) + concat + mux
AUTOMATED_QA: 10/10 PASS (arquivo abre, duração ≥600s, streams presentes,
              resolução exata, codecs corretos, áudio audível -20.9dB,
              sem clipping -2.6dB)
CAPTIONS: 99 cues reais (`lite/captions.py`, decisão REPLACE do Gate 1
          finalmente exercida — nunca importou `domain/segment.py`)
THUMBNAIL: reuso de beat_A.png (nenhuma imagem nova gerada para isso)
CHAPTERS: 9, derivados de transições reais de narrative_function no plano de 30 beats
MUSIC: nenhuma (explicitamente adiada, conforme instruído)
```

`youtube_bundle/` completo: `video.mp4`, `thumbnail.png`, `captions.srt`, `metadata.json`, `script.md`, `manifest.json`, `assets/` (narração + 30 imagens). `GATE_3D` fica `BLOCKED_PENDING_HUMAN_FULL_WATCH` — o gate final da fase experimental (SDD_SPDD.md §7 Definition of Done: `HUMAN_PASS` sozinho prova E2 plenamente).

---

# PART IX — CLICK PACKAGE / THUMBNAIL CONTRACT (especificado, NÃO implementado)

**Origem:** Gate 3D e Gate 3D.1/3D.2 resolveram inteiramente o **Watch Problem** (roteiro, narração, visuais, movimento, legendas, música — "o vídeo retém e satisfaz depois do clique?"). Nenhum deles endereça o **Click Problem** — "a embalagem faz o espectador pretendido querer clicar?" — que até esta revisão dependia inteiramente do reuso mecânico de `beat_A.png` como thumbnail, sem nenhum contrato de design, geração ou revisão humana dedicada. Esta Parte formaliza esse contrato. Relatório de acompanhamento completo, com exemplo trabalhado: [THUMBNAIL_CLICK_PACKAGE_SDD_REPORT.md](THUMBNAIL_CLICK_PACKAGE_SDD_REPORT.md).

## 64. Click Problem vs. Watch Problem

```text
WATCH PROBLEM ("por que continuar assistindo?"):
  roteiro, narração, visuais, movimento, legendas, música, montagem
  → já coberto por Gates 2/3A/3B/3C/3D/3D.1/3D.2

CLICK PROBLEM ("por que clicar?"):
  título, thumbnail
  → NÃO coberto até esta revisão — thumbnail era reuso mecânico de frame,
    sem contrato de design, sem candidatos, sem revisão humana dedicada
```

`TITLE + THUMBNAIL` deixam de ser decoração de pós-produção e passam a ser um artefato de produto de primeira classe: o **Click Package**.

## 65. Princípio Central

> Uma thumbnail não é "um frame bonito do vídeo aproveitado". É "uma promessa visual deliberadamente desenhada, otimizada para compreensão imediata e curiosidade num feed lotado".

Heurística primária: uma boa thumbnail comunica sua ideia visual central em ~1 segundo ou menos. Isso melhora a embalagem de clique — **não** garante viralidade (§76).

## 66. Click Package — Contrato Mínimo

```text
ClickPackage
  video_title: str
  thumbnail_candidates: list[ThumbnailCandidate]   # default 3, ver §70
  curiosity_gap: str                                # a pergunta central que a embalagem provoca
  title_thumbnail_relationship: str                  # como título e thumbnail se complementam (§67)
  selected_thumbnail: str | None                     # candidate_id escolhido pelo humano
  selection_status: "pending" | "selected" | "rejected_all"
```

Schema deliberadamente raso — sem campos hipotéticos sem consumidor real (nada de `predicted_ctr`, `virality_score`; ver §75/§85 Non-Goals).

## 67. Título e Thumbnail Como Sistema

Título e geração de thumbnail **não são tarefas independentes**. Modelo:

```text
PREMISSA DO VÍDEO
      ↓
CLICK PACKAGE
      ├── TITLE
      ├── THUMBNAIL CONCEPT
      ├── THUMBNAIL TEXT
      └── CURIOSITY GAP
```

A combinação deve produzir `PROMESSA + INTRIGA + COMPREENSÃO`. Regra de complementaridade: título e thumbnail devem se complementar, evitando duplicação — o texto da thumbnail não deve repetir o título inteiro (exemplo em §77 do relatório de acompanhamento).

## 68. Prioridades de Otimização da Thumbnail

```text
1. compreensão imediata
2. curiosidade
3. legibilidade mobile
4. hierarquia visual
5. reconhecimento do assunto
6. sinal emocional/narrativo
7. contraste
8. qualidade estética
```

Uma thumbnail bonita e incompreensível em tamanho de feed é uma thumbnail ruim — compreensão sempre vence estética em caso de conflito (§20 do briefing original).

## 69. Princípio de Uma Ideia Visual

Cada thumbnail comunica **uma** ideia visual primária (ex.: "homem apavorado com o relógio impossível"; não personagem + múltiplos personagens secundários + vários objetos + vários locais + texto longo + setas + selos + elementos decorativos). Sujeito primário preferido: **1**; até **2** quando justificado. Simplicidade visual é feature, não limitação técnica.

Rostos humanos são um mecanismo de atenção poderoso, mas **opcionais** — nunca constitucionalizados como obrigatórios. Quando usados: emoção narrativamente coerente (medo, surpresa, suspeita, tensão, espanto, confusão) — evitar boca aberta exagerada/"cara de choque de youtuber" genérica por padrão.

## 70. Curiosity Gap

Todo candidato define:

```text
WHAT_VIEWER_SEES:      o que a imagem mostra objetivamente
WHAT_VIEWER_INFERS:     a inferência que o espectador faz a partir disso
WHAT_REMAINS_UNANSWERED: a pergunta que a thumbnail deliberadamente não responde
```

O elemento não respondido cria o gap. A thumbnail provoca a pergunta; o vídeo entrega a resposta. Ela não deve resumir a história inteira — deve expor a anomalia, conflito, transformação, emoção, objeto ou pergunta mais convincente, e nada além disso.

## 71. Política de Texto na Thumbnail

Texto é **opcional** — usado quando melhora materialmente compreensão/curiosidade, omitido quando a imagem já comunica o conceito sozinha. Comprimento preferido: **2-5 palavras**; textos maiores exigem justificativa explícita. Evitar frases completas.

Função do texto: intensificar, contradizer, questionar, revelar um fato parcial, ou criar intriga — geralmente **não** apenas descrever a imagem (`"RELÓGIO DE VIDRO"` é fraco; `"ELE NÃO ENVELHECE"` é mais forte — exemplos ilustrativos, nunca hardcoded como resposta fixa).

## 72. Regra Arquitetural: Modelo de Imagem Não Escreve Texto Final

```text
MODELO DE IMAGEM:        gera composição visual SEM tipografia final da thumbnail
RENDERER DETERMINÍSTICO:  adiciona o texto final
```

Motivo: controle de ortografia, fonte, quebra de linha, posicionamento exato, reprodutibilidade, contraste, contorno/sombra, legibilidade mobile, localização — nenhuma dessas propriedades é confiável quando delegada à geração de imagem.

```text
FINAL_TEXT_INSIDE_GENERATION_PROMPT: FORBIDDEN_BY_DEFAULT
```

Exceções exigem justificativa explícita registrada em `provenance`.

## 73. Desenhar Para o Texto Antes de Gerar a Imagem

Ordem correta (nunca a inversa: "gerar imagem → encontrar onde encaixar texto depois"):

```text
conceito de thumbnail → layout → região de texto → requisito de espaço negativo
    → geração de imagem (o prompt já sabe onde precisa de "respiro" visual)
    → sobreposição de texto determinística
```

Regra de espaço negativo: quando há texto, a composição preserva deliberadamente espaço para ele (sujeito à direita → texto à esquerda, e variações análogas). Colisão texto/sujeito:

```text
TEXT_OVER_PRIMARY_SUBJECT: FORBIDDEN_BY_DEFAULT
TEXT_OVER_FACE:            FORBIDDEN
TEXT_OVER_HERO_OBJECT:     FORBIDDEN_BY_DEFAULT
```

Checks geométricos automatizados podem ser adicionados no futuro **só se permanecerem simples** — revisão humana continua autoritativa até lá.

## 74. Política de Tipografia

Política mínima, não um design system completo: peso bold/heavy, alta legibilidade, no máximo ~2 linhas, contorno/sombra controlados quando necessário, texto grande relativo ao canvas. **Nenhuma fonte específica é hardcoded** nesta especificação — só quando o projeto tiver um asset de fonte aprovado com licenciamento conhecido. Contraste: `COMPREENSÃO > CONTRASTE > DETALHE ESTÉTICO` — nunca presumir que imagem cinematográfica de baixo contraste funciona automaticamente como thumbnail.

## 75. Contrato de Geração de Thumbnail

A imagem da thumbnail é gerada especificamente para uso como thumbnail quando necessário — **não** exige reuso de um frame do vídeo (`THUMBNAIL_ASSET != VIDEO_FRAME_BY_DEFAULT`, embora um asset de vídeo existente possa ser reutilizado se satisfizer o Thumbnail Contract). A geração considera: canvas 16:9, sujeito primário, hero object, escala do sujeito, espaço negativo, zona de texto, margens seguras, visibilidade mobile — sujeitos importantes geralmente maiores/mais claros do que num frame cinematográfico normal.

```text
TARGET_RESOLUTION:    1280x720
TARGET_ASPECT_RATIO:  16:9
```

Mantido configurável caso requisitos do YouTube mudem. Se a fonte gerada tiver aspect ratio diferente de 16:9: `crop`/`reframe`/`resize` determinísticos — **nunca esticar** (mesma política já registrada para imagens de vídeo em §59). Preservar sujeito primário, hero object e espaço negativo de texto durante a normalização.

## 76. Renderer Determinístico de Texto

```text
ThumbnailConcept
      ↓
GeneratedImage
      ↓
Crop / Resize
      ↓
Deterministic Typography
      ↓
Contrast Treatment (se necessário)
      ↓
Final 1280x720 Thumbnail
      ↓
Mobile Previews
      ↓
Contact Sheet
```

Implementação futura permanece simples — não um clone de editor de imagem.

## 77. QA Mobile-First

Uma thumbnail não é avaliada só em 1280×720. Escada de revisão (tamanhos configuráveis):

```text
1280x720
320x180
160x90
```

Pergunta-chave: a thumbnail ainda comunica sua ideia primária instantaneamente em tamanho de feed pequeno? Artefato de revisão (QA, não de publicação): `thumbnail_contact_sheet.png`, mostrando cada candidato nos três tamanhos lado a lado.

## 78. Estratégia de Candidatos

Comportamento padrão: **3 conceitos de thumbnail**, conceitualmente diferentes (não a mesma composição com texto trocado). Taxonomia de exemplo (não hardcoded — o conteúdo real pode sugerir alternativa melhor):

```text
A — DRIVEN POR PERSONAGEM
B — DRIVEN POR OBJETO/MISTÉRIO
C — DRIVEN POR EVENTO/CONSEQUÊNCIA
```

`THUMBNAIL_CANDIDATES = 3` por padrão — nunca geração de 20 candidatos, otimização genética, A/B massivo automático ou "enxame de thumbnails" sem evidência futura que justifique.

Contrato mínimo por candidato:

```text
ThumbnailCandidate
  candidate_id: str
  concept: str
  psychological_angle: str
  primary_subject: str
  hero_object_if_any: str | None
  curiosity_gap: {what_viewer_sees, what_viewer_infers, what_remains_unanswered}
  thumbnail_text: ThumbnailText | None
  text_required: bool
  composition: ThumbnailLayout
  image_prompt: str
  image_asset: str                  # caminho do arquivo gerado
  final_thumbnail: str               # caminho pós-renderer determinístico
  mobile_preview: {320x180: str, 160x90: str}
```

```text
ThumbnailLayout
  primary_subject_zone: str          # ex.: "right-third"
  text_zone: str | None              # ex.: "left-third, lower"
  negative_space_required: bool
  safe_margins: {top, bottom, left, right}

ThumbnailText
  text: str
  word_count: int
  line_count: int
  function: "intensify" | "contradict" | "question" | "partial_reveal" | "intrigue"
```

Avaliar (não decidir agora) se o Click Package também produz um pequeno número de candidatos de **título** — preferência por minimalidade (ex.: 3 títulos + 3 thumbnails, nunca combinatória cartesiana de 9 sem justificativa).

## 79. Seleção Humana do Click Package

Antes da conclusão do bundle final, exige-se seleção humana da thumbnail durante a fase de validação experimental/local — humano escolhe entre `THUMBNAIL_A`/`THUMBNAIL_B`/`THUMBNAIL_C`. Automação futura pode ser justificada por evidência real; não agora.

```text
ThumbnailReview
  candidate_id: str
  notices_first: str
  comprehends_in_one_second: bool
  text_readable_immediately: bool
  text_readable_at_160x90: bool
  text_obstructs_subject: bool
  single_dominant_idea: bool
  creates_a_question: bool
  title_adds_information: bool
  accurately_represents_video: bool
  would_click_first: bool
```

## 80. Click Package QA — Duas Camadas

**QA estrutural** (automatizável): resolução correta, aspect ratio correto, contagem de candidatos correta, comprimento de texto dentro da faixa preferida (ou justificado), overlay de texto renderizado, previews mobile criados, contact sheet criado, metadata obrigatória presente.

**QA humana de clique** (não automatizável): compreensão instantânea, curiosidade, legibilidade, hierarquia visual, veracidade, complementaridade com o título, preferência de clique. Julgamento estético nunca é automatizado.

Métricas estruturais candidatas: `THUMBNAIL_WIDTH`, `THUMBNAIL_HEIGHT`, `ASPECT_RATIO`, `TEXT_WORD_COUNT`, `TEXT_LINE_COUNT`, `CANDIDATE_COUNT`, `MOBILE_PREVIEWS_CREATED`, `CONTACT_SHEET_CREATED`, `SELECTED_CANDIDATE`. **Métricas fictícias explicitamente evitadas**: `VIRALITY_SCORE`, `BEAUTY_SCORE`, `CTR_PREDICTION` — só entram se evidência empírica futura justificar.

## 81. Política de Clickbait

```text
PERMITIDO:     reter a resposta, enquadramento dramático, destacar anomalia,
               enfatizar conflito, enfatizar verdade surpreendente
NÃO PERMITIDO: prometer algo ausente do vídeo, fabricar eventos/pessoas/
               resultados, alegações factuais falsas, imagem enganosa que
               muda a premissa real
```

A thumbnail pode dramatizar a apresentação. Não pode falsificar o conteúdo. `CURIOSIDADE ≠ ENGANO`.

## 82. Custo de Geração de Thumbnail

Três candidatos podem exigir três assets visuais gerados. Preserva-se a política de execução existente (§26-28, `OPERATOR_CONTRACT.md`): preferir capacidade nativa/local/operador; evitar API paga sempre que possível; se geração paga for necessária, estimar custo e pedir autorização explícita, exatamente como no fluxo de imagens do Gate 3C/3D (§50, §60). Custo de geração de thumbnail nunca é escondido dentro do custo de vídeo — registrado separadamente em `provenance`.

## 83. Fronteira Engine/Operador (Thumbnail)

```text
ENGINE:     define requisitos de thumbnail (ThumbnailConcept, ThumbnailLayout)
OPERATOR:   materializa os assets de imagem-fonte a partir do manifesto
```

Mesma regra já estabelecida para imagens de vídeo (§21, §61): nenhuma menção a "Codex"/"Claude"/"OpenAI"/"DALL-E"/"GPT Image"/"Anthropic" na lógica de domínio do thumbnail.

## 84. Posição do Click Package no Pipeline

```text
BRIEFING → VIDEO SPECIFICATION → SCRIPT → NARRATION → VISUALS → RETENTION
    → CAPTIONS → MUSIC → VIDEO → CLICK PACKAGE (TITLE, THUMBNAIL A/B/C)
    → HUMAN SELECTION → FINAL YOUTUBE BUNDLE
```

**Questão arquitetural resolvida** (ver relatório de acompanhamento §22 para a análise completa): o Click Package pode, em princípio, começar a ser desenhado assim que roteiro + Visual Bible estiverem estáveis (antes do render final) — a *premissa* da história já é conhecida nesse ponto. Mas a especificação recomenda manter a criação do Click Package **depois** do vídeo final por padrão nesta fase experimental: minimiza acoplamento (nenhuma dependência nova entre o pipeline de thumbnail e o estado intermediário do render), evita esperas desnecessárias (o render de vídeo já é o item mais lento do pipeline; gerar 3 imagens de thumbnail em paralelo a ele economizaria pouco tempo de parede comparado ao risco de complexidade), e preserva conhecimento correto da história final (thumbnails desenhadas antes do render final podem referenciar cenas/momentos que ainda podem mudar). Paralelização é um candidato de otimização futura, não uma exigência atual — não implementada agora.

## 85. Maturidade e Não-Objetivos

YouTube Lite permanece em validação funcional local. O Click Package não é desenhado para milhões de vídeos — requisito atual: produzir 3 candidatos sólidos, renderizá-los corretamente, deixar um humano escolher, empacotar o vencedor.

Explicitamente **fora de escopo** desta especificação: predição automática de CTR, predição automática de viralidade, integração com analytics do YouTube, A/B testing automático, publicação automática, ranking neural de thumbnail, pontuação de emoção facial, simulação de eye-tracking, scraping de concorrentes, geração massiva de candidatos, editor tipo Photoshop, infraestrutura de renderização em nuvem.

A/B testing real de thumbnail no YouTube é documentado como possível capacidade futura E3/E4 (`candidato → publicação → evidência real de CTR → aprendizado`) — **não implementado agora**.

## 86. Mudanças no Artifact Contract e Operator Contract

Ver [ARTIFACT_CONTRACT.md](ARTIFACT_CONTRACT.md) §4/§7 e [OPERATOR_CONTRACT.md](OPERATOR_CONTRACT.md) §6.1 para o layout de `thumbnail_candidates/` e a extensão do fluxo de decisão de geração de imagem ao caso de thumbnail.

## 87. Princípios Registrados

```text
THUMBNAIL É UMA PROMESSA, NÃO UM RESUMO.
UMA THUMBNAIL = UMA IDEIA VISUAL.
TÍTULO + THUMBNAIL = UM CLICK PACKAGE.
TEXTO É OPCIONAL; LEGIBILIDADE NÃO É.
MODELO DE IMAGEM CRIA O VISUAL. CÓDIGO DETERMINÍSTICO CRIA A TIPOGRAFIA.
DESENHE O ESPAÇO NEGATIVO ANTES DA GERAÇÃO.
LEGIBILIDADE MOBILE É OBRIGATÓRIA.
CURIOSIDADE É PERMITIDA. ENGANO NÃO É.
TRÊS CONCEITOS DISTINTOS > VINTE VARIAÇÕES COSMÉTICAS.
SELEÇÃO HUMANA ANTES DE AUTOMAÇÃO.
EVIDÊNCIA REAL DE CTR > VIRALIDADE PREVISTA.
```

`GATE_3D2` continua em andamento de forma independente (Parte VIII/relatórios `GATE_3D2_*`) — esta Parte IX é puramente especificação, sem implementação e sem geração de thumbnail nesta revisão.

---

# PART X — YOUTUBE EXPERIENCE CONTRACT (especificado, NÃO implementado)

**Origem:** Gate 3D.1 e Gate 3D.2 descobriram, empiricamente e não hipoteticamente, duas lições que se repetiriam em qualquer futuro vídeo se não fossem formalizadas: (1) presença técnica de movimento (`zoompan` configurado, YAVG mensurável) não prova presença perceptual de movimento — o vídeo do Gate 3D.1 tinha 100% de cobertura de movimento configurado e ainda assim o humano relatou "o zoom precisa aproximar gradativamente"; (2) presença técnica de música na mixagem (`diferença de nível médio > 0`) não prova audibilidade perceptual — o vídeo do Gate 3D.1 tinha 0.30dB de diferença medida e o humano relatou "o som de fundo ainda está ausente". Esta Parte eleva essas duas lições (e o restante do vocabulário de experiência já usado ad-hoc nos Gates 3D.1/3D.2) a contrato de produto formal, para que a próxima produção não repita a mesma descoberta por acidente. Relatório de acompanhamento completo, com exemplo trabalhado: [YOUTUBE_EXPERIENCE_CONTRACT_SDD_REPORT.md](YOUTUBE_EXPERIENCE_CONTRACT_SDD_REPORT.md).

## 88. Terminologia

Deliberadamente **não** chamado de `ViralVideoContract` — a engine não pode garantir viralidade, milhões de views, CTR, watch time, compartilhamentos ou crescimento de inscritos. Chamado de `YouTubeExperienceContract`, que otimiza para **atenção, retenção, compreensão, imersão, satisfação e prontidão de publicação**. Comportamento real de audiência é quem valida se essas decisões realmente funcionam (§103).

## 89. Click vs. Watch — Dois Problemas Complementares

```text
PROBLEMA A — CLIQUE ("por que clicar?")     → CLICK PACKAGE (Part IX)
PROBLEMA B — ASSISTIR ("por que continuar?") → YOUTUBE EXPERIENCE CONTRACT (esta Parte)
```

Os dois contratos são complementares e **não são fundidos** numa abstração só — cada um tem seu próprio dono conceitual (embalagem vs. experiência) mesmo compartilhando a mesma "promessa" como elo (§93).

## 90. Princípio Central

> A engine não apenas monta mídia. A engine **dirige atenção**.

O pipeline deve eventualmente raciocinar sobre: o que o espectador ouve, o que vê, o que muda, quando muda, que pergunta permanece sem resposta, que estado emocional é pretendido, que informação está sendo revelada, e por que o espectador deveria continuar pelos próximos segundos.

## 91. Experience Timeline

```text
VIDEO SPECIFICATION
        ↓
NARRATIVE RHYTHM
        ↓
   VOICE PLAN │ VISUAL PLAN │ AUDIO PLAN
        ↓
EXPERIENCE TIMELINE
        ↓
FINAL VIDEO
```

**Decisão**: `ExperienceTimeline` é **(B) uma visão conceitual composta a partir das estruturas de timeline já existentes** (`VisualBeat`/`RetentionSegment`/`Cue`/plano de música), não uma nova estrutura de dados. Razão: cada eixo (visual, voz, áudio) já tem seu contrato próprio (`visual_beats.py`, `captions.py`, `audio_mix.py`, `retention.py`); uma nova classe `ExperienceTimeline` armazenando os mesmos dados de novo criaria uma segunda fonte de verdade sem consumidor real. Se um consumidor real precisar de uma visão agregada (ex.: um relatório de QA que cruza os três eixos por timestamp), ele lê e junta as estruturas existentes — não duplica.

## 92. Hook Contract

Comportamento padrão: **`HOOK_BEFORE_BRANDING`**. Evitar por padrão: logo → intro longa → apresentação de canal → "olá pessoal" → contexto → só então a parte interessante. Preferir: conteúdo imediato → curiosidade/conflito/anomalia → história.

O hook cria pelo menos um de: pergunta, anomalia, conflito, promessa, surpresa, consequência, lacuna de informação. O espectador entende rapidamente que algo interessante está acontecendo **e** que algo permanece sem resolução.

**O hook deve honrar a promessa do Click Package** (Part IX):

```text
PROMESSA DO CLICK PACKAGE (título + thumbnail)
        ↓
HOOK CONFIRMA A PROMESSA
        ↓
VÍDEO EXPANDE A PROMESSA
        ↓
PAYOFF CUMPRE A PROMESSA
```

Evitar: thumbnail/título de alta curiosidade seguidos de introdução lenta e não relacionada.

## 93. Primeiros 30 Segundos

Região de retenção particularmente importante. Minimizar: exposição desnecessária, branding, repetição, setup longo, meta-comentário. Maximizar: confirmação da promessa, movimento narrativo, curiosidade, valor antecipado, clareza visual. **Não** codificar cortes arbitrários a cada N segundos só porque os primeiros 30s importam — a regra é sobre conteúdo, não sobre cadência mecânica.

## 94. Narrative Rhythm Contract

Narrativa longa não deve depender de um único hook no segundo zero. O roteiro sustenta curiosidade através de micro-hooks recorrentes, perguntas, respostas parciais, revelações, escaladas, consequências e payoffs:

```text
HOOK → PERGUNTA → RESPOSTA PARCIAL → PERGUNTA MAIOR → COMPLICAÇÃO
     → REVELAÇÃO → CONSEQUÊNCIA → CLÍMAX → PAYOFF
```

Modelo narrativo, não template rígido. Ritmo pergunta/resposta: evitar resolver toda pergunta imediatamente **e** evitar reter tudo até o final — preferir `PERGUNTA → PAYOFF PARCIAL → NOVA PERGUNTA`, entregando valor repetidamente enquanto mantém motivo para continuar.

`MicroHook`: dispositivo narrativo de atenção (ex. conceitual: "mas havia um problema", "o que Mariana encontrou a seguir era pior" — nunca hardcoded como frase fixa, nunca exigindo cliffhanger artificial a cada poucas frases). O princípio é que a curiosidade se renova ao longo do vídeo, não a frequência exata.

## 95. Visual Dynamics Contract

Um vídeo do YouTube Lite não deve parecer um "slideshow narrado" — deve parecer contação de história visual contínua. Imagens estáticas são permitidas; apresentação perceptualmente estática por intervalos longos é desencorajada.

## 96. Visual Beat vs. Retention Beat (formalizado)

```text
VISUAL BEAT:     intervalo semântico/narrativo em que o mesmo sujeito/composição
                 visual permanece apropriado (já implementado, visual_beats.py,
                 visual_plan_gate3d.py)

RETENTION BEAT:  uma mudança visual perceptível destinada a manter a apresentação
                 viva (já implementado, retention.py::RetentionSegment, Gate 3D.1/3D.2)
```

Um Visual Beat pode conter múltiplos Retention Beats — já é exatamente o modelo implementado em `lite/retention.py` desde o Gate 3D.1, agora formalizado como contrato de produto, não só detalhe de implementação.

## 97. Heurística de ~7 Segundos

```text
~7 SEGUNDOS É UMA HEURÍSTICA EXPERIMENTAL DE RETENÇÃO.
NÃO é: lei do YouTube, garantia de viralidade, intervalo obrigatório de troca de imagem.
```

Interpretação preferida: `TARGET_MAX_PERCEPTUAL_STATIC_WINDOW ≈ 7s`, com tolerância a ~10s quando narrativamente justificado (já implementado: `TARGET_MAX_STATIC_WINDOW_SECONDS`/`TOLERATED_MAX_STATIC_WINDOW_SECONDS`, `lite/retention.py`). Intervalos mais longos podem existir quando explicitamente intencionais (`INTENTIONAL_CONTEMPLATIVE_HOLD`, já implementado).

**Definição importante**: `VISUAL_EVENT != NEW_IMAGE`. Um evento visual/de retenção pode ser: nova imagem, zoom, pan, reframe, mudança de composição, corte, transição, elemento gráfico, ênfase textual, animação, ou outra mudança visual perceptível. Mudança de texto de legenda **não** satisfaz automaticamente o requisito de retenção visual por si só.

## 98. Motion Contract

Movimento deve ser perceptível, narrativamente motivado, contido e contínuo quando apropriado. **Não** aceitar `MOTION_CONFIGURED = TRUE` como evidência de que o espectador experimenta movimento — lição empírica já registrada nesta mesma revisão: `TECHNICAL_MOTION_PRESENCE != PERCEPTUAL_MOTION_PRESENCE` (Gate 3D.1 tinha 100% de cobertura configurada e movimento pixel-a-pixel real, YAVG≈11, e ainda assim o feedback humano foi "o zoom precisa aproximar gradativamente" — a causa raiz foi reset de escala entre Retention Segments, já corrigido no Gate 3D.2, `GATE_3D2_CALIBRATION_REPORT.md` §3).

Distinção arquitetural mantida (já implementada): **Motion Configuration QA** (parâmetro, antes de renderizar) vs. **Motion Render QA** (pixel real, depois de renderizar) — a primeira sozinha não pega o caso de zoom configurado mas com quadros efetivamente estáticos.

## 99. Push-in / Depth Motion e Movimento Cumulativo

Para narrativa atmosférica, `CONTINUOUS_PUSH_IN` é definida como opção de movimento padrão importante — propósito: criar a sensação psicológica de entrar gradativamente na cena (câmera progride de `1.00` para `1.xx` ao longo de um intervalo visual significativo). **Não** resetar mecanicamente a trajetória de zoom a cada Retention Beat sem motivo.

Já implementado no Gate 3D.2 (`lite/retention.py::build_continuous_push_in_plan`, `segments_share_continuous_trajectory`): subsegmentos de retenção preservam estado cumulativo de câmera —

```text
VISUAL BEAT: start_scale=1.00
  segmento A: push-in
  segmento B: continua o push-in + pan sutil
  segmento C: continua o push-in + reframe
  end_scale=1.xx
```

em vez de `1.00→1.05 [reset] 1.00→1.05 [reset] 1.00→1.05` quando a experiência pretendida é profundidade progressiva. Zoom-in preferido para mistério/descoberta/tensão/objeto importante/emoção de personagem/revelação se aproximando/imersão; zoom-out reservado para revelação/escala/isolamento/consequência/estabelecimento de contexto/afastamento emocional/final — **nunca** alternar zoom-in/zoom-out mecanicamente. Pan/reframe para explorar ambiente, guiar atenção, evitar repetição de zoom — movimento sempre a serviço da cena.

Magnitude de movimento: nem imperceptivelmente fraca, nem agressivamente digital; limiares permanecem configuráveis e derivados experimentalmente. O valor atual do projeto (`0.004`/segundo, `GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND`) é documentado como **calibração experimental**, nunca lei permanente do YouTube.

## 100. Densidade de Imagens

**Não** codificar "50 imagens por 10 minutos" como regra permanente. Faixa de referência experimental para a narrativa atual: **~40-55 imagens únicas por vídeo de ~10 minutos**, sujeita a conteúdo/gênero/movimento/complexidade visual/ritmo narrativo/custo. O requisito real deriva de Visual Beats + necessidade de retenção + valor narrativo, nunca de uma meta de contagem isolada. `MORE_IMAGES != BETTER_VIDEO`: 45 imagens fortes + movimento eficaz + 90 eventos visuais significativos pode superar 100 imagens fracas + cortes aleatórios — preferir densidade visual significativa sobre contagem bruta.

## 101. Voice Performance Contract

Narração não deve apenas "ler o texto" — deve performar a história. Dimensões relevantes: ritmo, pausa, ênfase, intensidade, entonação, silêncio, direção emocional. Distinção formal: **texto de narração** != **plano de performance de voz**.

```text
VoicePerformancePolicy
  pace: str | None
  pause: str | None
  emphasis: str | None
  emotional_intent: str | None
```

Contrato mínimo deliberado — **não** uma DSL complexa de direção de voz. Pausas são conteúdo, não ausência de conteúdo (ex.: "O nome era... [pausa] ...Elias." — o pipeline não remove automaticamente todo silêncio). Prioridade de áudio: `NARRAÇÃO > MÚSICA > SFX` — nada deve reduzir materialmente a inteligibilidade da fala.

## 102. Caption Experience Contract

Para vídeos prontos para publicação do YouTube Lite: **legendas em português queimadas no vídeo são padrão obrigatório** (já implementado desde Gate 3D.1), com sidecar `.srt` mantido em paralelo (já implementado). Motivos: ambientes ruidosos, visualização sem som, acessibilidade, compreensão, visualização mobile.

Estilo preferido: contação de história de formato longo, não karaokê hiperativo de Shorts — 1-2 linhas, tamanho suficiente para mobile, contraste forte, margens seguras, chunking confortável, sincronizado com a narração (já implementado, `lite/captions.py::CaptionStyle`). Evitar por padrão: cada palavra saltando, animação constante, cores excessivas, competição visual com a história. Ênfase textual seletiva é permitida quando apoia materialmente uma revelação/nome importante/número/conceito/pergunta — **não** toda legenda como efeito visual.

## 103. Background Music Contract

Para a narrativa atual do YouTube Lite: **música de fundo é padrão obrigatório** (já implementado desde Gate 3D.1). Propósito: não é decorativo — apoia atmosfera, emoção, tensão, ritmo, transição, payoff.

**Lição empírica registrada** (a segunda descoberta central do Gate 3D.1→3D.2): `MUSIC_IN_MIX = TRUE` **não** prova `VIEWER_CAN_HEAR_MUSIC = TRUE`. O Gate 3D.1 media `FINAL_MIX_MEAN - NARRATION_ONLY_MEAN = 0.30dB` e considerava isso suficiente; o feedback humano foi "o som de fundo ainda está ausente" — a narração domina o nível médio total, então uma pequena diferença ali não prova audibilidade real. QA deve distinguir **presença técnica** de **presença perceptual**: já corrigido no Gate 3D.2 (`check_music_stem_relative_level`, comparando o STEM de música após ganho contra o STEM de narração isolado — não a mixagem final contra a narração pura). Regra: onde praticável, medir `NARRATION_STEM` vs. `MUSIC_STEM_AFTER_GAIN`, nunca só `FINAL_MIX_MEAN` vs. `NARRATION_MEAN` como prova de audibilidade.

Música permanece subordinada à narração — experiência desejada: claramente perceptível quando notada intencionalmente, mas não competindo por atenção durante escuta normal. Arco de música pode acompanhar progressão narrativa (`mistério inicial → tensão crescente → descoberta → confronto → revelação → resolução`) — **não** é exigida uma faixa diferente por fase; uma única faixa apropriada pode bastar (já é o caso atual, uma cama sintetizada única).

Direitos: música pronta para publicação precisa ter direitos de uso conhecidos — licença desconhecida é **proibida** no bundle final de publicação. Categorias aceitáveis: licenciada adequadamente, royalty-free compatível, CC0, original, gerada com direitos de publicação (categoria já usada, `lite/audio_mix.py`), ou asset local conhecido como seguro.

## 104. Sound Design Contract

Efeitos sonoros são **opcionais/seletivos** no nível de maturidade atual — não implementados. Devem apoiar momentos importantes, não preencher toda cena (exemplos conceituais: tique-taque de relógio, porta, papel, impacto, ambiente, som mecânico, silêncio intencional). Princípio: poucos SFX significativos, não SFX constante. Silêncio como efeito é permitido — redução/remoção temporária intencional da música antes de uma revelação/impacto/linha importante/som inesperado (`música → silêncio → SFX/frase importante → música retorna`) — **não** exigido em todo vídeo.

## 105. Pattern Interrupt Contract

Padrões visuais/de áudio repetidos se tornam previsíveis. A experiência deve introduzir ocasionalmente interrupções de padrão controladas (ex.: imagem cinematográfica × 3 → close-up; cena visual → documento → evidência textual → cena visual; música → silêncio breve → revelação). Propósito: renovar atenção, **não** criar caos — interrupções de padrão devem corresponder preferencialmente a informação nova, revelação, mudança emocional, mudança de local, objeto importante, ou escalada narrativa. `NÃO SUPERESTIMULAR`: o Lite de formato longo não deve imitar automaticamente TikTok/Shorts/edição hiperativa — alvo: dinâmico mas confortável, cinematográfico mas não estático, consciente de atenção mas não exaustivo.

## 106. Branding / Intro Contract

Padrão: `LONG_INTRO_BEFORE_HOOK: FORBIDDEN`. Animação de intro tradicional de vários segundos antes do conteúdo é desencorajada. Se branding existir, preferir: conteúdo primeiro → micro-branding opcional → continua o conteúdo. Micro-branding, se usado, permanece extremamente curto (alvo conceitual ~0.5-1.5s, sujeito a experimentação) e não interrompe o momentum da história. Branding é opcional — o SDD não força um intro/vinheta tradicional.

## 107. Ending / Payoff Contract

O final cumpre a promessa primária do vídeo: `PROMESSA DO CLICK PACKAGE → HOOK → ESCALADA → PAYOFF`. Evitar final com promessa não resolvida, a menos que seja intencionalmente parte do formato de conteúdo. Evitar sinalizar o fim cedo demais ("bom pessoal, então foi isso...") — uma vez que o espectador percebe que nenhum valor adicional está chegando, o abandono se torna racional. Preferir: payoff → fechamento curto → CTA opcional/ponte para o próximo conteúdo → fim. Evitar combinações longas de like/inscreva-se/sino/comente/compartilhe/siga — padrão: curto e contextualmente apropriado; uma ponte para outro vídeo relevante pode eventualmente valer mais que um CTA genérico longo.

## 108. Experience QA — Duas Categorias Formalizadas

```text
MEDIA QA:      o arquivo é tecnicamente correto?
               (codec, resolução, duração, stream de áudio, frame rate,
               cobertura da timeline, integridade do arquivo)

EXPERIENCE QA: a timeline produzida satisfaz estruturalmente a
               experiência de visualização pretendida?
               (hook começa prontamente, janela estática máxima percebida,
               cobertura de movimento, prova real de movimento renderizado,
               etapa de queima de legenda concluída, chunking de legenda
               válido, stem de música presente, nível relativo de música
               válido, pattern interrupts planejados, densidade visual,
               payoff existe, promessa de clique refletida na abertura)
```

Não são a mesma coisa — já implementado desde Gate 3D.1 (`lite/qa.py` vs. `lite/experience_qa.py`). Só checks determinísticos e úteis são adotados. **QA automatizado nunca finge medir qualidade subjetiva**: `ENGAGING = TRUE`, `VIRAL = TRUE`, `BEAUTIFUL = TRUE`, `CINEMATIC = TRUE`, `EMOTIONAL = TRUE` nunca são produzidos por código — revisão humana permanece autoritativa para essas qualidades.

## 109. Human Full Watch

Durante validação E2/local, todo vídeo candidato final exige assistida humana completa. Pergunta central autoritativa permanece: **"Eu publicaria este vídeo no YouTube sem editar o MP4?"** — só `YES` prova prontidão de publicação para aquele experimento (já em vigor desde Gate 3D). Checklist compacto de revisão de experiência:

```text
1. A abertura capturou atenção rapidamente?
2. Título/thumbnail bateram com a abertura?
3. Alguma seção pareceu visualmente estática?
4. O movimento foi perceptível mas confortável?
5. O zoom criou profundidade, não movimento mecânico?
6. As trocas de imagem tiveram ritmo apropriado?
7. As legendas foram legíveis?
8. A narração soou natural e expressiva?
9. A música foi audível mas subordinada?
10. Houve seções onde a atenção caiu?
11. As interrupções de padrão pareceram úteis, não aleatórias?
12. O final entregou a promessa?
13. Eu publicaria sem editar o MP4?
```

## 110. Evidência Real de Audiência (futuro)

Distinção formal: **heurísticas de experiência pré-publicação** (o que este contrato define agora) vs. **evidência de audiência pós-publicação** (métricas reais do YouTube — CTR, retenção nos primeiros 30s, duração média de visualização, percentual médio assistido, curva de retenção, quedas, picos, rewatches, engajamento, compartilhamentos). O contrato atual é primariamente pré-publicação. Nenhuma integração de analytics é implementada agora.

## 111. Loop de Feedback Futuro (E3)

```text
YOUTUBE EXPERIENCE CONTRACT → PUBLICAÇÃO → AUDIÊNCIA REAL → DADOS DE RETENÇÃO
    → QUEDAS/PICOS/MOMENTOS-CHAVE → ATUALIZAÇÃO DE HIPÓTESE → PRÓXIMO VÍDEO
```

Documentado como aprendizado futuro E3 — **não** construído agora.

## 112. Princípio de Evidência

```text
EVIDÊNCIA REAL DE AUDIÊNCIA > HEURÍSTICAS HUMANAS > MELHORES PRÁTICAS TEÓRICAS
```

Uma vez que dados reais suficientes existam, as heurísticas atuais devem ser revisáveis — ex.: meta de janela estática de ~7s, faixa de ~40-55 imagens, magnitude de movimento, densidade de legenda, nível de música, estrutura de hook. Permanecem parâmetros empíricos, nunca dogma (ver tabela de classificação, §114).

## 113. Perfil de Experiência / Gênero (ponto de extensão, não implementado)

Alguns parâmetros de experiência podem eventualmente pertencer a uma configuração mínima de gênero/perfil (ex.: `STORYTELLING`, `FINANCE`, `AI_NEWS`, `TIER_LIST`, `BOOK_SUMMARY`) — uma história de mistério e um explicador financeiro podem exigir ritmos diferentes. **Não** implementar variações específicas de gênero agora — só documentar o ponto de extensão. O experimento atual (`O Relojoeiro de Vidro`) pertence aproximadamente a `CINEMATIC_STORYTELLING`; muitas heurísticas atuais foram descobertas nesse contexto específico — **não presumir** que todo canal futuro deva usar o mesmo ritmo.

## 114. Tabela: Permanente vs. Experimental

| Categoria | Regra |
|---|---|
| **PERMANENTE / PRINCÍPIO FORTE DE PRODUTO** | Hook antes de branding desnecessário |
| | Movimento deve ser perceptível (não apenas configurado) |
| | Inteligibilidade da narração tem prioridade sobre música/SFX |
| | Legendas devem ser legíveis |
| | Licenciamento de música deve ser conhecido |
| | Human Full Watch obrigatório durante E2 |
| | QA automatizado não pode provar engajamento/qualidade subjetiva |
| | Visual Beat != Retention Beat; Retention Beat != nova imagem |
| **EXPERIMENTAL / REVISÁVEL** | Meta de janela estática de ~7s (tolerância ~10s) |
| | Faixa de ~40-55 imagens por vídeo de ~10min |
| | Taxa de zoom específica (`0.004`/s) |
| | Nível de ganho de música específico |
| | Duração de micro-branding |
| | Tamanho/estilo de legenda |
| | Frequência de pattern interrupts |

Nunca confundir as duas categorias — a coluna experimental existe precisamente para ser substituída por evidência real sem exigir uma nova revisão de SDD a cada vídeo.

## 115. Contrato Mínimo (Sketch)

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
```

Sketch completo de cada subpolítica no relatório de acompanhamento (§74/§52). Deliberadamente raso — parametrizar só o que realisticamente precisa variar (ex.: `target_static_window_seconds` é útil; 27 knobs de "viralidade" separados seria overengineering).

## 116. Artefatos e Proveniência (avaliado, não decidido)

Avaliar se runs futuros devem expor minimamente `experience_contract.json`, `experience_timeline.json`, `experience_qa.json` — só recomendados se fornecerem valor real de debugging/proveniência, nunca por "teatro de documentação". A proveniência final deveria eventualmente responder: qual contrato de experiência foi usado, quais limiares experimentais estavam ativos, qual perfil de movimento foi usado, qual nível/perfil de música, qual política de legenda, quais holds estáticos intencionais existiram, qual revisão humana aprovou a publicação.

## 117. Fronteira Engine/Operador e Responsabilidades SPDD

Mesma regra já estabelecida (§21, §61, §83): `ENGINE` define requisitos/manifestos/contratos; `OPERATOR` materializa assets externos/gerados quando necessário — nenhuma menção a Claude/Codex/OpenAI/DALL-E/GPT Image/Anthropic na lógica de domínio.

```text
ENGINE / DESENVOLVIMENTO:  contratos, timeline, instruções de movimento,
                            instruções de legenda, instruções de música, QA, empacotamento
OPERADOR DE EXECUÇÃO:      materializa assets de imagem/áudio necessários
HUMANO:                    calibra limiares subjetivos durante E2, revisa o
                            vídeo completo, aprova prontidão de publicação
```

## 118. Maturidade e Não-Objetivos

Mantida a disciplina de maturidade atual — não construir infraestrutura para milhões de vídeos, otimização automática, personalização em tempo real, farms de renderização em nuvem, orquestração multi-canal. Requisito atual: provar repetidamente `BRIEFING → ENGINE → VÍDEO FINAL → HUMAN FULL WATCH → PUBLICAR SEM EDITAR O MP4`.

Explicitamente **fora de escopo**: predição de viralidade, predição de CTR, IA de predição de retenção, upload automático ao YouTube, ingestão de analytics, infraestrutura de A/B testing, busca de stock-video, geração de vídeo completo, personagens animados, lip sync, motor de composição musical, motor complexo de SFX, suite de motion graphics, substituto do After Effects, motor de edição estilo TikTok, arquitetura em nuvem, enxame de agentes.

## 119. Princípios Registrados

```text
O CLIQUE GANHA O PRIMEIRO SEGUNDO. A EXPERIÊNCIA GANHA O SEGUNDO SEGUINTE.
HOOK ANTES DE BRANDING.
PROMESSA → HOOK → ESCALADA → PAYOFF.
UM HOOK NÃO BASTA; A CURIOSIDADE PRECISA SE RENOVAR.
VISUAL BEAT != RETENTION BEAT.
~7 SEGUNDOS É HEURÍSTICA, NÃO LEI.
EVENTO VISUAL != NOVA IMAGEM.
MOVIMENTO DEVE SER PERCEPTÍVEL, NÃO APENAS CONFIGURADO.
MOVIMENTO DEVE SERVIR A INTENÇÃO NARRATIVA.
PUSH-IN PODE CRIAR PROFUNDIDADE E IMERSÃO.
NÃO RESETE A PROGRESSÃO DE CÂMERA SEM MOTIVO.
MAIS IMAGENS != VÍDEO MELHOR.
A VOZ PERFORMA; NÃO APENAS LÊ.
PAUSAS SÃO PARTE DA PERFORMANCE.
LEGENDAS SÃO PARTE DA EXPERIÊNCIA.
MÚSICA PRECISA SER OUVIDA, NÃO APENAS MIXADA.
NARRAÇÃO SEMPRE TEM PRIORIDADE DE ÁUDIO.
SFX DEVE ENFATIZAR, NÃO SATURAR.
SILÊNCIO PODE SER UM EFEITO.
PATTERN INTERRUPTS DEVEM RENOVAR ATENÇÃO, NÃO CRIAR CAOS.
INTRO LONGA ANTES DO VALOR É DESENCORAJADA.
PAGUE A PROMESSA ANTES DE ENCERRAR.
QA AUTOMATIZADO PROVA ESTRUTURA, NÃO ENGAJAMENTO.
HUMAN FULL WATCH PERMANECE AUTORITATIVO EM E2.
DADOS REAIS DE AUDIÊNCIA SUBSTITUEM HEURÍSTICAS QUANDO DISPONÍVEIS.
```

`GATE_3D2` continua em andamento de forma independente — esta Parte X é puramente especificação, sem código de produção alterado, sem render, sem geração de assets nesta revisão.
