# Política de Segurança

Este documento descreve o modelo de ameaças, os controles implementados e o
processo de reporte de vulnerabilidades do
`PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE`.

## 1. Escopo

O motor lê arquivos fornecidos pelo operador, produz artefatos textuais em
disco e, **somente quando explicitamente habilitado**, envia requisições a
provedores externos de geração de mídia.

No modo padrão (`providers.execute_generation: false`) o motor:

- não abre conexões de rede;
- não envia o conteúdo do livro a terceiros;
- não consome APIs pagas;
- não lê credenciais.

## 2. Reporte de vulnerabilidades

Envie um relatório privado para **pedroarte2508@gmail.com** com o assunto
`[SECURITY] pedroarte-labs-motor-youtube-videos-vivos`.

- Não abra issues públicas para vulnerabilidades.
- Inclua passos de reprodução e o impacto observado.
- Prazo-alvo de primeira resposta: 5 dias úteis.

## 3. Segredos

- Nenhuma credencial é versionada. O arquivo `.env` está no `.gitignore`.
- `.env.example` contém apenas chaves vazias e serve como documentação.
- Credenciais são lidas **exclusivamente** de variáveis de ambiente, nunca de
  arquivos de projeto (`project.yaml`) ou de argumentos de linha de comando.
- O workflow `.github/workflows/security.yml` executa varredura de segredos e
  falha o build ao encontrar padrões de chave.
- Os logs passam por *redaction*: qualquer valor associado a chaves cujo nome
  contenha `key`, `token`, `secret`, `password`, `credential` ou `authorization`
  é substituído por `***REDACTED***`
  (`observability/redaction.py`).

## 4. Sistema de arquivos

Todo acesso a disco passa por `shared/paths.py`:

| Controle | Implementação |
| --- | --- |
| Path traversal | `resolve_within()` resolve o caminho e exige que o resultado esteja contido em uma raiz permitida; `..` e links simbólicos que escapam são rejeitados |
| Allowlist de raízes | `PathPolicy(allowed_roots=[...])`; o MCP e a API recebem uma allowlist mais restrita que a CLI |
| Allowlist de extensões | `.md .txt .docx .pdf .epub .json .yaml .yml` — arquivos fora da lista são ignorados na descoberta |
| Limite de tamanho | `max_file_bytes` (padrão 32 MiB por arquivo, 256 MiB por execução) |
| Sanitização de nomes | `safe_slug()` remove separadores, caracteres de controle, nomes reservados do Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`) e limita o comprimento |
| Escrita | Artefatos são gravados apenas sob `outputs/<project_slug>/<run_id>/`; execuções anteriores nunca são sobrescritas |

## 5. Execução de código

- O motor **não** executa código proveniente da entrada.
- Não há `eval`, `exec`, `pickle.loads` sobre dados não confiáveis nem
  `subprocess` com `shell=True`.
- `yaml.safe_load` é usado em toda leitura de YAML; `yaml.load` é proibido pelo
  lint (regra `S506` do Ruff / bandit).
- A regra `S` do Ruff está habilitada para todo o pacote.

## 6. Rede e provedores

- Os adaptadores de provedor ficam isolados em `adapters/` e só são carregados
  quando `execute_generation` está ativo.
- A execução real exige, cumulativamente: credencial presente em variável de
  ambiente, aceite explícito no projeto, orçamento máximo configurado, modelo
  em allowlist e diretório de saída válido.
- Toda chamada externa registra `idempotency_key`, prompt enviado (com
  redaction), status e custo estimado.
- Retry com backoff exponencial e *circuit breaker* protegem contra loops de
  falha.

## 7. Dependências

- Todas as dependências são fixadas por limite superior de major em
  `pyproject.toml`.
- `pip-audit` roda no workflow de segurança.
- Dependências opcionais (`parsers`, `api`, `docs`) não são instaladas por
  padrão, reduzindo a superfície de ataque da instalação mínima.

## 8. Conteúdo gerado

O `LEGAL_AND_RIGHTS_AGENT` sinaliza — sem oferecer aconselhamento jurídico:

- ausência de confirmação de direitos de adaptação;
- menções a pessoas públicas reais, marcas registradas e obras protegidas;
- pedidos de imitação de artistas vivos (bloqueados nos prompts compilados).

O relatório fica em `reports/legal_and_rights_report.md` de cada execução.

## 9. Versões suportadas

| Versão | Suporte |
| --- | --- |
| 0.1.x | ✅ |
