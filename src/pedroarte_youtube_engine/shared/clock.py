"""Abstração de tempo.

O motor nunca chama `datetime.now()` diretamente. Todo carimbo de tempo passa
por um `Clock`, o que torna as execuções reproduzíveis nos testes golden.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Fonte de tempo injetável."""

    def now(self) -> datetime:
        """Retorna o instante atual, sempre com `tzinfo` definido."""
        ...


class SystemClock:
    """Relógio real, ancorado no fuso local do sistema."""

    __slots__ = ()

    def now(self) -> datetime:
        return datetime.now(timezone.utc).astimezone()


class FrozenClock:
    """Relógio determinístico para testes e execuções reproduzíveis."""

    __slots__ = ("_current", "_step")

    def __init__(self, start: datetime, step_seconds: float = 0.0) -> None:
        if start.tzinfo is None:
            raise ValueError("FrozenClock exige um datetime com timezone.")
        self._current = start
        self._step = timedelta(seconds=step_seconds)

    def now(self) -> datetime:
        current = self._current
        self._current = current + self._step
        return current
