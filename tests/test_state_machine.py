"""Testes unitários da máquina de estados do pipeline."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.domain.state import (
    ALLOWED_TRANSITIONS,
    HAPPY_PATH,
    PipelineState,
    assert_transition,
    can_transition,
    next_state,
    progress_ratio,
)
from pedroarte_youtube_engine.shared.errors import StateTransitionError

pytestmark = pytest.mark.unit


class TestPipelineState:
    def test_terminal_states(self) -> None:
        assert PipelineState.COMPLETED.is_terminal
        assert PipelineState.FAILED.is_terminal
        assert not PipelineState.VALIDATING.is_terminal

    def test_active_states(self) -> None:
        assert PipelineState.DISCOVERING_INPUT.is_active
        assert not PipelineState.COMPLETED.is_active
        assert not PipelineState.PAUSED.is_active


class TestHappyPath:
    def test_starts_with_discovery(self) -> None:
        assert HAPPY_PATH[0] is PipelineState.DISCOVERING_INPUT

    def test_ends_with_completed(self) -> None:
        assert HAPPY_PATH[-1] is PipelineState.COMPLETED

    def test_no_duplicates(self) -> None:
        assert len(HAPPY_PATH) == len(set(HAPPY_PATH))

    def test_all_active_except_completed(self) -> None:
        for state in HAPPY_PATH[:-1]:
            assert state.is_active


class TestTransitions:
    def test_happy_path_forward(self) -> None:
        for current, following in zip(HAPPY_PATH, HAPPY_PATH[1:], strict=False):
            assert can_transition(current, following)

    def test_backward_disallowed(self) -> None:
        assert not can_transition(PipelineState.VALIDATING, PipelineState.DISCOVERING_INPUT)

    def test_any_active_can_fail(self) -> None:
        for state in PipelineState:
            if state.is_active:
                assert can_transition(state, PipelineState.FAILED)

    def test_any_active_can_pause(self) -> None:
        for state in PipelineState:
            if state.is_active:
                assert can_transition(state, PipelineState.PAUSED)

    def test_validating_can_repair(self) -> None:
        assert can_transition(PipelineState.VALIDATING, PipelineState.REPAIRING)

    def test_repairing_can_return_to_writing(self) -> None:
        assert can_transition(PipelineState.REPAIRING, PipelineState.WRITING_SEGMENTS)
        assert can_transition(PipelineState.REPAIRING, PipelineState.VALIDATING)

    def test_paused_resumes_to_any_active(self) -> None:
        for state in PipelineState:
            if state.is_active:
                assert can_transition(PipelineState.PAUSED, state)

    def test_assert_transition_raises(self) -> None:
        with pytest.raises(StateTransitionError):
            assert_transition(PipelineState.COMPLETED, PipelineState.DISCOVERING_INPUT)


class TestNextState:
    def test_advances_along_happy_path(self) -> None:
        assert next_state(PipelineState.DISCOVERING_INPUT) is PipelineState.INGESTING

    def test_completed_stays(self) -> None:
        assert next_state(PipelineState.COMPLETED) is PipelineState.COMPLETED

    def test_repairing_raises(self) -> None:
        with pytest.raises(StateTransitionError):
            next_state(PipelineState.REPAIRING)


class TestProgressRatio:
    def test_zero_at_start(self) -> None:
        assert progress_ratio(PipelineState.DISCOVERING_INPUT) == 0.0

    def test_one_at_completed(self) -> None:
        assert progress_ratio(PipelineState.COMPLETED) == 1.0

    def test_monotonically_increasing(self) -> None:
        values = [progress_ratio(s) for s in HAPPY_PATH]
        assert values == sorted(values)
        assert len(set(values)) == len(values)
