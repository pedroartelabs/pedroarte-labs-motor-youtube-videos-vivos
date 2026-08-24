"""Plano visual completo do Gate 3D — cobre os 650,3s inteiros da narração
aprovada (99 `SentenceBoundary` reais, Gate 3B.2), não só os 5 beats de
prova do Gate 3C.

Princípio (Gate 3D §"MASS GENERATION COST GATE" / discovery Lite): a
contagem de beats não é uma meta fixa — nasce do ritmo narrativo real do
roteiro aprovado. 28 beats resultou de agrupar as 99 sentenças em unidades
visuais coerentes (uma mudança de assunto, de lugar, de personagem em foco,
ou de função dramática = um novo beat; diálogo rápido no mesmo local/momento
= mesmo beat) — não de dividir 650s por um número alvo de imagens.

Os 5 beats do Gate 3C (`beat_A`..`beat_E`, aprovados por revisão humana) são
reaproveitados nas mesmas posições da timeline — não regenerados aqui.
"""

from __future__ import annotations

from pedroarte_youtube_engine.lite.visual_beats import FIVE_SELECTED_BEATS, NarrativeFunction, VisualBeat

_NEW_BEATS: tuple[VisualBeat, ...] = (
    VisualBeat(
        id="beat_02",
        start_seconds=21.9,
        end_seconds=35.9,
        script_excerpt="Fora gravado por dentro, no exato instante em que o vidro ainda era fogo líquido, quarenta anos atrás.",
        narrative_function=NarrativeFunction.MYSTERY,
        subject="O relógio de vidro sendo soprado/moldado ainda incandescente",
        environment="Cena de origem, ambígua no tempo — forno de vidro, luz alaranjada intensa",
        action="Um par de mãos (não identificadas) trabalha o vidro ainda líquido",
        visual_intent="Flashback visual abstrato — não mostrar rosto, só as mãos e o vidro incandescente, reforçando o mistério sem responder ainda.",
        continuity_refs=("O relógio de vidro",),
    ),
    VisualBeat(
        id="beat_03",
        start_seconds=35.9,
        end_seconds=65.5,
        script_excerpt="Portovelho é uma cidade pequena demais para ter segredos grandes... casas baixas, de telhado escuro.",
        narrative_function=NarrativeFunction.ESTABLISHING,
        subject="Vista aberta de Portovelho — telhados baixos, rio ao fundo, serra distante",
        environment="Cidade pequena litorânea/serrana, entardecer/noite, pouca luz elétrica",
        action="Nenhuma — plano estabelecedor amplo",
        visual_intent="Plano aberto, grande angular, estabelecendo o mundo inteiro antes de aproximar da oficina no beat_B.",
        continuity_refs=("Portovelho",),
    ),
    VisualBeat(
        id="beat_04",
        start_seconds=80.5,
        end_seconds=100.6,
        script_excerpt="Há uma regra ali, repetida em voz baixa por gerações: nunca se conserta um relógio parado depois da meia-noite.",
        narrative_function=NarrativeFunction.MYSTERY,
        subject="Um relógio parado sobre a bancada, à luz de lampião, tarde da noite",
        environment="Interior da oficina, escuro, só o lampião aceso",
        action="Nenhuma pessoa em quadro — o relógio parado é o sujeito",
        visual_intent="Plano fechado no relógio parado, sombra e silêncio — estabelece a regra central antes de qualquer personagem aparecer.",
        continuity_refs=("Oficina de Elias",),
    ),
    VisualBeat(
        id="beat_05",
        start_seconds=100.6,
        end_seconds=117.2,
        script_excerpt="Foi Mariana Duarte quem trouxe o relógio de vidro para dentro dessa história. Trinta e quatro anos, funcionária do cartório...",
        narrative_function=NarrativeFunction.CHARACTER,
        subject="Retrato de Mariana Duarte",
        environment="Fundo neutro/cartório desfocado, luz de dia comum",
        action="Mariana olha diretamente, expressão observadora — apresentação do personagem",
        visual_intent="Plano médio/retrato, primeira aparição de Mariana no vídeo, estabelece a aparência canônica dela.",
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_06",
        start_seconds=117.2,
        end_seconds=147.7,
        script_excerpt="O relógio era dele, encontrado dentro de uma caixa de papelão na casa antiga... relógio de bolso feito inteiramente de vidro.",
        narrative_function=NarrativeFunction.DISCOVERY,
        subject="Mariana abrindo a caixa de papelão com pertences do pai",
        environment="Casa antiga, quarto/sótão empoeirado, luz de janela",
        action="Mariana encontra o relógio de vidro dentro da caixa, entre cartas antigas",
        visual_intent="Plano médio-fechado, novo ambiente (casa do pai) — primeira vez que o relógio de vidro é mostrado por inteiro fora da oficina.",
        continuity_refs=("Mariana Duarte", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_07",
        start_seconds=147.7,
        end_seconds=165.7,
        script_excerpt="E, bem no meio do mecanismo... aquela inscrição impossível... Mariana não acreditou em coincidência.",
        narrative_function=NarrativeFunction.REVELATION,
        subject="Extreme close-up do mecanismo do relógio de vidro e da inscrição",
        environment="Sem ambiente — macro no objeto, fundo escuro",
        action="Nenhuma — o objeto é o foco absoluto",
        visual_intent="Macro/extreme close-up nas engrenagens visíveis, ecoando o beat_A mas de um ângulo diferente (mais próximo, mais técnico).",
        continuity_refs=("O relógio de vidro",),
    ),
    VisualBeat(
        id="beat_08",
        start_seconds=184.3,
        end_seconds=208.2,
        script_excerpt="Encontrou, entre as caixas de 1986, três registros com o sobrenome Varga... Ela fotografou a página duas vezes.",
        narrative_function=NarrativeFunction.DISCOVERY,
        subject="Mariana fotografando um documento antigo com as mãos trêmulas",
        environment="Arquivo morto do cartório (mesmo ambiente do beat_C)",
        action="Mariana seguraa uma certidão antiga, fotografando-a",
        visual_intent="Plano fechado nas mãos e no documento — tensão de descoberta crescente, mesmo ambiente do beat_C mas ação diferente (documentar, não só ler).",
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_09",
        start_seconds=208.2,
        end_seconds=232.0,
        script_excerpt="Era o quinto — talvez o sexto — nascimento forjado de Elias Varga... Ela reconheceu duas dessas assinaturas.",
        narrative_function=NarrativeFunction.REVELATION,
        subject="Várias certidões antigas espalhadas, assinaturas visíveis (não legíveis em detalhe)",
        environment="Mesa do arquivo morto, luz de lanterna/lampião portátil",
        action="Mariana organiza/compara os documentos lado a lado",
        visual_intent="Plano de cima (top-down) dos documentos — comunica a escala da descoberta (múltiplas décadas) sem depender de texto legível.",
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_10",
        start_seconds=232.1,
        end_seconds=254.8,
        script_excerpt="Quando ela voltou à oficina, de manhã, encontrou Elias sentado exatamente onde o deixara na véspera.",
        narrative_function=NarrativeFunction.CHARACTER,
        subject="Elias sozinho na oficina, sentado à bancada, luz da manhã entrando",
        environment="Interior da oficina, manhã, lampião ainda aceso mesmo com sol",
        action="Elias trabalha silenciosamente, sem perceber ainda a chegada de Mariana",
        visual_intent="Plano médio, momento de calma antes da confrontação — estabelece Elias sozinho, imóvel, antes do beat_D.",
        continuity_refs=("Elias Varga", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_11",
        start_seconds=266.4,
        end_seconds=283.2,
        script_excerpt="Elias não negou. Passou a mão pelo vidro do relógio, devagar, como quem acaricia um animal que pode morder.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Close-up nas mãos de Elias tocando o relógio de vidro sobre a bancada",
        environment="Bancada da oficina, mesmo ambiente do beat_D",
        action="Elias toca o vidro devagar, olhar baixo, sem responder ainda",
        visual_intent="Close-up nas mãos e no objeto — pausa emocional logo após a acusação de Mariana no beat_D.",
        continuity_refs=("Elias Varga", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_12",
        start_seconds=283.2,
        end_seconds=308.1,
        script_excerpt="Portovelho tem uma dívida — disse ele... As pessoas param. Envelhecem errado, adoecem sem causa.",
        narrative_function=NarrativeFunction.REVELATION,
        subject="Elias falando, olhando para Mariana, expressão grave",
        environment="Interior da oficina, luz de lampião, mesmo ambiente do beat_D",
        action="Elias explica a dívida da cidade",
        visual_intent="Plano médio em Elias, foco no rosto durante a explicação — início do monólogo central da história.",
        continuity_refs=("Elias Varga", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_13",
        start_seconds=308.1,
        end_seconds=342.0,
        script_excerpt="Eu descobri, há muito tempo, que dá para pagar essa dívida com tempo emprestado... Nunca consertar depois da meia-noite?",
        narrative_function=NarrativeFunction.MYSTERY,
        subject="Um relógio parado sendo consertado à luz de vela/lampião, à noite",
        environment="Bancada da oficina, à noite, ambiente isolado e simbólico",
        action="Mãos de Elias trabalhando um relógio parado — ilustração conceitual do 'tempo emprestado'",
        visual_intent="Imagem simbólica/conceitual (não literal da cena de diálogo) — representa visualmente a explicação de Elias sem repetir o mesmo plano de rosto.",
        continuity_refs=("Elias Varga", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_14",
        start_seconds=342.0,
        end_seconds=370.7,
        script_excerpt="Este relógio é meu, Mariana. Fui eu quem o fez, na noite em que nasci pela primeira vez... paguei a primeira dívida da cidade.",
        narrative_function=NarrativeFunction.CLIMAX,
        subject="Elias, close-up emocional, revelando a origem do relógio",
        environment="Bancada da oficina, luz de lampião concentrada no rosto",
        action="Elias fala olhando diretamente para Mariana (fora de quadro ou em perfil)",
        visual_intent="Close-up dramático — o momento de maior revelação pessoal de Elias até aqui.",
        continuity_refs=("Elias Varga", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_15",
        start_seconds=370.7,
        end_seconds=396.3,
        script_excerpt="Desde então, minto para continuar vivo... É um empréstimo que nunca fecha, e que eu deixei de saber calcular há muito tempo.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="O relógio de vidro sozinho sobre a bancada, foco nele, Elias desfocado ao fundo",
        environment="Bancada da oficina",
        action="Nenhuma ação — pausa contemplativa",
        visual_intent="Plano com profundidade de campo: relógio nítido em primeiro plano, Elias desfocado atrás — ilustra o peso do 'empréstimo que nunca fecha'.",
        continuity_refs=("O relógio de vidro", "Elias Varga"),
    ),
    VisualBeat(
        id="beat_16",
        start_seconds=396.3,
        end_seconds=415.6,
        script_excerpt="Ela olhou para a certidão do próprio pai, dobrada dentro da bolsa... Óbito em março.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Mariana segurando a certidão de óbito do pai, olhar distante",
        environment="Interior da oficina, junto à bancada",
        action="Mariana olha para o documento, momento pessoal e silencioso",
        visual_intent="Close-up em Mariana e no documento — muda o foco emocional dela para o próprio pai, não mais para Elias.",
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_17",
        start_seconds=415.6,
        end_seconds=436.7,
        script_excerpt="O senhor pegou o tempo do meu pai — disse ela... Ele já estava parando sozinho, havia anos.",
        narrative_function=NarrativeFunction.CONFRONTATION,
        subject="Mariana e Elias frente a frente, tensão direta",
        environment="Bancada da oficina, mesmo ambiente do beat_D",
        action="Mariana acusa diretamente; Elias começa a se explicar",
        visual_intent="Dois-shot, ângulo diferente do beat_D — continuação direta da confrontação, mais intensa.",
        continuity_refs=("Elias Varga", "Mariana Duarte", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_18",
        start_seconds=436.7,
        end_seconds=460.6,
        script_excerpt="Segurei tempo demais, talvez... Eu estou cansado, Mariana, e uma dívida cobrada por alguém cansado começa a cobrar errado.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Close-up no rosto cansado de Elias",
        environment="Bancada da oficina, luz baixa",
        action="Elias admite seu cansaço, olhar baixo",
        visual_intent="Close extremo no rosto — o momento de maior vulnerabilidade de Elias na história.",
        continuity_refs=("Elias Varga",),
    ),
    VisualBeat(
        id="beat_19",
        start_seconds=460.6,
        end_seconds=482.2,
        script_excerpt="O silêncio que se seguiu durou mais do que qualquer relógio... O que aconteceria se o senhor consertasse esse relógio agora?",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Mariana, expressão decidida, prestes a fazer a pergunta que muda tudo",
        environment="Bancada da oficina",
        action="Mariana quebra o silêncio com a pergunta central da história",
        visual_intent="Plano médio em Mariana — ponto de virada narrativo, ela toma a iniciativa.",
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_20",
        start_seconds=482.2,
        end_seconds=497.5,
        script_excerpt="Elias sorriu, pela primeira vez, um sorriso cansado e quase aliviado... Ninguém nunca tentou devolver.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Elias sorrindo — a primeira vez na história",
        environment="Bancada da oficina",
        action="Elias reage com um sorriso raro à pergunta de Mariana",
        visual_intent="Close-up capturando o sorriso — momento emocional único, não repetido em nenhum outro beat.",
        continuity_refs=("Elias Varga",),
    ),
    VisualBeat(
        id="beat_21",
        start_seconds=497.5,
        end_seconds=519.6,
        script_excerpt="Ele pegou a lupa, girou o relógio contra a luz da manhã, e encontrou... um espaço vazio, longo o suficiente para outro nome.",
        narrative_function=NarrativeFunction.REVELATION,
        subject="Extreme close-up do relógio de vidro através da lupa, mostrando o espaço vazio para gravação",
        environment="Bancada, luz da manhã",
        action="Elias examina o relógio com a lupa",
        visual_intent="Macro através da lupa — ecoa o beat_A/beat_07, fechando o círculo visual do objeto antes do clímax.",
        continuity_refs=("Elias Varga", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_22",
        start_seconds=519.6,
        end_seconds=538.5,
        script_excerpt="Ele consertou o relógio ali mesmo, ao meio-dia, com o sol batendo direto na vitrine... Gravou um segundo nome ao lado do seu.",
        narrative_function=NarrativeFunction.CLIMAX,
        subject="Elias gravando o novo nome no relógio de vidro, à luz plena do meio-dia",
        environment="Bancada da oficina, agora banhada de luz de sol direta — contraste com todas as cenas noturnas anteriores",
        action="Elias trabalha com uma agulha fina, gravando o vidro",
        visual_intent="Mudança de iluminação deliberada (dia pleno, não lampião) — sinaliza visualmente a virada da história: repor em vez de tomar emprestado.",
        continuity_refs=("Elias Varga", "O relógio de vidro", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_23",
        start_seconds=538.5,
        end_seconds=558.6,
        script_excerpt="Como uma dívida quitada, devolvida à origem... O ponteiro dos minutos, que estivera quebrado, moveu-se sozinho, uma única vez, e parou.",
        narrative_function=NarrativeFunction.RESOLUTION,
        subject="Close-up no ponteiro dos minutos do relógio de vidro se movendo",
        environment="Bancada, luz de meio-dia",
        action="O ponteiro, antes quebrado, move-se sozinho",
        visual_intent="Close extremo no mecanismo — o primeiro sinal visual de que a dívida foi quitada, sem precisar de texto.",
        continuity_refs=("O relógio de vidro",),
    ),
    VisualBeat(
        id="beat_24",
        start_seconds=558.6,
        end_seconds=573.2,
        script_excerpt="Naquela tarde... a oficina de Elias Varga fechou. A porta de madeira inchada... ganhou uma chave virada por dentro.",
        narrative_function=NarrativeFunction.RESOLUTION,
        subject="A porta da oficina sendo fechada/trancada, vista de dentro ou de fora",
        environment="Entrada da oficina, fim de tarde",
        action="A porta se fecha — primeira vez na história",
        visual_intent="Plano da porta fechando — transição visual entre o interior (clímax) e o exterior (payoff da vitrine no beat_E).",
        continuity_refs=("Oficina de Elias",),
    ),
    VisualBeat(
        id="beat_25",
        start_seconds=588.3,
        end_seconds=613.7,
        script_excerpt="Mariana ficou na calçada, olhando pela vitrine escura... Ela não sabia dizer se Elias tinha finalmente morrido, ou se tinha ido para casa.",
        narrative_function=NarrativeFunction.EMOTIONAL,
        subject="Mariana sozinha na calçada, olhando para a vitrine escura da oficina fechada",
        environment="Rua estreita de Portovelho, fim de tarde/entardecer, oficina fechada ao fundo",
        action="Mariana observa em silêncio, contemplativa",
        visual_intent="Plano médio/aberto, Mariana pequena diante da vitrine — eco visual do beat_B/beat_E mas agora com a personagem em quadro, sozinha.",
        continuity_refs=("Mariana Duarte", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_26",
        start_seconds=613.7,
        end_seconds=650.2,
        script_excerpt="O que ficou foi a cidade, respirando num ritmo mais lento... quantas dívidas silenciosas uma cidade inteira pode dever?",
        narrative_function=NarrativeFunction.RESOLUTION,
        subject="Vista final e ampla de Portovelho ao entardecer/anoitecer",
        environment="Cidade inteira, mesmo tipo de plano do beat_03, agora em tom mais calmo/resolvido",
        action="Nenhuma — imagem de fechamento",
        visual_intent="Plano de encerramento, callback ao beat_03 (mesma cidade, tom emocional diferente — mais calmo, resolvido) — última imagem do vídeo.",
        continuity_refs=("Portovelho",),
    ),
)

GATE3D_FULL_VISUAL_PLAN: tuple[VisualBeat, ...] = tuple(
    sorted((*FIVE_SELECTED_BEATS, *_NEW_BEATS), key=lambda beat: beat.start_seconds)
)


def validate_plan_coverage(
    plan: tuple[VisualBeat, ...], *, total_duration_seconds: float, gap_tolerance_seconds: float = 0.5
) -> dict[str, object]:
    """Confere que o plano cobre a narração inteira, sem furos nem sobreposição
    relevante — não confia cegamente no agrupamento manual dos beats."""
    ordered = sorted(plan, key=lambda beat: beat.start_seconds)
    gaps: list[tuple[float, float, str]] = []
    previous_end = 0.0
    for beat in ordered:
        if beat.start_seconds - previous_end > gap_tolerance_seconds:
            gaps.append((previous_end, beat.start_seconds, beat.id))
        previous_end = max(previous_end, beat.end_seconds)
    return {
        "beat_count": len(ordered),
        "covers_full_duration": abs(previous_end - total_duration_seconds) <= gap_tolerance_seconds * 2,
        "final_end_seconds": previous_end,
        "gaps": gaps,
        "status": "PASS" if not gaps and abs(previous_end - total_duration_seconds) <= gap_tolerance_seconds * 2 else "FAIL",
    }


# Política de reuso (SDD_SPDD.md §57-58 do briefing de Gate 3D): as 5 imagens
# aprovadas no Gate 3C NÃO são rejeitadas automaticamente por exibirem um dos
# desvios históricos que motivaram o endurecimento da Visual Bible. Só seriam
# regeneradas se o desvio ficasse materialmente perceptível na montagem final
# — decisão registrada por asset, não decidida unilateralmente aqui.
GATE3C_ASSET_REUSE_DECISIONS: tuple[dict[str, object], ...] = (
    {
        "beat_id": "beat_A",
        "decision": "REUSE",
        "flag": "monitorar",
        "reason": (
            "Relógio aparece com caixa metálica visível (desvio que motivou o "
            "endurecimento). É a primeira aparição do hero object no vídeo — "
            "recomenda-se reavaliar na montagem final se esse plano-âncora "
            "estabelece uma imagem mental incorreta do objeto para o resto do vídeo."
        ),
    },
    {"beat_id": "beat_B", "decision": "REUSE", "flag": "nenhum", "reason": "Sem desvio observado — ambiente puro, sem personagem nem hero object em close."},
    {"beat_id": "beat_C", "decision": "REUSE", "flag": "nenhum", "reason": "Sem desvio observado — Mariana não apresentou variação de continuidade."},
    {
        "beat_id": "beat_D",
        "decision": "REUSE",
        "flag": "monitorar",
        "reason": (
            "Instância real da variação de barba/idade de Elias que motivou o "
            "endurecimento. Cena de confrontação no meio do vídeo, não a "
            "âncora visual do personagem — recomenda-se reavaliar na montagem "
            "se o corte ao lado de beats com Elias sem barba (ex. beat_10, "
            "beat_12) torna a inconsistência perceptível em sequência."
        ),
    },
    {"beat_id": "beat_E", "decision": "REUSE", "flag": "nenhum", "reason": "Sem desvio de personagem/objeto — a contagem de relógios é tolerada por política, não é motivo de regeneração."},
)


def estimate_mass_generation_cost(
    *,
    new_images_required: int,
    per_image_low_usd: float = 0.02,
    per_image_high_usd: float = 0.20,
    assumed_retry_rate: float = 0.15,
    max_attempts_per_beat: int = 2,
) -> dict[str, object]:
    """Estimativa de custo — nunca inventa um valor exato (a API não retorna
    preço por chamada de geração de imagem, já registrado no Gate 3C).
    `assumed_retry_rate` é uma suposição explícita, não um dado observado:
    o Gate 3C teve 0% de retries em 5 imagens, mas uma amostra de 5 não é
    suficiente para projetar a taxa real em 25."""
    estimated_retries = round(new_images_required * assumed_retry_rate)
    total_generations_low = new_images_required + estimated_retries
    total_generations_high = new_images_required + min(
        estimated_retries * max_attempts_per_beat, new_images_required
    )
    return {
        "new_images_required": new_images_required,
        "assumed_retry_rate": assumed_retry_rate,
        "estimated_retries": estimated_retries,
        "per_image_cost_range_usd": [per_image_low_usd, per_image_high_usd],
        "estimated_total_cost_usd_range": [
            round(total_generations_low * per_image_low_usd, 2),
            round(total_generations_high * per_image_high_usd, 2),
        ],
        "note": (
            "Faixa estimada a partir da experiência real do Gate 3C (5 imagens, "
            "custo total aceito ~US$0,10-1,00) — não um valor garantido pela API."
        ),
    }
