"""Fixtures compartilhadas."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pedroarte_youtube_engine.shared.clock import FrozenClock

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def frozen_clock() -> FrozenClock:
    return FrozenClock(start=EPOCH)


@pytest.fixture()
def tmp_input(tmp_path: Path) -> Path:
    d = tmp_path / "input"
    d.mkdir()
    (d / "livro.md").write_text(
        "# Capítulo 1\n\nEra uma vez um mundo distante.\n\n"
        "# Capítulo 2\n\nO herói partiu em busca de respostas.\n",
        encoding="utf-8",
    )
    return d
