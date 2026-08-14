# PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE

Motor multiagente que transforma livros em pacotes de produção audiovisual completos para YouTube. Gera prompts estruturados para 6 famílias de formato (vídeo de 10 min, Shorts, longa-metragem, série, mini-novela, trailers) com decomposição em segmentos de 10 segundos, cada um contendo plano de vídeo, plano de áudio, legendas e estado de continuidade.

## Requisitos

- Python 3.11+
- Sem dependências de rede (roda 100% offline por padrão)

## Instalação

```bash
pip install -e .
```

Para desenvolvimento:

```bash
pip install -e ".[dev]"
```

Extras opcionais: `api` (FastAPI), `parsers` (PDF/DOCX/EPUB), `docs` (MkDocs).

## Uso Rápido

### CLI

```bash
# Executa o pipeline completo
living-video run input/

# Modo seco (não escreve artefatos)
living-video run input/ --dry-run

# Verifica dependências
living-video doctor

# Lista agentes e prompts registrados
living-video manifest
```

### Configuração

Crie um `project.yaml` na pasta de entrada. Veja `examples/project.yaml` para o modelo completo.

```yaml
project:
  title: "Meu Livro"
  author: "Autor"

providers:
  execute_generation: false  # padrão: só gera prompts
```

### API REST (opcional)

```bash
pip install -e ".[api]"
uvicorn pedroarte_youtube_engine.interfaces.api:app
```

Endpoints: `POST /run`, `GET /status/{id}`, `GET /health`, `GET /manifest`.

### MCP Server

O motor expõe 4 tools MCP para orquestração por LLM:
`living_video_run`, `living_video_status`, `living_video_manifest`, `living_video_doctor`.

## Arquitetura

```
src/pedroarte_youtube_engine/
  domain/          Modelos, value objects, estado, eventos
  ports/           Interfaces (protocols) para adaptadores
  adapters/        Compiladores de prompt, parsers, renderers
  agents/          26 agentes especializados + orquestrador
  prompts/         23 prompts versionados com hash
  rag/             Pipeline RAG: embedding, BM25, vector store
  infrastructure/  Artefatos, checkpoints, capacidades
  interfaces/      CLI (Typer), API (FastAPI), MCP server
  shared/          Clock, hashing, erros, texto, paths
  observability/   Logging, métricas, redação
```

O pipeline segue Clean Architecture / Hexagonal: o domínio nunca importa adaptadores ou SDKs de provedores.

## Pipeline

O motor executa 18 fases em sequência (máquina de estados):

1. Descoberta de entrada
2. Ingestão do livro
3. Indexação RAG
4. Extração de cânone (personagens, locais, props, timeline)
5. Construção de bíblias (mundo, personagem, audiovisual, voz, música)
6. Planejamento de formatos
7. Adaptação por formato
8. Planejamento de episódios
9. Decomposição em cenas
10. Escrita de segmentos (vídeo + áudio + continuidade)
11. Design de áudio
12. Compilação de prompts por provedor
13. Validação com repair loop (max 3 iterações)
14. Exportação de artefatos

## Segurança

- `execute_generation: false` por padrão (nenhuma chamada a API externa)
- Credenciais apenas via variáveis de ambiente, nunca em config
- Política de caminhos: path traversal bloqueado, symlinks rejeitados
- Nenhum nome de ator/celebridade usado como atalho visual
- Nenhuma imitação de músicas protegidas

## Testes

```bash
pytest tests/ -v
pytest tests/ -m unit        # só unitários
pytest tests/ -m contract    # contratos de porta/adaptador
```

## CI

O workflow GitHub Actions (`.github/workflows/ci.yml`) roda lint (ruff), typecheck (mypy) e testes em Python 3.11/3.12/3.13.

## Licença

Proprietário. Todos os direitos reservados.
