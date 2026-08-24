# THUMBNAIL CLICK PACKAGE — SDD DESIGN REPORT

Status: **DESIGN ONLY**. Nenhum código de produção foi escrito, nenhuma thumbnail foi gerada, o Gate 3D.2 em andamento não foi tocado. Este relatório acompanha a atualização feita em [SDD_SPDD.md](SDD_SPDD.md) Part IX (§64-87), [ARTIFACT_CONTRACT.md](ARTIFACT_CONTRACT.md) §7 e [OPERATOR_CONTRACT.md](OPERATOR_CONTRACT.md) §6.1.

## 1. Executive Summary

YouTube Lite resolveu inteiramente o **Watch Problem** (Gates 2 → 3D.2: roteiro, narração, visuais, movimento, legendas, música) mas nunca formalizou o **Click Problem** — o thumbnail sempre foi reuso mecânico de um frame (`beat_A.png`), sem contrato de design, sem candidatos alternativos, sem revisão humana dedicada. Esta revisão introduz o **Click Package** como artefato de produto de primeira classe, equivalente em seriedade ao roteiro ou à Visual Bible: um contrato mínimo (`ClickPackage`, `ThumbnailCandidate`, `ThumbnailLayout`, `ThumbnailText`, `ThumbnailReview`), uma política de geração (imagem sem texto final + renderer determinístico de tipografia), um pipeline de QA em duas camadas (estrutural automatizada + clique humano, nunca estética automatizada), e uma posição explícita no pipeline geral. Nada disso foi implementado nesta sessão — é especificação.

## 2. Current Publication Contract

Até esta revisão, `youtube_bundle/thumbnail.png` era produzido por `render_thumbnail()` (`ffmpeg_assembler.py`), que apenas recorta/normaliza uma imagem **já existente** do vídeo (`beat_A.png` em todos os gates até aqui) para 1280×720 — sem geração dedicada, sem candidatos, sem texto, sem revisão humana específica de thumbnail. O `SDD_SPDD.md` (pré-revisão) e o `ARTIFACT_CONTRACT.md` mencionavam `thumbnail.png` só como um item de checklist do bundle, sem nenhum contrato de design associado.

## 3. Identified Gap

```text
WATCH PROBLEM: coberto (Gates 2/3A/3B/3C/3D/3D.1/3D.2)
CLICK PROBLEM: NÃO coberto — título e thumbnail nunca foram tratados como
               parte do produto, apenas como metadados de empacotamento
```

Um vídeo tecnicamente perfeito e emocionalmente satisfatório (o que Gate 3D.2 está terminando de provar) ainda pode falhar completamente em produção real se ninguém clicar nele. Esse é um gap de produto, não um bug técnico.

## 4. Click Package Definition

Ver `SDD_SPDD.md` §66. `ClickPackage` agrega `video_title`, até 3 `thumbnail_candidates`, o `curiosity_gap` da embalagem como um todo, a `title_thumbnail_relationship` e o resultado da seleção humana (`selected_thumbnail`/`selection_status`). Schema deliberadamente raso — ver §52 abaixo para o sketch completo.

## 5. Thumbnail Product Principles

Ver `SDD_SPDD.md` §65/§87. Resumo: thumbnail é promessa, não resumo; uma thumbnail = uma ideia visual; compreensão em ~1s é a heurística central; nunca alegar que o contrato garante viralidade (§24 abaixo).

## 6. Thumbnail Contract

Ver `SDD_SPDD.md` §68-69/§75. Prioridades em ordem: compreensão imediata > curiosidade > legibilidade mobile > hierarquia visual > reconhecimento do assunto > sinal emocional > contraste > qualidade estética. 1 sujeito primário preferido (até 2 se justificado). Rostos são opcionais, nunca obrigatórios; quando usados, emoção narrativamente coerente, não exagero automático.

## 7. Title/Thumbnail Relationship

Ver `SDD_SPDD.md` §67. Título e thumbnail formam um sistema único, nunca tarefas independentes — juntos produzem promessa + intriga + compreensão. Regra de complementaridade: evitar que o texto da thumbnail repita o título inteiro (exemplo trabalhado em §53 abaixo).

## 8. Curiosity Gap

Ver `SDD_SPDD.md` §70. Todo candidato declara explicitamente o que o espectador vê, o que infere, e o que permanece sem resposta — esse último elemento é o gap que a thumbnail provoca e o vídeo resolve. A thumbnail nunca resume a história inteira.

## 9. Visual Hierarchy

Sujeito primário dominante, legível antes de qualquer outro elemento; texto (quando presente) como segunda camada de hierarquia, nunca competindo por atenção com o sujeito; elementos secundários (se houver) claramente subordinados. Hierarquia é avaliada na escada mobile (§15 abaixo), não só no canvas completo.

## 10. Text Policy

Ver `SDD_SPDD.md` §71. Opcional; 2-5 palavras preferidas; função é intensificar/contradizer/questionar/revelar parcialmente/criar intriga, não descrever a imagem.

## 11. Typography Policy

Ver `SDD_SPDD.md` §74. Política mínima (peso, legibilidade, ≤2 linhas, contorno/sombra, tamanho relativo ao canvas), sem hardcodar fonte específica sem asset aprovado e licenciamento conhecido.

## 12. Negative Space Policy

Ver `SDD_SPDD.md` §73. O layout (região do sujeito, região de texto, espaço negativo) é decidido **antes** da geração da imagem — o prompt de geração já precisa saber onde preservar "respiro" visual. Colisão texto/sujeito, texto/rosto e texto/hero-object são proibidas por padrão (rosto: proibição absoluta).

## 13. Thumbnail Generation Contract

Ver `SDD_SPDD.md` §75. Geração dedicada (não reuso automático de frame), canvas 16:9, resolução alvo 1280×720 configurável, normalização determinística (crop/reframe/resize, nunca stretch) quando a fonte não for 16:9 nativo — mesma política já usada para as 30 imagens do vídeo (§59 do SDD).

## 14. Deterministic Text Rendering

Ver `SDD_SPDD.md` §72/§76. Regra arquitetural central desta especificação: o modelo de imagem nunca escreve a tipografia final (`FINAL_TEXT_INSIDE_GENERATION_PROMPT: FORBIDDEN_BY_DEFAULT`); um renderer determinístico separado aplica o texto depois, com controle total de ortografia/fonte/quebra de linha/posição/contraste.

## 15. Mobile-First QA

Ver `SDD_SPDD.md` §77. Escada de revisão 1280×720 / 320×180 / 160×90 (tamanhos configuráveis); artefato de QA dedicado `thumbnail_contact_sheet.png` mostrando cada candidato em todos os tamanhos. Pergunta-chave: a ideia central sobrevive ao tamanho de feed pequeno?

## 16. Candidate Strategy

Ver `SDD_SPDD.md` §78. Padrão: 3 candidatos, conceitualmente distintos (não a mesma composição com texto trocado) — taxonomia de exemplo (personagem/objeto/consequência), não hardcoded. Explicitamente rejeitado: 20 candidatos, otimização genética, A/B massivo automático.

## 17. Human Selection

Ver `SDD_SPDD.md` §79. Obrigatória nesta fase experimental — humano escolhe entre os candidatos usando o checklist de 10 perguntas (`ThumbnailReview`). Automação da escolha é adiada até evidência real justificar.

## 18. Click Package QA

Ver `SDD_SPDD.md` §80. Duas camadas: estrutural (automatizável — resolução, aspect ratio, contagem de candidatos, comprimento de texto, previews/contact sheet criados) e humana de clique (compreensão, curiosidade, legibilidade, hierarquia, veracidade, complementaridade com o título, preferência de clique). Julgamento estético nunca é automatizado.

## 19. Artifact Contract Changes

Ver `ARTIFACT_CONTRACT.md` §7. Novo diretório `runs/<run_id>/output/thumbnail_candidates/` (candidatos + previews mobile + contact sheet + `click_package.json`), separado do `youtube_bundle/` final — só o candidato selecionado é copiado para `youtube_bundle/thumbnail.png`. `youtube_bundle/` em si **não muda de forma** nesta revisão (continua `video.mp4`, `thumbnail.png`, `captions.srt`, `metadata.json`, `script.md`, `manifest.json`, `assets/`).

## 20. Provenance Changes

`click_package.json` responde: qual conceito foi selecionado, qual imagem-fonte gerou cada candidato, qual prompt produziu a imagem-fonte, qual texto foi sobreposto, qual título foi pareado, quais alternativas existiam, quem/o que selecionou o vencedor, qual versão do Click Package produziu o resultado. Ver sketch completo em §20 do SDD (`ARTIFACT_CONTRACT.md` §7).

## 21. Operator Responsibilities

Ver `OPERATOR_CONTRACT.md` §6.1. Imagens-fonte de thumbnail seguem exatamente a mesma cadeia de decisão de geração de imagem já usada para o vídeo (nativa → API externa autorizada → local) — nenhum vocabulário novo. Diferenças são só de escopo: até 3 chamadas, nunca com texto final embutido, custo nunca escondido dentro do custo de vídeo.

## 22. Pipeline Position

Ver `SDD_SPDD.md` §84.

**Questão arquitetural**: Click Package deve ser criado (A) depois do render final, ou (B) em paralelo, assim que roteiro/Visual Bible estabilizarem?

**Decisão**: (A) depois do vídeo final, por padrão nesta fase. Racional:
- **Acoplamento**: (B) criaria uma dependência nova entre o pipeline de thumbnail e o estado intermediário (potencialmente ainda mutável) do render — mais superfície de coordenação sem benefício comprovado.
- **Espera desnecessária evitada, não criada**: o item mais lento do pipeline é o render de vídeo (~9 min para 650s neste projeto); gerar 3 imagens de thumbnail em paralelo economizaria pouco tempo de parede real frente ao risco de complexidade de coordenar dois fluxos concorrentes.
- **Conhecimento correto da história final**: um thumbnail desenhado antes do render final corre o risco de referenciar um momento/cena que ainda pode mudar (como de fato aconteceu neste projeto — Gate 3D.1→3D.2 mudou movimento e música após feedback humano). Desenhar o Click Package depois do vídeo aprovado garante que a "promessa" da thumbnail é sobre o vídeo que realmente existe.
- **Simplicidade**: (A) é o menor grafo que já cobre o caso real — nenhuma paralelização até haver evidência de que o tempo de parede importa.

Paralelização (B) fica registrada como otimização futura possível, não implementada.

## 23. Cost Policy

Ver `SDD_SPDD.md` §82. Mesma política de custo já usada para as 30 imagens de vídeo — preferir nativo/local, estimar e pedir autorização explícita antes de qualquer API paga, nunca esconder o custo de thumbnail dentro do custo de vídeo no `run_manifest.json`.

## 24. Future E3 Testing

Ver `SDD_SPDD.md` §85. A/B testing real de thumbnail no YouTube é uma capacidade E3/E4 documentada, não implementada: `candidato → publicação → evidência real de CTR → aprendizado`. Sem integração de analytics nesta fase.

## 25. Non-Goals

Predição automática de CTR/viralidade, integração com analytics do YouTube, A/B testing automático, publicação automática, ranking neural, pontuação de emoção facial, simulação de eye-tracking, scraping de concorrentes, geração massiva de candidatos, editor tipo Photoshop, infraestrutura de renderização em nuvem. Nenhum desses tem consumidor real hoje.

## 26. SDD Changes Made

| Arquivo | Mudança |
|---|---|
| [SDD_SPDD.md](SDD_SPDD.md) | Nova Parte IX (§64-87): Click Problem vs. Watch Problem, `ClickPackage`, princípios de thumbnail, curiosity gap, política de texto/tipografia/espaço negativo, contrato de geração, renderer determinístico, QA mobile-first, estratégia de candidatos, seleção humana, QA em duas camadas, política de clickbait, custo, fronteira engine/operador, posição no pipeline (com decisão arquitetural documentada), maturidade/não-objetivos, princípios registrados. Status header atualizado para v0.8. |
| [ARTIFACT_CONTRACT.md](ARTIFACT_CONTRACT.md) | Nova §7: layout `thumbnail_candidates/`, schema `click_package.json`, regra de que só o candidato selecionado entra no bundle final. |
| [OPERATOR_CONTRACT.md](OPERATOR_CONTRACT.md) | Nova §6.1: imagens-fonte de thumbnail seguem a mesma cadeia de decisão do §6, com as três diferenças de escopo explicitadas. Papel do Human (§1) atualizado para incluir seleção de thumbnail. |

Nenhum arquivo de código (`src/pedroarte_youtube_engine/lite/`) foi criado ou modificado. Nenhuma imagem foi gerada. O Gate 3D.2 (`scripts/lite/run_gate3d2_final.py`, `runs/2026...-gate3d2/`) não foi tocado.

## 27. Open Questions

- **Título — quantos candidatos?** Especificado como "avaliar, preferir minimalidade" (`SDD_SPDD.md` §78) — não decidido se serão sempre 3 títulos fixos ou um número menor/maior conforme o conteúdo. Fica para quando a implementação real expuser um consumidor.
- **Checks geométricos automatizados de colisão texto/sujeito** (`TEXT_OVER_FACE`, etc.) — a especificação permite adicioná-los no futuro "só se permanecerem simples", mas não define o método (bounding box manual vs. detecção). Deixado em aberto deliberadamente — nenhum consumidor real ainda.
- **Fonte tipográfica** — nenhuma fonte é hardcoded; a escolha real fica pendente de um asset de fonte aprovado com licenciamento conhecido.
- **Paralelização do Click Package com o render** (§22) — documentada como possibilidade futura, não como plano concreto.

## 28. Recommendation

Aprovar esta especificação como a base do Click Package para YouTube Lite. Implementação real (schemas de dados, `ThumbnailGenerationPort`, renderer determinístico de tipografia, QA estrutural, geração dos 3 candidatos + contact sheet + revisão humana) deve ser proposta como um gate próprio (ex.: **Gate 3E — Click Package**), só depois que o vídeo do Gate 3D.2 tiver `HUMAN_PASS` no Human Full Watch — consistente com a decisão arquitetural do §22 (thumbnail depois do vídeo final aprovado) e com o princípio geral do projeto de nunca antecipar a etapa mais cara antes da mais barata ter evidência (`SDD_SPDD.md` §36, Cost of Failure Principle).

---

## Contract Sketches (documentação apenas — sem implementação)

```text
ClickPackage
  video_title: str
  thumbnail_candidates: list[ThumbnailCandidate]     # default 3
  curiosity_gap: str
  title_thumbnail_relationship: str
  selected_thumbnail: str | None
  selection_status: "pending" | "selected" | "rejected_all"

ThumbnailCandidate
  candidate_id: str
  concept: str
  psychological_angle: str
  primary_subject: str
  hero_object_if_any: str | None
  curiosity_gap: {what_viewer_sees: str, what_viewer_infers: str, what_remains_unanswered: str}
  thumbnail_text: ThumbnailText | None
  text_required: bool
  composition: ThumbnailLayout
  image_prompt: str
  image_asset: str
  final_thumbnail: str
  mobile_preview: {"320x180": str, "160x90": str}

ThumbnailLayout
  primary_subject_zone: str        # ex.: "right-third"
  text_zone: str | None            # ex.: "left-third, lower"
  negative_space_required: bool
  safe_margins: {top: float, bottom: float, left: float, right: float}

ThumbnailText
  text: str
  word_count: int
  line_count: int
  function: "intensify" | "contradict" | "question" | "partial_reveal" | "intrigue"

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

## Worked Example — "O Relojoeiro de Vidro"

**Título:** O Relojoeiro Que Roubava Tempo dos Mortos

**Curiosity gap da embalagem (nível Click Package):** o espectador vê um objeto/evento impossível ligado à passagem do tempo; infere que há uma explicação sobrenatural ou criminosa; não sabe qual das duas, nem como.

| | Candidato A — Personagem | Candidato B — Objeto/Mistério | Candidato C — Evento/Consequência |
|---|---|---|---|
| **Visual** | Elias reagindo ao relógio de vidro impossível | Close-up extremo do relógio de vidro com a gravação impossível | Oficina escura, vários relógios parados exatamente na mesma hora impossível |
| **Ângulo psicológico** | Mistério de personagem | Anomalia de objeto | Consequência misteriosa |
| **Sujeito primário** | Elias (rosto, emoção de suspeita/tensão contida) | O relógio de vidro (hero object) | O conjunto de relógios (padrão visual repetido) |
| **Curiosity gap** | vê: Elias segurando o relógio, olhando para dentro dele com desconforto / infere: o objeto é pessoal, não só um item de conserto / não responde: por que ele reage assim a um relógio comum? | vê: uma gravação dentro do vidro, sem caixa nem mecanismo visível / infere: o objeto é fisicamente impossível de existir / não responde: como uma gravação foi parar lá dentro? | vê: vários relógios, todos parados no mesmo instante exato / infere: algo aconteceu simultaneamente a todos eles / não responde: o que causou isso, e por quê? |
| **Texto da thumbnail** | "ELE NÃO ENVELHECE" | "IMPOSSÍVEL" | "TODOS PARARAM" |
| **Função do texto** | Intensifica (contradiz expectativa sobre o personagem) | Intensifica (nomeia a anomalia sem explicá-la) | Revela parcialmente (aponta o evento, não a causa) |
| **Composição** | Elias ocupando o terço direito, olhar direcionado para o relógio (que aponta visualmente para o terço esquerdo, onde fica o texto) | Relógio centralizado/levemente à direita, espaço negativo à esquerda para o texto curto | Relógios em profundidade de campo, texto na metade superior sobre área escura de baixo contraste de detalhe |
| **Espaço negativo** | Terço esquerdo preservado, sem elementos de fundo complexos ali | Fundo desfocado/escuro à esquerda do relógio | Área superior escura da oficina, sem relógios sobrepostos ao texto |
| **Relação com o título** | Complementa: o título nomeia o "roubo de tempo"; a thumbnail mostra a reação humana a isso, sem repetir a frase do título | Complementa: o título é sobre a ação (roubar tempo); a thumbnail mostra a evidência física (o objeto impossível) | Complementa: o título aponta o crime; a thumbnail mostra a escala da consequência (não é um relógio, são vários) |
| **Expectativa de revisão mobile** | Rosto + objeto devem permanecer reconhecíveis a 160×90; texto de 3 palavras em fonte grande deve continuar legível | Textura/gravação do relógio pode se perder em 160×90 — validar se ainda comunica "objeto estranho" mesmo sem o detalhe da gravação | Padrão repetido de relógios deve continuar legível como "múltiplos objetos idênticos" mesmo pequeno — maior risco de perder clareza em 160×90, candidato a monitorar na revisão mobile |

Nenhuma dessas escolhas é uma decisão de produção — é só o exemplo ilustrativo pedido pela especificação, mostrando como o contrato se aplicaria a este vídeo específico.

---

## Bloco de Decisão Final

```
CLICK_PACKAGE_REQUIRED: YES
THUMBNAIL_CONTRACT_REQUIRED: YES
TITLE_THUMBNAIL_CO_DESIGN_REQUIRED: YES

DEFAULT_THUMBNAIL_CANDIDATES: 3
THUMBNAIL_TEXT_REQUIRED: NO (opcional, usado quando melhora compreensão/curiosidade)
PREFERRED_THUMBNAIL_TEXT_WORDS: 2-5
MAX_PRIMARY_SUBJECTS_PREFERRED: 1 (até 2 quando justificado)

FINAL_TEXT_GENERATED_BY_IMAGE_MODEL: FORBIDDEN_BY_DEFAULT
DETERMINISTIC_TEXT_OVERLAY_REQUIRED: YES

NEGATIVE_SPACE_PLANNING_REQUIRED: YES
TEXT_OVER_FACE_ALLOWED: NO
TEXT_OVER_HERO_OBJECT_ALLOWED: FORBIDDEN_BY_DEFAULT

TARGET_RESOLUTION: 1280x720
TARGET_ASPECT_RATIO: 16:9

MOBILE_PREVIEW_REQUIRED: YES
MOBILE_REVIEW_SIZES: [1280x720, 320x180, 160x90]
CONTACT_SHEET_REQUIRED: YES

CURIOSITY_GAP_REQUIRED: YES
CLICKBAIT_DECEPTION_ALLOWED: NO

HUMAN_SELECTION_REQUIRED: YES

STRUCTURAL_QA_REQUIRED: YES
AESTHETIC_AUTOMATED_QA_REQUIRED: NO
CTR_PREDICTION_REQUIRED: NO

CLICK_PACKAGE_ARTIFACTS: [thumbnail_candidates/*.png, thumbnail_*_320x180.png, thumbnail_*_160x90.png, thumbnail_contact_sheet.png, click_package.json]
FINAL_BUNDLE_CHANGE_REQUIRED: NO (youtube_bundle/thumbnail.png continua recebendo só o vencedor selecionado)

ENGINE_OPERATOR_BOUNDARY_PRESERVED: YES
ADVANCED_MODE_TOUCHED: NO

IMPLEMENTATION_PERFORMED: NO
PRODUCTION_CODE_CHANGED: NO

READY_FOR_CLICK_PACKAGE_IMPLEMENTATION: YES
RECOMMENDED_IMPLEMENTATION_GATE: Gate 3E — Click Package (após HUMAN_PASS do Gate 3D.2 no Human Full Watch)

SDD_VERDICT: CLICK_PACKAGE_SDD_APPROVED
```
