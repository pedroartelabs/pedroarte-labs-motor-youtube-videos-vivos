# YOUTUBE LITE — ARTIFACT CONTRACT

Companion a [SDD_SPDD.md](SDD_SPDD.md) §18. Define o layout de filesystem, os schemas de manifesto/tarefas, e o bundle final (referência de produto completo — Gate 3+, não implementado nesta fase).

## 1. Layout de Execução

```text
runs/
└── <run_id>/
    ├── input/              # briefing.yaml (Gate 3+) ou fixture do Gate 2
    ├── working/            # script.md, timeline.json — artefatos intermediários
    ├── assets/
    │   ├── narration.wav
    │   ├── music/          # só se música tiver sido usada (Gate 3+)
    │   └── images/          # image_0001.png, image_0002.png, ...
    ├── output/
    │   └── clip.mp4         # Gate 2; no Gate 3+, o output/ vira o youtube_bundle/ completo (§4)
    ├── run_manifest.json
    └── pending_tasks.json
```

`runs/` já está no `.gitignore` do repositório — nenhum artefato de execução é versionado.

`run_id` segue o padrão `<timestamp-iso-compacto>-<slug-curto>` (ex.: `20260823T153000Z-gate2-proof`), gerado localmente, sem dependência de rede.

## 2. `run_manifest.json`

```json
{
  "run_id": "20260823T153000Z-gate2-proof",
  "gate": "gate2",
  "owner": "claude_code",
  "status": "qa_passed",
  "created_at": "2026-08-23T15:30:00Z",
  "updated_at": "2026-08-23T15:34:12Z",
  "briefing_source": "fixture:gate2_short_script",
  "artifacts": [
    {
      "path": "output/clip.mp4",
      "kind": "video",
      "sha256": "…",
      "size_bytes": 0,
      "produced_by": "ffmpeg_assembler"
    }
  ],
  "provenance": {
    "narration": {
      "method": "local:sapi5",
      "voice": "Microsoft Maria Desktop",
      "language": "pt-BR"
    },
    "image": {
      "method": "local:gdi_placeholder",
      "provider": null,
      "model": null,
      "prompt": "…"
    }
  },
  "economics": {
    "external_api_cost": 0.0,
    "generation_time_seconds": 0.0,
    "human_review_time_seconds": null,
    "asset_count": 1,
    "render_time_seconds": 0.0,
    "retry_count": 0,
    "execution_environment": "claude_code",
    "generation_method": "local_first"
  },
  "qa": {
    "automated": {},
    "human": null
  }
}
```

`status` segue o enum `RunStatus` (SDD_SPDD.md §19): `started | script_ready | narration_ready | images_ready | assembled | qa_passed | qa_failed | failed`.

## 3. `pending_tasks.json`

```json
{
  "run_id": "20260823T153000Z-gate2-proof",
  "tasks": [
    {"id": "script", "status": "done"},
    {"id": "narration", "status": "done"},
    {"id": "image_0001", "status": "done"},
    {"id": "timeline", "status": "done"},
    {"id": "assembly", "status": "done"},
    {"id": "qa", "status": "done"}
  ]
}
```

`status` por item: `pending | in_progress | done | failed`. Um operador só marca `in_progress` o item que vai executar imediatamente (Operator Ownership Rule, `OPERATOR_CONTRACT.md` §3-4).

## 4. YouTube Bundle (referência — Gate 3+, não implementado nesta fase)

```text
youtube_bundle/
├── video.mp4
├── thumbnail.png
├── captions.srt
├── metadata.json
├── script.md
├── manifest.json           # fusão de run_manifest.json + provenance (discovery Lite, §21)
└── assets/
    ├── narration.*
    ├── music/
    └── images/
```

`metadata.json` mínimo:
```json
{"title": "...", "description": "...", "chapters": [{"at": "00:00", "title": "..."}], "hashtags": ["..."], "language": "pt-BR", "duration_seconds": 0}
```

## 5. Gate 2 — Artefatos Mínimos Exigidos

Diferente do bundle completo acima, o Gate 2 só precisa produzir, dentro de `runs/<run_id>/`:
```text
working/script.md
assets/narration.wav
assets/images/image_0001.png
working/timeline.json
output/clip.mp4
run_manifest.json
pending_tasks.json
```

Nenhum outro artefato (thumbnail, metadata, captions, bundle completo) é exigido nem produzido no Gate 2, por restrição explícita do SDD_SPDD.md §35.

## 6. Regras de Proveniência

Todo asset gerado registra, no mínimo: `asset_id`, `method` (`local:<estratégia>` ou `external_api:<provider>` ou `native_environment_capability`), `produced_by`, `output_path`, `hash` (sha256), `status`, `retries`. Prompt e parâmetros de geração são registrados quando aplicável. **Nunca** um valor de secret (`.env`) é registrado — só o nome do provider, nunca a chave.

## 7. Click Package / Thumbnail Candidates (especificado, NÃO implementado — ver `SDD_SPDD.md` Part IX)

Durante a produção experimental, antes da seleção humana, os candidatos de thumbnail vivem **fora** do `youtube_bundle/` final:

```text
runs/<run_id>/output/
├── youtube_bundle/                  # inalterado nesta revisão (§4) — recebe só o thumbnail.png SELECIONADO
└── thumbnail_candidates/
    ├── thumbnail_A.png
    ├── thumbnail_A_320x180.png
    ├── thumbnail_A_160x90.png
    ├── thumbnail_B.png
    ├── thumbnail_B_320x180.png
    ├── thumbnail_B_160x90.png
    ├── thumbnail_C.png
    ├── thumbnail_C_320x180.png
    ├── thumbnail_C_160x90.png
    ├── thumbnail_contact_sheet.png   # artefato de QA/revisão, não de publicação
    └── click_package.json            # ClickPackage completo (SDD_SPDD.md §66), pré-seleção
```

Só o candidato **selecionado pelo humano** (§79 do SDD) é copiado para `youtube_bundle/thumbnail.png` — `thumbnail_candidates/` nunca é publicado, é puramente um artefato de working/QA (paralelo a `working/` no layout de execução do §1).

`click_package.json` (proveniência mínima, permite responder às perguntas do §44 do briefing original — qual conceito foi selecionado, qual imagem-fonte, qual prompt, qual texto, qual título, quais alternativas existiam, quem/o que selecionou o vencedor):

```json
{
  "video_title": "...",
  "selected_thumbnail": "thumbnail_B",
  "selection_status": "selected",
  "candidates": [
    {
      "candidate_id": "thumbnail_A",
      "concept": "...",
      "psychological_angle": "character",
      "image_prompt": "...",
      "image_asset": "thumbnail_candidates/thumbnail_A.png",
      "thumbnail_text": {"text": "...", "word_count": 3, "function": "intensify"},
      "produced_by": "external_api:openai | local:<strategy> | native_environment_capability"
    }
  ],
  "human_review": {"reviewed_by": "human", "notes": "..."}
}
```

`generation_method` de cada `image_asset` segue exatamente o mesmo vocabulário e a mesma cadeia de decisão já usados para imagens de vídeo (`OPERATOR_CONTRACT.md` §6) — nenhum vocabulário novo é introduzido só para thumbnails.
