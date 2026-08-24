"""Gate 1 — Core Health.

Valida ISOLADAMENTE (sem `bootstrap()`, sem `EngineContext`, sem o
orquestrador dos 27 agentes) só os componentes legacy que a Matriz de Reuso
(docs/youtube-lite/SDD_SPDD.md §15) classifica como REUSE_AS_IS. Este arquivo
não testa o motor legacy inteiro — só prova que os componentes específicos que
o Lite vai importar diretamente funcionam por conta própria.

Não corrige nem adapta nada do legacy: se um componente exigisse grande
adaptação para funcionar isolado, a decisão do discovery é substituí-lo no
Lite, não consertar o legacy (ver `SubtitleCue`/`render_srt`, classificado
REPLACE, não testado aqui).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pedroarte_youtube_engine.observability.logging import RunLogger
from pedroarte_youtube_engine.shared.errors import PathSecurityError
from pedroarte_youtube_engine.shared.paths import PathPolicy, ensure_directory, write_text_atomic
from pedroarte_youtube_engine.shared.text import (
    count_words,
    safe_slug,
    sentence_split,
    slugify,
    speakable_duration_seconds,
)


class TestSharedTextReuseAsIs:
    """`shared/text.py` — zero dependência de domínio/agentes (confirmado por import)."""

    def test_count_words_pt_br(self) -> None:
        text = "O relojoeiro guardava um segredo entre engrenagens de vidro."
        assert count_words(text) == 9

    def test_speakable_duration_seconds_matches_word_count_and_rate(self) -> None:
        text = " ".join(["palavra"] * 150)  # 150 palavras
        seconds = speakable_duration_seconds(text, words_per_minute=150.0)
        assert seconds == pytest.approx(60.0, abs=0.01)

    def test_slugify_is_ascii_and_stable(self) -> None:
        assert slugify("O Relojoeiro de Vidro") == "o-relojoeiro-de-vidro"

    def test_safe_slug_rejects_windows_reserved_names(self) -> None:
        assert safe_slug("CON") != "con"

    def test_sentence_split_handles_pt_br_abbreviations(self) -> None:
        text = "O Dr. Elias abriu a porta. Ele não disse nada."
        sentences = sentence_split(text)
        assert len(sentences) == 2
        assert sentences[0].startswith("O Dr. Elias")


class TestSharedPathsReuseAsIs:
    """`shared/paths.py` — só depende de `shared/errors.py`."""

    def test_path_policy_allows_writes_within_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = PathPolicy.for_roots(root)
            target = root / "sub" / "file.txt"
            written = write_text_atomic(target, "conteudo", policy)
            assert written.read_text(encoding="utf-8") == "conteudo"

    def test_path_policy_blocks_traversal_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "allowed"
            root.mkdir()
            policy = PathPolicy.for_roots(root)
            outside = Path(tmp) / "outside" / "file.txt"
            with pytest.raises(PathSecurityError):
                write_text_atomic(outside, "x", policy)

    def test_ensure_directory_creates_within_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = PathPolicy.for_roots(root)
            created = ensure_directory(root / "runs" / "run_001", policy)
            assert created.is_dir()


class TestRunLoggerReuseAsIs:
    """`observability/logging.py::RunLogger` — usar com a assinatura real.

    A instanciação correta (sem `verbose=`, que só existe como bug em
    `_bootstrap.py`) prova que a classe em si está saudável.
    """

    def test_run_logger_accepts_correct_signature(self) -> None:
        logger = RunLogger(run_id="run_gate1", project_id="youtube-lite")
        logger.info("gate 1 smoke test", component="test")

    def test_run_logger_rejects_undocumented_verbose_kwarg(self) -> None:
        """Documenta o bug real do `_bootstrap.py` (discovery forense §11) sem
        tentar corrigi-lo: prova que a classe legacy é saudável, e que o
        Lite não deve reproduzir a chamada quebrada.
        """
        with pytest.raises(TypeError):
            RunLogger(run_id="run_gate1", project_id="youtube-lite", verbose=True)  # type: ignore[call-arg]

    def test_run_logger_bind_creates_derived_logger(self) -> None:
        logger = RunLogger(run_id="run_gate1", project_id="youtube-lite")
        derived = logger.bind(component="lite.narration")
        derived.info("bound logger works")
