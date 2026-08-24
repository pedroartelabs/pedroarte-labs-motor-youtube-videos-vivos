# YOUTUBE LITE — OPERATOR CONTRACT

Companion a [SDD_SPDD.md](SDD_SPDD.md) Part III. Define quem faz o quê, com que autoridade, e como uma execução muda de mãos sem depender de memória de conversa.

## 1. Papéis

| Papel | Quem | Responsabilidade primária |
|---|---|---|
| **Builder** | Claude Code | Arquitetura, implementação, testes, refatoração, contratos, debugging, documentação. Pode operar/testar o Lite quando necessário. |
| **Operator** | Codex | Runs locais, geração de assets via capacidade nativa do ambiente quando existir, smoke/E2E, inspeção, validação, evidências, atualização de manifests. |
| **Human** | Pessoa responsável pelo projeto | Gates A/B/C, decisão de gasto em API externa, decisão de publicação manual, seleção do candidato de thumbnail no Click Package (`SDD_SPDD.md` §79, especificado). |

Nenhum papel é exclusivo por natureza técnica — Claude Code pode operar, Codex pode (em tese) construir — mas os dois **nunca escrevem no mesmo `run_id` ao mesmo tempo** (§3).

## 2. Engine Capability ≠ Execution Environment Capability

A engine (código em `src/pedroarte_youtube_engine/lite/`) nunca hardcoda "chame o Codex" ou "chame a OpenAI". Ela expõe portas (`ImageGenerationPort`, `NarrationPort`) e uma requisição estruturada (`ImageGenerationRequest`, texto de narração). A decisão de qual estratégia usar é feita **fora** do domínio, por uma função de seleção pequena, chamada pelo operador ativo no momento da execução.

## 3. Operator Ownership Rule

Uma execução (`runs/<run_id>/`) tem **um escritor por vez**. O `run_manifest.json` registra:
```json
{"owner": "claude_code" | "codex" | "human", "status": "..."}
```
Antes de escrever em um `run_id` existente, o operador **lê** `owner` e `status`. Se `owner` for outro operador e `status` não for terminal (`assembled`, `qa_passed`, `qa_failed`, `failed`), o operador atual não escreve — reporta conflito e aguarda handoff explícito.

## 4. Handoff Contract

```text
RUN
 ↓
run_manifest.json      (estado: fases concluídas, artefatos existentes + hash, owner, status)
 ↓
pending_tasks.json     (o que falta, com status pending|in_progress|done|failed por item)
 ↓
próximo operador lê ambos, nunca a conversa
 ↓
produced_artifacts     (escritos no filesystem, nunca só descritos em texto)
 ↓
manifest e pending_tasks atualizados ANTES de devolver o controle
 ↓
continua
```

Regra de propriedade de tarefa: um operador só marca `in_progress` um item de `pending_tasks.json` que vai executar **agora** — nunca reserva lote antecipadamente. Ao terminar (ou falhar) um item, atualiza `pending_tasks.json` e `run_manifest.json` antes de qualquer outra coisa.

## 5. Local-First Policy (ordem de prioridade)

```text
1. processamento determinístico local
2. ferramentas já instaladas no ambiente
3. capacidades nativas do ambiente de execução (ex.: geração de imagem nativa do Codex, se existir)
4. capacidades gratuitas/locais compatíveis (ex.: SAPI5, edge-tts)
5. APIs externas pagas, quando justificadas
```

Não é dogma de zero-API — é uma ordem de preferência. Subir para o nível 5 exige justificativa registrada em `provenance` (por que os níveis 1-4 não bastaram) e, quando o custo não for trivial, autorização explícita do Human (nunca presumida).

## 6. Image Generation — Fluxo de Decisão

```text
IF operando em Codex E geração nativa de imagem confirmada disponível:
    usar geração nativa (generation_method = "native_environment_capability")
ELSE IF Human autorizou explicitamente uma chamada específica a um provider configurado:
    usar esse provider (generation_method = "external_api:<provider>")
ELSE:
    usar estratégia local (generation_method = "local:<strategy_name>")
```

`ANTHROPIC_API_KEY` **nunca** entra nesta cadeia — a Anthropic não oferece endpoint de geração de imagem. Apenas `OPENAI_API_KEY` (quando presente e autorizada para a chamada específica) é candidata a provider de imagem externo.

## 6.1 Thumbnail Source Images — Mesma Cadeia de Decisão (especificado em `SDD_SPDD.md` Part IX, NÃO implementado)

Imagens-fonte de thumbnail (antes do renderer determinístico de tipografia, `SDD_SPDD.md` §76) seguem **exatamente** o fluxo de decisão do §6 — nenhum vocabulário ou cadeia de decisão novos só para thumbnail. Diferenças de escopo, não de processo:

- São até **3** chamadas de geração por vídeo (`THUMBNAIL_CANDIDATES = 3`, `SDD_SPDD.md` §78), nunca escondidas dentro do custo/contagem de imagens do vídeo — registradas separadamente em `provenance` (`ARTIFACT_CONTRACT.md` §7).
- O prompt de geração de thumbnail **nunca** inclui a tipografia final (`FINAL_TEXT_INSIDE_GENERATION_PROMPT: FORBIDDEN_BY_DEFAULT`, `SDD_SPDD.md` §72) — o texto é sempre aplicado depois, por código determinístico, nunca pelo modelo de imagem.
- `THUMBNAIL_ASSET != VIDEO_FRAME_BY_DEFAULT`: reuso de um frame/imagem já existente do vídeo é permitido só se satisfizer o Thumbnail Contract (`SDD_SPDD.md` §75) — não é o comportamento padrão presumido.

## 7. TTS — Fluxo de Decisão

```text
Gate 2 (prova de pipeline): SAPI5 permitido, custo zero, sem verificação adicional.
Gate 3+ (qualidade de publicação): edge-tts como candidato inicial (validar antes de
    cristalizar); API paga só com autorização explícita do Human.
```

## 8. Custo e Autorização

- Nenhuma chamada paga é feita sem autorização explícita do Human para aquela chamada específica.
- "Autorização geral" de uma sessão anterior não se estende automaticamente a novas chamadas.
- Todo custo real incorrido é registrado em `run_manifest.json` (`external_api_cost`), nunca estimado como zero por omissão.
- Nunca ler, exibir ou registrar o valor de nenhuma variável de `.env` — só a presença/ausência do nome da variável pode ser verificada.

## 9. Escopo de Escrita

- Builder e Operator só escrevem dentro de `runs/<run_id>/` (por execução) e `src/pedroarte_youtube_engine/lite/` (por implementação).
- Nenhum dos dois papéis modifica `src/pedroarte_youtube_engine/agents/`, `interfaces/`, `domain/` (exceto leitura para reuso pontual conforme a matriz de reuso) ou qualquer arquivo do Advanced legacy.
