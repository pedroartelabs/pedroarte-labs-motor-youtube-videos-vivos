"""Logging estruturado com correlação.

Todo registro carrega `run_id`, `project_id` e `correlation_id`, e passa por
redaction antes de sair.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_CONFIGURED = False
_LOGGER_NAME = "living_video"


class _StructuredFormatter(logging.Formatter):
    """Formata cada registro como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        from pedroarte_youtube_engine.observability.redaction import redact, redact_mapping

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(redact_mapping(context))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class _ConsoleFormatter(logging.Formatter):
    """Formato humano, para uso interativo na CLI."""

    def format(self, record: logging.LogRecord) -> str:
        from pedroarte_youtube_engine.observability.redaction import redact

        base = f"{record.levelname:<8} {redact(record.getMessage())}"
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            extras = " ".join(
                f"{key}={value}"
                for key, value in sorted(context.items())
                if key not in {"run_id", "project_id"}
            )
            if extras:
                base = f"{base}  [{extras}]"
        return base


def configure_logging(*, level: str = "INFO", fmt: str = "console") -> None:
    """Configura o logger raiz do motor. Idempotente."""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        _StructuredFormatter() if fmt.lower() == "json" else _ConsoleFormatter()
    )
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str = "") -> logging.Logger:
    """Devolve um logger filho, configurando o raiz na primeira chamada."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)


class RunLogger:
    """Logger com o contexto da execução preso a cada registro."""

    __slots__ = ("_context", "_logger")

    def __init__(
        self,
        *,
        run_id: str,
        project_id: str,
        correlation_id: str = "",
        component: str = "",
    ) -> None:
        self._logger = get_logger(component)
        self._context: dict[str, Any] = {
            "run_id": run_id,
            "project_id": project_id,
        }
        if correlation_id:
            self._context["correlation_id"] = correlation_id

    def bind(self, **extra: Any) -> "RunLogger":
        """Cria um logger derivado com contexto adicional."""
        clone = RunLogger(
            run_id=str(self._context["run_id"]),
            project_id=str(self._context["project_id"]),
        )
        clone._logger = self._logger
        clone._context = {**self._context, **extra}
        return clone

    def debug(self, message: str, **extra: Any) -> None:
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, **extra: Any) -> None:
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, **extra: Any) -> None:
        self._log(logging.ERROR, message, extra)

    def exception(self, message: str, **extra: Any) -> None:
        self._logger.exception(message, extra={"context": {**self._context, **extra}})

    def _log(self, level: int, message: str, extra: dict[str, Any]) -> None:
        self._logger.log(level, message, extra={"context": {**self._context, **extra}})
