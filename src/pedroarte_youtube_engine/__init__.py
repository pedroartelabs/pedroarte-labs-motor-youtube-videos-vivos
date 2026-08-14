"""PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE.

Motor multiagente que transforma livros em pacotes de produção audiovisual para
YouTube: vídeos principais, Shorts, vídeos longos, séries, mini-novelas,
trailers e teasers.

O pacote segue Clean Architecture / Hexagonal Architecture. A regra de
dependência é estrita e verificada por `scripts/check_domain_purity.py`:

    interfaces ──► application ──► domain ◄── (nada)
         │              │
         └──► adapters ─┘  (implementam `ports`)

O subpacote `domain` não importa nenhum SDK de fornecedor, framework web,
framework de agentes ou banco vetorial.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
