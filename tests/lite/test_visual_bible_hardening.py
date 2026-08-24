"""Revisão de reforço de continuidade da Visual Bible (Gate 3D, evidência do
Gate 3C) — confirma que a v2 endurece só o que precisa e preserva tudo o mais
(regra: "não é redesenho")."""

from __future__ import annotations

from pedroarte_youtube_engine.lite.visual_bible import (
    RELOJOEIRO_VISUAL_BIBLE,
    RELOJOEIRO_VISUAL_BIBLE_HARDENED,
)
from pedroarte_youtube_engine.shared.hashing import structural_hash

UNCHANGED_FIELDS = (
    "overall_style",
    "realism_level",
    "color_language",
    "lighting",
    "environment_language",
    "mood",
)


class TestArtisticDirectionUnchanged:
    def test_style_palette_lighting_realism_environment_mood_identical(self) -> None:
        for field in UNCHANGED_FIELDS:
            assert getattr(RELOJOEIRO_VISUAL_BIBLE, field) == getattr(
                RELOJOEIRO_VISUAL_BIBLE_HARDENED, field
            ), f"{field} não deveria mudar na revisão de endurecimento."

    def test_mariana_unchanged(self) -> None:
        original = RELOJOEIRO_VISUAL_BIBLE.character_by_name("Mariana Duarte")
        hardened = RELOJOEIRO_VISUAL_BIBLE_HARDENED.character_by_name("Mariana Duarte")
        assert original == hardened


class TestVersioning:
    def test_versions_differ(self) -> None:
        assert RELOJOEIRO_VISUAL_BIBLE.version == "v1_gate3c"
        assert RELOJOEIRO_VISUAL_BIBLE_HARDENED.version == "v2_gate3d_hardened"

    def test_hashes_differ(self) -> None:
        v1_hash = structural_hash(RELOJOEIRO_VISUAL_BIBLE.to_dict())
        v2_hash = structural_hash(RELOJOEIRO_VISUAL_BIBLE_HARDENED.to_dict())
        assert v1_hash != v2_hash


class TestEliasHardening:
    def test_beard_explicitly_forbidden(self) -> None:
        elias = RELOJOEIRO_VISUAL_BIBLE_HARDENED.character_by_name("Elias Varga")
        assert "sem barba" in elias.distinguishing_features.lower()
        forbidden_text = " ".join(RELOJOEIRO_VISUAL_BIBLE_HARDENED.forbidden_elements).lower()
        assert "barba" in forbidden_text

    def test_age_locked_to_a_single_value(self) -> None:
        elias = RELOJOEIRO_VISUAL_BIBLE_HARDENED.character_by_name("Elias Varga")
        assert "62 anos" in elias.approximate_age
        assert "nunca" in elias.approximate_age.lower()


class TestHeroObjectHardening:
    def test_metallic_case_explicitly_forbidden(self) -> None:
        forbidden_text = " ".join(RELOJOEIRO_VISUAL_BIBLE_HARDENED.forbidden_elements).lower()
        assert "metálica" in forbidden_text or "metalica" in forbidden_text
        assert "vidro" in RELOJOEIRO_VISUAL_BIBLE_HARDENED.hero_object.description.lower()

    def test_engraving_readability_not_required(self) -> None:
        features = RELOJOEIRO_VISUAL_BIBLE_HARDENED.hero_object.distinctive_features.lower()
        assert "não precisa ser legível" in features


class TestClockCountTolerance:
    def test_clock_count_treated_as_best_effort(self) -> None:
        constraints_text = " ".join(RELOJOEIRO_VISUAL_BIBLE_HARDENED.continuity_constraints).lower()
        assert "15" in constraints_text and "18" in constraints_text
        assert "não exigem nova" in constraints_text or "nao exigem nova" in constraints_text


class TestForbiddenElementsIsSuperset:
    def test_v2_keeps_all_v1_forbidden_elements(self) -> None:
        v1_set = set(RELOJOEIRO_VISUAL_BIBLE.forbidden_elements)
        v2_set = set(RELOJOEIRO_VISUAL_BIBLE_HARDENED.forbidden_elements)
        assert v1_set <= v2_set
        assert v2_set - v1_set  # algo novo foi adicionado
