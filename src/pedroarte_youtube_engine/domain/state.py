"""Máquina de estados do pipeline (seção 10).

As transições permitidas vivem no domínio, e não no orquestrador: assim o
conjunto de caminhos válidos pode ser testado sem instanciar infraestrutura, e
um orquestrador alternativo não consegue inventar um caminho novo.
"""

from __future__ import annotations

from enum import StrEnum

from pedroarte_youtube_engine.shared.errors import StateTransitionError


class PipelineState(StrEnum):
    """Estados explícitos da execução."""

    DISCOVERING_INPUT = "DISCOVERING_INPUT"
    INGESTING = "INGESTING"
    INDEXING = "INDEXING"
    EXTRACTING_CANON = "EXTRACTING_CANON"
    BUILDING_BIBLES = "BUILDING_BIBLES"
    PLANNING_FORMATS = "PLANNING_FORMATS"
    ADAPTING = "ADAPTING"
    PLANNING_EPISODES = "PLANNING_EPISODES"
    DECOMPOSING_SCENES = "DECOMPOSING_SCENES"
    WRITING_SEGMENTS = "WRITING_SEGMENTS"
    DESIGNING_AUDIO = "DESIGNING_AUDIO"
    COMPILING_PROMPTS = "COMPILING_PROMPTS"
    VALIDATING = "VALIDATING"
    REPAIRING = "REPAIRING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"

    @property
    def is_terminal(self) -> bool:
        return self in {PipelineState.COMPLETED, PipelineState.FAILED}

    @property
    def is_active(self) -> bool:
        return not self.is_terminal and self is not PipelineState.PAUSED


#: Sequência feliz do pipeline, na ordem da seção 10.
HAPPY_PATH: tuple[PipelineState, ...] = (
    PipelineState.DISCOVERING_INPUT,
    PipelineState.INGESTING,
    PipelineState.INDEXING,
    PipelineState.EXTRACTING_CANON,
    PipelineState.BUILDING_BIBLES,
    PipelineState.PLANNING_FORMATS,
    PipelineState.ADAPTING,
    PipelineState.PLANNING_EPISODES,
    PipelineState.DECOMPOSING_SCENES,
    PipelineState.WRITING_SEGMENTS,
    PipelineState.DESIGNING_AUDIO,
    PipelineState.COMPILING_PROMPTS,
    PipelineState.VALIDATING,
    PipelineState.EXPORTING,
    PipelineState.COMPLETED,
)


def _build_transitions() -> dict[PipelineState, frozenset[PipelineState]]:
    transitions: dict[PipelineState, set[PipelineState]] = {
        state: set() for state in PipelineState
    }
    # Avanço linear pelo caminho feliz.
    for current, following in zip(HAPPY_PATH, HAPPY_PATH[1:], strict=False):
        transitions[current].add(following)

    # Qualquer estado ativo pode falhar ou ser pausado.
    for state in PipelineState:
        if state.is_active:
            transitions[state].add(PipelineState.FAILED)
            transitions[state].add(PipelineState.PAUSED)

    # A validação pode acionar o repair loop; o reparo devolve o fluxo para as
    # etapas que produzem conteúdo, e daí o pipeline revalida.
    transitions[PipelineState.VALIDATING].add(PipelineState.REPAIRING)
    transitions[PipelineState.REPAIRING].update(
        {
            PipelineState.WRITING_SEGMENTS,
            PipelineState.DESIGNING_AUDIO,
            PipelineState.COMPILING_PROMPTS,
            PipelineState.DECOMPOSING_SCENES,
            PipelineState.VALIDATING,
        }
    )

    # Uma execução pausada retoma no estado em que parou.
    transitions[PipelineState.PAUSED].update(
        {state for state in PipelineState if state.is_active}
    )

    return {state: frozenset(targets) for state, targets in transitions.items()}


#: Grafo de transições permitidas.
ALLOWED_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = _build_transitions()


def can_transition(source: PipelineState, target: PipelineState) -> bool:
    """Verifica se a transição é permitida."""
    return target in ALLOWED_TRANSITIONS[source]


def assert_transition(source: PipelineState, target: PipelineState) -> None:
    """Levanta `StateTransitionError` quando a transição é proibida."""
    if not can_transition(source, target):
        raise StateTransitionError(
            f"Transição proibida: {source.value} → {target.value}.",
            source=source.value,
            target=target.value,
            allowed=sorted(state.value for state in ALLOWED_TRANSITIONS[source]),
        )


def next_state(current: PipelineState) -> PipelineState:
    """Próximo estado do caminho feliz."""
    if current not in HAPPY_PATH:
        raise StateTransitionError(
            f"{current.value} não pertence ao caminho feliz.", state=current.value
        )
    index = HAPPY_PATH.index(current)
    if index == len(HAPPY_PATH) - 1:
        return current
    return HAPPY_PATH[index + 1]


def progress_ratio(current: PipelineState) -> float:
    """Fração concluída, para barra de progresso e para `get_run_status`."""
    if current is PipelineState.COMPLETED:
        return 1.0
    if current in HAPPY_PATH:
        return HAPPY_PATH.index(current) / (len(HAPPY_PATH) - 1)
    return 0.0
