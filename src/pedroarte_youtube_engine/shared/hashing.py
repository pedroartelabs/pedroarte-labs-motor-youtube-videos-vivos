"""Hashing determinístico.

Usado para proveniência (`SourceReference`), para chaves de cache, para
idempotência de jobs de provedor e para o versionamento de prompts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_ALGORITHM = "sha256"
_CHUNK_BYTES = 1024 * 1024


def content_hash(data: str | bytes) -> str:
    """Hash canônico de um conteúdo, prefixado pelo algoritmo."""
    payload = data.encode("utf-8") if isinstance(data, str) else data
    digest = hashlib.sha256(payload).hexdigest()
    return f"{_ALGORITHM}:{digest}"


def file_hash(path: Path) -> str:
    """Hash de um arquivo lido em blocos, sem carregá-lo inteiro na memória."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            hasher.update(chunk)
    return f"{_ALGORITHM}:{hasher.hexdigest()}"


def canonical_json(value: Any) -> str:
    """Serialização estável: chaves ordenadas, sem espaços supérfluos.

    Duas estruturas equivalentes produzem exatamente a mesma string, o que
    permite comparar e hashear payloads sem falsos negativos.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def structural_hash(value: Any) -> str:
    """Hash de uma estrutura de dados arbitrária, via JSON canônico."""
    return content_hash(canonical_json(value))


def stable_short_id(*parts: str, length: int = 6) -> str:
    """Identificador curto e determinístico derivado das partes informadas.

    Usado no sufixo do `run_id`. Não é criptograficamente único; serve para
    desambiguar execuções iniciadas no mesmo segundo.
    """
    if length < 4 or length > 32:
        raise ValueError("O comprimento do id curto deve estar entre 4 e 32.")
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]
