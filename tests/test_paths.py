"""Testes unitários da política de caminhos."""

from __future__ import annotations

from pathlib import Path

import pytest

from pedroarte_youtube_engine.shared.errors import PathSecurityError
from pedroarte_youtube_engine.shared.paths import DiscoveryBudget, PathPolicy

pytestmark = pytest.mark.unit


class TestPathPolicy:
    def test_resolve_within_allowed(self, tmp_path: Path) -> None:
        policy = PathPolicy.for_roots(tmp_path)
        f = tmp_path / "file.txt"
        f.write_text("x")
        assert policy.resolve_within(f) == f.resolve()

    def test_resolve_outside_raises(self, tmp_path: Path) -> None:
        policy = PathPolicy.for_roots(tmp_path)
        with pytest.raises(PathSecurityError):
            policy.resolve_within(tmp_path / ".." / ".." / "etc" / "passwd")

    def test_no_roots_raises(self) -> None:
        with pytest.raises(PathSecurityError):
            PathPolicy.for_roots()

    def test_allowed_extension(self, tmp_path: Path) -> None:
        policy = PathPolicy.for_roots(tmp_path)
        assert policy.is_allowed_extension(Path("file.md"))
        assert not policy.is_allowed_extension(Path("file.exe"))

    def test_check_file_size(self, tmp_path: Path) -> None:
        f = tmp_path / "small.txt"
        f.write_text("x")
        policy = PathPolicy.for_roots(tmp_path, max_file_bytes=10)
        assert policy.check_file_size(f) == f.stat().st_size

    def test_check_file_size_too_large(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("x" * 100)
        policy = PathPolicy.for_roots(tmp_path, max_file_bytes=10)
        with pytest.raises(PathSecurityError):
            policy.check_file_size(f)


class TestDiscoveryBudget:
    def test_within_budget(self, tmp_path: Path) -> None:
        budget = DiscoveryBudget(max_total_bytes=1000)
        budget.consume(500, path=tmp_path / "a")
        assert budget.consumed_bytes == 500

    def test_exceeds_budget(self, tmp_path: Path) -> None:
        budget = DiscoveryBudget(max_total_bytes=100)
        with pytest.raises(PathSecurityError):
            budget.consume(200, path=tmp_path / "a")
