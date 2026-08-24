"""Compõe `ImageGenerationRequest` a partir de Visual Bible + Visual Beat
(Gate 3C §29-30):

    PROMPT = GLOBAL VISUAL LANGUAGE + SCENE REQUIREMENTS +
             CHARACTER/OBJECT CONTINUITY + COMPOSITION + NEGATIVE CONSTRAINTS

Não uma lista infinita de adjetivos — instruções concretas: sujeito, ação,
ambiente, composição, iluminação, materiais, continuidade, proibições.
Reutiliza `ImageGenerationRequest`/`ImageGenerationPort` do Gate 2 sem
nenhuma mudança de forma — mais um consumidor real do mesmo contrato.
"""

from __future__ import annotations

from pathlib import Path

from pedroarte_youtube_engine.lite.images.ports import ImageGenerationRequest
from pedroarte_youtube_engine.lite.visual_bible import VisualBibleLite
from pedroarte_youtube_engine.lite.visual_beats import VisualBeat


def _continuity_block(bible: VisualBibleLite, beat: VisualBeat) -> str:
    lines: list[str] = []
    for ref in beat.continuity_refs:
        character = bible.character_by_name(ref)
        if character is not None:
            lines.append(character.continuity_text())
        elif ref == bible.hero_object.name:
            lines.append(bible.hero_object.continuity_text())
        else:
            lines.append(ref)
    return " | ".join(lines)


def build_image_request(
    *, bible: VisualBibleLite, beat: VisualBeat, output_path: Path, width: int = 1920, height: int = 1080
) -> ImageGenerationRequest:
    scene_requirements = (
        f"CENA: {beat.subject}. AÇÃO: {beat.action}. AMBIENTE: {beat.environment}."
    )
    continuity = f"CONTINUIDADE: {_continuity_block(bible, beat)}."
    composition = f"COMPOSIÇÃO: {beat.visual_intent}"
    prompt = "\n".join([scene_requirements, continuity, composition])

    negative = ", ".join(bible.forbidden_elements) + (
        ", texto/legendas sobrepostas, marca d'água, assinatura, "
        "mãos deformadas, membros extras, simetria artificial, "
        "engrenagens fisicamente incoerentes"
    )

    return ImageGenerationRequest(
        prompt=prompt,
        output_path=output_path,
        width=width,
        height=height,
        negative_constraints=negative,
        style_prefix=bible.global_style_prefix(),
    )
