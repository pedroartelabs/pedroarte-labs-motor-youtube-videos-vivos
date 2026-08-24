"""YOUTUBE LITE — vertical slice novo, isolado do orquestrador legacy.

Este pacote NÃO importa `pedroarte_youtube_engine.agents`,
`pedroarte_youtube_engine.interfaces._bootstrap` nem
`pedroarte_youtube_engine.agents.orchestrator`. Ele reaproveita, por
importação direta, só um punhado de funções puras de `shared/` e
`observability/` (ver docs/youtube-lite/SDD_SPDD.md §15 — Matriz de Reuso).

Escopo desta fase (Gate 1 + Gate 2): provar que
`script curto -> narração real -> imagem real -> timeline -> FFmpeg -> clip.mp4`
funciona de ponta a ponta, localmente, a custo zero. Nada além disso.
"""

from __future__ import annotations
