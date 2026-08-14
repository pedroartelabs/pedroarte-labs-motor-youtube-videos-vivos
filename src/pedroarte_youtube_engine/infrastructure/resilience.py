"""Resiliência: retry com backoff, circuit breaker e idempotência.

Estes mecanismos só entram em cena quando há chamada externa
(`execute_generation: true`). No modo padrão, o motor não tem nada que possa
falhar por rede — e é por isso que o exemplo roda sem eles.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import TypeVar

from pedroarte_youtube_engine.shared.errors import ProviderError, ProviderUnavailable
from pedroarte_youtube_engine.shared.hashing import structural_hash

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Política de repetição com backoff exponencial e jitter determinístico."""

    max_attempts: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    multiplier: float = 2.0

    def delay_for(self, attempt: int) -> float:
        """Atraso antes da tentativa `attempt` (1-indexada)."""
        if attempt <= 1:
            return 0.0
        raw = self.base_delay_seconds * (self.multiplier ** (attempt - 2))
        # Jitter determinístico (±12,5%) evita sincronizar retentativas em lote
        # sem introduzir aleatoriedade que quebraria os testes.
        jitter = ((attempt * 2654435761) % 1000) / 1000.0 - 0.5
        return min(self.max_delay_seconds, raw * (1.0 + jitter * 0.25))


def with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    on_retry: Callable[[int, Exception], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Executa `operation` repetindo em caso de `ProviderError`.

    Erros que não são de provedor sobem imediatamente: repetir um bug não o
    conserta, apenas atrasa o diagnóstico.
    """
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        delay = policy.delay_for(attempt)
        if delay > 0:
            sleep(delay)
        try:
            return operation()
        except ProviderError as exc:
            last_error = exc
            if on_retry is not None:
                on_retry(attempt, exc)
    raise ProviderError(
        f"Operação falhou após {policy.max_attempts} tentativas.",
        cause=str(last_error) if last_error else "",
    )


class BreakerState(StrEnum):
    CLOSED = "fechado"
    OPEN = "aberto"
    HALF_OPEN = "meio_aberto"


@dataclass(slots=True)
class CircuitBreaker:
    """Impede que uma sequência de falhas consuma quota e tempo.

    Depois de `failure_threshold` falhas o circuito abre; após `recovery_seconds`
    ele deixa passar uma tentativa de sondagem antes de fechar de novo.
    """

    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    name: str = "provider"
    _failures: int = field(default=0, init=False)
    _opened_at: datetime | None = field(default=None, init=False)
    _state: BreakerState = field(default=BreakerState.CLOSED, init=False)

    @property
    def state(self) -> BreakerState:
        if self._state is BreakerState.OPEN and self._recovery_elapsed():
            self._state = BreakerState.HALF_OPEN
        return self._state

    def _recovery_elapsed(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = datetime.now(timezone.utc) - self._opened_at
        return elapsed >= timedelta(seconds=self.recovery_seconds)

    def before_call(self) -> None:
        """Levanta `ProviderUnavailable` quando o circuito está aberto."""
        if self.state is BreakerState.OPEN:
            raise ProviderUnavailable(
                f"Circuito aberto para '{self.name}'. "
                f"Aguardando {self.recovery_seconds:.0f}s antes de nova tentativa.",
                provider=self.name,
                failures=self._failures,
            )

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._state = BreakerState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = BreakerState.OPEN
            self._opened_at = datetime.now(timezone.utc)


def idempotency_key(*parts: str) -> str:
    """Chave estável para uma chamada de provedor.

    Reexecutar o motor sobre a mesma entrada e a mesma configuração gera a mesma
    chave — o que permite ao provedor (ou ao cache local) reconhecer a
    duplicidade em vez de gerar e cobrar duas vezes.
    """
    digest = structural_hash(list(parts))
    return digest.split(":", 1)[1][:48]
