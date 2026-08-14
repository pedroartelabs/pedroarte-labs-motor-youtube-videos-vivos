"""Testes unitários do registro de prompts."""

from __future__ import annotations

from datetime import date

import pytest

from pedroarte_youtube_engine.domain.value_objects import PromptVersion
from pedroarte_youtube_engine.prompts import REGISTRY
from pedroarte_youtube_engine.prompts.registry import PromptDefinition, PromptRegistry
from pedroarte_youtube_engine.shared.errors import ConfigurationError

pytestmark = pytest.mark.unit


def _make_prompt(name: str = "test_prompt", agent: str = "test_agent") -> PromptDefinition:
    return PromptDefinition(
        name=name,
        version=PromptVersion(major=1, minor=0, patch=0),
        agent=agent,
        objective="Test objective for prompt " + name,
        template="Hello {name}, you are {role}.",
        changed_at=date(2026, 1, 1),
        evaluation_criteria=("criterion_one",),
    )


class TestPromptDefinition:
    def test_hash_deterministic(self) -> None:
        p = _make_prompt()
        assert p.hash == p.hash

    def test_qualified_name(self) -> None:
        p = _make_prompt()
        assert "@" in p.qualified_name

    def test_render(self) -> None:
        p = _make_prompt()
        result = p.render(name="João", role="narrador")
        assert "João" in result

    def test_render_missing_variable(self) -> None:
        p = _make_prompt()
        with pytest.raises(ConfigurationError):
            p.render(name="João")


class TestPromptRegistry:
    def test_get_existing(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        assert reg.get("test_prompt") is not None

    def test_get_missing(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        assert reg.get("nonexistent") is None

    def test_require_raises(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        with pytest.raises(ConfigurationError):
            reg.require("nonexistent")

    def test_duplicate_raises(self) -> None:
        p = _make_prompt()
        with pytest.raises(ConfigurationError):
            PromptRegistry((p, p))

    def test_for_agent(self) -> None:
        p1 = _make_prompt("prompt_aaa", "agent_x")
        p2 = _make_prompt("prompt_bbb", "agent_y")
        reg = PromptRegistry((p1, p2))
        assert len(reg.for_agent("agent_x")) == 1

    def test_len(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        assert len(reg) == 1

    def test_contains(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        assert "test_prompt" in reg

    def test_manifest(self) -> None:
        reg = PromptRegistry((_make_prompt(),))
        m = reg.manifest()
        assert len(m) == 1
        assert "name" in m[0]


class TestGlobalRegistry:
    def test_has_prompts(self) -> None:
        assert len(REGISTRY) >= 20

    def test_all_have_hash(self) -> None:
        for p in REGISTRY.all():
            assert p.hash.startswith("sha256:")
