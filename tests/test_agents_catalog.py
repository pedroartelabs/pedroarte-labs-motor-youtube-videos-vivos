"""Testes de contrato do catálogo de agentes."""

from __future__ import annotations

import pytest

from pedroarte_youtube_engine.agents import CATALOG, agent_manifest
from pedroarte_youtube_engine.agents.base import AgentContract

pytestmark = pytest.mark.contract


class TestAgentCatalog:
    def test_has_agents(self) -> None:
        assert len(CATALOG) >= 25

    def test_no_duplicate_names(self) -> None:
        names = [a.__name__ for a in CATALOG]
        assert len(names) == len(set(names))

    def test_manifest_returns_list(self) -> None:
        m = agent_manifest()
        assert isinstance(m, list)
        assert len(m) >= 25

    def test_manifest_entry_shape(self) -> None:
        m = agent_manifest()
        entry = m[0]
        assert "name" in entry
        assert "phase" in entry
