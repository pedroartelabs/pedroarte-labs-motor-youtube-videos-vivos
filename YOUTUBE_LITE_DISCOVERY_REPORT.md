# YOUTUBE LITE — DISCOVERY & ARCHITECTURE REPORT

**Repositório:** `pedroarte-labs-motor-youtube-videos-vivos`
**Insumo:** [DISCOVERY_REPORT_YOUTUBE_ENGINE.md](DISCOVERY_REPORT_YOUTUBE_ENGINE.md) (discovery forense anterior, mesma sessão) + inspeções locais adicionais feitas para este documento (nenhuma alteração de código, nenhuma chamada paga).
**Data:** 2026-08-23
**Regra seguida:** nada foi implementado, refatorado, corrigido ou instalado. As únicas ações executadas foram leituras e inspeções locais gratuitas (ver §3 e evidências ao longo do texto).

---

## 1. Executive Summary

O discovery anterior provou, por execução real, que o motor atual (`pedroarte_youtube_engine`) é um **compilador de pré-produção textual** — nunca produz um `.mp4` — e que sua fiação (`bootstrap()`) está quebrada em todas as três interfaces (CLI/API/MCP). Diante disso, a decisão de produto já tomada (congelar o pipeline avançado e priorizar um **YouTube Lite**) é a correta: continuar consertando/estendendo uma arquitetura de 27 agentes que nunca terminou uma execução seria o pior uso do próximo ciclo de trabalho.

Este documento recomenda a **Estratégia Híbrida (essencialmente um vertical slice novo e pequeno)**: um módulo Lite novo, linear, fora do orquestrador de 27 agentes, que reaproveita por composição um punhado de peças já comprovadas e desacopladas (renderização de legendas, forma de dados de metadados, utilitário de estimativa de duração de fala) e constrói o resto do zero, pequeno e testável.

Inspeções locais feitas agora confirmam o ambiente de execução real:
- **FFmpeg não está instalado**, mas está disponível via `winget` (`Gyan.FFmpeg`) — instalação de um comando, offline depois de baixado, gratuita. É o candidato correto para montagem/render (§17, §21).
- **Existe uma voz TTS pt-BR nativa do Windows** ("Microsoft Maria Desktop", SAPI5), zero custo, zero instalação — suficiente para *provar* o pipeline de sincronização, mas de qualidade datada demais para a barra de "eu publicaria isso" (§19).
- **Nenhuma biblioteca de TTS/imagem/vídeo está instalada no venv do projeto** (`pip list` não retorna nenhuma correspondência a TTS, difusão de imagem, OpenCV, MoviePy, Whisper etc.).
- **O `.env` real do projeto contém `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`** (nomes de variável confirmados, valores nunca lidos/exibidos, conforme regra 6). **Isso não implica capacidade de geração de imagem**: a Anthropic não oferece endpoint de geração de imagem em sua API — só a OpenAI, entre as duas, o faz. Nenhuma chave de `ElevenLabs` ou `Gemini/Google` está presente no `.env` real (só no `.env.example`, como template).

**Maior gap para E2:** nenhum componente de geração real de imagem/voz/vídeo está instalado ou conectado hoje — nem no motor, nem no ambiente. **Melhor caminho:** um vertical slice Lite de ~12 componentes pequenos, a maioria novos, prendendo o caminho `briefing → vídeo ≥10 min` antes de qualquer sofisticação.

**Primeiro experimento recomendado:** Gate 1→4 na sequência da §33/§40, usando SAPI (zero custo) para provar sincronização/montagem primeiro, e só then decidir entre `edge-tts` (gratuito, melhor qualidade) e uma API paga para a narração final publicável.

---

## 2. Strategic Pivot

O pivot é tecnicamente justificado pelas evidências do discovery anterior, não apenas por preferência de produto:
- 126 testes passam, mas nenhum exercita `bootstrap()` ou `PipelineOrchestrator.execute()` — a arquitetura anterior tinha **profundidade de unidade sem profundidade de integração**.
- Havia infraestrutura para escala (retry, circuit breaker, orçamento, 6 famílias de formato, 27 agentes) **antes** de qualquer vídeo ter sido produzido — exatamente o antipadrão que a regra 19 deste discovery proíbe repetir.
- O produto real do motor anterior sempre foi texto (prompts) para colar em outro sistema — nunca um arquivo de mídia. YouTube Lite muda o contrato de saída para **"o MP4 é o produto"**, o que é uma mudança de eixo, não uma extensão incremental.

## 3. Current Engine Assets

Ativos comprovadamente sólidos e reutilizáveis (detalhados em §35 do discovery anterior, resumidos aqui com foco em Lite):

| Ativo | Onde | Por que serve ao Lite |
|---|---|---|
| `render_srt`/`render_vtt`/`build_cues` | `adapters/renderers/subtitles.py` | Funções puras, testadas; só precisam de timing real (pós-TTS) em vez do timing sintético de 10s |
| `speakable_duration_seconds`/`count_words` | `shared/text.py` | Estimativa de duração de fala pré-TTS, útil para dimensionar o roteiro alvo antes de sintetizar áudio |
| Forma de dados de `PublicationMetadata` | `domain/artifacts.py` | Título/descrição/capítulos/hashtags — exatamente o que `metadata.json` do Lite precisa, só menor |
| Padrão de configuração Pydantic estrita (`extra="forbid"`, validadores) | `domain/configuration.py` | Bom padrão para o `briefing.yaml` do Lite — não a classe em si, o padrão |
| `RunLogger`/logging estruturado com redaction | `observability/` | Reutilizável como está (uma vez corrigido o bug de assinatura já identificado, que é trabalho de implementação, fora deste discovery) |
| Política de caminhos (`PathPolicy`, allowlist, anti-traversal) | `shared/paths.py` | Diretamente reutilizável para escrever `youtube_bundle/` com segurança |

Ativos que **não** ajudam o Lite hoje (detalhes em §34): os 27 agentes, a máquina de estados de 15 fases, o RAG, os serviços de continuidade cinematográfica, os provedores fake, retry/circuit breaker — todos desenhados para um produto diferente (compilação de prompts em lote para múltiplos formatos), não para "um vídeo real, agora".

## 4. Lite Product Definition

> Dado um briefing curto (tópico, tom, idioma, duração-alvo, opcionalmente estilo visual), o YouTube Lite produz localmente um `youtube_bundle/` contendo um `video.mp4` de ~10-15 minutos, com narração compreensível, imagens coerentes entre si, música/ambiente opcional bem mixado, legendas `.srt`, thumbnail, metadados e proveniência — revisável e publicável manualmente sem edição obrigatória do MP4.

Isso é deliberadamente **menor** que o produto do motor anterior: um único formato (vídeo principal), sem Shorts/série/mini-novela/trailer, sem seleção de "modo profissional vs. cinematográfico" (não existe ainda nenhum modo — só existe Lite).

## 5. Definition of Done

A hipótese de DoD do briefing é boa e **não deve ser enfraquecida** no requisito central (MP4 utilizável). Duas críticas construtivas:

1. **"Sem necessidade obrigatória de edição" é subjetivo demais para ser um gate automatizado sozinho.** Recomendo mantê-lo como o **Gate C humano** (§31), não como algo que um script decide. O automatizado deve verificar proxies objetivos (arquivo abre, duração, resolução, codec, stream de áudio presente, SRT parseia, sem clipping/loudness fora da faixa) — e o julgamento final de "eu publicaria" fica exclusivamente com a pessoa.
2. **Faltava um proxy objetivo de qualidade de áudio.** Adicionar ao DoD automatizado: medição de loudness integrado (EBU R128, via `ffmpeg loudnorm` em modo de medição) dentro de uma faixa alvo (ex.: -16 a -14 LUFS, padrão comum de streaming) e ausência de clipping (picos < -1 dBTP). Isso é barato de medir e evita o caso óbvio de falha "áudio estourado ou inaudível" chegar ao gate humano.

Ajuste sugerido ao texto do DoD (adição, não substituição):
> "...o áudio final não apresenta clipping e está dentro de uma faixa de loudness aceitável (medida automaticamente); o julgamento final de 'publicável sem edição' é humano, não automatizado."

## 6. Minimum Architecture

Avaliação componente a componente da hipótese da §7 do briefing:

| Componente | Necessário? | Já existe algo reutilizável? | Simplificar? | Novo? | Pode adiar? |
|---|---|---|---|---|---|
| Briefing Normalizer | Sim | Padrão Pydantic estrito (não a classe) | — | Sim, pequeno | Não |
| Video Specification | Sim | Mesmo padrão | — | Sim, pequeno | Não |
| Script Planner + Script | Sim | Não (heurístico não gera prosa nova) | — | Sim — ver §11 | Não |
| Visual Bible Lite | Sim | Campos de `AudiovisualBible` como referência | Sim, drasticamente | Sim, pequeno | Não |
| Visual Manifest | Sim | Forma de `ProviderPrompt` como referência conceitual | Sim | Sim, pequeno | Não |
| Asset Generation (imagens) | Sim | Nada real existe | — | Sim | Não |
| Narration (TTS) | Sim | Nada real existe; SAPI nativo do SO disponível | — | Sim (integração) | Não |
| Timeline Builder | Sim | `speakable_duration_seconds` | Sim, ficar bem simples (nível de parágrafo, não fonema) | Sim, pequeno | Não |
| Audio Mixer | Sim | Nada existe; FFmpeg resolve | — | Sim, mas é "config de FFmpeg", não código novo pesado | Ducking pode adiar (§20) |
| Assembler/Render | Sim | Nada existe; FFmpeg resolve | — | Sim, mas idem acima | Não |
| Captions | Sim | `render_srt`/`build_cues` | Adaptar timing | Pouco | Não |
| QA | Sim | Padrão de `ValidationIssue`/severidade como referência conceitual | Sim, drasticamente menor | Sim, pequeno | Não |
| Packager | Sim | Padrão de `FilesystemArtifactAdapter` como referência | Sim | Sim, pequeno | Não |
| Thumbnail | Sim | Mesma política de imagem do resto | — | Reuso do componente de imagem | Não |
| Metadata | Sim | Forma de `PublicationMetadata` | Sim, trimmed | Pouco | Não |
| Provenance | Sim | Nada existe | — | Sim, pequeno | Não |

**Pode ser ainda menor?** Sim, em uma dimensão: **Visual Bible Lite e Visual Manifest podem começar fundidos** em v0.1 — um único arquivo `visual_plan.json` com o estilo global no topo e a lista de beats/imagens embaixo, em vez de dois artefatos separados. Separar os dois só se justifica quando houver reuso do mesmo Visual Bible entre múltiplos vídeos (P2/P3), o que não é o caso na primeira prova.

**Contagem mínima realista de componentes novos e não-trivial:** 8 (Script Planner, Visual Manifest+Bible fundidos, Asset Generation, Narration, Timeline Builder, Assembler/FFmpeg config, QA, Packager). Os demais (Briefing Normalizer, Video Spec, Captions adaptado, Metadata, Provenance) são pequenos o suficiente para não contar como risco arquitetural.

## 7. Existing vs New Components

Ver tabela da §6 (coluna "Já existe/Novo") e a matriz de reuso completa em §35.

## 8. Adapt vs Vertical Slice vs Hybrid

| Critério | A — Adapt Existing | B — Lite Vertical Slice | C — Hybrid |
|---|---|---|---|
| Complexidade para começar | Alta — primeiro conserta 4 pontos de fiação quebrada, depois precisa *adicionar* execução real de mídia a uma arquitetura que nunca teve isso | Baixa — módulo novo, linear, sem dependência do orquestrador | Baixa-média — módulo novo + algumas importações pontuais de funções puras existentes |
| Risco | Alto — qualquer mudança no orquestrador de 27 agentes arrisca reintroduzir acoplamento e regressões em um sistema já frágil | Baixo — superfície pequena, isolada | Baixo — mesma superfície pequena, com reuso seletivo bem delimitado |
| Custo/tempo | Alto | Baixo | Baixo (marginalmente maior que B, mas evita reescrever legendas/metadados que já funcionam) |
| Testabilidade | Baixa — testar exige montar todo o `EngineContext`/`bootstrap()`, que hoje nem compila corretamente | Alta — funções/módulos pequenos, testáveis isoladamente, sem framework de agente | Alta — mesma vantagem, com um ou dois testes de contrato extra para as funções importadas |
| Chance de atingir E2 rápido | Baixa | Alta | **Alta (recomendada)** |

**Recomendação: Estratégia C (Híbrida), que na prática é a Estratégia B com reuso cirúrgico.** Não há vantagem em reescrever `render_srt` ou o formato de `PublicationMetadata` do zero — mas também não há vantagem em passar por `EngineContext`, `PipelineOrchestrator` ou qualquer um dos 27 agentes para produzir o primeiro vídeo. O módulo Lite deve **importar funções/formas de dados específicas**, nunca o framework de agentes/orquestração.

## 9. Briefing Contract

Proposta mínima (não implementar agora — só especificar):

```yaml
# briefing.yaml (Lite)
topic: "..."                # tema/tese central, obrigatório
title_hint: "..."           # opcional, título candidato
audience: "..."             # opcional, tom/público
language: "pt-BR"           # default
tone: "..."                 # opcional (ex.: "documental calmo")
target_min_minutes: 10.0    # default 10
target_max_minutes: 15.0    # default 15
visual_style: "..."         # opcional, texto livre para a Visual Bible Lite
reference_material: []      # opcional: caminhos para .md/.txt de apoio
music: "opcional/nenhuma/estilo"
rights_confirmed: false     # obrigatório = true para prosseguir (herda a política de direitos do motor atual)
```

Deve ser validado com o mesmo padrão rígido (`extra="forbid"`) do motor atual — isso é uma prática comprovadamente boa a reutilizar, mesmo que a classe não seja a mesma.

**BRIEFING_CONTRACT_STATUS: a especificar** — o formato acima é uma proposta de discovery, não um contrato fechado; deve ser validado com um briefing real antes de qualquer implementação.

## 10. Duration Strategy

A faixa `target_min_minutes=10 / target_max_minutes=15` proposta no briefing é razoável e **deve existir como validação pós-fato, não pré-fato**: o roteiro é escrito para cobrir o tópico com a profundidade que ele exigir; a duração real só é conhecida depois da síntese de voz (a duração de fala estimada por `speakable_duration_seconds` é um proxy de planejamento, não a verdade final). O gate de QA deve:
1. Medir a duração real do `narration.*` gerado.
2. Se `< target_min_minutes`: **falhar e pedir mais roteiro** (mais seções/profundidade), nunca inserir silêncio ou desacelerar a narração artificialmente — exatamente como o briefing exige.
3. Se `> target_max_minutes` por uma margem grande: sinalizar para revisão humana (pode ser aceitável se o conteúdo justificar; não é motivo automático de falha, diferente do limite inferior).

## 11. Script Strategy

Comparação direta, respondendo à pergunta do §18: **o `DeterministicLLMProvider`/análise heurística atual NÃO é suficiente para gerar um roteiro original de 10-15 minutos com qualidade publicável.** Motivo: por design, esses componentes **extraem estrutura de um texto já existente** (um livro fornecido) — eles não escrevem prosa nova e persuasiva a partir de um tópico. Um briefing Lite tipicamente fornece um tópico, não um manuscrito de 10 páginas para extrair.

| Abordagem | Qualidade | Custo | Reprodutibilidade | Latência | Veredito |
|---|---|---|---|---|---|
| Heurística/determinística atual | Baixa para prosa nova (adequada só para *estruturar* texto-fonte já existente) | Zero | Total | Baixa | Insuficiente sozinha |
| Modelo local pequeno | Desconhecida sem teste; tipicamente abaixo de modelos de fronteira para prosa longa coerente | Zero (após setup) | Alta | Média-alta (CPU) | Candidato só se custo zero for inegociável — não avaliado neste discovery por falta de instalação local |
| Claude Code como operador (a própria sessão que constrói/testa) | Alta — mesma capacidade usada para escrever este relatório | Já coberto pela sessão de trabalho | Média (não determinístico) | Baixa | **Viável e recomendado para prototipagem** |
| Codex como operador, chamando um LLM | Depende do LLM configurado | Depende | Média | Depende | Viável, condicionado à disponibilidade real no ambiente Codex |
| LLM externo via API (`ANTHROPIC_API_KEY` presente no `.env`) | Alta | Baixo por vídeo (texto é barato) | Média | Baixa | **Viável e recomendado para produção**, dado que a chave já existe |
| Híbrido: LLM gera prosa, código determinístico valida (contagem de palavras, duração estimada, repetição, presença de gancho/CTA) | Alta + auditável | Baixo | Média (geração) + Total (validação) | Baixa | **Recomendação final** |

## 12. Visual Bible Lite

Campos recomendados, avaliados um a um contra a hipótese do briefing:

| Campo proposto | Manter? | Já existe equivalente? |
|---|---|---|
| `visual_style` | Sim | Não — é novo, mas simples (texto curto) |
| `palette` | Sim | `AudiovisualBible` tem paleta — reaproveitar o *conceito*, não a classe |
| `lighting` | Sim | Idem |
| `composition` | Sim, mas como texto livre curto, não um sistema de regras de câmera | `CameraPlan` do motor atual é overkill para Lite |
| `characters` | Só se o vídeo tiver personagens recorrentes (nem todo tópico tem) — tornar opcional | Conceito existe em `CanonBible`, mas com muito mais campos do que o Lite precisa |
| `locations` | Idem — opcional | Idem |
| `recurring_objects` | Opcional, baixa prioridade | Novo |
| `historical_period` | Opcional, só quando relevante ao tema | Novo |
| `forbidden_elements` | **Manter — é o mecanismo mais barato de evitar risco de direitos/marca** (mesmo padrão de regex de marca/celebridade do `LegalAndRightsAgent` pode ser reaproveitado como *lista de checagem*, não como agente) | Reuso do *padrão*, não da classe |
| `continuity_constraints` | Manter, mas como texto curto ("mesma paleta e estilo de ilustração em todas as imagens"), não como serviço de continuidade cinematográfica | Não construir `VisualContinuityService` para Lite — over-engineering para imagens estáticas |

**Como chega à geração de imagem:** o `visual_style`/`palette`/`forbidden_elements` devem ser **prefixados em todo prompt de imagem** (texto concatenado, não um sistema de injeção sofisticado) — mecanismo mais simples possível para fazer imagens independentes parecerem do mesmo vídeo, consistente com a regra 26 (simplicidade > sofisticação).

**Como verificar consistência sem sistema sofisticado:** revisão humana por amostragem (Gate B, §31) é suficiente para v0.1. Não construir comparação automática de embeddings de imagem nesta fase — não há consumidor real ainda para essa capacidade (regra 17).

## 13. Visual Asset Strategy

Modelo do briefing (10-15min → 20-50 beats → 20-50 imagens → pan/zoom/Ken Burns → transições simples) é razoável como **ordem de grandeza**, não como número fixo. Estratégia recomendada para decidir a contagem real:
- Derivar beats da estrutura do roteiro (uma imagem por parágrafo temático, tipicamente 30-60s de narração por imagem) — não por tempo fixo de segundo a segundo.
- Para 10-15 min de narração a ~150 palavras/min (`speech_rate_wpm` padrão do motor atual, reutilizável como referência), isso dá **1500-2250 palavras**, o que tipicamente produz **15-30 parágrafos temáticos** — dentro da faixa 20-50 do briefing, tendendo à ponta inferior para manter custo de geração de imagem baixo no v0.1.
- Ken Burns (pan/zoom lento) por imagem estática é o mecanismo de movimento mínimo suficiente — evita "parecer slideshow genérico" (risco §40) sem exigir vídeo generativo.

## 14. Narration/TTS Strategy

Avaliação com evidência de execução local real (comando executado nesta sessão, sem custo):

| Opção | Disponível agora? | Qualidade esperada pt-BR | Custo | Instalação | Offline |
|---|---|---|---|---|---|
| Windows SAPI5 ("Microsoft Maria Desktop") | **Sim, confirmado instalado** (`Add-Type System.Speech` → voz pt-BR listada) | Baixa-média (voz "Desktop" legada, robótica pelos padrões atuais) | Zero | Zero (já no SO) | Sim |
| `edge-tts` (vozes neurais gratuitas da Microsoft) | Não instalado no venv (`pip list` não retorna) | Alta (vozes neurais modernas, incluindo pt-BR) | Zero (sem chave de API) | Precisa `pip install edge-tts` (fora de escopo instalar agora) | Não (chama endpoint público da Microsoft) |
| OpenAI TTS (API) | Chave presente no `.env` (`OPENAI_API_KEY`, não validada) | Alta | Pago por caractere | SDK a adicionar | Não |
| ElevenLabs | **Sem chave no `.env` real** (só no `.env.example`) | Alta | Pago | SDK a adicionar + credencial a obter | Não |
| Modelo local (Coqui/Piper) | Não instalado, não avaliado (exigiria download de modelo, fora do escopo de "inspeção gratuita") | Variável | Zero após setup | Instalação + download de modelo, não trivial no Windows | Sim |

**Recomendação em duas etapas:**
1. **Prova de pipeline (Gate 2, custo zero):** SAPI5 nativo — sem precisar adicionar nenhuma dependência, prova que sincronização/timeline/mixagem funcionam.
2. **Barra de publicação (v0.1 real):** `edge-tts`, por ser gratuito e de qualidade sensivelmente superior ao SAPI — é a recomendação de menor custo total que atinge a barra de "eu publicaria isso". APIs pagas (OpenAI TTS, com chave já disponível) ficam como upgrade opcional se `edge-tts` não bastar.

## 15. Audio/Music Strategy

FFmpeg sozinho resolve o MVP — não há necessidade de DAW. Cadeia mínima:
```
narration.wav → loudnorm (medir + normalizar) →
[music.mp3 → volume -20dB → afade in/out → loop/trim para duração total] →
amix (narration + music) → track final
```
- **Normalização:** `loudnorm` do FFmpeg (padrão EBU R128), suficiente e gratuito.
- **Ducking:** **adiar para P1** — para v0.1, música constante em volume baixo (ex. -20 a -24dB) sob a narração já evita mascaramento sem exigir sidechain compression dinâmica. Só reconsiderar se a revisão humana (Gate C) apontar problema real.
- **Fade in/out:** trivial via `afade`.
- **Clipping:** checar picos via `ffmpeg` (`astats`/`loudnorm` em modo medição) como parte do QA automatizado (§5).
- **Loop seguro de música:** só necessário se a faixa for mais curta que o vídeo — usar `-stream_loop` do FFmpeg com corte no ponto certo; não construir crossfade de loop sofisticado no v0.1.

## 16. Timeline & Synchronization

Menor mecanismo suficiente, respondendo à comparação pedida no §22: **alinhamento por parágrafo/beat, usando a duração real do áudio de narração pós-TTS**, não forced alignment fonema-a-fonema:
1. Estimar duração por parágrafo *antes* do TTS via `speakable_duration_seconds` (proporcional a contagem de palavras) — usado só para planejar quantas imagens gerar.
2. Sintetizar a narração **como um único áudio contínuo** (ou por parágrafo, concatenado depois — mais simples de gerenciar).
3. Se o TTS escolhido fornecer marcações de limite de palavra/frase (muitos serviços neurais oferecem; SAPI5 também expõe eventos de palavra via `SpeakProgress`), usar essas marcações reais para os cortes de imagem.
4. Se não fornecer, distribuir os cortes de imagem **proporcionalmente à contagem de palavras de cada parágrafo sobre a duração real total do áudio** — aproximação suficiente para v0.1, sem exigir forced alignment (ex. `aeneas`/`whisper` com timestamps), que é um componente adicional não instalado e não necessário nesta fase.

Isso responde diretamente à pergunta do briefing: **alinhamento por parágrafo com duração real pós-TTS é a menor abordagem aceitável**; forced alignment é P2/P3, só se a revisão humana mostrar dessincronia perceptível.

## 17. FFmpeg / Assembly Strategy

FFmpeg é o candidato correto e único avaliado — não há vantagem concreta em alternativa (MoviePy, por exemplo, é uma camada Python sobre FFmpeg com overhead extra e menos controle fino; não instalado, sem motivo para preferir).

Confirmado nesta sessão:
- `ffmpeg`/`ffprobe` **não estão no PATH** hoje (`ffmpeg: command not found`).
- **Disponível via `winget show ffmpeg` → `Gyan.FFmpeg` (versão 9.0)** — instalação de um comando, gratuita, sem conta, portátil no Windows. Isso deve ser um pré-requisito de setup do Gate 1, não uma decisão de arquitetura em aberto.

Recursos do FFmpeg a usar no v0.1: `zoompan`/`scale`+`crop` (Ken Burns), `xfade` (crossfade), concat (imagens + áudio), `loudnorm`/`afade`/`amix` (áudio), `-c:v libx264 -pix_fmt yuv420p` (compatibilidade ampla com YouTube), 1920×1080 ou 1280×720 @ 24-30fps. Aceleração de hardware (NVENC/QSV) é uma otimização de **P2** (velocidade), não um requisito de E2 — `libx264` por software é suficiente e mais portátil para provar o conceito primeiro.

## 18. Captions

- **Reutilizar diretamente:** `build_cues`, `render_srt` (`adapters/renderers/subtitles.py`) — já são funções puras e testadas.
- **Os timestamps atuais não são suficientemente precisos** para o Lite, porque hoje derivam de segmentos sintéticos de 10s do pipeline antigo — precisam ser recalculados a partir da timeline real pós-TTS (§16), não do timing hipotético do motor anterior.
- **SRT é suficiente para v0.1.**
- **Preferência confirmada: sidecar `.srt`**, não burn-in — mais simples, editável, e não exige reprocessar o vídeo para corrigir uma legenda.

## 19. Thumbnail

Reutiliza a mesma política de geração de imagem do resto do vídeo (§25/§27), com um prompt adicional focado em legibilidade a distância. Definições mínimas:
- Dimensões: 1280×720 (padrão recomendado pelo próprio YouTube).
- Prompt: derivado do "beat" de maior tensão/relevância do roteiro (mesmo princípio já usado no motor anterior para thumbnail-prompt, reaproveitável como *heurística*, não como código).
- Safe areas: manter elementos textuais/focais fora das bordas (~10% de margem) para sobreviver a cortes de interface do YouTube.
- Não construir sistema de otimização de CTR — é P3 por definição do briefing.

## 20. Metadata

Reaproveitar a **forma** de `PublicationMetadata`, reduzida:
```json
{
  "title": "...",
  "description": "...",
  "chapters": [{"at": "00:00", "title": "..."}],
  "hashtags": ["..."],
  "language": "pt-BR",
  "duration_seconds": 645
}
```
Sem SEO engine, sem múltiplos títulos alternativos, sem playlist/linked-shorts (irrelevantes ao Lite de formato único).

## 21. YouTube Bundle

Contrato proposto, com uma crítica ao exemplo do briefing:

```text
youtube_bundle/
├── video.mp4
├── thumbnail.png
├── captions.srt
├── metadata.json
├── script.md
├── manifest.json
├── provenance.json
└── assets/
    ├── narration.wav
    ├── music/            (só se música tiver sido usada)
    └── images/
```

**Crítica:** manter exatamente como proposto. Único ajuste: `provenance.json` pode ser **uma seção dentro de `manifest.json`** em vez de arquivo separado no v0.1 — reduz de 7 para 6 arquivos de nível superior sem perder nenhuma informação, e evita dois arquivos que precisam ficar sincronizados manualmente. Recomprometer como arquivo separado só se a proveniência crescer o suficiente para poluir o manifesto (decisão a revisitar em P2, não uma objeção forte).

## 22. Claude Code Responsibilities

Fronteira proposta (Builder) é razoável. Crítica: a frase "pode também operar/testar a engine quando necessário" cria sobreposição com o papel do Codex-Operador — isso é aceitável **desde que a fonte de verdade seja sempre o filesystem** (manifest/run directory), nunca o estado implícito de uma conversa (consistente com a regra 29 e §28). Recomendo adicionar uma regra de desempate explícita: **quem estiver ativamente conduzindo uma execução é o único a escrever no diretório daquela execução**; o outro operador só lê. Sobre geração de imagem por Claude Code via API externa quando não há capacidade nativa equivalente: coerente com a política local-first (§17) — é exatamente a situação em que uma API externa é "justificada" (regra 13/27), não dogmática.

## 23. Codex Responsibilities

Fronteira proposta (Operator) é razoável e simétrica à de Claude Code. **Não posso confirmar nem negar, a partir desta sessão (que roda em Claude Code, não em Codex), se geração nativa de imagem está de fato disponível no ambiente Codex** — isso deve ser verificado dentro de uma sessão Codex real antes de qualquer implementação que dependa disso. Rotular como **UNKNOWN, requer verificação em ambiente Codex** é a postura evidence-first correta aqui, não uma suposição otimista.

## 24. Execution Environment Capabilities

Resumo de tudo verificado localmente nesta sessão (Claude Code, Windows):

| Capability | Status | Evidência |
|---|---|---|
| FFmpeg no PATH | Ausente | `ffmpeg: command not found` |
| FFmpeg instalável via winget | Disponível | `winget show ffmpeg` → `Gyan.FFmpeg` 9.0 |
| TTS nativo do SO (SAPI5, pt-BR) | Presente | `System.Speech` lista "Microsoft Maria Desktop", `Culture=pt-BR` |
| Bibliotecas Python de TTS/imagem/vídeo no venv do projeto | Ausentes | `pip list` sem correspondência a TTS/imagem/vídeo/diffusers/whisper |
| `ANTHROPIC_API_KEY` no `.env` | Presente (nome da variável; valor nunca lido) | `grep` de nomes de chave, sem exibir valores |
| `OPENAI_API_KEY` no `.env` | Presente (nome da variável; valor nunca lido) | idem |
| `ELEVENLABS_API_KEY`/`GEMINI_API_KEY`/`GOOGLE_API_KEY` no `.env` real | Ausentes (só existem no `.env.example`, como template) | idem |
| Geração nativa de imagem em ambiente Codex | **UNKNOWN — não verificável a partir desta sessão** | esta sessão é Claude Code, não Codex |

## 25. Image Generation Policy

Política avaliada e considerada **viável com uma ressalva importante**: a Anthropic (única chave "de plataforma LLM" mais forte presente no `.env`) **não oferece geração de imagem via API** — isso deve ficar explícito em qualquer implementação futura para não gerar uma tentativa de chamada a um endpoint inexistente. Entre as chaves realmente presentes, **OpenAI é a única com endpoint de geração de imagem documentado**. O modelo de `image_manifest.json` proposto no briefing (§14) é bem desenhado — pequeno, com campos suficientes para proveniência (`prompt`, `negative_constraints`, `aspect_ratio`, `visual_bible_reference`) e para o Codex (ou qualquer operador) preencher `expected_output_path` sem precisar de contexto de conversa.

## 26. External API Policy

**API externa é justificada para:** (1) geração de imagem, porque não existe alternativa local instalada e comprovada nesta sessão; (2) geração do roteiro/prosa, porque a alternativa determinística/heurística comprovadamente não produz prosa nova de qualidade (§11); (3) narração, **somente se `edge-tts`/SAPI não atingirem a barra de qualidade** (§14) — aqui a API é a segunda escolha, não a primeira, porque existe alternativa gratuita plausível ainda não testada.

**API externa NÃO é justificada, no v0.1, para:** QA, empacotamento, geração de legendas, timeline, mixagem de áudio — todos resolvidos localmente com custo zero e sem perda de qualidade perceptível.

## 27. Fallback Strategy

```text
REQUEST IMAGE
     ↓
Ambiente é Codex com geração nativa disponível?  → SIM → usar geração nativa
     ↓ NÃO / DESCONHECIDO
Existe OPENAI_API_KEY configurada e válida?       → SIM → usar OpenAI (única com endpoint de imagem confirmado)
     ↓ NÃO
Existe outro provider de imagem configurado (ex.: Gemini, se a chave for adicionada)? → SIM → usar
     ↓ NÃO
FALHAR de forma explícita e visível — nunca degradar silenciosamente para um placeholder genérico
```

`ANTHROPIC_API_KEY` **não entra nesta cadeia de fallback de imagem** — é relevante apenas para o `ScriptGenerationPort`, não para o `ImageGenerationPort`. Essa distinção deve ficar explícita no design (§13) para não ser esquecida por quem implementar depois.

## 28. SDD/SPDD Proposal

Crítica à árvore de documentos proposta no briefing (§29): 8 arquivos + pasta ADR é documentação demais para um v0.1 que ainda não provou nada. Proposta enxuta:

| Documento | Mantém? | Justificativa |
|---|---|---|
| `SDD.md` | Sim, único, cobrindo também o que seria `SPDD.md` | Nesta fase, decisão de sistema e decisão de produto são o mesmo punhado de pessoas/decisões — separar cedo é burocracia sem consumidor real (regra 15) |
| `SPDD.md` | **Fundir em `SDD.md`** | idem |
| `EXECUTION_POLICY.md` | Sim, fundido com `IMAGE_GENERATION_POLICY.md` | Ambos descrevem a mesma cadeia de decisão local-first/fallback (§27) — um documento só, seções internas |
| `IMAGE_GENERATION_POLICY.md` | **Fundir em `EXECUTION_POLICY.md`** | idem |
| `OPERATOR_CONTRACT.md` | Sim | Papel de Claude/Codex/Humano + regra de desempate de escrita (§22) — conteúdo genuinamente distinto |
| `ARTIFACT_CONTRACT.md` | Sim | Schema do bundle + manifest + proveniência (§21, §27 do briefing) |
| `QA_GATES.md` | Sim | Gates automatizados + humanos (§31, §33) — público diferente (quem roda QA) do público de arquitetura |
| `ADR/` | Sim, mas só para decisões realmente irreversíveis/caras de reverter (ex.: "por que vertical slice, não adaptar o pipeline existente"; "por que FFmpeg, não um renderer próprio") — não um ADR por escolha trivial | Regra 30: não construir documentação bonita por si só |

**Resultado: 4 documentos (`SDD.md`, `EXECUTION_POLICY.md`, `OPERATOR_CONTRACT.md`, `ARTIFACT_CONTRACT.md`, `QA_GATES.md` — 5, corrigindo a contagem) + `ADR/` com 2-3 decisões, não 8+.** Nenhum arquivo é criado agora, por regra deste discovery.

## 29. Claude ↔ Codex Handoff Contract

O contrato de handoff do briefing (`run_manifest.json → pending_tasks.json → operador → produced_artifacts → manifest atualizado → continua`) é sólido e consistente com a regra 29 (filesystem como fonte de verdade). Refinamento proposto:

- `run_manifest.json`: estado da execução (que fases concluíram, quais artefatos existem, hash de cada um) — **fonte única de verdade**, nunca a conversa.
- `pending_tasks.json`: lista explícita do que falta (ex.: "gerar imagem para beat 7", "sintetizar narração do parágrafo 3") com `status: pending|in_progress|done|failed` por item — permite que qualquer operador pegue exatamente de onde o outro parou sem precisar reconstruir contexto.
- Regra de propriedade: um operador só marca `in_progress` um item que vai executar **agora**; nunca reserva lote antecipadamente (evita deadlock de duas sessões "reservando" o mesmo trabalho).
- Ao terminar (ou falhar) um item, o operador atualiza `pending_tasks.json` e `run_manifest.json` **antes** de devolver o controle — nunca depois, e nunca "de memória" numa próxima sessão.

## 30. Human-in-the-Loop

Gates conforme o briefing, com uma definição operacional para cada:

- **Gate A — Script:** recomendo **obrigatório, porém rápido** (leitura de ~2 min do `script.md`) — é o ponto mais barato de pegar um problema de fundo (tese fraca, alucinação factual) antes de gastar geração de imagem/TTS em cima dele.
- **Gate B — Visual Assets:** **spot check** (amostragem de ~20-30% das imagens), não revisão total — revisão total de 20-50 imagens tem custo de tempo humano desproporcional ao risco, que é maioritariamente "estilo inconsistente", detectável por amostragem.
- **Gate C — Final Video:** **obrigatório, vídeo assistido integralmente**, exatamente como o briefing define. Este é o gate que decide `HUMAN_PASS`/`HUMAN_PASS_WITH_NOTES`/`HUMAN_FAIL`.

## 31. Local Testing Strategy

Pirâmide mínima que protege especificamente `BRIEFING → MP4`:

- **Unit:** funções puras isoladas (estimativa de duração, formatação de SRT, cálculo de loudness-alvo, validação do schema de briefing).
- **Contract:** forma de `image_manifest.json`, `pending_tasks.json`, `run_manifest.json`, `metadata.json` — testes que travam o schema para não quebrar o handoff entre operadores.
- **Integration:** um teste que monta um `briefing.yaml` de fixture pequeno e roda o Timeline Builder + Assembler contra **áudio/imagens de fixture já existentes** (não gerados de verdade) — prova a colagem sem gastar geração real.
- **Smoke:** um `.mp4` de ~30-60s gerado de ponta a ponta com SAPI + 2-3 imagens estáticas de fixture, custo zero, para rodar em CI/local a cada mudança — prova que o cano inteiro (script→narração→imagens→FFmpeg→captions→QA→bundle) fecha, sem pagar por um vídeo de 10 minutos toda vez.
- **E2E local (não em CI):** o teste completo de ~10-15 min, rodado manualmente quando necessário — é caro em tempo, não deve rodar automaticamente a cada commit.

Não maximizar número de testes — cada nível acima existe só para proteger uma junção específica do cano (regra do próprio briefing).

## 32. E2E Test Design

- **INPUT:** um `briefing.yaml` realista (tema com profundidade suficiente para 10-15 min de conteúdo genuíno, não um tópico raso que forçaria enchimento).
- **EXECUTION ENVIRONMENT:** local (Claude Code ou Codex, conforme disponibilidade), Windows confirmado como plataforma real de teste desta sessão.
- **ASSET STRATEGY:** Codex-nativo se confirmado disponível (§23); caso contrário, OpenAI para imagem (única com endpoint confirmado) e `edge-tts` para narração (§14), com justificativa registrada em `provenance`.
- **EXPECTED OUTPUT:** `youtube_bundle/` completo conforme §21.
- **AUTOMATED PASS:** arquivo `.mp4` existe e abre (`ffprobe` sem erro); duração ≥ `target_min_minutes`; resolução e codec batem com o especificado; stream de áudio presente e sem clipping, loudness dentro da faixa; `captions.srt` parseia e cobre a duração toda; `thumbnail.png` existe nas dimensões corretas; `metadata.json` tem todos os campos obrigatórios; `manifest.json` fecha sem item pendente obrigatório.
- **HUMAN PASS:** vídeo assistido integralmente, veredito `HUMAN_PASS`/`HUMAN_PASS_WITH_NOTES`/`HUMAN_FAIL`.
- **COST:** registrar `external_api_cost` real incorrido (não estimado) e `generation_time`.
- **RESULT:** `E2_PROVEN` somente se automatizado + humano passarem; `E2_NOT_PROVEN` caso contrário — **nenhum dos dois critérios sozinho basta**, coerente com a regra 5 do briefing (não conceder E2 sem o artefato final avaliado por humano).

## 33. Development Gates

Os gates propostos no briefing são bons; simplificação sugerida (fundir 2 e 3, que são a mesma preocupação de "consegue produzir um insumo real, sozinho, antes de compor"):

- **Gate 0 — Discovery:** este documento.
- **Gate 1 — Existing Core Health:** confirmar que os componentes reutilizados (renderização de SRT, forma de metadados, utilitário de duração) funcionam isoladamente **fora** do orquestrador quebrado — mais barato que "consertar o motor inteiro", porque testa só a função, não o `bootstrap()`.
- **Gate 2 — Single Asset Proof:** UMA narração real (SAPI, custo zero) + UMA imagem real (via provider configurado) + UM clipe curto montado no FFmpeg. Prova a cadeia de ponta a ponta em miniatura antes de escalar para 10-15 min.
- **Gate 3 — Full Duration:** briefing real → vídeo ≥10 min, com narração de qualidade publicável (`edge-tts` ou API, não mais SAPI).
- **Gate 4 — Human Pass:** revisão integral, veredito registrado.

(Reduzido de 7 para 5 gates em relação à proposta original, fundindo Áudio+Visual em "Single Asset Proof" — eles têm o mesmo objetivo de prova de conceito em miniatura antes da escala completa, e separá-los adiciona uma junção de mais sem reduzir risco de forma proporcional.)

## 34. Unit Economics Instrumentation

Registrar por execução, em `manifest.json`/`provenance`, sem construir um sistema de analytics (isso é P3, fora de escopo por regra 21):
```text
external_api_cost         # soma real observada (0 se só local/nativo)
generation_time_seconds   # tempo total da execução
human_review_time_seconds # tempo do Gate C
asset_count                # imagens + áudio gerados
render_time_seconds        # só a etapa FFmpeg
retry_count                 # falhas de geração recuperadas
execution_environment       # "claude_code" | "codex" | outro
generation_method            # "native_environment_capability" | "external_api:<provider>"
```
Quando geração nativa do ambiente for usada, registrar explicitamente `external_api_cost: 0` **e** `generation_method: native_environment_capability` — nunca deixar implícito que "0 custo de API" significa "0 custo computacional", conforme a distinção exigida pelo briefing (§39).

## 35. Reuse Matrix

| Componente | Classificação | Justificativa |
|---|---|---|
| `ProjectConfiguration` (classe) | REPLACE (novo schema Lite) | Campos do motor atual (6 formatos, segmentação de 10s) não se aplicam; o *padrão* Pydantic estrito é reaproveitado, a classe não |
| `PromptSegment` | FREEZE | Modelo pesado, desenhado para compilação de prompt por provedor de vídeo/imagem/voz separadamente — Lite usa um "beat visual" muito mais simples |
| Máquina de estados (`domain/state.py`) | FREEZE | 15 estados desenhados para o pipeline de compilação de prompts; Lite precisa de um status de execução muito mais simples |
| Cânone (`CanonExtractorAgent` etc.) | REUSE_LATER | Útil se/quando briefings Lite incluírem material de referência longo a estruturar; não necessário para um briefing curto de tópico |
| Bíblia audiovisual | REUSE_SIMPLIFIED | Alguns campos (paleta, iluminação) inspiram a Visual Bible Lite, drasticamente reduzida |
| Analisador heurístico | REUSE_LATER | Mesmo raciocínio do cânone — útil só quando houver texto-fonte longo a estruturar |
| RAG | FREEZE | Nenhum consumidor real no Lite v0.1 (briefings curtos não precisam de recuperação sobre um livro inteiro) |
| Serviços de continuidade cinematográfica | FREEZE | Desenhados para continuidade entre segmentos de vídeo gerado; Lite usa consistência por Visual Bible + prompt compartilhado, muito mais simples |
| QA de domínio (`domain/validation.py`) | REUSE_LATER | O *padrão* (issue estruturada, severidade, bloqueante) é bom; os *checks* concretos são sobre completude de prompt, não sobre propriedades de arquivo `.mp4` — Lite precisa de checks novos e pequenos |
| Compiladores de prompt | REUSE_SIMPLIFIED | A forma "texto estruturado + restrições negativas" inspira o prompt de imagem do Lite |
| `render_srt`/`render_vtt`/`build_cues` | **REUSE_AS_IS** | Funções puras corretas; só precisam de timing real como entrada |
| Metadados (`PublicationMetadata`) | REUSE_SIMPLIFIED | Forma boa, campos de multi-formato removidos |
| Manifests | REUSE_SIMPLIFIED | Padrão bom, schema menor |
| Checkpoints | REUSE_LATER | Valioso quando execuções Lite ficarem longas/caras o bastante para justificar resume; não crítico para o primeiro vídeo |
| Telemetria/logging | REUSE_AS_IS | Padrão correto e agnóstico de domínio |
| Retry/circuit breaker | FREEZE | Poucas chamadas de API no v0.1 não justificam essa infraestrutura; `try/except` simples com log basta |
| Provedores fake | REMOVE_CANDIDATE | Zero consumidores mesmo em teste, confirmado no discovery anterior |
| 27 agentes / orquestrador | FREEZE | É o "Advanced Mode" — não tocar, não estender |
| Seis famílias de formato | FREEZE | Lite é um formato só (vídeo principal ≥10min) |

## 36. Freeze/Defer Matrix

| Item | Status |
|---|---|
| Modo cinematográfico/profissional | FROZEN |
| Vídeo generativo | FROZEN |
| Continuidade de personagem sofisticada | FROZEN |
| Planejamento avançado de câmera | FROZEN |
| Múltiplos provedores de vídeo | FROZEN |
| Seleção automática de modo | FROZEN (não existe modo ainda) |
| Shorts/série/mini-novela/trailers | FROZEN |
| Upload automático | FROZEN por decisão de escopo (não é "futuro provável", é fronteira deliberada) |
| Analytics de audiência | FROZEN |
| Ducking dinâmico de áudio | DEFERRED a P1 |
| Forced alignment fonema-a-fonema | DEFERRED a P2/P3 |
| Cache/reaproveitamento de assets entre execuções | DEFERRED a P2 |
| Otimização de CTR de thumbnail | DEFERRED a P3 |

## 37. Risks

| Risco | Probabilidade | Impacto | Mitigação | Deve resolver antes de E2? |
|---|---|---|---|---|
| Roteiro raso/alucinação factual | Média | Alto | Gate A humano + validação determinística de estrutura (contagem de palavras, repetição) | Sim |
| Imagens inconsistentes entre si | Média | Médio | Visual Bible Lite prefixada em todo prompt + Gate B por amostragem | Sim |
| TTS soar artificial demais (abaixo da barra de publicação) | **Alta com SAPI, baixa-média com `edge-tts`** | Alto | Usar SAPI só para prova de pipeline; `edge-tts`/API para o vídeo real | Sim |
| Vídeo parecer "slideshow genérico" | Média | Alto | Ken Burns + transições + variedade de composição no prompt de imagem | Sim |
| Música inadequada/alta demais | Baixa (mitigável facilmente) | Médio | Volume fixo conservador + medição de loudness no QA | Sim |
| Risco de copyright (marca/pessoa real) | Baixa-média | Alto (bloqueia publicação) | Reaproveitar heurística de regex de marca/celebridade do motor atual como checklist do QA | Sim |
| Duração inflada artificialmente | Baixa (mitigado por design) | Alto (viola requisito central) | Gate de duração pós-TTS falha e pede mais roteiro real, nunca padding | Sim |
| Pipeline lento (muitas imagens/segmentos) | Média | Baixo-médio (custo de tempo, não de qualidade) | Manter contagem de beats na ponta inferior da faixa (15-30) no v0.1 | Não — é P2 |
| Handoff Claude/Codex perder contexto | Média | Médio | Filesystem como fonte de verdade + `pending_tasks.json` explícito | Sim |
| Dependência de capability específica do ambiente (Codex nativo) | Alta (hoje é UNKNOWN) | Médio | Fallback explícito para API configurada, nunca falha silenciosa | Sim |
| Mudança futura de ferramentas (provider de imagem/TTS trocar) | Média | Baixo | `ImageGenerationPort`/`NarrationPort` como abstração fina, não acoplamento direto (§13) | Não — é P2, mas o desenho deve já prever isso |
| Custo oculto (tempo humano de revisão, tempo de máquina) | Alta (quase certo de existir) | Baixo se medido, alto se ignorado | Instrumentação da §34 desde o v0.1 | Sim (medir, não necessariamente otimizar) |
| Overengineering (repetir o erro do motor anterior) | Média (risco real, dado o histórico) | Alto | Regra 35/17 deste discovery: nenhum componente sem consumidor real no vertical slice | Sim — é a restrição arquitetural central deste documento |

## 38. Complexity Critique

A hipótese de arquitetura mínima (§6/§7) já está bem próxima do menor sistema viável. O único risco de complexidade real hoje é a **tentação de reaproveitar demais** do motor anterior por já existir (ex.: tentar encaixar o Lite dentro do `EngineContext`/`PipelineOrchestrator` "porque já tem infraestrutura de agente") — isso seria repetir exatamente o erro descrito na regra 35 do briefing. A recomendação deste documento (Estratégia Híbrida = vertical slice + importação cirúrgica de funções puras) evita esse risco por construção, porque nenhuma das importações recomendadas (§35, linhas "REUSE_AS_IS"/"REUSE_SIMPLIFIED") exige o framework de agentes.

## 39. P0/P1/P2/P3

### P0 — Somente o necessário para Briefing → vídeo ≥10min → bundle → Human Review
1. Schema de `briefing.yaml` + validação estrita.
2. Script Planner (LLM, com validação determinística de duração/estrutura pós-geração).
3. Visual Bible Lite + Visual Manifest (fundidos em v0.1).
4. Geração de imagem via provider configurado (política de fallback, §27), com registro de proveniência.
5. Narração via SAPI (prova) → `edge-tts` (produção).
6. Timeline por parágrafo com duração real pós-TTS.
7. Mixagem simples (loudnorm + música opcional em volume fixo) via FFmpeg.
8. Montagem/render via FFmpeg (Ken Burns + crossfade + concat + mux).
9. Captions SRT reaproveitando `render_srt`/`build_cues` com timing real.
10. QA automatizado mínimo (arquivo abre, duração, resolução/codec, áudio presente, loudness/clipping, SRT parseia, campos obrigatórios do manifesto).
11. Packager (`youtube_bundle/`).
12. Thumbnail (reuso da política de imagem).
13. Metadata (`metadata.json` reduzido).
14. `manifest.json` + proveniência (fundidos, §21).
15. Gate C humano (obrigatório).

### P1 — Qualidade/confiabilidade imediatamente úteis
- Ducking dinâmico de áudio (se Gate C apontar necessidade).
- Reconectar/reaproveitar heurística de risco de direitos (marca/celebridade) como checklist automatizado.
- Melhorar timeline com marcações reais de palavra do TTS escolhido, se disponíveis.
- Retry simples (não circuit breaker) para chamadas de imagem/TTS que falharem.

### P2 — Economia, velocidade, repetibilidade
- Cache/reaproveitamento de imagens entre execuções sobre o mesmo tema.
- Aceleração de hardware no FFmpeg.
- Checkpoints/resume real (reaproveitando o padrão do motor atual, corrigido).
- Estimativa de custo pré-execução.
- Forced alignment, se a amostra mostrar dessincronia perceptível.

### P3 — Futuro
- Modo profissional/cinematográfico (o pipeline atual, quando/se retomado).
- Múltiplos formatos (Shorts, série, etc.) sobre a mesma base Lite.
- Otimização de thumbnail por CTR.
- Analytics pós-publicação, ligados por `run_id`.

## 40. Recommended Implementation Sequence

1. Gate 1 (Existing Core Health) — validar isoladamente as poucas funções reutilizadas.
2. Instalar FFmpeg (`winget install Gyan.FFmpeg`) como pré-requisito de ambiente — ação de setup, não de arquitetura.
3. Gate 2 (Single Asset Proof) — um parágrafo, uma imagem, um clipe curto, com SAPI.
4. Decidir e testar o provider de imagem real (OpenAI, dado que é a única chave presente com endpoint de imagem confirmado) sobre 2-3 imagens.
5. Trocar SAPI por `edge-tts` e validar naturalidade em um trecho curto.
6. Gate 3 (Full Duration) — primeiro briefing real de ponta a ponta.
7. Gate 4 (Human Pass) — veredito registrado.
8. Só então escrever os 5 documentos do SDD/SPDD enxuto (§28), já informados pelo que realmente funcionou, em vez de especular.

## 41. Final Verdict

O YouTube Lite é viável como próximo passo, com uma condição clara: **construir um vertical slice novo e pequeno, não estender o motor de 27 agentes.** Todos os riscos identificados são gerenciáveis com mitigações já mapeadas (§37), e o ambiente local já tem parte do caminho comprovado (FFmpeg instalável, TTS pt-BR nativo disponível, uma chave de API com endpoint de imagem confirmado). O maior fator de incerteza restante não é técnico dentro deste repositório — é a **capacidade real do ambiente Codex**, que não pôde ser verificada nesta sessão.

---

## VEREDITO OBRIGATÓRIO

```text
YOUTUBE_LITE_RECOMMENDED: SIM
YOUTUBE_LITE_AS_DEFAULT_RECOMMENDED: SIM
CURRENT_ENGINE_REUSE_PERCENT_ESTIMATE: ~10-15% (poucas funções puras e padrões de forma de dado; nenhum componente de execução/orquestração é reutilizado como está)
RECOMMENDED_STRATEGY: HYBRID (na prática, um vertical slice com importação cirúrgica de funções puras existentes)
MINIMUM_COMPONENT_COUNT: 8 componentes novos não triviais (Script Planner, Visual Bible+Manifest fundidos, Asset Generation, Narration, Timeline Builder, Assembler/FFmpeg, QA, Packager) + 5 pequenos/triviais
COMPONENTS_TO_REUSE: render_srt/render_vtt/build_cues (as-is); speakable_duration_seconds/count_words (as-is); forma de PublicationMetadata (simplificada); padrão de config Pydantic estrita; RunLogger/logging; PathPolicy
COMPONENTS_TO_SIMPLIFY: metadados de publicação; manifests; forma de prompt de imagem (restrições negativas); QA (padrão de issue estruturada, checks novos)
COMPONENTS_TO_FREEZE: 27 agentes/orquestrador; máquina de estados de 15 fases; seis famílias de formato; RAG; serviços de continuidade cinematográfica; retry/circuit breaker; provedores fake (candidatos a remoção)
COMPONENTS_TO_BUILD: briefing schema Lite; Script Planner (LLM + validação determinística); Visual Bible/Manifest Lite; Image Generation Port + fallback; Narration Port; Timeline Builder por parágrafo; config de mixagem/montagem FFmpeg; QA de arquivo/mídia; Packager; provenance/manifest Lite
BRIEFING_CONTRACT_STATUS: PROPOSTO, NÃO VALIDADO (schema no §9 é hipótese de discovery)
DURATION_POLICY_RECOMMENDATION: target_min=10min / target_max=15min, validado PÓS-TTS (nunca por padding artificial); abaixo do mínimo falha e exige mais roteiro real
SCRIPT_STRATEGY: LLM (Claude Code como builder, ou API Anthropic já configurada) gera prosa; validação determinística (contagem de palavras/duração/repetição) audita o resultado
VISUAL_STRATEGY: 15-30 imagens estáticas de alta qualidade + Ken Burns + crossfade; sem vídeo generativo
VISUAL_BIBLE_LITE_RECOMMENDED: SIM, campos reduzidos (~7-8 campos, personagens/locais opcionais)
IMAGE_GENERATION_STRATEGY: Codex nativo se disponível (UNKNOWN, requer verificação em ambiente Codex) → senão OpenAI (única chave confirmada com endpoint de imagem) → falhar explicitamente, nunca degradar silenciosamente
CODEX_NATIVE_IMAGE_GENERATION_VIABLE: UNKNOWN — não verificável a partir desta sessão Claude Code
CODEX_OPERATOR_MODEL_VIABLE: SIM, condicionado à verificação acima
CLAUDE_BUILDER_MODEL_VIABLE: SIM
CLAUDE_IMAGE_GENERATION_STRATEGY: API externa (OpenAI) quando não houver capacidade nativa equivalente no ambiente Claude Code — justificado, não dogmático
EXTERNAL_API_REQUIRED_FOR_E2: SIM, para geração de imagem (nenhuma alternativa local comprovada) e para roteiro de qualidade (heurística atual insuficiente); narração pode começar sem API (SAPI/edge-tts)
EXTERNAL_API_AVOIDABLE_FOR_CODEX_E2: PARCIALMENTE — só se a geração nativa de imagem do Codex for confirmada; roteiro provavelmente ainda se beneficia de LLM real
PROVIDER_FALLBACK_STRATEGY: nativo do ambiente → provider configurado com endpoint confirmado (hoje: OpenAI para imagem) → falha explícita; ANTHROPIC_API_KEY nunca entra na cadeia de imagem
TTS_RECOMMENDATION: SAPI5 (Microsoft Maria Desktop, pt-BR) para prova de pipeline sem custo; edge-tts para a barra de qualidade publicável no v0.1; API paga (OpenAI TTS, chave já presente) como upgrade opcional
AUDIO_MIXING_RECOMMENDATION: FFmpeg (loudnorm + afade + amix); ducking dinâmico adiado para P1
ASSEMBLY_RECOMMENDATION: FFmpeg (zoompan/Ken Burns + xfade + concat + mux); sem renderer próprio
FFMPEG_RECOMMENDED: SIM — não instalado hoje, mas confirmado disponível via winget (Gyan.FFmpeg), instalação é pré-requisito de setup do Gate 1
CLAUDE_CODE_PRIMARY_RESPONSIBILITY: Builder (discovery, arquitetura, implementação, testes, contratos, correção de bugs) + operação/teste da engine quando necessário
CODEX_PRIMARY_RESPONSIBILITY: Operator (execução local, geração de assets via capacidade nativa quando disponível, validação, evidências, manifests/proveniência)
ENGINE_EXECUTION_ENVIRONMENT_DECOUPLED: PROPOSTO (ImageGenerationPort/NarrationPort como abstração fina) — não implementado ainda, por regra deste discovery
SDD_REQUIRED: SIM, um único documento fundindo SDD+SPDD no v0.1
SPDD_REQUIRED: NÃO como arquivo separado no v0.1 (fundir em SDD.md)
HANDOFF_CONTRACT_REQUIRED: SIM (run_manifest.json + pending_tasks.json, filesystem como fonte de verdade)
IMAGE_GENERATION_POLICY_REQUIRED: SIM, fundida em EXECUTION_POLICY.md
YOUTUBE_UPLOAD_IN_SCOPE: NÃO
ANALYTICS_IN_SCOPE: NÃO
ADVANCED_MODE_STATUS: FROZEN/FUTURE
LOCAL_FIRST_VIABLE: PARCIALMENTE — narração (SAPI) e montagem (FFmpeg) sim; geração de imagem e roteiro de qualidade dependem de API externa ou capacidade nativa do ambiente, hoje não substituíveis localmente sem perda de qualidade
E2_LOCAL_TEST_VIABLE: SIM, com as ressalvas de dependência de API/ambiente acima
MINIMUM_E2_TEST: briefing.yaml de fixture → pipeline Lite completo → youtube_bundle/ → checks automatizados (§32) → Gate C humano
EXPECTED_VIDEO_DURATION: 10-15 minutos (faixa alvo), determinado pelo conteúdo real, nunca por padding
HUMAN_REVIEW_REQUIRED: SIM, obrigatório no Gate C (vídeo assistido integralmente)
BIGGEST_TECHNICAL_RISK: qualidade de TTS abaixo da barra de publicação se SAPI for usado além da prova de conceito
BIGGEST_PRODUCT_RISK: vídeo parecer "slideshow genérico" em vez de conteúdo com valor percebido
BIGGEST_ARCHITECTURAL_RISK: repetir o erro do motor anterior — reaproveitar o framework de agentes/orquestração "porque já existe" em vez de manter o vertical slice pequeno
P0_COUNT: 15
ESTIMATED_IMPLEMENTATION_COMPLEXITY: MEDIUM (a maioria dos componentes é pequena e bem delimitada; o risco está em integração de providers externos e qualidade percebida, não em volume de código)
OVERENGINEERING_RISK_AFTER_PIVOT: LOW, se a restrição da regra 35 do briefing (nenhuma abstração sem consumidor real no vertical slice) for de fato seguida na implementação
READY_TO_WRITE_SDD_SPDD: SIM, com o entendimento de que alguns detalhes (ex.: capacidade real do Codex) só se resolvem durante o Gate 1-2
READY_TO_IMPLEMENT_YOUTUBE_LITE: SIM, começando pelo Gate 1 (Existing Core Health) e Gate 2 (Single Asset Proof) antes de qualquer execução de 10-15 minutos
RECOMMENDED_NEXT_ACTION: Escrever o SDD.md enxuto (§28) e então executar Gate 1 → Gate 2 (prova de um único parágrafo + uma imagem + um clipe curto, custo zero via SAPI e um provider de imagem já configurado) antes de comprometer qualquer briefing completo de 10-15 minutos
GATE_VERDICT: LITE_VIABLE_WITH_CONSTRAINTS
```
