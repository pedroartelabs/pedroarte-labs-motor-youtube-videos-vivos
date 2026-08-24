"""Visual Beat — unidade narrativa durante a qual uma composição visual pode
permanecer semanticamente válida (Gate 3C §6-7). NÃO é `1 SentenceBoundary =
1 beat`: os 99 boundaries reais do Gate 3B.2 são a fonte de tempo, mas um
beat agrupa vários quando formam uma única ideia visual.

Campo descartado da hipótese original do briefing: `importance` — sem
consumidor real nesta fase (nenhum código lê esse campo para decidir nada
ainda). Se um consumidor real aparecer (ex.: priorização automática de quais
beats gerar primeiro em escala), adicionar então, não antes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NarrativeFunction(StrEnum):
    HOOK = "hook"
    ESTABLISHING = "establishing"
    CHARACTER = "character"
    DISCOVERY = "discovery"
    MYSTERY = "mystery"
    CONFRONTATION = "confrontation"
    REVELATION = "revelation"
    EMOTIONAL = "emotional"
    CLIMAX = "climax"
    RESOLUTION = "resolution"


@dataclass(frozen=True, slots=True)
class VisualBeat:
    id: str
    start_seconds: float
    end_seconds: float
    script_excerpt: str
    narrative_function: NarrativeFunction
    subject: str
    environment: str
    action: str
    visual_intent: str
    continuity_refs: tuple[str, ...]
    # Gate 3D: aponta para um asset já aprovado no Gate 3C (ex. "beat_A") em
    # vez de exigir nova geração. `None` = precisa de imagem nova. Campo
    # adicionado só porque o Gate 3D tem um consumidor real para ele (a
    # política de reuso de assets aprovados, SDD_SPDD.md §57-58).
    reuse_of: str | None = None

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @property
    def requires_new_generation(self) -> bool:
        return self.reuse_of is None


# Os 5 beats experimentais do Gate 3C, com timestamps reais extraídos de
# runs/20260823T200332Z-gate3b2-full-narration/assets/narration/narration_full.timing.json
# (99 SentenceBoundary, 650.3s) — não estimados por word count. Selecionados
# para testar simultaneamente: continuidade de objeto, de ambiente, de
# personagem, composição multi-personagem e o payoff visual final (Gate 3C §20-21).
FIVE_SELECTED_BEATS: tuple[VisualBeat, ...] = (
    VisualBeat(
        id="beat_A",
        reuse_of="beat_A",
        start_seconds=0.1,
        end_seconds=21.9,
        script_excerpt=(
            "Há um nome gravado dentro de um relógio de vidro, num lugar onde nenhuma "
            "ferramenta jamais poderia ter chegado... Elias Varga olhou para aquelas "
            "letras e sentiu o rosto perder a cor."
        ),
        narrative_function=NarrativeFunction.HOOK,
        subject="Elias Varga segurando o relógio de vidro, olhando para dentro dele",
        environment="Bancada de relojoeiro, close-up, fundo desfocado da oficina",
        action="Elias observa, com a lupa, a inscrição impossível gravada por dentro do vidro",
        visual_intent=(
            "Close/plano médio, foco total no relógio e na reação de Elias — o "
            "primeiro objeto e o primeiro mistério da história."
        ),
        continuity_refs=("Elias Varga", "O relógio de vidro"),
    ),
    VisualBeat(
        id="beat_B",
        reuse_of="beat_B",
        start_seconds=65.5,
        end_seconds=80.5,
        script_excerpt=(
            "No centro, na esquina mais estreita, fica a oficina de Elias Varga... "
            "A vitrine tem dezessete relógios, e nenhum deles marca a hora certa."
        ),
        narrative_function=NarrativeFunction.ESTABLISHING,
        subject="A fachada/vitrine da oficina de relojoaria",
        environment="Esquina estreita de Portovelho, vitrine com dezessete relógios visíveis",
        action="Nenhuma — plano estabelecedor, sem personagens em primeiro plano",
        visual_intent=(
            "Plano aberto estabelecendo o mundo: a rua estreita, a vitrine cheia de "
            "relógios em horas diferentes, a atmosfera âmbar/azul da cidade."
        ),
        continuity_refs=("Oficina de Elias", "Dezessete relógios da vitrine", "Portovelho"),
    ),
    VisualBeat(
        id="beat_C",
        reuse_of="beat_C",
        start_seconds=165.7,
        end_seconds=184.3,
        script_excerpt=(
            "Voltou ao cartório na mesma noite, desceu ao arquivo morto... Encontrou, "
            "entre as caixas de 1986, três registros com o sobrenome Varga."
        ),
        narrative_function=NarrativeFunction.DISCOVERY,
        subject="Mariana Duarte, sozinha, entre prateleiras de arquivo",
        environment="Arquivo morto do cartório — prateleiras de metal, caixas antigas, pouca luz",
        action="Mariana folheia/examina documentos antigos, momento de descoberta silenciosa",
        visual_intent=(
            "Plano médio, Mariana isolada num espaço apertado e empoeirado — tensão "
            "de descoberta, não de perigo."
        ),
        continuity_refs=("Mariana Duarte",),
    ),
    VisualBeat(
        id="beat_D",
        reuse_of="beat_D",
        start_seconds=254.8,
        end_seconds=266.4,
        script_excerpt=(
            "Ela colocou a certidão sobre a bancada, ao lado do relógio de vidro... "
            "— O senhor não nasceu em 1986 — disse ela."
        ),
        narrative_function=NarrativeFunction.CONFRONTATION,
        subject="Elias Varga e Mariana Duarte, frente a frente, na oficina",
        environment="Interior da oficina, bancada entre os dois, relógio de vidro visível sobre ela",
        action="Mariana confronta Elias com a certidão; Elias reage com calma tensa",
        visual_intent=(
            "Composição de dois personagens (multi-character) — a bancada e o "
            "relógio de vidro como ponto focal entre eles, luz de lampião dividindo "
            "os dois em âmbar e sombra."
        ),
        continuity_refs=("Elias Varga", "Mariana Duarte", "O relógio de vidro", "Oficina de Elias"),
    ),
    VisualBeat(
        id="beat_E",
        reuse_of="beat_E",
        start_seconds=573.2,
        end_seconds=588.3,
        script_excerpt=(
            "Os dezessete relógios da vitrine, cada um preso numa hora diferente havia "
            "gerações, moveram-se todos ao mesmo tempo e pararam juntos."
        ),
        narrative_function=NarrativeFunction.RESOLUTION,
        subject="A vitrine com os dezessete relógios, agora todos na mesma hora",
        environment="Vitrine da oficina, vista de fora, à tarde",
        action="Nenhuma ação humana em quadro — o payoff é visual e silencioso",
        visual_intent=(
            "Callback direto ao Beat B: mesma vitrine, mesmos dezessete relógios, "
            "agora sincronizados — a imagem deve ecoar a composição do Beat B para "
            "que o payoff seja legível."
        ),
        continuity_refs=("Oficina de Elias", "Dezessete relógios da vitrine", "Portovelho"),
    ),
)
