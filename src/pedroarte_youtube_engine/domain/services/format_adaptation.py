"""Estratégia de adaptação por formato.

Cada formato seleciona beats de um jeito diferente. É o que impede que o vídeo
longo seja o vídeo de dez minutos esticado, e que o trailer seja um recorte
mecânico do vídeo principal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pedroarte_youtube_engine.domain.canon import NarrativeBeat
from pedroarte_youtube_engine.domain.value_objects import (
    NarrativeFunction,
    ProductionVariant,
)


class SelectionStrategy(StrEnum):
    """Como os beats são escolhidos para um formato."""

    SPINE = "espinha_dorsal"
    FULL_DEVELOPMENT = "desenvolvimento_completo"
    SINGLE_PEAK = "pico_unico"
    RELATIONAL = "relacional"
    ESCALATION = "escalada"
    ATMOSPHERE = "atmosfera"


@dataclass(frozen=True, slots=True)
class AdaptationStrategy:
    """Instruções concretas para adaptar a obra a um formato."""

    variant: ProductionVariant
    selection: SelectionStrategy
    rationale: str
    preserve: tuple[str, ...]
    condense: tuple[str, ...]
    reorganize: tuple[str, ...]


_STRATEGIES: dict[ProductionVariant, AdaptationStrategy] = {
    ProductionVariant.MAIN_10_MINUTES: AdaptationStrategy(
        variant=ProductionVariant.MAIN_10_MINUTES,
        selection=SelectionStrategy.SPINE,
        rationale=(
            "História condensada em torno da espinha dorsal: os beats de maior peso "
            "dramático, na ordem original, com pontes narrativas entre eles."
        ),
        preserve=("tese central", "protagonistas", "incidente incitante", "clímax", "desfecho"),
        condense=("subtramas", "descrições estendidas", "personagens de passagem"),
        reorganize=("exposição diluída, reagrupada em blocos de informação",),
    ),
    ProductionVariant.LONG_FORM: AdaptationStrategy(
        variant=ProductionVariant.LONG_FORM,
        selection=SelectionStrategy.FULL_DEVELOPMENT,
        rationale=(
            "Desenvolvimento completo com atos, subtramas, cenas de respiro e epílogo. "
            "Nunca uma versão esticada do vídeo de dez minutos."
        ),
        preserve=(
            "arco de cada personagem principal",
            "subtramas",
            "consequências",
            "ambiguidade",
        ),
        condense=("repetições internas do texto",),
        reorganize=("preparação e pagamento distribuídos entre atos",),
    ),
    ProductionVariant.SERIES: AdaptationStrategy(
        variant=ProductionVariant.SERIES,
        selection=SelectionStrategy.ESCALATION,
        rationale=(
            "Cada episódio fecha um movimento e abre outro: um gancho no início, um "
            "cliffhanger no fim, progressão explícita de temporada."
        ),
        preserve=("progressão dos arcos", "mistérios centrais"),
        condense=("cenas de transição sem consequência",),
        reorganize=("blocos de capítulo redistribuídos por episódio",),
    ),
    ProductionVariant.MINI_NOVELA: AdaptationStrategy(
        variant=ProductionVariant.MINI_NOVELA,
        selection=SelectionStrategy.RELATIONAL,
        rationale=(
            "Ênfase em personagens, relações, diálogos e revelações. A estrutura de "
            "cada capítulo tem seis passos: abertura, contexto, complicação, confronto, "
            "mudança de estado e pergunta final."
        ),
        preserve=("relações", "conflitos interpessoais", "revelações", "identidade sonora"),
        condense=("descrições de mundo sem função relacional",),
        reorganize=("cenas agrupadas por par de personagens",),
    ),
    ProductionVariant.SHORTS: AdaptationStrategy(
        variant=ProductionVariant.SHORTS,
        selection=SelectionStrategy.SINGLE_PEAK,
        rationale=(
            "Um único pico compreensível sem contexto externo, com gancho imediato e "
            "fechamento em pergunta ou convite."
        ),
        preserve=("clareza autossuficiente", "gancho nos primeiros segundos"),
        condense=("todo o resto",),
        reorganize=("ordem alterada quando o impacto exigir",),
    ),
    ProductionVariant.TRAILERS: AdaptationStrategy(
        variant=ProductionVariant.TRAILERS,
        selection=SelectionStrategy.ATMOSPHERE,
        rationale=(
            "Promessa sem entrega: seleção de momentos por escalada emocional e sonora, "
            "controlando revelações. Cada trailer usa uma estratégia própria."
        ),
        preserve=("tom", "promessa", "identidade sonora"),
        condense=("enredo explícito",),
        reorganize=("montagem não linear guiada pela música",),
    ),
}

#: Funções narrativas que um trailer nunca revela.
_TRAILER_FORBIDDEN = frozenset(
    {NarrativeFunction.CLIMAX, NarrativeFunction.RESOLUTION, NarrativeFunction.EPILOGUE}
)


class FormatAdaptationService:
    """Seleciona e ordena beats de acordo com a estratégia de cada formato."""

    def strategy_for(self, variant: ProductionVariant) -> AdaptationStrategy:
        return _STRATEGIES[variant]

    def select_beats(
        self,
        beats: tuple[NarrativeBeat, ...],
        *,
        variant: ProductionVariant,
        wanted: int,
        offset: int = 0,
    ) -> tuple[NarrativeBeat, ...]:
        """Escolhe `wanted` beats segundo a estratégia do formato.

        `offset` desloca a seleção — é o que faz o Short nº 3 e o Short nº 4
        contarem momentos diferentes em vez de repetirem o mesmo trecho.
        """
        if not beats or wanted <= 0:
            return ()

        strategy = self.strategy_for(variant)
        pool = self._pool_for(beats, strategy.selection, variant)
        if not pool:
            pool = list(beats)

        if strategy.selection is SelectionStrategy.FULL_DEVELOPMENT:
            chosen = self._spread(pool, wanted)
        elif strategy.selection is SelectionStrategy.SINGLE_PEAK:
            chosen = self._peak_window(pool, wanted, offset)
        elif strategy.selection is SelectionStrategy.ATMOSPHERE:
            chosen = self._atmosphere(pool, wanted, offset)
        elif strategy.selection is SelectionStrategy.RELATIONAL:
            chosen = self._relational(pool, wanted, offset)
        elif strategy.selection is SelectionStrategy.ESCALATION:
            chosen = self._escalation(pool, wanted, offset)
        else:
            chosen = self._spine(pool, wanted)

        return tuple(chosen)

    # -- pools -------------------------------------------------------------

    def _pool_for(
        self,
        beats: tuple[NarrativeBeat, ...],
        selection: SelectionStrategy,
        variant: ProductionVariant,
    ) -> list[NarrativeBeat]:
        if variant is ProductionVariant.TRAILERS:
            # Trailers não entregam o clímax nem o desfecho.
            cutoff = int(len(beats) * 0.8) or len(beats)
            return list(beats[:cutoff])
        if selection is SelectionStrategy.RELATIONAL:
            relational = [beat for beat in beats if len(beat.participants) >= 2]
            return relational or list(beats)
        return list(beats)

    # -- estratégias -------------------------------------------------------

    def _spine(self, pool: list[NarrativeBeat], wanted: int) -> list[NarrativeBeat]:
        """Os beats de maior peso, devolvidos na ordem cronológica original."""
        ranked = sorted(pool, key=lambda beat: (-beat.weight, beat.order))
        chosen = ranked[:wanted]
        return sorted(chosen, key=lambda beat: beat.order)

    def _spread(self, pool: list[NarrativeBeat], wanted: int) -> list[NarrativeBeat]:
        """Amostragem uniforme: preserva o ritmo do livro inteiro."""
        if wanted >= len(pool):
            return list(pool)
        step = len(pool) / wanted
        return [pool[min(len(pool) - 1, int(index * step))] for index in range(wanted)]

    def _peak_window(
        self, pool: list[NarrativeBeat], wanted: int, offset: int
    ) -> list[NarrativeBeat]:
        """Uma janela contígua em torno de um pico de tensão."""
        ranked = sorted(pool, key=lambda beat: (-beat.tension, -beat.weight, beat.order))
        if not ranked:
            return []
        anchor = ranked[offset % len(ranked)]
        center = pool.index(anchor)
        start = max(0, center - wanted // 2)
        window = pool[start : start + wanted]
        if len(window) < wanted:
            window = pool[max(0, len(pool) - wanted) :]
        return window

    def _atmosphere(
        self, pool: list[NarrativeBeat], wanted: int, offset: int
    ) -> list[NarrativeBeat]:
        """Momentos de textura e mudança de tom, espalhados pela obra."""
        candidates = [beat for beat in pool if beat.changes_tone] or pool
        rotated = candidates[offset % len(candidates) :] + candidates[: offset % len(candidates)]
        chosen = self._spread(rotated, wanted)
        return sorted(chosen, key=lambda beat: beat.order)

    def _relational(
        self, pool: list[NarrativeBeat], wanted: int, offset: int
    ) -> list[NarrativeBeat]:
        """Beats com pelo menos dois personagens, priorizando diálogo."""
        ranked = sorted(
            pool,
            key=lambda beat: (-len(beat.dialogue_excerpts), -len(beat.participants), beat.order),
        )
        rotated = ranked[offset % len(ranked) :] + ranked[: offset % len(ranked)]
        return sorted(rotated[:wanted], key=lambda beat: beat.order)

    def _escalation(
        self, pool: list[NarrativeBeat], wanted: int, offset: int
    ) -> list[NarrativeBeat]:
        """Fatia contígua da obra: um episódio cobre um trecho, não amostras soltas."""
        if wanted >= len(pool):
            return list(pool)
        start = (offset * wanted) % max(1, len(pool))
        window = pool[start : start + wanted]
        if len(window) < wanted:
            window = window + pool[: wanted - len(window)]
        return sorted(window, key=lambda beat: beat.order)

    # -- utilidades --------------------------------------------------------

    @staticmethod
    def forbidden_functions_for(variant: ProductionVariant) -> frozenset[NarrativeFunction]:
        """Funções narrativas que um formato não pode exibir."""
        if variant is ProductionVariant.TRAILERS:
            return _TRAILER_FORBIDDEN
        return frozenset()

    def describe(self, variant: ProductionVariant) -> str:
        strategy = self.strategy_for(variant)
        return (
            f"### {variant.value}\n\n"
            f"**Seleção:** {strategy.selection.value}\n\n"
            f"{strategy.rationale}\n\n"
            f"- **Preservar:** {', '.join(strategy.preserve)}\n"
            f"- **Condensar:** {', '.join(strategy.condense)}\n"
            f"- **Reorganizar:** {', '.join(strategy.reorganize)}\n"
        )
