"""Estratégia real do `ScriptGenerationPort` para o Gate 3A.

Não é uma chamada de API programática, e não é um texto hardcoded genérico
reaproveitado de outro run: o texto é composto pelo LLM que conduz a sessão
operacional (Claude Code) especificamente para o `VideoSpecification` da
execução — a "capacidade do ambiente de execução" priorizada pela política
local-first (SDD_SPDD.md §26, §38.3). Esta classe só empacota esse texto já
autorado com a proveniência correta; ela não gera nada sozinha.

Isso é o que distingue `CONTENT_GENERATION_PASS` de `INFRASTRUCTURE_PASS`: o
texto muda com o briefing porque foi escrito para ele, não porque um template
foi preenchido.
"""

from __future__ import annotations

from pedroarte_youtube_engine.lite.script_generation.ports import (
    ScriptGenerationRequest,
    ScriptGenerationResult,
)


class OperatorAuthoredScriptStrategy:
    """Implementa `ScriptGenerationPort` com um texto já autorado pelo operador (LLM)."""

    def __init__(self, *, script_text: str, model_label: str) -> None:
        if not script_text.strip():
            raise ValueError("script_text não pode ser vazio.")
        self._script_text = script_text
        self._model_label = model_label

    def generate(self, request: ScriptGenerationRequest) -> ScriptGenerationResult:
        return ScriptGenerationResult(
            script_text=self._script_text,
            method="operator:claude_code",
            provider=None,
            model=self._model_label,
            input_tokens=None,
            output_tokens=None,
            extra={
                "note": (
                    "Token counts não são observáveis de dentro da sessão operacional "
                    "que autora o texto — não estimados para evitar falsa precisão."
                )
            },
        )
