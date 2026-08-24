"""Visual Bible Lite (SDD_SPDD.md §40 do briefing do Gate 3C).

Não é um prompt gigante, não é Character Engine, não é Cinematic Engine — é o
menor contrato que responde "que regras fazem imagens diferentes parecerem
parte da mesma obra?". Campos incluídos só porque esta história específica
os exige (continuidade de personagem: Elias e Mariana aparecem repetidamente;
continuidade de objeto: o relógio de vidro é o hero object; continuidade de
ambiente: a oficina/Portovelho recorrem). Campos descartados por falta de
necessidade real nesta história: `camera_language` detalhado (planos
específicos, não uma "cinematic engine" de câmera), `period_language`
separado (dobrado em `continuity_constraints` — a história é deliberadamente
atemporal), `recurring_objects` genérico (só há um hero object real).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class CharacterVisual:
    name: str
    approximate_age: str
    physical_appearance: str
    hair: str
    wardrobe: str
    distinguishing_features: str
    visual_demeanor: str

    def continuity_text(self) -> str:
        return (
            f"{self.name} ({self.approximate_age}): {self.physical_appearance}. "
            f"Cabelo: {self.hair}. Vestuário: {self.wardrobe}. "
            f"Traços distintivos: {self.distinguishing_features}. "
            f"Presença: {self.visual_demeanor}."
        )


@dataclass(frozen=True, slots=True)
class HeroObjectVisual:
    name: str
    description: str
    distinctive_features: str

    def continuity_text(self) -> str:
        return f"{self.name}: {self.description} Traços distintivos: {self.distinctive_features}"


@dataclass(frozen=True, slots=True)
class VisualBibleLite:
    version: str
    overall_style: str
    realism_level: str
    color_language: str
    lighting: str
    environment_language: str
    mood: str
    characters: tuple[CharacterVisual, ...]
    hero_object: HeroObjectVisual
    forbidden_elements: tuple[str, ...]
    continuity_constraints: tuple[str, ...]

    def to_dict(self) -> dict:
        """Forma canônica para hashing (`structural_hash`) — usada por todo
        driver que precisa registrar/comparar a versão da Visual Bible em uso."""
        return {
            "version": self.version,
            "overall_style": self.overall_style,
            "realism_level": self.realism_level,
            "color_language": self.color_language,
            "lighting": self.lighting,
            "environment_language": self.environment_language,
            "mood": self.mood,
            "characters": [asdict(c) for c in self.characters],
            "hero_object": asdict(self.hero_object),
            "forbidden_elements": list(self.forbidden_elements),
            "continuity_constraints": list(self.continuity_constraints),
        }

    def global_style_prefix(self) -> str:
        """A parte "GLOBAL VISUAL LANGUAGE" da fórmula de prompt (Gate 3C §29)."""
        return (
            f"{self.overall_style} {self.realism_level} "
            f"Paleta e cor: {self.color_language} "
            f"Iluminação: {self.lighting} "
            f"Atmosfera: {self.mood}"
        )

    def character_by_name(self, name: str) -> CharacterVisual | None:
        for character in self.characters:
            if character.name == name:
                return character
        return None


# Visual Bible desta produção específica ("O Relojoeiro de Vidro") — decisão
# artística registrada, derivada do roteiro aprovado, sem contradizer nada
# nele. Elementos não definidos no roteiro (aparência física exata) foram
# escolhidos aqui deliberadamente e ficam registrados, não inventados de
# forma oculta em cada prompt separadamente.
#
# v1_gate3c — versão original, usada para gerar as 5 imagens do Gate 3C.
# Aprovada (HUMAN_PASS_WITH_NOTES) com dois achados empíricos de
# continuidade: variação na aparência de Elias entre imagens, e relógio de
# vidro gerado com caixa metálica visível. Mantida aqui, inalterada, como
# registro histórico/auditável — não editar retroativamente.
RELOJOEIRO_VISUAL_BIBLE = VisualBibleLite(
    version="v1_gate3c",
    overall_style=(
        "Realismo mágico cinematográfico, atmosfera latino-americana/brasileira "
        "de cidade pequena, sobrenatural sutil e nunca explícito."
    ),
    realism_level="Materiais e texturas realistas — pele, madeira, vidro, metal, tecido — sem estilização cartunesca.",
    color_language=(
        "Paleta restrita: âmbar/dourado quente (luz de lampião) contra azul-petróleo "
        "frio (noite/sombra) — a mesma dualidade cromática em toda a produção."
    ),
    lighting="Luz natural ou de lampião, direcional e suave, nunca uniforme ou 'estúdio'; sombras longas.",
    environment_language=(
        "Portovelho: cidade pequena litorânea/serrana, casas baixas de telhado escuro, "
        "pouca luz elétrica à noite. Oficina de Elias: estreita, madeira envelhecida, "
        "vitrine com dezessete relógios em horas diferentes, bancada de relojoeiro, "
        "lampião aceso mesmo de dia."
    ),
    mood="Melancólico, contido, com tensão silenciosa — nunca ação explícita ou violência.",
    characters=(
        CharacterVisual(
            name="Elias Varga",
            approximate_age="Aparenta 62 anos, mas com uma qualidade atemporal/cansada nos olhos",
            physical_appearance="Alto, curvado, magro, pele clara castigada pelo tempo",
            hair="Branco, ralo, penteado para trás",
            wardrobe="Avental de couro gasto de relojoeiro sobre camisa simples, sempre o mesmo traje",
            distinguishing_features="Mãos de artesão, lupa de relojoeiro presa ao olho ou no bolso, postura curvada sobre a bancada",
            visual_demeanor="Precisão contida, cansaço antigo, olhar distante mesmo quando presente",
        ),
        CharacterVisual(
            name="Mariana Duarte",
            approximate_age="34 anos",
            physical_appearance="Baixa estatura, compleição comum, expressão observadora e séria",
            hair="Castanho escuro, preso em coque simples de trabalho",
            wardrobe="Roupas discretas de funcionária pública — blazer/casaco simples, sem adornos",
            distinguishing_features="Postura ereta e atenta, mãos frequentemente seguras (documentos, o relógio)",
            visual_demeanor="Reservada, precisa, observadora — nunca dramática nos gestos",
        ),
    ),
    hero_object=HeroObjectVisual(
        name="O relógio de vidro",
        description=(
            "Relógio de bolso feito inteiramente de vidro transparente, engrenagens "
            "internas visíveis e finas como se desenhadas no ar, tamanho de um relógio "
            "de bolso comum (cabe na palma da mão)."
        ),
        distinctive_features=(
            "Uma inscrição minúscula gravada por dentro do vidro (não na superfície), "
            "legível apenas de perto; ponteiro dos minutos visivelmente quebrado até o "
            "clímax da história. Nunca mostrar o texto da inscrição de forma legível "
            "(ver política de texto em imagem, §19)."
        ),
    ),
    forbidden_elements=(
        "violência gráfica",
        "marcas registradas reais",
        "celebridades ou pessoas reais",
        "texto legível gerado dentro da imagem",
        "elementos tecnológicos modernos óbvios (smartphones, carros modernos, telas)",
    ),
    continuity_constraints=(
        "Época deliberadamente indefinida/atemporal — sem marcadores claros de década.",
        "Elias e Mariana devem manter a mesma aparência (rosto, cabelo, roupa) em toda imagem em que aparecem.",
        "O relógio de vidro deve ser reconhecível como o mesmo objeto em toda imagem em que aparece.",
        "A dualidade cromática âmbar/azul-petróleo deve estar presente em toda imagem, em proporção variável conforme a cena.",
    ),
)


# v2_gate3d_hardened — revisão de reforço de continuidade (Gate 3D), NÃO um
# redesenho. `overall_style`, `realism_level`, `color_language`, `lighting`,
# `environment_language` e `mood` são idênticos a v1_gate3c — só os campos com
# falha empírica observada no Gate 3C (Elias, hero object) e a tolerância de
# contagem de relógios foram reforçados/adicionados.
#
# HARDENING_REASON: o Gate 3C gerou 5 imagens reais e revisão humana (com
# achados já sinalizados antes do julgamento) identificou duas fraquezas de
# continuidade reais, não hipotéticas: (1) Elias variou em idade
# aparente/presença de barba entre as imagens A e D — a v1 não travava uma
# política de barba nem uma silhueta explícita; (2) o relógio de vidro foi
# gerado com caixa/aro metálico visível — a v1 dizia "inteiramente de vidro"
# mas não proibia explicitamente uma caixa metálica como elemento negativo.
# Esta revisão só torna esses dois pontos mais explícitos e travados, e
# formaliza a contagem de relógios como intenção/melhor esforço (15-18
# aceitável) para não desperdiçar gerações boas regenerando por causa de um
# detalhe secundário que o próprio briefing do gate classificou como
# best-effort, não requisito rígido.
RELOJOEIRO_VISUAL_BIBLE_HARDENED = VisualBibleLite(
    version="v2_gate3d_hardened",
    overall_style=RELOJOEIRO_VISUAL_BIBLE.overall_style,
    realism_level=RELOJOEIRO_VISUAL_BIBLE.realism_level,
    color_language=RELOJOEIRO_VISUAL_BIBLE.color_language,
    lighting=RELOJOEIRO_VISUAL_BIBLE.lighting,
    environment_language=RELOJOEIRO_VISUAL_BIBLE.environment_language,
    mood=RELOJOEIRO_VISUAL_BIBLE.mood,
    characters=(
        CharacterVisual(
            name="Elias Varga",
            approximate_age=(
                "Sempre aparenta exatamente 62 anos em toda imagem — nunca mais jovem, "
                "nunca mais velho; qualidade atemporal/cansada nos olhos, mas idade "
                "facial estável."
            ),
            physical_appearance=(
                "Alto, curvado, magro, pele clara castigada pelo tempo, rosto alongado "
                "com rugas marcadas na testa e ao redor dos olhos — mesma estrutura "
                "facial (formato do rosto, nariz, queixo) idêntica em toda imagem; "
                "silhueta magra e curvada para frente, reconhecível mesmo em plano aberto."
            ),
            hair="Sempre branco, ralo, penteado para trás, mesmo comprimento e recuo em toda imagem — nunca varia.",
            wardrobe=(
                "Sempre o mesmo avental de couro marrom gasto de relojoeiro sobre camisa "
                "cinza simples de mangas arregaçadas — nenhuma outra combinação de roupa "
                "é usada em nenhuma imagem."
            ),
            distinguishing_features=(
                "SEMPRE completamente sem barba (rosto bem barbeado) — nunca gerar Elias "
                "com barba, bigode ou barba por fazer em nenhuma imagem, esta é uma regra "
                "travada, não uma preferência. Mãos de artesão, lupa de relojoeiro presa "
                "ao olho ou no bolso, postura curvada sobre a bancada."
            ),
            visual_demeanor="Precisão contida, cansaço antigo, olhar distante mesmo quando presente",
        ),
        # Mariana não apresentou falha de continuidade observada no Gate 3C —
        # mantida idêntica a v1 (não redesenhar o que já funciona).
        CharacterVisual(
            name="Mariana Duarte",
            approximate_age="34 anos",
            physical_appearance="Baixa estatura, compleição comum, expressão observadora e séria",
            hair="Castanho escuro, preso em coque simples de trabalho",
            wardrobe="Roupas discretas de funcionária pública — blazer/casaco simples, sem adornos",
            distinguishing_features="Postura ereta e atenta, mãos frequentemente seguras (documentos, o relógio)",
            visual_demeanor="Reservada, precisa, observadora — nunca dramática nos gestos",
        ),
    ),
    hero_object=HeroObjectVisual(
        name="O relógio de vidro",
        description=(
            "Relógio de bolso feito INTEIRAMENTE de vidro transparente — SEM NENHUMA "
            "caixa, aro, moldura ou coroa de corda metálica visível em nenhuma parte do "
            "objeto; toda a estrutura externa é vidro ou material transparente, do "
            "mesmo jeito que o vidro que compõe o corpo do relógio. Engrenagens internas "
            "visíveis e finas como se desenhadas no ar, tamanho de um relógio de bolso "
            "comum (cabe na palma da mão)."
        ),
        distinctive_features=(
            "Geometria circular reconhecível e consistente entre imagens (mesmo tamanho "
            "relativo, mesma disposição das engrenagens internas visíveis). Uma "
            "inscrição minúscula gravada por dentro do vidro (não na superfície), "
            "legível apenas de perto — o texto da inscrição não precisa ser legível na "
            "imagem gerada. Ponteiro dos minutos visivelmente quebrado até o clímax da "
            "história. Nunca mostrar o texto da inscrição de forma legível."
        ),
    ),
    forbidden_elements=(
        *RELOJOEIRO_VISUAL_BIBLE.forbidden_elements,
        "caixa, aro ou moldura metálica visível no relógio de vidro",
        "Elias Varga com barba, bigode ou barba por fazer",
    ),
    continuity_constraints=(
        "Época deliberadamente indefinida/atemporal — sem marcadores claros de década.",
        "Elias deve manter idade aparente, estrutura facial, cabelo, silhueta e "
        "vestuário idênticos em toda imagem — nenhuma variação de idade ou presença de "
        "barba é permitida (reforçado no Gate 3D após falha observada no Gate 3C).",
        "Mariana deve manter a mesma aparência (rosto, cabelo, roupa) em toda imagem em que aparece.",
        "O relógio de vidro nunca deve exibir caixa, aro ou moldura metálica — toda a "
        "estrutura externa é vidro transparente (reforçado no Gate 3D após falha "
        "observada no Gate 3C, onde uma caixa metálica apareceu).",
        "A contagem de dezessete relógios na vitrine é intenção narrativa/melhor "
        "esforço — variações entre 15 e 18 relógios são aceitáveis e NÃO exigem nova "
        "geração só por causa da contagem exata.",
        "A dualidade cromática âmbar/azul-petróleo deve estar presente em toda imagem, "
        "em proporção variável conforme a cena.",
    ),
)
