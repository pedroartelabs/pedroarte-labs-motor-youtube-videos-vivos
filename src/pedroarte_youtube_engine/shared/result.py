"""Result Pattern.

O motor evita exceções para falhas *esperadas* (um segmento inválido, um
provedor incompatível, um gate reprovado). Essas falhas são valores, para que o
orquestrador possa agregá-las, contá-las e alimentar o repair loop sem
`try/except` espalhado pelo pipeline.

Exceções continuam sendo usadas para falhas *inesperadas* (bug, disco cheio).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, NoReturn, TypeVar

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
F = TypeVar("F")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Resultado bem-sucedido."""

    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value

    def map(self, fn: Callable[[T], U]) -> "Ok[U]":
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[object], object]) -> "Ok[T]":
        return self

    def and_then(self, fn: "Callable[[T], Result[U, E]]") -> "Result[U, E]":
        return fn(self.value)


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Resultado com falha esperada."""

    error: E

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise ValueError(f"unwrap() chamado sobre Err: {self.error!r}")

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, fn: Callable[[object], object]) -> "Err[E]":
        return self

    def map_err(self, fn: Callable[[E], F]) -> "Err[F]":
        return Err(fn(self.error))

    def and_then(self, fn: "Callable[[object], Result[U, E]]") -> "Err[E]":
        return self


Result = Ok[T] | Err[E]
"""Alias de união usado nas assinaturas públicas do motor."""


def collect(results: "list[Result[T, E]]") -> "Result[list[T], list[E]]":
    """Agrega resultados: `Ok` com todos os valores ou `Err` com todos os erros.

    Diferente de um *fail fast*, esta função percorre a lista inteira, porque o
    repair loop precisa da lista completa de problemas para planejar reparos.
    """
    values: list[T] = []
    errors: list[E] = []
    for item in results:
        if isinstance(item, Ok):
            values.append(item.value)
        else:
            errors.append(item.error)
    if errors:
        return Err(errors)
    return Ok(values)
