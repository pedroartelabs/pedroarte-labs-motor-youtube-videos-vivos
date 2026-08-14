"""Redaction de segredos em logs e relatórios.

Regra da seção 27: **nunca registrar** chaves, tokens ou credenciais. A redaction
acontece na borda de saída — se um segredo chegou até aqui por engano, ele não
sai daqui.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***REDACTED***"

#: Nomes de campo cujo valor é sempre suprimido.
_SENSITIVE_KEYS = (
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "authorization",
    "auth",
    "api_key",
    "apikey",
    "private",
    "session",
    "cookie",
)

#: Formatos de credencial reconhecíveis mesmo fora de um campo nomeado.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{12,})['\"]?"
    ),
)


def is_sensitive_key(key: str) -> bool:
    """Informa se o nome do campo indica conteúdo sensível."""
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEYS)


def redact(value: str) -> str:
    """Substitui credenciais reconhecíveis dentro de um texto livre."""
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Aplica redaction recursivamente a uma estrutura de dados."""
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if is_sensitive_key(key):
            result[key] = REDACTED
        elif isinstance(value, dict):
            result[key] = redact_mapping(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [
                redact_mapping(item)
                if isinstance(item, dict)
                else (redact(item) if isinstance(item, str) else item)
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = redact(value)
        else:
            result[key] = value
    return result
