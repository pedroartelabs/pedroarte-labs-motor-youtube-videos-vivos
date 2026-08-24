# YOUTUBE ENGINE — DISCOVERY REPORT

**Repositório:** `pedroarte-labs-motor-youtube-videos-vivos` (pacote `pedroarte_youtube_engine`, CLI `living-video`)
**Método:** leitura de código-fonte completa (src/, tests/, config/, examples/), execução real do CLI e da suíte de testes, inspeção do histórico de commits. Nenhuma alteração foi feita no motor. Nenhuma API paga foi chamada.
**Data do discovery:** 2026-08-23

Toda afirmação abaixo é rotulada **PROVEN** (execução real observada), **IMPLEMENTED_NOT_PROVEN** (código existe, não executado), **PARTIAL**, **DOCUMENTED_ONLY**, **STUB/MOCK**, **NOT_FOUND** ou **UNKNOWN**, conforme a seção 1 do protocolo.

---

## 1. Executive Summary

Este repositório **não é um motor de renderização de vídeo**. É um **compilador de pré-produção**: um pipeline de 27 agentes, orientado por máquina de estados, que lê um livro em Markdown/PDF/DOCX/EPUB e produz **prompts de texto estruturados** — um por segmento de 10 segundos, por modalidade (vídeo, imagem, voz) — junto com uma bíblia de cânone, uma bíblia audiovisual, uma lista de planos (shotlist), uma transcrição e um manifesto. Ele **nunca** chama uma API de geração de vídeo, imagem, TTS ou música: não existe nenhum adaptador real para nenhum desses provedores em lugar nenhum do código, apenas dublês determinísticos (`fakes.py`) usados só por ele mesmo e nunca conectados à execução real. A flag `execute_generation`, que prometeria acionar chamadas pagas, é validada na configuração mas **não é lida por nenhum agente** — é decorativa.

O conceito de **"modo de execução"** pedido neste discovery (profissional × simples/slideshow × outros) **não existe no código nem na documentação**. O que existe são seis **famílias de formato por duração** (vídeo de 10 min, Shorts, longa, série, mini-novela, trailers) — um eixo de *duração/estrutura narrativa*, não de *estilo de produção/complexidade visual*. Não há seleção de "modo simples vs. profissional" em lugar nenhum: um único pipeline linear atende todas as variantes.

Mais grave: **o pipeline não executa de ponta a ponta hoje, em nenhuma interface.** Executei o CLI (`living-video run`), a API e o MCP server chamam todos a mesma função `bootstrap()` (`src/pedroarte_youtube_engine/interfaces/_bootstrap.py`), e ela quebra imediatamente com `TypeError: RunLogger.__init__() got an unexpected keyword argument 'verbose'` — comprovado por execução real (ver §11 e veredito). Corrigindo isso à mão, encontrei pelo menos **mais três** incompatibilidades de assinatura entre `_bootstrap.py` e a camada de infraestrutura (`FilesystemArtifactAdapter`, `CheckpointStore`) só por leitura de código. Nenhum teste do repositório chama `bootstrap()` ou `PipelineOrchestrator.execute()` — os 126 testes que passam (`pytest tests/ -v` → 126 passed) são inteiramente unitários/de contrato sobre peças isoladas; a fiação entre elas nunca foi exercitada.

**Melhor caminho hoje:** nenhum, sem trabalho de correção primeiro. O menor experimento real (§26) é justamente destravar essa fiação — não é uma pergunta de produto, é um bug de integração de ~3 linhas por ponto de quebra.

**Maior gap:** zero capacidade de produzir um arquivo de vídeo, áudio, imagem ou legenda. O produto real hoje é texto (Markdown/CSV/JSON) para um humano colar num gerador externo.

---

## 2. Repository Map

```
pyproject.toml         deps: pydantic, typer, rich, PyYAML, Jinja2, jsonschema
                        extras: api (fastapi/uvicorn), parsers (pypdf/python-docx/
                        EbookLib/bs4 — só para LER o livro), dev, docs
                        SEM nenhuma lib de vídeo/áudio/imagem (sem ffmpeg-python,
                        moviepy, elevenlabs, openai, anthropic, google-genai, etc.)

src/pedroarte_youtube_engine/
  domain/          entidades, value objects, máquina de estados, serviços de
                    domínio (Clean Architecture — não importa adapters/SDKs)
  ports/           Protocols: llm, media, parsing, embedding, retrieval,
                    storage, vector_store, queue, capabilities, analysis
  adapters/
    analysis/       HeuristicNarrativeAnalyzer (regex + léxicos PT-BR)
    parsers/        text, binary (pdf/docx/epub via extras opcionais)
    prompt_compilers/  generic.py, gemini.py — geram TEXTO, não chamam API
    providers/      deterministic_llm.py (padrão, não é LLM real) + fakes.py
                     (dublês; usados só neles mesmos)
    renderers/      markdown.py, subtitles.py (SRT/VTT — gerado em memória,
                     não exportado pelo orquestrador)
  agents/          27 classes BaseAgent + orchestrator.py
  prompts/         registro de definições de prompt versionadas com hash
                    (usadas para instruir o DeterministicLLMProvider — não há
                    LLM real consumindo-as)
  rag/             chunking, BM25, embeddings hash-based, vector store em
                    memória — 100% local, sem rede
  infrastructure/  artifacts.py, checkpoints.py, capabilities.py,
                    config_loader.py, resilience.py (retry/circuit breaker,
                    só relevante quando execute_generation=true, que nunca
                    é lido)
  interfaces/      cli.py (Typer), api.py (FastAPI opcional), mcp_server.py,
                    _bootstrap.py (cola compartilhada — QUEBRADA)
  observability/   logging.py, metrics.py, redaction.py

tests/             9 arquivos, 126 testes, 100% unitário/contrato — ZERO
                    referência a bootstrap() ou orchestrator.execute()

config/provider_capabilities/generic.yaml   único arquivo de capacidades
examples/          project.yaml (config exemplo), sample_living_book/ (livro
                    de exemplo "O Relojoeiro de Vidro")
schemas/           referenciado no pyproject.toml (sdist) e no CHANGELOG
                    ("JSON Schemas publicados em schemas/") — NOT_FOUND:
                    o diretório não existe no repositório.
```

Não há projetos relacionados dentro deste repositório. O README menciona um "motor editorial" de livros como referência conceitual em outro produto da mesma família (PedroArteLabs) — não auditado aqui, usado só como paridade conceitual (§13).

---

## 3. What Goes In

| Entrada | Formato | Obrigatória? | Consumidor | Evidência | Status |
|---|---|---|---|---|---|
| Livro/manuscrito | `.md`, `.txt`, `.pdf`\*, `.docx`\*, `.epub`\* (\*extras opcionais) | Sim | `InputDiscoveryAgent`, `BookIngestionAgent` | [ingestion.py](src/pedroarte_youtube_engine/agents/ingestion.py), [parsers/registry.py](src/pedroarte_youtube_engine/adapters/parsers/registry.py) | PROVEN (parser de texto testado; PDF/DOCX/EPUB IMPLEMENTED_NOT_PROVEN, exigem extras não instalados por padrão) |
| `project.yaml` | YAML tipado (Pydantic, `extra="forbid"`) | Não (usa defaults) | `ConfigurationLoader` → `ProjectConfiguration` | [configuration.py](src/pedroarte_youtube_engine/domain/configuration.py), [config_loader.py](src/pedroarte_youtube_engine/infrastructure/config_loader.py) | PROVEN como schema; **BLOQUEADO na prática** pelo bug de §11 |
| `formats.*` (booleans) | 6 famílias de formato | Não (todas `true` por padrão) | `FormatPlannerAgent` | [configuration.py:45-62](src/pedroarte_youtube_engine/domain/configuration.py) | PROVEN (validado por testes de domínio) |
| `main_video.duration_minutes` | float, default 10.0 | Não | `MainVideoSection` | [configuration.py:74-83](src/pedroarte_youtube_engine/domain/configuration.py) | PROVEN |
| `segmentation.target_segment_seconds` | float, default 10.0 | Não | todas as seções de duração devem ser múltiplas disso | [configuration.py:321-356](src/pedroarte_youtube_engine/domain/configuration.py) | PROVEN — validador de domínio recusa configs cuja duração não feche exatamente |
| `rights.user_confirms_adaptation_rights` | bool | Não (default `false`, gera risco bloqueante em `LegalAndRightsAgent`) | `LegalAndRightsAgent` | [packaging.py:444-461](src/pedroarte_youtube_engine/agents/packaging.py) | PROVEN |
| `providers.execute_generation` | bool, default `false` | Não | validado, mas **nunca lido por nenhum agente para mudar comportamento** | [configuration.py:249-268](src/pedroarte_youtube_engine/domain/configuration.py); grep confirma único uso é descritivo em `director.py:71` e `packaging.py:609` | DOCUMENTED_ONLY / decorativo |
| `audio.speech_rate_wpm`, idioma, on/off de narração/diálogo/música/ambiente/SFX | vários | Não | `AudioCompletenessService` | [configuration.py:234-241](src/pedroarte_youtube_engine/domain/configuration.py) | PROVEN |
| **Modo de execução / preset / perfil de qualidade / slideshow vs. cinematográfico** | — | — | — | grep exaustivo em `domain/`, `agents/`, `interfaces/` por `mode`, `preset`, `profile` (fora de `FormatProfile`), `slideshow`, `cinematic`, `profissional` | **NOT_FOUND** |

**Menor entrada válida para iniciar uma execução:** uma pasta com um único arquivo `.md` ou `.txt` (ver fixture `tmp_input` em [conftest.py](tests/conftest.py) — duas linhas de texto bastam para passar pelos parsers). `project.yaml` é totalmente opcional; todos os defaults produzem um vídeo principal de 10 minutos.

**Existe um contrato formal de briefing?** Sim, para o eixo de formato/duração/qualidade/direitos/idioma — `ProjectConfiguration` é um schema Pydantic rígido (`extra="forbid"`), bem tipado e validado. **Não existe** um campo para expressar "modo de execução desejado" porque esse conceito não existe no domínio.

---

## 4. Execution Modes

**Resultado da varredura obrigatória (regras 15–19):** não há nenhum mecanismo de seleção de modo/perfil/preset/estilo de produção no código. A busca por `mode`, `preset`, `profile` (excluindo `FormatProfile`/`profile_id`, que é o perfil técnico de *formato*, não de *estilo*), `render_mode`, `production_mode`, `slideshow`, `cinematic`, `profissional`, `simples` retorna **um único falso-positivo não relacionado**: `CanonSocialClass.PROFESSIONAL = "profissional"` em [domain/canon.py:144](src/pedroarte_youtube_engine/domain/canon.py), que é uma classe social de personagem do livro (ex.: "profissional liberal"), sem qualquer relação com produção de vídeo.

O único eixo de variação real é `ProductionVariant` (6 valores): `main_10_minutes`, `shorts`, `long_form`, `series`, `mini_novela`, `trailers`. Todos correm pelo **mesmo código de pipeline** (`Episode` com `number=1` para formatos avulsos — comentário explícito em [production.py:159-164](src/pedroarte_youtube_engine/domain/production.py)) e diferem apenas em duração-alvo, aspect ratio e contagem de segmentos — não em complexidade visual, tipo de asset, quantidade de movimento, ou pipeline de montagem.

| Modo | Existe no código? | Como é ativado | Altera o pipeline? | Classificação |
|---|---|---|---|---|
| "Profissional" (cinematográfico, com clipes de vídeo, câmera, transições) | Não | — | — | **NOT_FOUND** |
| "Simples/Slideshow" (imagens estáticas + narração + música de fundo) | Não | — | — | **NOT_FOUND** |
| Vídeo principal 10 min / Shorts / Longa / Série / Mini-novela / Trailers (`ProductionVariant`) | Sim | `formats.*: true/false` em `project.yaml` | Só duração, aspect ratio e contagem de segmentos — mesmo pipeline de agentes para todos | PROVEN como *família de formato*, mas isso **não é** o eixo "modo de produção" pedido neste discovery |

**Respostas às 17 perguntas da seção 5 do protocolo:** não aplicável — não há modo a avaliar. Nenhum dos 17 critérios (ativação, alteração de providers, fallback entre modos, determinismo, testes por modo etc.) tem alvo.

**A engine possui uma estratégia explícita de trade-off entre qualidade, custo, tempo e complexidade?** Não. O único trade-off modelado é o de **custo monetário de chamadas de API versus volume de segmentos** (`CostAndQuotaAgent`, §17), e mesmo esse é hipotético porque nenhuma chamada paga é de fato feita.

**É possível escolher o modo adequado a partir do briefing?** Pergunta sem objeto — não há modos para escolher.

---

## 5. What It Does

Responsabilidade real, comprovada por código: transformar um livro em um **pacote de pré-produção textual** com:
- cânone extraído (personagens, locais, props, timeline, regras do mundo, perguntas em aberto);
- bíblias (mundo, personagem, audiovisual — iluminação/paleta/lentes por padrão, voz, música);
- plano de produção por formato (episódios, sequências, cenas, contínuas em timecode);
- **segmentos de 10s** com plano de vídeo *e* plano de áudio obrigatórios (`PromptSegment` — nenhum segmento pode ser mudo, por invariante de domínio, [segment.py:1-10](src/pedroarte_youtube_engine/domain/segment.py));
- prompts compilados por modalidade (vídeo, imagem-quadro, voz) e por "provedor" (só o alvo genérico e um alvo Gemini existem: [prompt_compilers/](src/pedroarte_youtube_engine/adapters/prompt_compilers/));
- gates de qualidade estrutural/narrativa com repair loop (até 3 iterações);
- metadados de publicação (título, descrição, capítulos, hashtags, prompts de thumbnail) e legendas SRT/VTT — **gerados em memória, não persistidos** (§8);
- relatório de riscos de direitos autorais/marcas/semelhança com pessoa real (heurística de regex);
- relatório de custo estimado (contagem de chamadas, não valor monetário, porque não há tabela de preço configurada).

## 6. How It Works

Máquina de estados explícita ([domain/state.py](src/pedroarte_youtube_engine/domain/state.py)) com **15 estados** no caminho feliz (o README afirma "18 fases" em prosa mas lista 14 itens numerados — nenhum dos três números bate exatamente com o código; discrepância documental confirmada). `PipelineOrchestrator.execute()` chama, em sequência: descoberta → ingestão → extração de cânone → bíblias → planejamento de formatos/adaptação/episódios → decomposição em cenas (dentro de `SegmentBuilderAgent`) → escrita de segmentos → compilação de prompts → validação com repair loop → exportação.

**Achado relevante:** o estado `DESIGNING_AUDIO` existe em `HAPPY_PATH` (entre `WRITING_SEGMENTS` e `COMPILING_PROMPTS`), mas **`PipelineOrchestrator.execute()` nunca transiciona para ele** — não existe `_phase_design_audio()`. Os dois agentes que existem para essa fase, `VoiceCastingAgent` e `MusicSupervisorAgent` ([agents/audiovisual.py:359](src/pedroarte_youtube_engine/agents/audiovisual.py) e `:492`), **não são chamados em nenhum lugar de `orchestrator.py`** (confirmado por leitura completa do arquivo — a lista de agentes instanciados nas 10 fases não os inclui). Eles têm contrato completo, tipagem, critérios de conclusão — mas estão órfãos: implementados e desconectados do pipeline real. Classificação: **PARTIAL** (implementado, não integrado).

| Etapa | Provider real usado | Determinístico/IA | Evidência |
|---|---|---|---|
| Extração de cânone/personagens | `HeuristicNarrativeAnalyzer`: regex + léxicos PT-BR (atribuição de fala, posição de sujeito, capitalização, frequência) | 100% determinístico, **não é IA generativa** | [adapters/analysis/heuristic.py:1-20](src/pedroarte_youtube_engine/adapters/analysis/heuristic.py) |
| "LLM" do pipeline | `DeterministicLLMProvider` — devolve o próprio texto da requisição, sem chamar nenhum modelo | Determinístico por design; docstring afirma "o motor não depende de um LLM" | [adapters/providers/deterministic_llm.py:1-32](src/pedroarte_youtube_engine/adapters/providers/deterministic_llm.py) |
| Geração de vídeo/imagem/voz/música real | **Nenhum adaptador real existe.** `FakeVideoProvider`/`FakeImageProvider`/`FakeVoiceProvider`/`FakeMusicProvider` retornam um nome de arquivo hash (`.mp4`/`.png`/`.wav`) sem gerar bytes, e não são referenciados fora de `fakes.py` (nem em testes) | STUB/MOCK, não conectado | [adapters/providers/fakes.py](src/pedroarte_youtube_engine/adapters/providers/fakes.py); `grep -rl FakeVideoProvider src/ tests/` → só o próprio arquivo |
| Montagem/render final | Não existe. Sem FFmpeg, sem MoviePy, sem qualquer lib de composição de vídeo nas dependências (`pyproject.toml`) | — | NOT_FOUND |
| Legendas SRT/VTT | `render_srt`/`render_vtt` — geração real de texto a partir dos segmentos, **testada isoladamente**, mas nunca chamada pelo `_export_artifacts` do orquestrador | Determinístico, PROVEN na função, não exportado no fluxo real | [adapters/renderers/subtitles.py](src/pedroarte_youtube_engine/adapters/renderers/subtitles.py); usada em [agents/packaging.py:380-381](src/pedroarte_youtube_engine/agents/packaging.py); ausente em [agents/orchestrator.py:434-505](src/pedroarte_youtube_engine/agents/orchestrator.py) |
| Continuidade visual/personagem | `VisualContinuityService`, `CharacterContinuityService`, `VoiceContinuityService` — comparam campos estruturados entre segmentos (não usam seeds/embeddings de imagem) | Determinístico, baseado em regras de domínio | [domain/services/continuity.py](src/pedroarte_youtube_engine/domain/services/continuity.py) |

## 7. Mode-Specific Pipelines

Não aplicável — não existem pipelines por modo (§4). Existe um único pipeline, compartilhado por todas as 6 famílias de formato.

## 8. What Comes Out

Arquivos **realmente escritos em disco** por `_export_artifacts()` ([orchestrator.py:434-505](src/pedroarte_youtube_engine/agents/orchestrator.py)), quando a exportação é alcançada:

| Artefato | Formato | Escrito? | Evidência |
|---|---|---|---|
| `canon_bible.md` | Markdown | Sim | `orchestrator.py:454` |
| `audiovisual_bible.md` | Markdown | Sim | `orchestrator.py:456-458` |
| `<variant>/<episodio>/<segmento>.md` | Markdown (um por segmento de 10s, com plano de vídeo + áudio) | Sim | `orchestrator.py:460-472` |
| `<variant>/<episodio>/shotlist.csv` | CSV | Sim | `orchestrator.py:473-477` |
| `<variant>/<episodio>/transcript.md` | Markdown | Sim | `orchestrator.py:478-482` |
| `manifest.json` | JSON | Sim | `orchestrator.py:484-504` |
| **Vídeo (`.mp4`)** | — | **Não.** Nenhum arquivo de vídeo é gerado ou escrito. | NOT_FOUND |
| **Áudio (`.wav`/`.mp3`)** | — | **Não.** | NOT_FOUND |
| **Imagens/quadros-chave** | — | **Não.** Só o *texto do prompt* de imagem existe. | NOT_FOUND |
| **Legendas `.srt`/`.vtt`** | — | Conteúdo é gerado em memória (`AccessibilityPackage.srt_content`/`.vtt_content`) mas **não é escrito em arquivo** pelo `_export_artifacts` atual. | PARTIAL (gerado, não exportado) |
| **Thumbnail** | — | Só o *prompt de texto* da thumbnail (`ThumbnailPrompt`) é gerado; nenhuma imagem é escrita. | NOT_FOUND (imagem) / PROVEN (prompt de texto) |
| **Metadados YouTube** (título/descrição/capítulos/hashtags) | — | `PublicationMetadata` é calculado em memória, mas **também não é escrito em arquivo** pelo `_export_artifacts` atual — não há `youtube_metadata.json` nem equivalente no código de exportação. | PARTIAL (calculado, não exportado) |
| **Pacote "pronto para YouTube" (`youtube_bundle/`)** | — | Não existe estrutura equivalente. | NOT_FOUND |
| Prompts de provedor compilados (vídeo/imagem/voz) | texto (em `provider_prompts`, no `scratch` do contexto) | **Não exportados como arquivo individual** pela rotina de exportação atual — só entram no manifesto como contagem. | PARTIAL |
| Checkpoints | JSON | Só se `CheckpointStore` for alcançável — ver bug de assinatura em §11 | PARTIAL/quebrado |

O próprio código documenta a fronteira: `PublicationMetadata` traz o comentário "*O motor prepara os metadados; a publicação em si permanece fora do escopo desta versão (ver roadmap)*" ([domain/artifacts.py:76-81](src/pedroarte_youtube_engine/domain/artifacts.py)).

## 9. Proven Capability Matrix

| Capacidade | Status | Evidência |
|---|---|---|
| Ler livro `.md`/`.txt` | PROVEN | testes de `BookIngestionAgent`/parsers passam |
| Ler `.pdf`/`.docx`/`.epub` | IMPLEMENTED_NOT_PROVEN | exige extra `parsers`, não testado neste discovery |
| Extrair cânone (personagens/locais/timeline) via heurística PT-BR | PROVEN | `tests/` cobre `heuristic.py`; execução real seria bloqueada por §11 antes de chegar lá |
| Gerar segmento de 10s com vídeo+áudio obrigatórios | PROVEN a nível de unidade | invariante de domínio testada; nunca produzido ponta a ponta (§11) |
| Compilar prompt de texto por segmento/modalidade | PROVEN a nível de unidade | `adapters/prompt_compilers/generic.py` |
| Gerar vídeo/imagem/áudio real | **NOT_FOUND** | nenhum adaptador real existe |
| Executar geração paga (`execute_generation: true`) | **STUB/MOCK** (flag decorativa) | nenhum agente lê a flag para agir |
| Rodar pipeline completo via CLI/API/MCP | **NOT PROVEN — PROVEN QUEBRADO** | execução real: `TypeError` em `bootstrap()` (§11) |
| Gerar legendas SRT/VTT em texto | PROVEN a nível de função | não chega a ser exportado no fluxo real |
| Escrever pacote de metadados do YouTube em arquivo | **NOT_FOUND** | calculado, nunca exportado |
| Checkpoint/resume | PARTIAL — desenhado corretamente, mas com assinatura incompatível com o orquestrador (§11) | leitura de código |
| QA estrutural com repair loop | PROVEN a nível de unidade | `domain/validation.py`, `agents/validation.py`, testes passam |
| Upload automático no YouTube | **NOT_FOUND, fora de escopo por design** | comentário explícito no código |

## 10. Mode Capability Matrix

Não aplicável — não há modos (§4).

## 11. Briefing → 10-Minute Video Assessment

**Esta é a descoberta central do discovery, obtida por execução real, não por leitura.**

Executei a suíte de testes (`pytest tests/ -v` → **126 passed**, todos unitários/contrato — nenhum integra `bootstrap()` ou `orchestrator.execute()`, confirmado por `grep -rln "bootstrap" tests/` e `grep -rln "PipelineOrchestrator" tests/`, ambos vazios).

Em seguida tentei rodar o pipeline real contra o livro de exemplo (`examples/sample_living_book/input/book.md`, "O Relojoeiro de Vidro"):

1. **`living-video` (script instalado) está quebrado por erro de empacotamento.** `pyproject.toml` declara `living-video = "pedroarte_youtube_engine.interfaces.cli.main:run"`, mas `interfaces/cli.py` é um módulo único (não um pacote `cli/`) e não expõe `main` como submódulo. Executar o binário instalado produz:
   ```
   ModuleNotFoundError: No module named 'pedroarte_youtube_engine.interfaces.cli.main';
   'pedroarte_youtube_engine.interfaces.cli' is not a package
   ```
   **PROVEN por execução** (`living-video --help` no venv do projeto).

2. Contornando isso e invocando `cli.app` diretamente (via `Typer.testing.CliRunner`, o mesmo Typer que a própria suíte usaria), com o `examples/project.yaml` documentado no README: falha em **outro** ponto — `is_sensitive_key("author")` retorna `True` porque a palavra "author" contém a substring `"auth"`, que está na lista de marcadores de segredo ([observability/redaction.py:16-30](src/pedroarte_youtube_engine/observability/redaction.py)). O carregador de configuração rejeita `project.author: "Autor Exemplo"` como se fosse uma credencial:
   ```
   Erro na inicialização: O campo 'project.author' parece conter um segredo.
   ```
   **PROVEN por execução.** O `project.yaml` de exemplo que o próprio README manda copiar não consegue ser carregado, sem que o operador entenda por quê (a mensagem não indica que é um falso positivo de substring).

3. Contornando isso com uma config sem o campo `author`: falha em **um terceiro** ponto, agora dentro de `bootstrap()` — a função de "cola" chamada igualmente pelo CLI, pela API (`interfaces/api.py:73`) e pelo MCP server (`interfaces/mcp_server.py:98`):
   ```
   Erro na inicialização: RunLogger.__init__() got an unexpected keyword argument 'verbose'
   ```
   `_bootstrap.py:62-66` chama `RunLogger(project_id=..., run_id=..., verbose=verbose)`, mas `RunLogger.__init__` ([observability/logging.py:85-99](src/pedroarte_youtube_engine/observability/logging.py)) só aceita `run_id`, `project_id`, `correlation_id`, `component` — não `verbose`. **PROVEN por execução**, com traceback completo capturado.

4. Por leitura de código (não testado por execução, pois a falha em (3) impede chegar lá), o mesmo `bootstrap()` também chama:
   - `FilesystemArtifactAdapter(root=effective_output)` — mas o construtor real exige `run_directory` **e** `policy`, não `root` ([infrastructure/artifacts.py:26-34](src/pedroarte_youtube_engine/infrastructure/artifacts.py) vs. [_bootstrap.py:76](src/pedroarte_youtube_engine/interfaces/_bootstrap.py)).
   - `CheckpointStore(root=effective_output / ".checkpoints")` — mas o construtor real exige `run_directory` **e** `policy` ([infrastructure/checkpoints.py:49](src/pedroarte_youtube_engine/infrastructure/checkpoints.py) vs. `_bootstrap.py:77`).
   - Adiante, `orchestrator._checkpoint()` chama `self._checkpoints.save(run_id=..., label=..., data=...)`, mas `CheckpointStore.save()` espera um único objeto `Checkpoint` ([infrastructure/checkpoints.py:57-64](src/pedroarte_youtube_engine/infrastructure/checkpoints.py) vs. [agents/orchestrator.py:426-430](src/pedroarte_youtube_engine/agents/orchestrator.py)).

   Cada uma dessas é, por inspeção direta de assinatura, uma quebra garantida do tipo `TypeError` — não uma suposição.

**Conclusão da seção:** as três interfaces do motor (CLI, API REST, MCP server) compartilham o mesmo ponto único de falha. Não há, hoje, **nenhum caminho documentado ou programático** para completar uma execução do pipeline — nem para gerar o pacote de prompts (que já seria "só" texto), muito menos um vídeo de 10 minutos.

| Caminho | Briefing aceito | Produz pacote de prompts | Produz vídeo de ~10 min | Classificação | Evidência |
|---|---|---|---|---|---|
| CLI `living-video` (instalado) | — | — | — | **E — NOT CAPABLE hoje** | `ModuleNotFoundError` real |
| CLI via `python -m` / `cli.app` | Sim (parcialmente, após 2 correções manuais) | Não chega a produzir | Não | **E — NOT CAPABLE hoje** | `TypeError` real em `bootstrap()` |
| API REST (`POST /run`) | — | — | — | **E — NOT CAPABLE hoje** (mesma `bootstrap()`) | leitura de código |
| MCP `living_video_run` | — | — | — | **E — NOT CAPABLE hoje** (mesma `bootstrap()`) | leitura de código |
| Chamando `PipelineOrchestrator` diretamente, contornando `bootstrap()` com objetos construídos à mão | Hipoteticamente sim | Hipoteticamente sim (texto) | **Nunca** — não existe gerador de vídeo | **D — ARCHITECTURAL** para o pacote de prompts; vídeo real é E | inspeção de código |

**Qual é o modo mínimo capaz de entregar valor publicável?** Nenhum, sem consertar a fiação de `bootstrap()`/`FilesystemArtifactAdapter`/`CheckpointStore` primeiro (estimado em poucas horas — são 3-4 chamadas com parâmetros errados, não uma reformulação de arquitetura). Depois de consertado, o "valor publicável" máximo alcançável é o **pacote de prompts de pré-produção em texto** — nunca um vídeo.

## 12. YouTube-Ready Assessment

Usando a lista mínima do protocolo ("pronto para upload" = vídeo renderizado + duração + resolução/codec + áudio + narração + sincronização + montagem + transições + tratamento de áudio + legendas + thumbnail/indicação de ausência + título + descrição + metadados + riscos de direitos + artefatos organizados):

| Item | Status |
|---|---|
| Vídeo renderizado | NOT_FOUND |
| Duração aproximada ao briefing | PROVEN só na *matemática do plano* (segmentação exata em múltiplos de 10s); nunca materializada em mídia |
| Resolução/codec | Especificado no domínio (`Resolution`, `FrameRate`); nunca aplicado a um arquivo real |
| Áudio final/narração | NOT_FOUND (só texto de síntese de voz) |
| Sincronização audiovisual | Modelada em timecodes no domínio; nunca verificada contra mídia real |
| Montagem/transições | Descritas em texto (`TransitionType` no prompt); nenhuma montagem executada |
| Tratamento de áudio (loudness/ducking) | NOT_FOUND — não há conceito de mixagem de áudio real no código |
| Legendas | Geradas em memória, não exportadas (§8) |
| Thumbnail ou indicação explícita de ausência | Só o *prompt* de thumbnail; nenhuma imagem, e o manifesto não sinaliza explicitamente "sem thumbnail" para o operador |
| Título/descrição/metadados | Calculados, mas não exportados em arquivo (§8) |
| Riscos de copyright/licenciamento | PROVEN — `LegalAndRightsAgent` roda heurística de regex sobre marcas/celebridades e bloqueia se direitos não confirmados |
| Artefatos organizados para publicação | PARTIAL — o que é escrito (Markdown/CSV/JSON) é bem organizado; falta o essencial (mídia) |

**Separação exigida pelo protocolo — produção do pacote vs. upload vs. gestão do canal:** o código só toca o primeiro item, e mesmo esse fica incompleto no formato hoje exportado (texto de pré-produção, não um pacote de mídia). Upload e gestão de canal: **NOT_FOUND, fora de escopo por decisão explícita do autor** (comentário em `domain/artifacts.py`, §8).

## 13. Comparison With Publishing Engine

Comparação apenas de **capacidade de resolução E2E**, sem acesso ao código do motor editorial (fora do escopo deste discovery) — baseada só no que o README desta engine e o discovery atual permitem inferir.

| Capacidade | Motor Editorial (referência conceitual) | YouTube Engine (este repo) | Gap |
|---|---|---|---|
| Receber intenção | — | PROVEN (schema de configuração rígido) | — |
| Formalizar especificação | — | PROVEN | — |
| Escolher modo de produção | — | **NOT_FOUND** — não existe eixo de modo | Total |
| Planejar produto | — | PROVEN (plano de episódios/cenas/segmentos) | — |
| Produzir conteúdo final | (fora de escopo verificar aqui) | **NOT_FOUND** para mídia; PROVEN só para texto de pré-produção | Grande, se o padrão de comparação for "artefato publicável" |
| QA | — | PROVEN (estrutural/narrativo); ausente para mídia (não há mídia) | Parcial |
| Gerar artefato final | — | **NOT_FOUND** (nenhum vídeo) | Total |
| Validar artefato final | — | **NOT_FOUND** | Total |
| Empacotar publicação | — | PARTIAL (Markdown/CSV/JSON, não um bundle de YouTube) | Grande |
| Retomar execução | — | PARTIAL — desenhado, mas quebrado por incompatibilidade de assinatura (§11) | Grande |
| Telemetria | — | PROVEN (logging estruturado, métricas, eventos de domínio) | — |
| Controle de custo | — | PARTIAL (conta chamadas; não estima dinheiro sem tabela de preço) | Parcial |

**A Video/YouTube Engine consegue desempenhar para vídeos o mesmo papel que o motor editorial desempenha para livros?** Não, hoje. Ela cobre bem a etapa de *especificação e planejamento* (equivalente ao que um motor editorial faria para outline/estrutura), mas para exatamente antes da etapa de *produção do artefato final* — que é justamente onde um motor editorial de livros entregaria o `.epub`/`.pdf` publicável. Aqui, o equivalente ao "livro publicável" (o vídeo `.mp4`) não existe.

## 14. Engine Boundary

### O que é responsabilidade da engine (conforme o código a implementa hoje)

| Item | Classificação |
|---|---|
| Ingestão e parsing do livro | CORE ENGINE |
| Extração de cânone e bíblias | CORE ENGINE |
| Planejamento de formato/episódios/cenas/segmentos | CORE ENGINE |
| Compilação de prompts multimodais (texto) | CORE ENGINE |
| QA estrutural/narrativo e repair loop | CORE ENGINE |
| Geração de metadados de YouTube (texto) | CORE ENGINE |
| Sinalização de risco de direitos/marcas | CORE ENGINE |
| Estimativa de volume de chamadas/custo | ADJACENT |
| Geração real de vídeo/imagem/áudio | **Pretendido como CORE, mas NOT_FOUND na implementação** |
| Seleção de modo de produção | Pretendido pelo discovery, **inexistente no código** |
| Empacotamento final para upload | Pretendido, PARTIAL/NOT_FOUND |

### O que não é responsabilidade da engine

| Item | Classificação | Evidência |
|---|---|---|
| Upload/publicação no YouTube | OUT OF SCOPE, por decisão explícita | comentário em `domain/artifacts.py` |
| Gerenciamento de conta/credenciais de API de terceiros | OUT OF SCOPE | nenhuma credencial é lida de config, só de env vars (por design de segurança) |
| Escolha de nicho/estratégia de canal/SEO/calendário editorial | OUT OF SCOPE | nenhuma menção no código |
| Analytics, comentários, comunidade, monetização | OUT OF SCOPE | nenhuma menção no código |
| Renderização/montagem de vídeo real (FFmpeg etc.) | Deveria ser DOWNSTREAM de um provedor real, mas hoje não há sequer o provedor — o "downstream" não tem "upstream" que o alimente | nenhuma dependência de mídia no `pyproject.toml` |

## 15. Technical Limits

| Limite | Onde vive | Evidência |
|---|---|---|
| Duração do segmento configurável (5–120s, default 10s) | domínio | `SegmentationSection.target_segment_seconds` |
| Duração total deve ser múltiplo exato da duração de segmento | domínio, validado | `configuration.py:321-356` |
| Shorts: 1–50 unidades, 5–180s cada | domínio | `ShortsSection` |
| Longa: 0–600 min | domínio | `LongFormSection` |
| `max_repair_iterations`: 0–10 (default 3) | domínio | `QualitySection` |
| `minimum_approval_score`: 0.0–1.0 (default 0.90) | domínio | `QualitySection` |
| Capacidades de provedor genérico: vídeo até 300s, imagem até 4096px, áudio até 600s | `config/provider_capabilities/generic.yaml` | arquivo lido, mas nunca usado para de fato limitar uma chamada real (não há chamada) |
| `max_retries`, `retry_backoff_seconds`, `circuit_breaker_threshold` | domínio + `infrastructure/resilience.py` | implementado e testável isoladamente; **irrelevante na prática** porque não há chamada de rede a proteger |
| Path traversal bloqueado, symlinks rejeitados, raízes permitidas (`allowed_roots`) | `shared/paths.py`, `McpSection` | PROVEN, testado |

**Limite da engine vs. limite do provedor:** como não há provedor real conectado, todos os limites de mídia (`generic.yaml`) são **hipotéticos** — nunca aplicados a uma chamada de fato.

## 16. Quality Limits

Como nenhuma mídia é produzida, dimensões de qualidade de **mídia** (naturalidade da narração, artefatos visuais de IA, ducking, clipping, legibilidade de legenda na tela) são **NOT_SUPPORTED** por ausência de objeto a avaliar — não é um bug de qualidade, é a ausência da própria mídia.

| Dimensão | Status | Evidência |
|---|---|---|
| Coerência narrativa do plano (estrutura, cânone, continuidade) | PROVEN a nível de dado estruturado | `domain/services/{canon_consistency,continuity,narrative_coverage}.py`, testados |
| Ritmo/retenção do plano | PROVEN a nível heurístico simples (score baseado em tensão declarada por segmento) | `agents/packaging.py:55-143` (`RetentionAndHookAgent`) |
| Naturalidade da narração real | NOT_SUPPORTED (não existe áudio) | — |
| Sincronização audiovisual real | NOT_SUPPORTED (não existe mídia) | — |
| Continuidade visual real (entre frames/imagens geradas) | NOT_SUPPORTED (não existem imagens) | — |
| Qualidade do texto de prompt (completude de campos, ausência de placeholder) | PROVEN | `domain/services/prompt_completeness.py`, testado |
| Legibilidade de legenda | PARTIAL — a lógica de `render_srt`/`render_vtt` é testada isoladamente; nunca chega a arquivo no fluxo real | §8 |

## 17. Operational Limits

- **Resume:** desenhado (`CheckpointStore`, fingerprint de entrada/configuração) mas **quebrado** por incompatibilidade de assinatura com o orquestrador (§11) — nunca provado em execução real.
- **Se a cena 47 falhar depois de 35 minutos:** hipoteticamente, o checkpoint permitiria retomar sem refazer o já concluído — mas isso nunca foi observado funcionando, porque a execução não chega perto disso hoje.
- **Idempotência de chamada de provedor:** `idempotency_key()` existe e é testável (`infrastructure/resilience.py:127-135`), mas não há chamada de provedor real para proteger.
- **Paralelismo:** não identificado — o pipeline é sequencial, agente por agente, dentro de um único processo.
- **Retry/circuit breaker:** implementados e testáveis isoladamente; nunca exercitados em um caminho real porque não há chamada de rede.

## 18. Mode Trade-offs

Não aplicável — não há modos (§4).

## 19. What It Cannot Do

| Capacidade desejada | Evidência da ausência | Consequência | Modo afetado | Necessária para Briefing→YouTube Ready? | Complexidade para adicionar |
|---|---|---|---|---|---|
| Rodar o pipeline de ponta a ponta via CLI/API/MCP | `TypeError` real em `bootstrap()`; 3 incompatibilidades adicionais por leitura de código | Nenhuma execução completa é possível hoje, em nenhuma interface | TODOS | Sim, é pré-requisito de tudo o mais | **LOW** — são assinaturas erradas em ~4 pontos, não uma questão de design |
| Selecionar modo de produção a partir do briefing | Conceito inexistente no domínio | Não há como pedir "vídeo simples" vs. "vídeo elaborado" | TODOS | Sim (é o objeto central deste discovery) | **HIGH** — exige novo eixo de domínio, novos agentes/branches de pipeline |
| Executar modo profissional (câmera, transições, montagem real) | Nenhuma implementação encontrada | — | — | Sim | **VERY HIGH** (depende de gerar vídeo real primeiro) |
| Executar modo simples/slideshow (imagens + narração + música baixa) | Nenhuma implementação encontrada | — | — | Sim | **HIGH** — mas notavelmente menor que o profissional, pois usa TTS + imagens estáticas + composição simples, sem geração de vídeo/câmera |
| Sincronizar slides com narração | Não há noção de "slide" no domínio; só timecodes de segmento | — | — | Sim, se o modo slideshow for adotado | **MEDIUM**, dado que a segmentação por timecode já existe |
| Controlar música de fundo / aplicar ducking | Nenhum mecanismo de mixagem de áudio real; só `music_enabled: bool` | — | — | Sim | **HIGH** (exige pipeline de áudio real, hoje inexistente) |
| Gerar vídeo/imagem/áudio real (qualquer modo) | Nenhum adaptador real; só `fakes.py`, não conectado | Todo o "produto" hoje é texto | TODOS | Sim | **HIGH** (integração com provedor externo pago) a **VERY HIGH** (se for geração de vídeo com continuidade visual) |
| Exportar legendas/metadados/thumbnail-prompt já calculados para arquivo | Calculados em memória, não escritos por `_export_artifacts` | Pacote de saída incompleto mesmo dentro do que a engine já sabe fazer | TODOS | Sim | **LOW** — são poucas linhas a mais na função de exportação já existente |
| Produzir pacote pronto para upload em qualquer modo | Depende de tudo acima | — | TODOS | Sim | **VERY HIGH** no total; mas o caminho mínimo textual (§26) é **LOW** |

## 20. Código que Talvez Não Devesse Existir

| Item | Classificação | Nota |
|---|---|---|
| `adapters/providers/fakes.py` (4 provedores de mídia falsos) | **KEEP**, mas reclassificar a intenção — hoje parece infraestrutura de teste "pronta para produção" mas está completamente desconectada (nem os testes a usam); é morta em termos de consumidores reais até que exista um adaptador real de verdade | zero consumidores fora do próprio arquivo |
| `infrastructure/resilience.py` (retry/circuit breaker) | **KEEP** (bem escrito, testável), mas sem nenhum lugar real que o chame ainda — é infraestrutura à espera de um provedor real | nenhuma chamada de rede existe para proteger hoje |
| `AudioSection`/`ProvidersSection.execute_generation` e todo o aparato de `max_budget_usd`/`allowed_models` | **SIMPLIFY ou DEFER** — valida uma pré-condição rica para um comportamento que nunca é de fato acionado | flag lida só descritivamente |
| `VoiceCastingAgent`/`MusicSupervisorAgent` | **REMOVE_CANDIDATE ou reconectar** — implementados com contrato completo, mas órfãos do orquestrador (fase `DESIGNING_AUDIO` nunca é chamada) | confirmado por leitura de `orchestrator.py` |
| 6 famílias de formato simultâneas desde a v0.1.0 (Shorts, longa, série, mini-novela, trailers, além do vídeo principal) | **DEFER** — antes de multiplicar formatos, vale prender o pipeline básico de ponta a ponta para um só formato | nenhum dos 6 formatos foi provado E2E ainda |
| `schemas/` referenciado em `pyproject.toml` e no `CHANGELOG.md` ("JSON Schemas publicados... validados no CI") | **Inconsistência documental** — diretório não existe no repositório | `find . -iname schemas` vazio |

Não removi nada — apenas classifiquei.

## 21. O Que Vale Reutilizar

| Componente | Valor | Evidência | Reuso recomendado |
|---|---|---|---|
| Modelo de domínio do segmento (`PromptSegment`, vídeo+áudio obrigatórios) | Alto — invariante bem desenhada, testável, força completude estrutural | `domain/segment.py`, testes de contrato | Manter como espinha dorsal, mesmo que o pipeline de mídia mude |
| Máquina de estados explícita (`domain/state.py`) | Alto — transições auditáveis, caminho feliz + repair loop bem modelado | testado (`test_state_machine.py`) | Manter; só corrigir a lacuna do `DESIGNING_AUDIO` |
| `HeuristicNarrativeAnalyzer` | Médio-alto — extração de cânone PT-BR sem custo/rede é um diferencial real | testado | Manter como caminho padrão offline; permitir LLM real como upgrade opcional (a porta já existe) |
| Serviços de QA de domínio (continuidade, cânone, completude, timeline) | Alto — validação estrutural rigorosa e bem coberta por teste | `domain/services/*` | Manter integralmente |
| `CheckpointStore`/fingerprinting | Médio — bom design, só precisa da fiação corrigida | `infrastructure/checkpoints.py` | Reparar e reusar, não redesenhar |
| Compiladores de prompt genérico/Gemini | Médio — bom ponto de partida para adaptar a um provedor real | `adapters/prompt_compilers/` | Reusar como camada de "texto"; acoplar um cliente HTTP real por trás |
| `render_srt`/`render_vtt`/`render_shotlist_csv` | Alto — funções puras, testadas, só precisam ser chamadas na exportação | `adapters/renderers/` | Conectar ao `_export_artifacts` (mudança pequena, alto retorno) |

## 22. Gap Analysis — Briefing → YouTube Ready

```
BRIEFING            [GREEN]  aceito, schema rígido
MODE SELECTION       [RED]   inexistente
SPECIFICATION       [GREEN]  ProjectConfiguration validado
SCRIPT               [ORANGE] extraído/planejado, nunca provado E2E (bootstrap quebrado)
SCENE/SLIDE PLAN     [ORANGE] cenas sim; "slide" não existe como conceito
ASSET PRODUCTION      [RED]   nenhum adaptador real de vídeo/imagem/voz/música
VOICE/AUDIO           [RED]   só texto de síntese; nenhum áudio real
MUSIC/MIXING          [RED]   só flag on/off; nenhuma mixagem real
ASSEMBLY               [RED]   nenhuma montagem de vídeo
CAPTIONS             [ORANGE] gerado em memória, não exportado
QA                  [GREEN]  estrutural/narrativo, robusto e testado
RENDER                 [RED]   inexistente
YOUTUBE PACKAGE       [ORANGE] metadados calculados, não empacotados em arquivo
```

Não há pipeline "profissional" nem "simples/slideshow" a marcar separadamente — existe um único pipeline, e o diagrama acima já o descreve por completo.

## 23. Improvements

### P0 — necessárias para qualquer E2E (comum a tudo, nenhum modo específico existe)
1. Corrigir `RunLogger.__init__` para aceitar (ou `_bootstrap.py` para não passar) `verbose`.
2. Corrigir `_bootstrap.py` para construir `FilesystemArtifactAdapter` com `run_directory=`/`policy=` em vez de `root=`.
3. Corrigir `_bootstrap.py` para construir `CheckpointStore` com `run_directory=`/`policy=` em vez de `root=`.
4. Corrigir `orchestrator._checkpoint()` para montar um objeto `Checkpoint` antes de chamar `CheckpointStore.save()`.
5. Corrigir o entry point `[project.scripts]` em `pyproject.toml` (`interfaces.cli.main:run` → `interfaces.cli:main`) para que o binário `living-video` instalado funcione.
6. Corrigir o falso positivo de `is_sensitive_key("author")` (substring `"auth"`) em `observability/redaction.py` — no mínimo, o `project.yaml` de exemplo do próprio README precisa carregar sem erro.
7. Adicionar **um** teste de integração que chame `bootstrap()` + `orchestrator.execute()` sobre a fixture de livro existente, para que essa classe inteira de bug não volte a passar despercebida (hoje `grep -rln bootstrap tests/` é vazio).
8. Escrever os artefatos já calculados e hoje descartados: SRT/VTT (`AccessibilityPackage`), metadados do YouTube (`PublicationMetadata`), prompts de provedor individuais — na rotina `_export_artifacts`.

### P0 — necessário para seleção de modo (não existe hoje)
9. Decidir e modelar o eixo de "modo de produção" (se o produto realmente precisar dele) como um campo de primeira classe em `ProjectConfiguration`, com pelo menos um pipeline alternativo real por trás — hoje não há nem o campo nem o pipeline.

### P1 — qualidade/confiabilidade
- Reconectar `VoiceCastingAgent`/`MusicSupervisorAgent` à fase `DESIGNING_AUDIO` (ou removê-los, se a decisão for adiar áudio real).
- Fazer `execute_generation` de fato acionar (ou bloquear explicitamente, com mensagem clara) um caminho de geração real, em vez de ser lido e ignorado.
- QA específico para mídia real, quando ela existir (hoje não há nada a validar além de texto).

### P2 — economia/escala
- Estimativa de custo monetário real (hoje `CostReport.estimated_cost` é sempre `0.0` sem tabela configurada — `cost_table_configured: bool = False` por padrão).
- Cache/reaproveitamento de artefatos entre execuções sobre o mesmo livro.

### P3 — futuro
- Modos adicionais além de "simples" e "profissional".
- Geração de múltiplas versões do mesmo vídeo.
- Otimização por retenção real (hoje o score de retenção é uma heurística sobre o *plano*, não sobre dados de audiência).

## 24. Minimum Real Experiment

Dado que não há modos, o experimento mínimo tem uma única via — o próprio pacote de pré-produção em texto, que é tudo que a engine consegue produzir hoje mesmo depois de corrigida.

- **INPUT:** `examples/sample_living_book/input/book.md` ("O Relojoeiro de Vidro", já no repo) + um `project.yaml` mínimo sem o campo `author` (para evitar o falso positivo de §11) com `formats: {main_10_minutes: true, shorts: false, long_form: false, series: false, mini_novela: false, trailers: false}`.
- **COMMAND / EXECUTION PATH:** depois de aplicar as correções P0 #1–4 acima (poucas linhas), `python -m pedroarte_youtube_engine.interfaces.cli run examples/sample_living_book/input --config <config_minima>.yaml`.
- **EXPECTED OUTPUT:** `canon_bible.md`, `audiovisual_bible.md`, segmentos Markdown do episódio único, `shotlist.csv`, `transcript.md`, `manifest.json` — nenhum vídeo.
- **PASS CRITERIA:** o comando termina em `PipelineState.COMPLETED`, `QualityAssessment.approved == True`, e os 6 artefatos acima existem em disco com conteúdo não vazio referente ao livro de exemplo.
- **FAIL CRITERIA:** qualquer exceção não tratada, ou `QualityVerdict.REJECTED` após esgotar as 3 iterações de reparo.
- **COST TO MEASURE:** zero — `execute_generation` permanece `false`; nenhuma chamada de rede.
- **HUMAN REVIEW REQUIRED:** sim — ler os `.md` de segmento gerados e julgar se o texto é utilizável como prompt real para colar num gerador externo.
- **MODE-SPECIFIC REVIEW:** não aplicável.

Só depois de provar isso (o "produto textual" de ponta a ponta) faz sentido investir em qualquer geração real de mídia ou em um eixo de "modo profissional vs. slideshow" — hoje seria construir modos para um pipeline que nem termina.

## 25. Experience First Classification

**E1 — Experience.** Não chega a E2 (Functional Local) porque E2 exige evidência significativa de entrega funcional do valor proposto, e a execução real prova que o pipeline não completa em nenhuma interface hoje. Há, sim, uma experiência de código rica, bem tipada e parcialmente testada por unidade (o que a diferencia de E0 — Concept), mas nenhuma demonstração funcional de ponta a ponta foi possível, mesmo tentando ativamente.

## 26. Final Verdict

O motor é, hoje, um **planejador/compilador de pré-produção textual para adaptação de livros em roteiro audiovisual segmentado**, com engenharia de domínio séria (máquina de estados, invariantes estruturais, QA narrativo, RAG local) — mas **sem nenhuma capacidade de gerar mídia** e **sem uma execução de ponta a ponta funcional em nenhuma das três interfaces**, por bugs de integração concretos e comprovados por execução real, não por suspeita. O conceito de "modo profissional vs. modo simples/slideshow" pedido neste discovery **não existe no código nem na documentação** — o único eixo de variação é a família de formato por duração (vídeo principal, Shorts, longa, série, mini-novela, trailers), que usa o mesmo pipeline único para todos.

```text
CURRENT_ENGINE_STATUS: Compilador de pré-produção textual (prompts + bíblias + plano), sem geração de mídia e sem execução E2E funcional hoje.
EXPERIENCE_FIRST_LEVEL: E1 — Experience
EXECUTION_MODES_FOUND: Nenhum modo de produção/qualidade encontrado; só 6 famílias de formato por duração (main_10_minutes, shorts, long_form, series, mini_novela, trailers), todas no mesmo pipeline.
DEFAULT_EXECUTION_MODE: N/A (não existe eixo de modo); formato padrão = main_10_minutes (10 min, 16:9, 24fps)
MODE_SELECTION_SUPPORTED: NOT_FOUND
MODE_SELECTION_FROM_BRIEFING_SUPPORTED: NOT_FOUND
PROFESSIONAL_MODE_STATUS: NOT_FOUND
SIMPLE_SLIDESHOW_MODE_STATUS: NOT_FOUND
OTHER_MODES_STATUS: NOT_FOUND
BRIEFING_INPUT_SUPPORTED: PROVEN (schema Pydantic rígido; bloqueado na prática por bug de falso-positivo em detecção de segredo, ver P0 #6)
SCRIPT_GENERATION_SUPPORTED: PARTIAL (extração/estruturação heurística determinística, PT-BR; não é geração criativa via LLM; nunca provado E2E)
SCENE_PLANNING_SUPPORTED: PROVEN a nível de unidade; não provado E2E
SLIDE_PLANNING_SUPPORTED: NOT_FOUND (conceito de "slide" não existe)
VISUAL_GENERATION_SUPPORTED: NOT_FOUND (só prompt de texto de imagem)
VIDEO_GENERATION_SUPPORTED: NOT_FOUND
VOICE_GENERATION_SUPPORTED: NOT_FOUND (só prompt de texto de síntese de voz)
AUDIO_ASSEMBLY_SUPPORTED: NOT_FOUND
BACKGROUND_MUSIC_SUPPORTED: NOT_FOUND (só flag on/off, sem mixagem real)
AUDIO_DUCKING_SUPPORTED: NOT_FOUND
CAPTIONS_SUPPORTED: PARTIAL (gerado em memória e testado isoladamente; não exportado em arquivo pelo fluxo real)
FINAL_RENDER_SUPPORTED: NOT_FOUND
THUMBNAIL_SUPPORTED: PARTIAL (só prompt de texto; nenhuma imagem)
YOUTUBE_METADATA_SUPPORTED: PARTIAL (calculado em memória; não exportado em arquivo)
YOUTUBE_PACKAGE_SUPPORTED: NOT_FOUND
AUTOMATIC_UPLOAD_SUPPORTED: NOT_FOUND (fora de escopo por decisão explícita no código)
PROFESSIONAL_MODE_10_MIN_VIDEO_E2E_STATUS: E — NOT CAPABLE (modo inexistente)
SIMPLE_SLIDESHOW_MODE_10_MIN_VIDEO_E2E_STATUS: E — NOT CAPABLE (modo inexistente)
OTHER_MODES_10_MIN_VIDEO_E2E_STATUS: E — NOT CAPABLE
10_MIN_VIDEO_E2E_STATUS: E — NOT CAPABLE (comprovado por execução real: bootstrap() falha em todas as 3 interfaces)
YOUTUBE_READY_STATUS: NOT CAPABLE (nem o pacote de texto completa E2E hoje)
CAN_TAKE_BRIEFING_AND_RETURN_UPLOAD_READY_VIDEO_TODAY: NÃO
CAN_SELECT_APPROPRIATE_MODE_FROM_BRIEFING: NÃO (não há modos a selecionar)
HUMAN_INTERVENTION_REQUIRED: TOTAL — mesmo o pacote de texto exige correção manual de código antes de rodar; depois de corrigido, ainda exige colar prompts manualmente em geradores externos
PAID_EXTERNAL_DEPENDENCIES: NENHUMA CONECTADA (execute_generation existe na config mas não é lida por nenhum agente; nenhum cliente de API paga existe no código)
COST_PER_RUN_MEASURABLE: NÃO (CostReport.estimated_cost é sempre 0.0 sem tabela de preço configurada, que não existe)
COST_BY_MODE_MEASURABLE: N/A (sem modos)
BIGGEST_BLOCKER: bootstrap() quebrado por incompatibilidade de assinatura com RunLogger/FilesystemArtifactAdapter/CheckpointStore — nenhuma das 3 interfaces (CLI/API/MCP) completa uma execução
SECOND_BIGGEST_BLOCKER: ausência total de qualquer adaptador real de geração de vídeo/imagem/voz/música (só stubs desconectados em fakes.py)
THIRD_BIGGEST_BLOCKER: ausência do eixo "modo de produção" pedido neste discovery — não existe no domínio, precisaria ser desenhado do zero
BEST_CURRENT_PATH_TO_VALIDATE: consertar os 4 pontos de fiação em bootstrap()/orchestrator (P0 #1-4), depois rodar o pipeline sobre examples/sample_living_book e inspecionar manualmente o pacote de texto resultante
RECOMMENDED_FIRST_MODE_TO_TEST: N/A — não há modos; o primeiro teste real é o pipeline único, formato main_10_minutes, com todos os outros formatos desligados
ARCHITECTURE_COMPLEXITY: MEDIUM-HIGH (Clean Architecture bem separada, 27 agentes, máquina de estados explícita — mas a complexidade não é acompanhada de uma execução E2E provada)
OVERENGINEERING_RISK: MEDIUM (resiliência/retry/circuit-breaker/orçamento construídos para chamadas de provedor que não existem; 6 famílias de formato antes de provar 1; agentes de áudio implementados e nunca chamados)
REUSE_POTENTIAL: HIGH para o modelo de domínio, máquina de estados, serviços de QA e renderizadores de texto; BAIXO para qualquer coisa relacionada a mídia real, que simplesmente não existe ainda
P0_GAPS_COUNT: 9 (4 de fiação bootstrap/orchestrator + 1 de packaging do CLI + 1 de falso-positivo de segredo + 1 de teste de integração ausente + 1 de exportação de artefatos já calculados + 1 de modelagem do eixo de modo)
MINIMUM_REAL_TEST_POSSIBLE: SIM — pacote de pré-produção em texto sobre o livro de exemplo já incluso no repo, após corrigir P0 #1-4
NEW_IMPLEMENTATION_REQUIRED_BEFORE_TEST: SIM, mas mínima para o teste textual (correção de assinaturas, não redesenho); GRANDE para qualquer vídeo real (adaptador de provedor pago ainda não existe)
RECOMMENDED_NEXT_ACTION: Corrigir os 4 pontos de fiação bootstrap/orchestrator e adicionar um teste de integração que os cubra; só então decidir se vale desenhar o eixo de "modo profissional vs. simples/slideshow" pedido neste discovery.
GATE_VERDICT: MAJOR_REWORK_REQUIRED
```
