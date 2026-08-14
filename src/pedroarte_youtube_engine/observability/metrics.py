"""Métricas da execução (seção 27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StageTiming:
    """Duração de uma etapa do pipeline."""

    stage: str
    seconds: float
    ok: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "seconds": round(self.seconds, 4), "ok": self.ok}


@dataclass(slots=True)
class MetricsCollector:
    """Acumula contadores e tempos de uma execução."""

    timings: list[StageTiming] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    agent_failures: dict[str, int] = field(default_factory=dict)

    def record_stage(self, stage: str, seconds: float, *, ok: bool = True) -> None:
        self.timings.append(StageTiming(stage=stage, seconds=seconds, ok=ok))

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def record_agent_failure(self, agent: str) -> None:
        self.agent_failures[agent] = self.agent_failures.get(agent, 0) + 1

    @property
    def total_seconds(self) -> float:
        return sum(timing.seconds for timing in self.timings)

    def slowest_stages(self, limit: int = 5) -> list[StageTiming]:
        return sorted(self.timings, key=lambda timing: -timing.seconds)[:limit]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_seconds": round(self.total_seconds, 4),
            "stages": [timing.as_dict() for timing in self.timings],
            "counters": dict(sorted(self.counters.items())),
            "gauges": {key: round(value, 6) for key, value in sorted(self.gauges.items())},
            "agent_failures": dict(sorted(self.agent_failures.items())),
        }
