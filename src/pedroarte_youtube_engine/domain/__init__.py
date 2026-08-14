"""Camada de domínio.

Regra arquitetural inegociável (seção 6.1 da especificação): nada aqui importa
SDK de fornecedor, framework de agentes, banco vetorial, framework web ou
biblioteca de nuvem. O único vizinho permitido é `pedroarte_youtube_engine.shared`.

A conformidade é verificada por `scripts/check_domain_purity.py`, executado no
pre-commit e no CI.
"""

from __future__ import annotations
