# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [0.1.0] — 2026-08-06

### Adicionado

- **Domínio audiovisual completo**: value objects imutáveis (`Timecode`,
  `Duration`, `AspectRatio`, `Resolution`, `VoiceIdentity`, `ContentHash`, …),
  entidades, agregados (`AdaptationProject`, `CanonBible`, `AudiovisualBible`,
  `ProductionPlan`, `Episode`, `Sequence`, `Scene`, `PromptPackage`,
  `GenerationJob`), serviços de domínio e eventos de domínio.
- **Contrato do segmento audiovisual** com seções de vídeo *e* áudio
  obrigatórias; nenhum segmento é aprovado sem `voice_plan` explícito.
- **Catálogo de 31 agentes** com entrada tipada, saída tipada, ferramentas
  autorizadas, versão de prompt e critérios de conclusão.
- **Orquestrador com máquina de estados explícita**, gates de qualidade,
  repair loop limitado e checkpoints para retomada.
- **RAG narrativo local**: chunking estrutural, índice lexical BM25, embeddings
  determinísticos locais, vector store em memória, recuperação híbrida com
  reranking e proveniência.
- **Seis famílias de formato**: vídeo principal de 10 minutos, Shorts, vídeo
  longo (>30 min), série com temporadas, mini-novela e trailers/teasers.
- **Ports & adapters** para LLM, vídeo, imagem, voz, música, embeddings, vector
  store e armazenamento de artefatos, com registro de capacidades de provedor.
- **Interfaces**: CLI `living-video` (com modo interativo), API FastAPI opcional
  e servidor MCP com tools e resources.
- **JSON Schemas** publicados em `schemas/` e validados no CI.
- **Suíte de testes** unitária, de propriedades (Hypothesis), de integração, de
  contrato e golden, sem dependência de rede ou credenciais.
- **Obra sintética original** "O Relojoeiro de Vidro" como exemplo e fixture.

### Segurança

- Allowlist de raízes e extensões, proteção contra path traversal, sanitização
  de nomes de arquivo, limites de tamanho e redaction de segredos em log.
- `execute_generation: false` por padrão: nenhuma chamada externa sem aceite
  explícito.

[Não publicado]: https://github.com/pedroartelabs/pedroarte-labs-motor-youtube-videos-vivos/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pedroartelabs/pedroarte-labs-motor-youtube-videos-vivos/releases/tag/v0.1.0
