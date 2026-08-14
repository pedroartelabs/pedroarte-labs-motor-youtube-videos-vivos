"""Renderização Markdown dos artefatos legíveis por humanos.

O `render_segment_markdown` implementa exatamente o template da seção 15 da
especificação — todas as seções, na mesma ordem, sem campo omitido.
"""

from __future__ import annotations

import csv
import io

from pedroarte_youtube_engine.domain.aggregates import AudiovisualBible, CanonBible
from pedroarte_youtube_engine.domain.segment import ContinuitySnapshot, PromptSegment
from pedroarte_youtube_engine.domain.services.segment_compilation import (
    SegmentCompilationService,
)

_COMPILER = SegmentCompilationService()


# ---------------------------------------------------------------------------
# Segmento — template da seção 15
# ---------------------------------------------------------------------------


def render_segment_markdown(segment: PromptSegment, *, project_title: str = "") -> str:
    """Renderiza um segmento no template humano completo."""
    video = segment.video
    audio = segment.audio
    lines: list[str] = ["# SEGMENTO AUDIOVISUAL", ""]

    # -- Identificação -----------------------------------------------------
    lines += [
        "## Identificação",
        "",
        f"- Projeto: {project_title or segment.project_id}",
        f"- Produção: {segment.production_variant.value}",
        f"- Episódio: {segment.episode_id or 'produção de vídeo único'}",
        f"- Cena: {segment.scene_id}",
        f"- Segmento: {segment.segment_number:03d} (`{segment.segment_id}`)",
        f"- Timecode: {segment.range.start} → {segment.range.end}",
        f"- Duração narrativa: {segment.duration.target.seconds:.1f}s",
        f"- Duração do provedor: {_provider_duration(segment)}",
        f"- Proporção: {segment.segment_format.aspect_ratio}",
        f"- Resolução: {segment.segment_format.resolution}",
        f"- Idioma: {_language_of(segment)}",
        "",
    ]

    # -- Função narrativa --------------------------------------------------
    lines += [
        "## Função narrativa",
        "",
        segment.narrative.purpose,
        "",
        f"- Beat: `{segment.narrative.beat}`",
        f"- Função dramática: {segment.narrative.function.value}",
        f"- Arco emocional: {segment.narrative.emotional_start.value} → "
        f"{segment.narrative.emotional_end.value}",
        f"- Tensão: {segment.narrative.tension}/10",
        _bullet_list("Informação revelada", segment.narrative.information_revealed),
        _bullet_list("Informação retida", segment.narrative.information_withheld),
        "",
    ]

    # -- Continuidade de entrada -------------------------------------------
    lines += ["## Continuidade de entrada", "", *_snapshot_lines(segment.continuity_in), ""]

    # -- Descrição visual --------------------------------------------------
    lines += [
        "## Descrição visual completa",
        "",
        f"**Cenário.** {video.setting}",
        "",
        f"**Ação principal.** {video.action}",
        "",
        f"**Horário.** {video.time_of_day} · **Clima.** {video.weather}",
        "",
        f"**Iluminação.** {video.lighting}",
        "",
        f"**Composição.** {video.composition}",
        "",
        f"**Ritmo visual.** {video.visual_rhythm}",
        "",
    ]
    if video.relevant_props:
        lines += [f"**Objetos relevantes.** {', '.join(video.relevant_props)}", ""]

    # -- Direção de câmera -------------------------------------------------
    camera = video.camera
    lines += [
        "## Direção de câmera",
        "",
        f"- Plano: {camera.shot_type.value}",
        f"- Ângulo: {camera.angle.value}",
        f"- Lente: {camera.lens}",
        f"- Altura: {camera.height}",
        f"- Distância: {camera.distance}",
        f"- Movimento: {camera.movement.value}",
        f"- Velocidade: {camera.movement_speed}",
        f"- Foco: {camera.focus}",
        f"- Profundidade: {camera.depth_of_field}",
        f"- Quadro inicial: {video.initial_frame}",
        f"- Quadro final: {video.final_frame}",
        "",
    ]

    # -- Interpretação -----------------------------------------------------
    lines += ["## Interpretação", "", video.performance, ""]
    if video.characters:
        for presence in video.characters:
            lines += [
                f"### {presence.display_name}",
                "",
                f"- Âncora visual: {presence.appearance_anchor}",
                f"- Figurino: {presence.wardrobe} ({presence.wardrobe_condition})",
                f"- Expressão: {presence.expression}",
                f"- Postura: {presence.posture}",
                f"- Movimentação: {presence.blocking}",
                f"- Mãos: {presence.hands_occupied_with}",
                f"- Olhar: {presence.gaze_direction}",
                f"- Ferimentos visíveis: "
                f"{', '.join(presence.visible_injuries) or 'nenhum'}",
                "",
            ]

    # -- Vozes -------------------------------------------------------------
    lines += ["## Vozes", ""]
    for entry in audio.voice_plan:
        lines += [
            f"### {entry.voice_id} — {entry.decision.value}",
            "",
            f"- Personagem: {entry.character_id or 'narração / som fora de quadro'}",
            f"- Descrição: {entry.description}",
            f"- Intensidade: {entry.intensity}",
            f"- Janela: {entry.range.start} → {entry.range.end}",
        ]
        if entry.justification:
            lines.append(f"- Justificativa: {entry.justification}")
        lines.append("")

    if audio.dialogue:
        lines += ["### Diálogo", ""]
        for line in audio.dialogue:
            lines += [
                f"- **{line.speaker_name}** (`{line.voice_id}`, {line.emotion.value})",
                f"  - Texto: «{line.text}»",
                f"  - Intenção: {line.intention}",
                f"  - Velocidade: {line.pace} · Pausas: {line.pauses}",
                f"  - Respiração: {line.breathing}",
                f"  - Entrada: {line.range.start} · Saída: {line.range.end}",
                f"  - Sincronia labial: {line.lip_sync_note}",
            ]
        lines.append("")

    # -- Narração ----------------------------------------------------------
    lines += ["## Narração", ""]
    if audio.narration:
        for line in audio.narration:
            lines += [
                f"- Voz: `{line.voice_id}` ({line.narrator_name})",
                f"- Texto: «{line.text}»",
                f"- Intenção: {line.intention}",
                f"- Ritmo: {line.rhythm}",
                f"- Timecode: {line.range.start} → {line.range.end}",
                "",
            ]
    else:
        lines += ["Sem narração neste segmento — a informação chega por imagem e som.", ""]

    # -- Som ambiente ------------------------------------------------------
    lines += ["## Som ambiente", ""]
    for ambient in audio.ambient_sound:
        lines.append(
            f"- {ambient.description} — fonte: {ambient.source}; "
            f"espacialidade: {ambient.spatiality}; nível relativo "
            f"{ambient.relative_db:+.1f} dB"
        )
    lines.append("")

    # -- Efeitos sonoros ---------------------------------------------------
    lines += ["## Efeitos sonoros", ""]
    if audio.sound_effects:
        for effect in audio.sound_effects:
            lines.append(
                f"- `{effect.at}` {effect.description} "
                f"({'fora de quadro' if effect.off_screen else 'em quadro'}, "
                f"{effect.spatiality}, {effect.relative_db:+.1f} dB) — "
                f"sincronizado com: {effect.synced_to_action}"
            )
    else:
        lines.append("- Nenhum efeito pontual: o segmento se apoia no ambiente contínuo.")
    lines.append("")

    # -- Música ------------------------------------------------------------
    music = audio.music
    lines += ["## Música", ""]
    if music.enabled:
        lines += [
            f"- Função: {music.function}",
            f"- Descrição: {music.description}",
            f"- Instrumentação: {', '.join(music.instrumentation) or 'não especificada'}",
            f"- Andamento: {music.tempo}",
            f"- Intensidade: {music.intensity_start} → {music.intensity_end}",
            f"- Entrada: {music.entry_timecode or segment.range.start}",
            f"- Saída: {music.exit_timecode or segment.range.end}",
            f"- Relação com diálogos: {music.relationship_to_dialogue}",
        ]
    else:
        lines.append("- Ausente por decisão dramática: o silêncio carrega a cena.")
    lines.append("")

    # -- Mixagem -----------------------------------------------------------
    lines += ["## Mixagem", ""]
    for level in sorted(audio.mixing_notes, key=lambda item: item.priority):
        lines.append(f"- {level}")
    lines.append("")

    # -- Sincronização -----------------------------------------------------
    lines += ["## Sincronização audiovisual", ""]
    if audio.synchronization_cues:
        for cue in audio.synchronization_cues:
            lines.append(f"- `{cue.at}` {cue.visual_action} ↔ {cue.audio_event}")
    else:
        lines.append("- Sem marcas de sincronia rígida; o corte segue o ritmo da ação.")
    lines.append("")

    # -- Transição de saída ------------------------------------------------
    lines += [
        "## Transição de saída",
        "",
        f"- Imagem: {video.transition_out.value}",
        f"- Áudio: {audio.audio_transition_out}",
        "",
    ]

    # -- Restrições negativas ----------------------------------------------
    lines += ["## Restrições negativas", ""]
    for constraint in _COMPILER.negative_constraints(segment):
        lines.append(f"- {constraint}")
    lines.append("")

    # -- Continuidade de saída ---------------------------------------------
    lines += ["## Continuidade de saída", "", *_snapshot_lines(segment.continuity_out), ""]

    # -- Proveniência ------------------------------------------------------
    if segment.source_references:
        lines += ["## Proveniência", ""]
        for reference in segment.source_references:
            lines.append(
                f"- {reference.citation()} — confiança {reference.confidence} — "
                f"«{reference.excerpt}»"
            )
        lines.append("")

    # -- Prompt compilado --------------------------------------------------
    lines += [
        "## Prompt compilado para o provedor",
        "",
        "```text",
        _COMPILER.build_full_prompt(segment),
        "```",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bíblias
# ---------------------------------------------------------------------------


def render_canon_bible(canon: CanonBible) -> str:
    """Bíblia de Cânone em Markdown."""
    lines = [
        f"# Bíblia de Cânone — {canon.title or canon.project_id}",
        "",
        f"**Autor:** {canon.author or 'não informado'}  ",
        f"**Idioma:** {canon.language}  ",
        f"**Projeto:** `{canon.project_id}`",
        "",
        "> Este documento é a autoridade narrativa da adaptação. Todo prompt gerado",
        "> pelo motor é comparado com ele pelo `CANON_GUARDIAN_AGENT`.",
        "",
    ]

    if canon.logline:
        lines += ["## Logline", "", canon.logline, ""]
    if canon.thesis:
        lines += ["## Tese central", "", canon.thesis, ""]

    lines += ["## Personagens", ""]
    for character in canon.characters:
        appearance = character.appearance
        lines += [
            f"### {character.canonical_name}",
            "",
            f"- **ID:** `{character.character_id}`",
            f"- **Papel:** {character.role}",
            f"- **Apelidos:** {', '.join(character.aliases) or 'nenhum'}",
            f"- **Menções:** {character.mention_count} · "
            f"**Falas:** {character.dialogue_line_count}",
            f"- **Primeira aparição:** capítulo {character.first_chapter_index + 1}",
            "",
            f"**Âncora de aparência.** {appearance.anchor_text()}",
            "",
            f"**Temperamento.** {', '.join(character.temperament) or 'não determinado'}",
            "",
            f"**Movimentação.** {appearance.movement_signature}",
            "",
        ]
        if character.wardrobe_sets:
            lines.append("**Figurinos.**")
            lines.append("")
            for wardrobe in character.wardrobe_sets:
                lines.append(
                    f"- `{wardrobe.name}` (a partir do capítulo "
                    f"{wardrobe.applies_from_chapter + 1}): {wardrobe.description} "
                    f"— estado: {wardrobe.condition}"
                )
            lines.append("")
        if character.forbidden_variations:
            lines.append("**Variações proibidas.**")
            lines.append("")
            for forbidden in character.forbidden_variations:
                lines.append(f"- {forbidden}")
            lines.append("")
        if character.references:
            lines.append(
                f"**Proveniência.** {character.references[0].citation()}"
            )
            lines.append("")

    lines += ["## Relações", ""]
    if canon.relationships:
        for relationship in canon.relationships:
            lines.append(
                f"- `{relationship.source_character_id}` → "
                f"`{relationship.target_character_id}` "
                f"({relationship.kind.value}, tensão {relationship.tension}/10): "
                f"{relationship.description}"
            )
    else:
        lines.append("- Nenhuma relação explícita foi extraída.")
    lines.append("")

    lines += ["## Locais", ""]
    for location in canon.locations:
        lines += [
            f"### {location.canonical_name}",
            "",
            f"- **ID:** `{location.location_id}`",
            f"- **Tipo:** {'interior' if location.interior else 'exterior'}",
            f"- **Menções:** {location.mention_count}",
            f"- **Horário padrão:** {location.default_time_of_day}",
            f"- **Clima padrão:** {location.default_weather}",
            f"- **Assinatura sonora:** "
            f"{', '.join(location.ambient_sound_signature) or 'não definida'}",
            "",
        ]
        if location.description:
            lines += [location.description, ""]

    lines += ["## Objetos", ""]
    if canon.props:
        for prop in canon.props:
            lines.append(
                f"- **{prop.canonical_name}** (`{prop.prop_id}`, peso narrativo "
                f"{prop.narrative_weight}/5): {prop.description or 'sem descrição'}"
            )
    else:
        lines.append("- Nenhum objeto recorrente identificado.")
    lines.append("")

    lines += ["## Cronologia", ""]
    for event in canon.timeline:
        lines.append(
            f"{event.order + 1}. **{event.title}** (cap. {event.chapter_index + 1}, "
            f"tensão {event.tension}/10, tom {event.tone.value}) — {event.description}"
        )
    lines.append("")

    lines += _section_list("Regras do mundo", canon.world_rules)
    lines += _section_list("Proibições", canon.prohibitions)
    lines += _section_list("Mistérios em aberto", canon.mysteries)

    lines += ["## Questões não resolvidas", ""]
    if canon.unresolved_questions:
        lines.append(
            "> O motor prefere declarar a lacuna a preenchê-la por invenção. "
            "Os itens abaixo pedem decisão autoral."
        )
        lines.append("")
        for question in canon.unresolved_questions:
            lines.append(
                f"- **{question.question}** (confiança {question.confidence}) — "
                f"{question.why_it_matters}"
            )
    else:
        lines.append("- Nenhuma lacuna registrada.")
    lines.append("")

    return "\n".join(lines)


def render_audiovisual_bible(bible: AudiovisualBible) -> str:
    """Bíblia Audiovisual em Markdown."""
    identity = bible.visual_identity
    lines = [
        f"# Bíblia Audiovisual — `{bible.project_id}`",
        "",
        "> A tradução do cânone em decisões de tela e de som. É o que faz o segmento 1",
        "> e o segmento 216 pertencerem visivelmente ao mesmo filme.",
        "",
        "## Identidade visual",
        "",
        identity.style_statement,
        "",
        f"- **Paleta conceitual:** {', '.join(identity.conceptual_palette)}",
        f"- **Doutrina de iluminação:** {identity.lighting_doctrine}",
        f"- **Linguagem de lentes:** {identity.lens_language}",
        f"- **Doutrina de câmera:** {identity.camera_doctrine}",
        f"- **Textura:** {identity.texture_and_grain}",
        f"- **Plano padrão:** {identity.default_shot_type.value}",
        f"- **Ângulo padrão:** {identity.default_angle.value}",
        f"- **Movimento padrão:** {identity.default_movement.value}",
        f"- **Transição padrão:** {identity.default_transition.value}",
        "",
    ]

    if identity.recurring_motifs:
        lines += ["### Motivos recorrentes", ""]
        lines += [f"- {motif}" for motif in identity.recurring_motifs]
        lines.append("")

    lines += ["### Restrições visuais", ""]
    lines += [f"- {item}" for item in identity.visual_restrictions]
    lines.append("")

    lines += ["## Bíblia de Vozes", ""]
    for voice in bible.voices:
        lines += [
            f"### `{voice.voice_id}` — {voice.display_name}",
            "",
            f"- **Personagem:** {voice.character_id or 'narrador'}",
            f"- **Idioma:** {voice.identity.language}",
            f"- **Sotaque:** {voice.identity.accent_region}",
            f"- **Idade vocal:** {voice.identity.apparent_age_range}",
            f"- **Altura:** {voice.identity.pitch}",
            f"- **Textura:** {voice.identity.texture}",
            f"- **Ritmo:** {voice.identity.pace}",
            f"- **Articulação:** {voice.identity.articulation}",
            f"- **Respiração:** {voice.identity.breathing}",
            f"- **Faixa emocional:** "
            f"{', '.join(tone.value for tone in voice.emotional_range) or 'ampla'}",
            f"- **Pausas:** {voice.pauses}",
            "",
        ]
        if voice.pronunciation_dictionary:
            lines.append("**Dicionário de pronúncia.**")
            lines.append("")
            for term, pronunciation in sorted(voice.pronunciation_dictionary.items()):
                lines.append(f"- `{term}` → {pronunciation}")
            lines.append("")
        lines.append("**Variações proibidas.**")
        lines.append("")
        lines += [f"- {item}" for item in voice.forbidden_variations]
        lines.append("")

    lines += ["## Temas musicais", ""]
    for theme in bible.music_themes:
        lines += [
            f"### {theme.name} (`{theme.theme_id}`)",
            "",
            f"- **Função:** {theme.role.value}",
            f"- **Instrumentação:** {', '.join(theme.instrumentation)}",
            f"- **Andamento:** {theme.tempo_bpm_range} BPM",
            f"- **Caráter:** {theme.key_character}",
            f"- **Curva de intensidade:** {theme.intensity_curve}",
            "",
            theme.motif_description,
            "",
        ]

    lines += ["## Motivos sonoros", ""]
    for motif in bible.sound_motifs:
        lines.append(
            f"- **{motif.name}** (`{motif.motif_id}`): {motif.description} — "
            f"gatilho: {motif.trigger}; espacialidade: {motif.spatiality}"
        )
    lines.append("")

    lines += ["## Ambientes", ""]
    for profile in bible.location_profiles:
        lines.append(
            f"- `{profile.location_id}`: paleta {', '.join(profile.palette) or '—'}; "
            f"luz {profile.lighting or '—'}; lente {profile.default_lens}; "
            f"som {', '.join(profile.ambient_sound) or '—'}"
        )
    lines.append("")

    lines += ["## Âncoras de continuidade", ""]
    for anchor in bible.continuity_anchors:
        marker = "**obrigatória**" if anchor.hard_constraint else "recomendada"
        lines.append(f"- [{anchor.category}] {anchor.subject}: {anchor.statement} ({marker})")
    lines.append("")

    if bible.transitions_doctrine:
        lines += ["## Doutrina de transições", "", bible.transitions_doctrine, ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shotlist
# ---------------------------------------------------------------------------


def render_shotlist_csv(segments: tuple[PromptSegment, ...]) -> str:
    """Shotlist em CSV, pronta para uma planilha de produção."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        (
            "segmento",
            "id",
            "inicio",
            "fim",
            "duracao_s",
            "cena",
            "plano",
            "angulo",
            "lente",
            "movimento",
            "local",
            "personagens",
            "funcao_narrativa",
            "decisao_vocal",
            "musica",
            "transicao_saida",
        )
    )
    for segment in segments:
        writer.writerow(
            (
                f"{segment.segment_number:03d}",
                segment.segment_id.value,
                segment.range.start.formatted(),
                segment.range.end.formatted(),
                f"{segment.duration.target.seconds:.1f}",
                segment.scene_id.value,
                segment.video.camera.shot_type.value,
                segment.video.camera.angle.value,
                segment.video.camera.lens,
                segment.video.camera.movement.value,
                str(segment.video.location_id or ""),
                "; ".join(
                    presence.display_name for presence in segment.video.characters
                ),
                segment.narrative.function.value,
                _COMPILER.voice_decision_summary(segment),
                "sim" if segment.audio.music.enabled else "não",
                segment.video.transition_out.value,
            )
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _snapshot_lines(snapshot: ContinuitySnapshot) -> list[str]:
    data = snapshot.model_dump(mode="json")
    lines: list[str] = []
    for key, value in data.items():
        if not value:
            continue
        if isinstance(value, dict):
            rendered = "; ".join(f"{name}: {item}" for name, item in value.items())
        elif isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        lines.append(f"- **{key}:** {rendered}")
    return lines or ["- Estado inicial vazio (abertura da produção)."]


def _bullet_list(label: str, items: tuple[str, ...]) -> str:
    if not items:
        return f"- {label}: nenhum"
    return f"- {label}: " + "; ".join(items)


def _section_list(title: str, items: tuple[str, ...]) -> list[str]:
    lines = [f"## {title}", ""]
    if items:
        lines += [f"- {item}" for item in items]
    else:
        lines.append("- Nada registrado.")
    lines.append("")
    return lines


def _provider_duration(segment: PromptSegment) -> str:
    seconds = segment.duration.provider_seconds
    if seconds is None:
        return "igual à narrativa (nenhuma recompilação necessária)"
    return (
        f"{seconds:.1f}s × {segment.duration.provider_call_count} chamada(s) "
        f"— estratégia: {segment.duration.recompilation_strategy or 'direto'}"
    )


def _language_of(segment: PromptSegment) -> str:
    lines = segment.audio.all_spoken_lines()
    return str(lines[0].language) if lines else "pt-BR"
